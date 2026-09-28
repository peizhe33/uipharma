import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

class ScannerPage extends StatefulWidget {
  const ScannerPage({super.key});

  @override
  State<ScannerPage> createState() => _ScannerPageState();
}

class _ScannerPageState extends State<ScannerPage> with WidgetsBindingObserver {
  final MobileScannerController _controller = MobileScannerController(
    autoStart: false,
    formats: const [BarcodeFormat.qrCode],
    invertImage: kIsWeb,
  );
  bool _hasPopped = false;
  bool _isStarting = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) => _startScanner());
  }

  Future<void> _startScanner() async {
    if (!mounted || _hasPopped || _isStarting || _controller.value.isRunning) {
      return;
    }

    _isStarting = true;
    try {
      await _controller.start();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to start the camera: $error')),
      );
    } finally {
      _isStarting = false;
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    switch (state) {
      case AppLifecycleState.resumed:
        _startScanner();
        break;
      case AppLifecycleState.inactive:
      case AppLifecycleState.paused:
      case AppLifecycleState.detached:
      case AppLifecycleState.hidden:
        _controller.stop();
        break;
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _controller.dispose();
    super.dispose();
  }

  Future<void> _finishScan(String value) async {
    await _controller.stop();
    if (!mounted) return;
    Navigator.of(context).pop(value);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scan QR Code')),
      body: MobileScanner(
        controller: _controller,
        onDetect: (capture) {
          if (_hasPopped || capture.barcodes.isEmpty) {
            return;
          }

          final value = capture.barcodes
              .map((barcode) =>
                (barcode.rawValue ?? barcode.displayValue)?.trim())
              .whereType<String>()
              .firstWhere((value) => value.isNotEmpty, orElse: () => '');
          if (value.isEmpty) {
            return;
          }

          setState(() {
            _hasPopped = true;
          });

          _finishScan(value);
        },
      ),
    );
  }
}