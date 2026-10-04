import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'patient_view_page.dart';
import 'scanner_page.dart';

class ReadOnlyPatientDashboard extends StatelessWidget {
  final String patientUuid;

  const ReadOnlyPatientDashboard({super.key, required this.patientUuid});

  @override
  Widget build(BuildContext context) {
    return PatientViewPage(patientId: patientUuid);
  }
}

class PatientPortalOtpGate extends StatefulWidget {
  final String patientUuid;

  const PatientPortalOtpGate({super.key, required this.patientUuid});

  @override
  State<PatientPortalOtpGate> createState() => _PatientPortalOtpGateState();
}

class _PatientPortalOtpGateState extends State<PatientPortalOtpGate> {
  final _otpController = TextEditingController();
  String? _registeredEmail;
  String? _internalPatientId;
  String? _errorMessage;
  int otpFailCount = 0;
  bool _isVerified = false;
  bool _isLoading = true;
  bool _isVerifying = false;

  @override
  void initState() {
    super.initState();
    _loadEmailAndSendOtp();
  }

  @override
  void dispose() {
    _otpController.dispose();
    super.dispose();
  }

  Future<void> _loadEmailAndSendOtp() async {
    try {
      final data = await Supabase.instance.client
          .from('patients')
          .select('id, emergency_contact_email')
          .eq('qr_uuid', widget.patientUuid)
          .maybeSingle();
      final internalPatientId = data?['id'] as String?;
      final registeredEmail = data?['emergency_contact_email'] as String?;

      if (registeredEmail == null || registeredEmail.trim().isEmpty) {
        throw Exception('No registered emergency contact email found.');
      }

      await Supabase.instance.client.auth.signInWithOtp(email: registeredEmail);
      if (!mounted) return;
      setState(() {
        _registeredEmail = registeredEmail;
        _internalPatientId = internalPatientId;
        _isLoading = false;
      });
    } catch (e) {
      debugPrint('OTP Error: $e');
      if (!mounted) return;
      setState(() {
        _errorMessage =
            'Error: OTP Error. Unknown QR code or no registered email.';
        _isLoading = false;
      });
    }
  }

  Future<void> _verifyOtp() async {
    final email = _registeredEmail;
    final userInput = _otpController.text.trim();
    if (email == null || userInput.length != 8 || _isVerifying) return;

    setState(() => _isVerifying = true);
    try {
      await Supabase.instance.client.auth.verifyOTP(
        type: OtpType.email,
        token: userInput,
        email: email,
      );
      if (!mounted) return;
      setState(() {
        _isVerified = true;
        _isVerifying = false;
      });
    } catch (_) {
      if (!mounted) return;
      otpFailCount++;
      setState(() => _isVerifying = false);
      if (otpFailCount < 3) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Invalid OTP. Please check your email and try again.',
            ),
          ),
        );
        return;
      }

      otpFailCount = 0;
      await showDialog<void>(
        context: context,
        barrierDismissible: false,
        builder: (context) => AlertDialog(
          title: const Text('Security lockout'),
          content: const Text('Exceeded maximum attempts.'),
          actions: [
            FilledButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('OK'),
            ),
          ],
        ),
      );
      if (!mounted) return;
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const ScannerPage()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isVerified) {
      final dashboard = ReadOnlyPatientDashboard(
        patientUuid: _internalPatientId!,
      );
      return dashboard;
    }

    return Scaffold(
      backgroundColor: const Color(0xFFF1F3F5),
      body: Stack(
        fit: StackFit.expand,
        children: [
          Center(
            child: Card(
              margin: const EdgeInsets.all(24),
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: _buildOtpPrompt(context),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildOtpPrompt(BuildContext context) {
    if (_isLoading) {
      return const SizedBox(
        width: 280,
        child: Center(child: CircularProgressIndicator()),
      );
    }

    return SizedBox(
      width: 320,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.lock_outline, size: 42, color: Colors.teal),
          const SizedBox(height: 16),
          const Text(
            'Enter the 8-digit OTP sent to your email.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600),
          ),
          if (_errorMessage != null) ...[
            const SizedBox(height: 12),
            Text(
              _errorMessage!,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.red),
            ),
          ],
          const SizedBox(height: 20),
          TextField(
            controller: _otpController,
            autofocus: true,
            keyboardType: TextInputType.number,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            maxLength: 8,
            textAlign: TextAlign.center,
            decoration: const InputDecoration(
              labelText: 'OTP',
              counterText: '',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: _isVerifying ? null : _verifyOtp,
              child: const Text('Verify OTP'),
            ),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
        ],
      ),
    );
  }
}
