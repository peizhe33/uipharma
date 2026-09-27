import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class NurseDispenseScannerScreen extends StatefulWidget {
  final String selectedPatientId;
  final WidgetBuilder? verifiedMedicationsBuilder;
  final WidgetBuilder? nursePreparationBuilder;
  final String dispensingTable;
  final String dispensingTimestampColumn;

  const NurseDispenseScannerScreen({
    super.key,
    required this.selectedPatientId,
    this.verifiedMedicationsBuilder,
    this.nursePreparationBuilder,
    this.dispensingTable = 'patients',
    this.dispensingTimestampColumn = 'dispensed_at',
  });

  @override
  State<NurseDispenseScannerScreen> createState() =>
      _NurseDispenseScannerScreenState();
}

class _NurseDispenseScannerScreenState extends State<NurseDispenseScannerScreen>
    with WidgetsBindingObserver {
  final MobileScannerController _controller = MobileScannerController();
  int failedAttempts = 0;
  bool _isProcessingScan = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    switch (state) {
      case AppLifecycleState.resumed:
        _controller.start();
      case AppLifecycleState.inactive:
      case AppLifecycleState.paused:
      case AppLifecycleState.detached:
      case AppLifecycleState.hidden:
        _controller.stop();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _controller.stop();
    _controller.dispose();
    super.dispose();
  }

  Future<void> _handleScan(BarcodeCapture capture) async {
    if (_isProcessingScan || capture.barcodes.isEmpty) return;

    final scannedUuid = capture.barcodes.first.rawValue;
    if (scannedUuid == null || scannedUuid.isEmpty) return;

    _isProcessingScan = true;
    await _controller.stop();

    if (scannedUuid == widget.selectedPatientId) {
      await _handleMatchingWristband();
    } else {
      await _handleMismatchedWristband();
    }
  }

  Future<void> _handleMatchingWristband() async {
    if (!mounted) return;

    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Wristband verified'),
        content: const Text('The wristband matches the selected patient.'),
        icon: const Icon(Icons.check_circle, color: Colors.green, size: 48),
        actions: [
          FilledButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Continue'),
          ),
        ],
      ),
    );

    try {
      final timestamp = DateTime.now().toIso8601String();
      await Supabase.instance.client
          .from(widget.dispensingTable)
          .update({widget.dispensingTimestampColumn: timestamp})
          .eq('id', widget.selectedPatientId);

      if (!mounted) return;
      final builder = widget.verifiedMedicationsBuilder;
      if (builder != null) {
        Navigator.pushReplacement(context, MaterialPageRoute(builder: builder));
      } else {
        Navigator.pop(context, timestamp);
      }
    } catch (error) {
      if (!mounted) return;
      _isProcessingScan = false;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to record dispensing: $error')),
      );
      _controller.start();
    }
  }

  Future<void> _handleMismatchedWristband() async {
    failedAttempts++;
    if (!mounted) return;

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Wristband mismatch! Attempt $failedAttempts of 3.'),
      ),
    );

    if (failedAttempts >= 3) {
      await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Maximum scan attempts exceeded'),
          content: const Text(
            'Maximum scan attempts exceeded. Please re-verify patient selection.',
          ),
          icon: const Icon(Icons.error, color: Colors.red, size: 48),
          actions: [
            FilledButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Return to queue'),
            ),
          ],
        ),
      );

      if (!mounted) return;
      final builder = widget.nursePreparationBuilder;
      if (builder != null) {
        Navigator.pushAndRemoveUntil(
          context,
          MaterialPageRoute(builder: builder),
          (route) => false,
        );
      } else {
        Navigator.pop(context);
      }
      return;
    }

    _isProcessingScan = false;
    _controller.start();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Verify Wristband'),
        actions: [
          IconButton(
            tooltip: 'Cancel',
            icon: const Icon(Icons.close),
            onPressed: () => Navigator.pop(context),
          ),
        ],
      ),
      body: MobileScanner(controller: _controller, onDetect: _handleScan),
    );
  }
}
