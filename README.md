
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

## Roadmap / Known Gaps

- Patient view currently has no dedicated access control (e.g. a per-patient
  access code or QR link) — access is by patient ID only, which is fine for a
  demo but should be hardened before handling real patient data.
- SmartPharma backend is reached via a dev ngrok tunnel; needs a stable
  deployment for anything beyond demos.