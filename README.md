# SmartPharma

AI-assisted inpatient medication verification system. SmartPharma runs as three parts that work together on the same network.

| Part | Folder | What it does |
|---|---|---|
| AI verification backend | `AI_Backend/` | Python Flask server. Runs the deterministic safety checks, retrieves guideline evidence (RAG) and calls the local language model through Ollama. Listens on port `5009`. |
| SmartPharma app | `lib/` and platform folders | Flutter app for doctors, pharmacists, nurses and patients. Sends prescriptions to the backend and stores records in Supabase. |
| Bedside terminal | `pi_scanner.py`, `start_smartpharma.sh` | Raspberry Pi 5 with Camera Module 3. Scans the patient wristband QR before administration. |

The backend and the app are separate programs. **Start the backend first, then the app.**

---

## Running SmartPharma

### 1. Prerequisites

- Python 3.10 or newer
- [Ollama](https://ollama.com) installed and running
- Flutter SDK
- All devices (backend machine, phone or tablet, Raspberry Pi) on the same Wi-Fi network

### 2. Start the AI backend (terminal 1)

```bash
cd AI_Backend

# create and activate a virtual environment (first time only)
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

Load the language model into Ollama (first time only):

```bash
ollama pull [MODEL_NAME]       # or: ollama create [MODEL_NAME] -f Modelfile
```

Build the guideline vector database (first time only). The `chroma/` folder is not stored in this repository because it can be regenerated:

```bash
python build_database.py
```

Start the server:

```bash
python app.py
```

The backend is ready when it reports that it is running on port `5009`. Leave this terminal open.

### 3. Point the app at the backend

In `lib/services/api.dart`, set `_baseUrl` to the IP address of the machine running the backend:

```dart
static const String _baseUrl = 'http://<backend-machine-IP>:5009';
```

Use `http://127.0.0.1:5009` if the app runs on the same machine as the backend. Find the IP with `ipconfig` (Windows) or `ip a` (Linux).

### 4. Run the app (terminal 2)

```bash
flutter pub get
flutter run
```

### 5. Bedside terminal (Raspberry Pi)

Install the camera packages once:

```bash
sudo apt install -y python3-picamera2 python3-opencv python3-pyzbar libzbar0
```

Then launch the app on the Pi with `./start_smartpharma.sh`. The app starts and stops `pi_scanner.py` by itself when a scan screen opens.

### Troubleshooting

- **App shows a connection error when verifying.** Check the backend terminal is still running, the IP in `api.dart` is correct, and both devices are on the same network.
- **Backend fails to start with a Chroma or collection error.** Run `python build_database.py` again.
- **Model not found.** Run `ollama list` and check the model name matches the one in `AI_Backend/config.py`.

---


## App Developer Notes

1. **Install dependencies**
```bash
   flutter pub get
```
2. **Configure Supabase** — the URL and anon key are set in `lib/main.dart`.
   Replace with your own project's credentials if you're not using the shared
   demo instance, and confirm Row Level Security policies before going beyond a demo.
3. **Configure the SmartPharma backend URL** — set in `lib/services/api.dart`
   (`_baseUrl`). During development this points at a local server exposed via
   ngrok; update it to point at wherever your backend instance is running.
4. **Run the app**
```bash
   flutter run
```

---

# SmartPharma Portal

SmartPharma is a Flutter application for coordinating patient records, clinical review, medication verification, patient medicine instructions, and nurse dispensing. The main portal presents role-based entry points for doctors, pharmacists, nurses, and patients.

The app uses Supabase for shared clinical data, `shared_preferences` for local demo persistence, a Python SmartPharma service for prescription analysis, and QR scanning for patient and wristband identification.

> **Important:** This repository is a clinical workflow prototype. It is not production-ready medical software. Validate all medication decisions with qualified clinicians, secure the backend before handling real patient data, and complete a formal privacy and security review before deployment.

## Features

- **Doctor portal**
  - Doctor ID gate using the `D######` format.
  - Patient search and selection.
  - Patient demographics, ward assignment, condition records, vital signs, allergies, renal function, and history.
  - Current-condition entry and review.
  - eGFR history and chart views.
  - Medication recommendation and prescription submission.
  - Prescription alerts, AI/rule-based explanations, and pharmacist decision notifications.
  - New patient registration and feedback submission.

- **Pharmacist portal**
  - Pharmacist ID gate using the `P######` format.
  - Separate **To be verified** and **Verified** tabs.
  - Search by patient name.
  - Review of patient context and prescription medicines.
  - Dose, frequency, route, unit, and PRN review.
  - Approve a prescription or reject individual medicines with a reason and suggested alternative.
  - Notifications when a doctor responds to a pharmacist rejection.

- **Nurse portal**
  - Nurse ID authentication against the Supabase `nurses` table using `N######` codes.
  - Patient queue searchable by patient name or ward.
  - Patient details and condition records.
  - Wristband QR verification before dispensing.
  - Device camera support on mobile/web and Raspberry Pi camera support on Linux.
  - Only pharmacist-approved medicines are shown after a successful wristband match.
  - Medication administration timestamps recorded in Supabase.
  - Failed or mismatched QR scans are logged and medication remains locked.

- **Patient view**
  - Open by patient ID for direct internal/demo use.
  - Open by scanning a wristband QR code.
  - Email OTP gate using the patient's registered emergency contact email.
  - Read-only list of verified medicines with dose, timing, route, frequency, and instructions.
  - Flagged, rejected, unsafe, pending, or contraindicated medicines are hidden from the patient view.

## User Flows

### Portal home

The app starts at `PatientOverviewPage`, titled **SmartPharma Portal**. It exposes these actions:

1. **Patient Database** - enter a doctor ID and open the patient list.
2. **Patient View** - enter a patient ID or scan a QR code, then complete OTP verification.
3. **New Registration** - create a patient and assign a ward location.
4. **Pharmacist Portal** - verify the pharmacist code and open the prescription queue.
5. **Nurse Portal** - verify the nurse code and open the patient queue.
6. **Feedback** - submit product feedback to Supabase.

### Prescription lifecycle

The intended medication handoff is:

```text
Doctor recommendation
        |
        v
prescriptions.status = pending_verification
        |
        v
Pharmacist review
   |                 |
   | approve         | reject
   v                 v
status = verified    status = pharmacist_rejected
   |                 |
   v                 v
Patient view and     Doctor notification and
nurse dispensing     review cycle
```

Pharmacist approvals are also written to `prescription_verifications` with `status = approved`. Rejected reviews are written with `status = pharmacist_rejected`; doctor responses may use `doctor_rejected`, `doctor_approved`, or `doctor_approved_read` depending on the review flow.

### Nurse dispensing

The nurse flow is intentionally locked until the physical wristband is verified:

1. Nurse signs in with a valid nurse code.
2. Nurse selects a patient from the queue.
3. The dispense screen opens the appropriate scanner.
4. The scanned value must match that patient's `patients.qr_uuid`.
5. A mismatch is logged and the medication list stays locked.
6. A successful match loads pharmacist-approved medicines only.
7. The nurse confirms each administration after giving the medication.
8. The app records the event in `medication_administrations`.

## Architecture

```text
Flutter UI
  lib/main.dart
  lib/screens/
  lib/widgets/
        |
        +-- PatientSupabaseService / NurseService / FeedbackService
        |       |
        |       +-- Supabase tables and auth OTP
        |
        +-- SmartPharmaApi
        |       |
        |       +-- Python HTTP API: POST /ask
        |
        +-- ScannerPage (mobile_scanner)
        |       or PiScannerPage (Linux process bridge)
        |
        +-- PatientDatabase (local SharedPreferences demo store)
```

Important code locations:

| Area | Location |
| --- | --- |
| App bootstrap, theme, routing | [`lib/main.dart`](lib/main.dart) |
| Portal home and doctor patient list | [`lib/screens/doctor_patient_overview.dart`](lib/screens/doctor_patient_overview.dart) |
| Patient medicine view | [`lib/screens/patient_view_page.dart`](lib/screens/patient_view_page.dart) |
| Patient OTP gate | [`lib/screens/patient_portal_otp_gate.dart`](lib/screens/patient_portal_otp_gate.dart) |
| Nurse workflow | [`lib/screens/nurse_patient_list_page.dart`](lib/screens/nurse_patient_list_page.dart), [`lib/screens/nurse_dispense_page.dart`](lib/screens/nurse_dispense_page.dart) |
| Pharmacist workflow | [`lib/screens/pharmacist_page.dart`](lib/screens/pharmacist_page.dart), [`lib/screens/dose_verification_page.dart`](lib/screens/dose_verification_page.dart) |
| Supabase data access | [`lib/services/patient_supabase_service.dart`](lib/services/patient_supabase_service.dart), [`lib/services/nurse_service.dart`](lib/services/nurse_service.dart) |
| SmartPharma API client and fallback | [`lib/services/api.dart`](lib/services/api.dart) |
| Local demo database | [`lib/services/patient_database.dart`](lib/services/patient_database.dart) |
| Shared domain models | [`lib/models/models.dart`](lib/models/models.dart) |
| Raspberry Pi QR scanner | [`pi_scanner.py`](pi_scanner.py) |
| Nurse schema reference | [`supabase/nurse_console_feature1.sql`](supabase/nurse_console_feature1.sql) |

## Requirements

- Flutter SDK compatible with Dart `^3.9.2`.
- A configured Supabase project.
- Android, iOS, web, Windows, macOS, Linux, or a supported Flutter target.
- Camera permissions for device QR scanning.
- For Raspberry Pi scanning:
  - Raspberry Pi OS Bookworm or Trixie.
  - Raspberry Pi Camera Module 3 or a USB camera.
  - Python 3 with Picamera2/OpenCV/pyzbar dependencies.
- Optional: a running Python SmartPharma backend exposing `POST /ask` on port `5009`.

## Installation

```bash
git clone <repository-url>
cd uipharma-main
flutter pub get
```

Check the local toolchain:

```bash
flutter doctor
flutter devices
```

Run the application on a connected device or desktop target:

```bash
flutter run
```

Common targets:

```bash
flutter run -d chrome
flutter run -d windows
flutter run -d linux
```

Build examples:

```bash
flutter build web
flutter build apk
flutter build windows
flutter build linux
```

## Configuration

### Supabase

Supabase is initialized in [`lib/main.dart`](lib/main.dart). Before using a different project, update the URL and anon key, then verify the database schema and policies.

The application currently reads and writes these logical tables:

- `patients`
- `patient_history`
- `patient_current_conditions`
- `lab_results`
- `prescriptions`
- `prescription_verifications`
- `pharmacists`
- `nurses`
- `qr_scan_logs`
- `medication_administrations`
- `feedback`

The nurse-specific table definitions and sample nurse are in [`supabase/nurse_console_feature1.sql`](supabase/nurse_console_feature1.sql). The seed example creates nurse code `N123456`.

At minimum, the patient records used by the app need fields equivalent to:

```text
patients
  id
  qr_uuid
  ward_room_no
  name
  gender
  age
  height
  weight
  blood_type
  emergency_contact_email
```

Prescription medicine details are stored as JSON arrays. The UI expects fields such as `name`, `dose`, `unit`, `frequency`, `route`, and `prn`; pharmacist review adds approval or rejection metadata to the same bundle.

### SmartPharma backend

The Flutter client calls `POST /ask` using the base URL in [`lib/services/api.dart`](lib/services/api.dart). Configure `_baseUrl` for the environment running the backend:

- Same computer: `http://127.0.0.1:5009`
- Another device on the same network: `http://<computer-lan-ip>:5009`
- A secure tunnel may be used for temporary development access.

The request can include patient data, vitals, labs, diagnosis, and prescribed medicines. The response is expected to contain `answer`, `report`, `preprocessing_alerts`, `retrieved`, `rag_failure`, and `elapsed_s` fields.

If the backend returns a known local file-permission error, the app uses an on-device rule-based fallback. That fallback checks common allergy conflicts, high doses, and eGFR below 60, but it is not a replacement for the full SmartPharma retrieval and guideline service.

## Raspberry Pi QR Scanner

The Linux Flutter build starts and stops `pi_scanner.py` when a Raspberry Pi scanner screen is opened. Do not start the scanner manually for normal app use.

Install the scanner dependencies on Raspberry Pi OS:

```bash
sudo apt install -y python3-picamera2 python3-opencv python3-pyzbar libzbar0
```

Test the camera hardware:

```bash
rpicam-hello
```

Run a manual scanner test with an OpenCV preview:

```bash
python3 pi_scanner.py --show-window
```

The scanner process communicates over standard output:

```text
READY
QR:<value>
ERROR:<message>
```

The provided [`start_smartpharma.sh`](start_smartpharma.sh) launcher expects the Linux release bundle at `~/SmartPharma/uipharma-main/build/linux/arm64/release/bundle/pj`.

## Camera and Platform Notes

- Android and iOS use `mobile_scanner` through `ScannerPage`.
- Web can use the device camera when browser permissions allow it.
- Linux uses the Raspberry Pi process bridge because `mobile_scanner` does not provide the same Linux desktop camera support.
- Camera permissions must be configured in the platform project before deploying to a real device.
- QR payloads are treated as wristband UUID values. A QR value alone should not be considered a complete authentication mechanism.

## Demo Data

The app initializes a local `PatientDatabase` using `shared_preferences`. Optional demo seeding and clearing calls are present in `lib/main.dart` but are commented out:

```dart
// await PatientDatabase.instance.clearAll();
// await PatientDatabase.instance.seedDemoDataIfEmpty();
```

The Supabase service also contains example patient seed helpers. Use these only in a disposable development project.

## Testing and Quality Checks

Run static analysis and tests before submitting changes:

```bash
flutter analyze
flutter test
```

The current widget test covers rendering of an orange guideline warning for a `NOT_INDICATED` prescription alert. Add focused tests for role gates, OTP failure behavior, QR mismatch handling, approval status transitions, and medication administration recording when changing those workflows.

## Security and Privacy Checklist

Before production use:

- Move Supabase URL, anon key, backend URLs, and environment-specific configuration out of source-controlled constants.
- Replace format-only doctor and pharmacist gates with real authenticated sessions and role-based authorization.
- Enforce least-privilege Row Level Security policies. The reference nurse SQL contains permissive demo policies for `anon` and `authenticated`; do not reuse them unchanged for real patient data.
- Add server-side authorization for patient lookup, prescription review, QR matching, and administration writes.
- Do not expose internal patient IDs through unsecured routes or logs.
- Protect the OTP flow with rate limiting, expiry, audit logging, and a production email provider.
- Use HTTPS/TLS for the SmartPharma backend and Supabase connections.
- Review whether emergency-contact email is appropriate for the intended patient access model.
- Audit and retain QR scan, pharmacist review, and medication administration events according to organizational policy.
- Treat AI or rule-based output as decision support. A qualified clinician must make the final prescribing and dispensing decision.

## Troubleshooting

### Supabase data does not load

Confirm the project URL/key, table names, column names, network connection, and Row Level Security policies. Inspect the Flutter exception shown by the relevant screen.

### Patient OTP cannot be sent

The scanned `qr_uuid` must match a patient and that patient must have a non-empty `emergency_contact_email`. Supabase email OTP must also be enabled and configured.

### QR scanner cannot start

Check camera permissions on the device. On Linux, verify the Pi camera with `rpicam-hello`, install the Python packages, and confirm that no stale `pi_scanner.py` process is holding the camera.

### SmartPharma verification fails

Confirm that the backend is reachable from the device running Flutter and that `_baseUrl` uses the correct LAN address. On a phone, `127.0.0.1` refers to the phone, not the development computer. The app may fall back to local rules for the specific file-permission errors handled in `SmartPharmaApi`.

## License

No public license is declared in this repository. Treat the project as private unless the maintainers add explicit licensing terms.

