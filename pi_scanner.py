# Install dependencies:
# python3 -m pip install opencv-python pyzbar pynput

import time

import cv2
from pynput.keyboard import Controller, Key
from pyzbar.pyzbar import decode


CAMERA_INDEX = 0
SCAN_COOLDOWN_SECONDS = 3


def main() -> None:
    camera = cv2.VideoCapture(CAMERA_INDEX)
    keyboard = Controller()

    if not camera.isOpened():
        raise RuntimeError('Unable to open the default camera.')

    try:
        while True:
            success, frame = camera.read()
            if not success:
                print('Unable to read a frame from the camera.')
                break

            for qr_code in decode(frame):
                scanned_value = qr_code.data.decode('utf-8').strip()
                if not scanned_value:
                    continue

                keyboard.type(scanned_value)
                keyboard.press(Key.enter)
                keyboard.release(Key.enter)
                print(f'Scanned and typed: {scanned_value}')
                time.sleep(SCAN_COOLDOWN_SECONDS)
                break

            cv2.imshow('Raspberry Pi QR Scanner', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
