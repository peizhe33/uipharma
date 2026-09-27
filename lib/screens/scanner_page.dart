import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

class ScannerPage extends StatefulWidget {
  const ScannerPage({super.key});

  @override
  State<ScannerPage> createState() => _ScannerPageState();
}

class _ScannerPageState extends State<ScannerPage> with WidgetsBindingObserver {
  final MobileScannerController _controller = MobileScannerController();
  bool _hasPopped = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (!_controller.value.isInitialized) return;
    
    switch (state) {
      case AppLifecycleState.resumed:
        if (mounted) _controller.start();
        break;
      case AppLifecycleState.inactive:
      case AppLifecycleState.paused:
      case AppLifecycleState.detached:
      case AppLifecycleState.hidden:
        _controller.stop();
        break;
    }
  }

  // THIS IS THE MAGIC FIX
  // deactivate() fires whenever the widget is removed from the active screen,
  // even if it is just temporarily hidden by another page or tab.
  @override
  void deactivate() {
    _controller.stop();
    super.deactivate();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    // Let dispose() handle the cleanup directly without calling stop() first
    // to prevent plugin race conditions.
    _controller.dispose(); 
    super.dispose();
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

          final value = capture.barcodes.first.rawValue;
          if (value == null) {
            return;
          }

          setState(() {
            _hasPopped = true;
          });
          
          // Stop the camera immediately upon successful scan before popping
          _controller.stop().then((_) {
            if (mounted) {
              Navigator.pop(context, value);
            }
          });
        },
      ),
    );
  }
}