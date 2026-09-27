
## Getting Started

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

That is an even better strategy. If your teammate uses an AI coding agent to build the Nurse Console, giving them a clean, clear integration guide in the repository (e.g., in `README.md` or `NURSE_CONSOLE_INTEGRATION.md`) will allow their AI to read the rules and hook directly into your services without breaking anything.

Here is a ready-to-use developer integration guide you can drop into your repository or hand straight to your teammate and their AI:

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
