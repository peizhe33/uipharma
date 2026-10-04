import 'package:flutter/material.dart';

import '../services/nurse_service.dart';
import '../widgets/responsive.dart';
import 'nurse_patient_list_page.dart';

/// Clears the nurse session screens and returns to the nurse login page
/// (the portal home stays underneath so "Back to Portal" still works).
void exitToNurseLogin(BuildContext context) {
  Navigator.of(context).pushAndRemoveUntil(
    MaterialPageRoute(builder: (_) => const NurseIdGatePage()),
    (route) => route.isFirst,
  );
}

/// Nurse login: N + 6 digits (e.g. N123456), checked against `nurses` table.
class NurseIdGatePage extends StatefulWidget {
  const NurseIdGatePage({super.key});

  @override
  State<NurseIdGatePage> createState() => _NurseIdGatePageState();
}

class _NurseIdGatePageState extends State<NurseIdGatePage> {
  final TextEditingController _idCtrl = TextEditingController();
  final RegExp _nurseIdRegex = RegExp(r'^N\d{6}$');
  bool _valid = false;
  bool _loading = false;

  @override
  void dispose() {
    _idCtrl.dispose();
    super.dispose();
  }

  void _checkValid(String v) {
    setState(() => _valid = _nurseIdRegex.hasMatch(v.trim().toUpperCase()));
  }

  Future<void> _continue() async {
    final id = _idCtrl.text.trim().toUpperCase();
    if (!_nurseIdRegex.hasMatch(id)) {
      _snack('Invalid Nurse ID. Use format: N123456');
      return;
    }

    setState(() => _loading = true);
    try {
      final nurse = await NurseService.login(id);
      if (!mounted) return;
      if (nurse == null) {
        _snack('Nurse not found in system');
        return;
      }
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => NursePatientListPage(nurse: nurse)),
      );
    } catch (e) {
      if (mounted) _snack('Error: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _snack(String msg) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Nurse Verification'),
        centerTitle: true,
        backgroundColor: Colors.teal.shade700,
        foregroundColor: Colors.white,
      ),
      body: LayoutBuilder(
        builder: (context, constraints) {
          final keyboardOpen = MediaQuery.viewInsetsOf(context).bottom > 0;
          final minHeight = keyboardOpen
              ? 0.0
              : (constraints.maxHeight - 48).clamp(0.0, double.infinity).toDouble();

          return SingleChildScrollView(
            padding: Responsive.pagePadding(context).add(
              EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom + 24),
            ),
            child: ConstrainedBox(
              constraints: BoxConstraints(minHeight: minHeight),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 650),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Icon(Icons.local_hospital, size: 64, color: Colors.teal.shade600),
                      const SizedBox(height: 12),
                      const Text(
                        'Enter Nurse ID',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 10),
                      const Text(
                        'Format: N + 6 digits (Example: N123456)',
                        textAlign: TextAlign.center,
                        style: TextStyle(color: Colors.black54),
                      ),
                      const SizedBox(height: 24),
                      TextField(
                        controller: _idCtrl,
                        onChanged: _checkValid,
                        textCapitalization: TextCapitalization.characters,
                        onSubmitted: (_) => _valid && !_loading ? _continue() : null,
                        decoration: const InputDecoration(
                          labelText: 'Nurse ID',
                          border: OutlineInputBorder(),
                          prefixIcon: Icon(Icons.badge),
                        ),
                      ),
                      const SizedBox(height: 20),
                      ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.teal.shade700,
                          foregroundColor: Colors.white,
                        ),
                        onPressed: _valid && !_loading ? _continue : null,
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 14),
                          child: _loading
                              ? const SizedBox(
                                  height: 22,
                                  width: 22,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2.5,
                                    color: Colors.white,
                                  ),
                                )
                              : const Text('Continue', style: TextStyle(fontSize: 18)),
                        ),
                      ),
                      const SizedBox(height: 12),
                      OutlinedButton(
                        onPressed: () =>
                            Navigator.of(context).popUntil((r) => r.isFirst),
                        child: const Padding(
                          padding: EdgeInsets.symmetric(vertical: 14),
                          child: Text('Back to Portal', style: TextStyle(fontSize: 18)),
                        ),
                      ),
                    ],
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
