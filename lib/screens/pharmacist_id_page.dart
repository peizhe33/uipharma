import 'package:flutter/material.dart';
import 'pharmacist_page.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../widgets/responsive.dart';

class PharmacistIdGatePage extends StatefulWidget {
  const PharmacistIdGatePage({super.key});

  @override
  State<PharmacistIdGatePage> createState() => _PharmacistIdGatePageState();
}

class _PharmacistIdGatePageState extends State<PharmacistIdGatePage> {
  final TextEditingController _idCtrl = TextEditingController();
  bool _valid = false;

  // ✅ Required format: P + 6 digits (Example: P123456)
  final RegExp _pharmacistIdRegex = RegExp(r'^P\d{6}$');

  @override
  void dispose() {
    _idCtrl.dispose();
    super.dispose();
  }

  void _checkValid(String v) {
    setState(() {
      _valid = _pharmacistIdRegex.hasMatch(v.trim());
    });
  }

  Future<void> _continue() async {
  final id = _idCtrl.text.trim();

  if (!_pharmacistIdRegex.hasMatch(id)) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Invalid Pharmacist ID. Use format: P123456'),
      ),
    );
    return;
  }

  try {
    final supabase = Supabase.instance.client;

    final res = await supabase
        .from('pharmacists')
        .select('id, pharmacist_code')
        .eq('pharmacist_code', id)
        .maybeSingle();

    if (res == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Pharmacist not found in system')),
      );
      return;
    }

    final pharmacistUuid = res['id'];

    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (_) => PharmacistPage(pharmacistId: pharmacistUuid),
      ),
    );
  } catch (e) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Error: $e')),
    );
  }
}

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Pharmacist Verification'),
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
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Text(
                        'Enter Pharmacist ID',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 10),
                      const Text(
                        'Format: P + 6 digits (Example: P123456)',
                        textAlign: TextAlign.center,
                        style: TextStyle(color: Colors.black54),
                      ),
                      const SizedBox(height: 24),
                      TextField(
                        controller: _idCtrl,
                        onChanged: _checkValid,
                        decoration: const InputDecoration(
                          labelText: 'Pharmacist ID',
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
          );
        },
      ),
    );
  }
}
