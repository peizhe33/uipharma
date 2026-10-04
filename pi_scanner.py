"""
SmartPharma - Raspberry Pi wristband QR scanner
Hardware: Raspberry Pi Camera Module 3 (12MP, autofocus, RPI-CAM3)

How it works
------------
You do NOT start this script yourself any more. The SmartPharma app starts it
when a "Scan QR" screen opens and stops it when that screen closes, so the
camera is only switched on while a scan is in progress.

The script talks to the app through its standard output, one line per event:

    READY            the camera is running
    QR:<value>       a QR code was read (with --once the script then exits)
    ERROR:<message>  the camera could not be started or stopped working

With --preview-file PATH the latest camera frame is saved to PATH as a small
JPEG (about 8 times a second), and the app shows it as a live preview inside
its own window. Log messages go to standard error so they never mix with the
lines above.

Setup on Raspberry Pi OS (Bookworm or Trixie)
---------------------------------------------
    sudo apt install -y python3-picamera2 python3-opencv python3-pyzbar libzbar0

No keyboard emulation is used, so X11, pynput and window focus no longer
matter.

Manual test (opens an OpenCV window, prints every code it sees, q to quit):
    python3 pi_scanner.py --show-window
Test the camera itself first:  rpicam-hello
"""

import argparse
import os
import signal
import sys
import time

import cv2
from pyzbar.pyzbar import ZBarSymbol, decode

FRAME_SIZE = (1280, 720)      # enough detail for a wristband QR at 10-30 cm
PREVIEW_WIDTH = 640           # size of the preview frame sent to the app
PREVIEW_INTERVAL_S = 0.12     # roughly 8 preview frames per second
PREVIEW_JPEG_QUALITY = 70
MIRROR_PREVIEW = True         # mirror the preview like a selfie camera
SCAN_COOLDOWN_SECONDS = 3     # manual mode only: ignore the same code for this long


def log(message):
    """Human-readable messages go to stderr, never to the app protocol."""
    print(message, file=sys.stderr, flush=True)


def emit(line):
    """Send one protocol line to the app."""
    try:
        print(line, flush=True)
    except BrokenPipeError:
        # The app closed the pipe (screen closed). Stop quietly.
        raise SystemExit(0)


def _stop_on_signal(signum, frame):
    # Turn SIGTERM from the app into a normal exit so the camera is closed
    # in the finally block below.
    raise SystemExit(0)


class PiCamera3:
    """Camera Module 3 via Picamera2 (libcamera) with continuous autofocus."""

    def __init__(self):
        from picamera2 import Picamera2
        from libcamera import controls

        self.cam = Picamera2()
        config = self.cam.create_preview_configuration(
            main={"size": FRAME_SIZE, "format": "RGB888"}
        )
        self.cam.configure(config)
        self.cam.start()
        # Camera Module 3 has autofocus - keep refocusing as the wristband moves.
        self.cam.set_controls({
            "AfMode": controls.AfModeEnum.Continuous,
            "AfSpeed": controls.AfSpeedEnum.Fast,
        })
        time.sleep(0.8)  # let exposure and focus settle

    def read(self):
        # Picamera2 "RGB888" is BGR byte order, which is what OpenCV expects.
        return self.cam.capture_array()

    def close(self):
        try:
            self.cam.stop()
        finally:
            self.cam.close()


class UsbCamera:
    """Fallback for a USB webcam (or a laptop webcam when testing on a PC)."""

    def __init__(self, index=0):
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise RuntimeError("no USB camera found either")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_SIZE[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_SIZE[1])

    def read(self):
        ok, frame = self.cap.read()
        return frame if ok else None

    def close(self):
        self.cap.release()


def open_camera(usb_index=0):
    try:
        cam = PiCamera3()
        log("Using Raspberry Pi Camera Module 3 (Picamera2, autofocus on).")
        return cam
    except Exception as pi_exc:  # picamera2 missing, no CSI camera, or busy
        log(f"Pi camera not available ({pi_exc}); trying a USB camera.")
        try:
            return UsbCamera(usb_index)
        except Exception as usb_exc:
            raise RuntimeError(
                "No camera found. Check the ribbon cable and run rpicam-hello. "
                f"(Pi camera: {pi_exc}; USB: {usb_exc})"
            ) from usb_exc


def find_qr(frame):
    """Return (value, rect) for the first QR code in the frame, or None."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    for qr in decode(gray, symbols=[ZBarSymbol.QRCODE]):
        value = qr.data.decode("utf-8", errors="replace").strip()
        if value:
            return value, qr.rect
    return None


def write_preview(frame, path):
    """Save a small JPEG of the frame. Written to a temp file and swapped in,
    so the app never reads a half-written image."""
    h, w = frame.shape[:2]
    small = cv2.resize(frame, (PREVIEW_WIDTH, int(h * PREVIEW_WIDTH / w)))
    if MIRROR_PREVIEW:
        small = cv2.flip(small, 1)
    ok, buf = cv2.imencode(
        ".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, PREVIEW_JPEG_QUALITY]
    )
    if not ok:
        return
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "wb") as f:
            f.write(buf.tobytes())
        os.replace(tmp_path, path)
    except OSError:
        pass  # the app was reading it (Windows); the next frame will do


def parse_args():
    parser = argparse.ArgumentParser(description="SmartPharma wristband QR scanner")
    parser.add_argument("--once", action="store_true",
                        help="exit after the first QR code (used by the app)")
    parser.add_argument("--preview-file", metavar="PATH",
                        help="keep the latest camera frame at PATH as a JPEG")
    parser.add_argument("--show-window", action="store_true",
                        help="show an OpenCV preview window (manual testing)")
    parser.add_argument("--usb-index", type=int, default=0,
                        help="USB camera index for the fallback camera")
    return parser.parse_args()


def main():
    args = parse_args()
    signal.signal(signal.SIGTERM, _stop_on_signal)
    start_ppid = os.getppid()

    try:
        camera = open_camera(args.usb_index)
    except Exception as exc:
        emit(f"ERROR:{exc}")
        return 1

    emit("READY")
    last_value, last_time = None, 0.0
    last_preview = 0.0

    try:
        while True:
            # If the app crashed or was closed mid-scan, do not keep the
            # camera running in the background.
            if start_ppid > 1 and os.getppid() != start_ppid:
                log("App is gone; stopping the camera.")
                return 0

            frame = camera.read()
            if frame is None:
                emit("ERROR:Unable to read a frame from the camera.")
                return 1

            found = find_qr(frame)
            now = time.time()

            if found is not None:
                x, y, w, h = found[1]
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 200, 0), 4)

            if args.preview_file and (
                found is not None or now - last_preview >= PREVIEW_INTERVAL_S
            ):
                write_preview(frame, args.preview_file)
                last_preview = now

            if found is not None:
                value = found[0]
                repeat = value == last_value and now - last_time < SCAN_COOLDOWN_SECONDS
                if not repeat:
                    emit(f"QR:{value}")
                    log(f"Scanned: {value}")
                    last_value, last_time = value, now
                    if args.once:
                        return 0

            if args.show_window:
                cv2.imshow("SmartPharma Pi QR Scanner (q to quit)", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    return 0
    finally:
        camera.close()
        if args.show_window:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    sys.exit(main())
