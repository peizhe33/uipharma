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

# Nurse Console Integration Guide (`SmartPharma`)

### Overview

The Nurse Console workflow is **decoupled from the Patient 2FA OTP Gate**. Nurses scan a physical wristband QR code and bypass the OTP step to instantly view patient records and dispense medication.

---

### Core Integration Building Blocks

1. **Hardware-Aware Scanner Router** (`lib/services/scanner_router.dart`)
Do not instantiate `ScannerPage` or `PiScannerPage` directly. Call `pushScanner(context)` instead. It automatically checks `Platform.isLinux` to decide whether to open the mobile camera feed or the Raspberry Pi hidden text-field listener.
2. **UUID Translation Service** (`lib/services/patient_supabase_service.dart`)
QR wristbands output a public `qr_uuid`. Call `PatientSupabaseService.getInternalIdFromQrUuid(qrUuid)` to resolve the public string into the internal database primary key `id`.

---

### Copy-Pasteable Nurse Scan Flow

Use this exact pattern inside any Nurse Console widget action (e.g., a "Scan Wristband to Dispense" button):

```dart
import 'package:flutter/material.dart';
import '../services/scanner_router.dart';
import '../services/patient_supabase_service.dart';
import 'patient_view_page.dart'; // Or your nurse dispensary screen

Future<void> handleNurseScan(BuildContext context) async {
  // 1. Launch the hardware-aware scanner (Mobile or Pi)
  final String? scannedUuid = await pushScanner(context);
  
  if (scannedUuid == null || scannedUuid.trim().isEmpty) {
    // User canceled or backed out of scanning
    return;
  }

  // 2. Resolve public qr_uuid to internal patient ID
  final String? internalPatientId = 
      await PatientSupabaseService.getInternalIdFromQrUuid(scannedUuid.trim());

  if (internalPatientId == null) {
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Patient not found for scanned wristband.')),
    );
    return;
  }

  // 3. Navigate directly to patient dispensary (Bypassing 2FA)
  if (!context.mounted) return;
  Navigator.push(
    context,
    MaterialPageRoute(
      builder: (_) => PatientViewPage(patientId: internalPatientId),
    ),
  );
}

```

---

### Database Row Level Security (RLS) Requirement

Ensure the Supabase `patients`, `medication`, and `prescriptions` tables have RLS policies set to allow `authenticated` reads for logged-in nurse user roles (`TO authenticated USING (true)`).
