import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

class ScannerPage extends StatefulWidget {
  const ScannerPage({super.key});

  @override
  State<ScannerPage> createState() => _ScannerPageState();
}

class _ScannerPageState extends State<ScannerPage> {
  bool _hasPopped = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scan QR Code')),
      body: MobileScanner(
        onDetect: (capture) {
          if (_hasPopped || capture.barcodes.isEmpty) {
            return;
          }

          final value = capture.barcodes.first.rawValue;
          if (value == null) {
            return;
          }

          _hasPopped = true;
          Navigator.pop(context, value);
        },
      ),
    );
  }
}