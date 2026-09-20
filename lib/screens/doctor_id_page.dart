import 'package:flutter/material.dart';
import 'doctor_patient_overview.dart'; // for PatientListPage
import '../widgets/responsive.dart';

class DoctorIdGatePage extends StatefulWidget {
  const DoctorIdGatePage({super.key});

  @override
  State<DoctorIdGatePage> createState() => _DoctorIdGatePageState();
}

class _DoctorIdGatePageState extends State<DoctorIdGatePage> {
  final _formKey = GlobalKey<FormState>();
  final _idCtrl = TextEditingController();

  bool _valid = false;

  // ✅ Required format: D + 6 digits
  final RegExp _doctorIdRegex = RegExp(r'^D\d{6}$');

  @override
  void dispose() {
    _idCtrl.dispose();
    super.dispose();
  }

  void _checkValid(String v) {
    setState(() {
      _valid = _doctorIdRegex.hasMatch(v.trim());
    });
  }

  void _continue() {
    final id = _idCtrl.text.trim();

    if (!_doctorIdRegex.hasMatch(id)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Invalid Doctor ID. Use format: D123456')),
      );
      return;
    }

    // ✅ Valid -> go to Select Patient page
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (_) => const PatientListPage()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Doctor Verification'),
        centerTitle: true,
      ),
      body: LayoutBuilder(
        builder: (context, constraints) {
          final keyboardOpen = MediaQuery.viewInsetsOf(context).bottom > 0;
          final minHeight = keyboardOpen
              ? 0.0
              : (constraints.maxHeight - 48)
                  .clamp(0.0, double.infinity)
                  .toDouble();

          return SingleChildScrollView(
            padding: Responsive.pagePadding(context).add(
              EdgeInsets.only(
                bottom: MediaQuery.viewInsetsOf(context).bottom + 24,
              ),
            ),
            child: ConstrainedBox(
              constraints: BoxConstraints(minHeight: minHeight),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 650),
                  child: Form(
                    key: _formKey,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Text(
                          'Enter Doctor ID',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 10),
                        const Text(
                          'Format: D + 6 digits (Example: D123456)',
                          textAlign: TextAlign.center,
                          style: TextStyle(color: Colors.black54),
                        ),
                        const SizedBox(height: 24),
                        TextFormField(
                          controller: _idCtrl,
                          onChanged: _checkValid,
                          decoration: const InputDecoration(
                            labelText: 'Doctor ID',
                            border: OutlineInputBorder(),
                            prefixIcon: Icon(Icons.badge),
                          ),
                        ),
                        const SizedBox(height: 20),
                        ElevatedButton(
                          onPressed: _valid ? _continue : null,
                          child: const Padding(
                            padding: EdgeInsets.symmetric(vertical: 14),
                            child: Text(
                              'Continue',
                              style: TextStyle(fontSize: 18),
                            ),
                          ),
                        ),
                        const SizedBox(height: 12),
                        OutlinedButton(
                          onPressed: () => Navigator.pop(context),
                          child: const Padding(
                            padding: EdgeInsets.symmetric(vertical: 14),
                            child: Text(
                              'Back',
                              style: TextStyle(fontSize: 18),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
