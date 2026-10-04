import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/nurse_service.dart';
import '../widgets/responsive.dart';
import 'nurse_id_page.dart';
import 'pi_scanner_page.dart';
import 'scanner_page.dart';

/// Feature 1 flow:
/// 1. Screen is locked and the scanner opens straight away.
/// 2. Scanned wristband QR must equal this patient's `qr_uuid`.
///    - No match: nurse chooses "Scan QR again" or "Exit to login page".
/// 3. Match: shows only pharmacist-approved medicines (with approval date).
/// 4. Nurse gives the medicine, presses OK/Done -> timestamp saved to
///    `medication_administrations` and a green tick is shown.
class NurseDispensePage extends StatefulWidget {
  final NurseSession nurse;
  final Patient patient;

  const NurseDispensePage({super.key, required this.nurse, required this.patient});

  @override
  State<NurseDispensePage> createState() => _NurseDispensePageState();
}

class _NurseDispensePageState extends State<NurseDispensePage> {
  bool _busy = false;
  QrMatchResult? _verifiedScan;
  ScanMethod? _verifiedMethod;
  DateTime? _verifiedAt;

  List<ApprovedMedicine> _meds = [];
  Map<String, DateTime> _givenToday = {};
  final Set<String> _saving = {};
  String? _loadError;

  bool get _unlocked => _verifiedScan != null;

  /// Pi (Linux build) defaults to the Pi camera; phone/web to the device camera.
  ScanMethod get _defaultMethod =>
      (!kIsWeb && defaultTargetPlatform == TargetPlatform.linux)
          ? ScanMethod.piCamera
          : ScanMethod.phoneCamera;

  /// mobile_scanner has no Linux desktop support, so hide that option there.
  bool get _deviceCameraAvailable =>
      kIsWeb || defaultTargetPlatform != TargetPlatform.linux;

  @override
  void initState() {
    super.initState();
    // "The app forces the barcode scanner to pop out."
    WidgetsBinding.instance.addPostFrameCallback((_) => _scan(_defaultMethod));
  }

  Future<void> _scan(ScanMethod method) async {
    if (_busy) return;
    final value = await Navigator.push<String>(
      context,
      MaterialPageRoute(
        builder: (_) => method == ScanMethod.piCamera
            ? const PiScannerPage()
            : const ScannerPage(),
      ),
    );
    if (!mounted || value == null || value.trim().isEmpty) return;

    setState(() => _busy = true);
    try {
      final result = await NurseService.verifyWristband(
        nurse: widget.nurse,
        patientId: widget.patient.id,
        patientName: widget.patient.name,
        scannedValue: value,
        method: method,
      );
      if (!mounted) return;

      if (result.matched) {
        setState(() {
          _verifiedScan = result;
          _verifiedMethod = method;
          _verifiedAt = DateTime.now();
        });
        await _loadMedicines();
      } else {
        setState(() => _busy = false);
        await _showMismatch(result, method);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Verification failed: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _showMismatch(QrMatchResult result, ScanMethod method) async {
    final choice = await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        icon: const Icon(Icons.gpp_bad, color: Colors.red, size: 48),
        title: const Text('Wristband does not match'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'The scanned QR code is not ${widget.patient.name}\'s wristband.',
              style: const TextStyle(fontSize: 16),
            ),
            if (result.otherPatientLabel != null) ...[
              const SizedBox(height: 10),
              Text(
                'Scanned wristband belongs to: ${result.otherPatientLabel}',
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  color: Colors.red,
                ),
              ),
            ],
            const SizedBox(height: 10),
            const Text(
              'Medication stays locked. This attempt has been logged.',
              style: TextStyle(color: Colors.black54),
            ),
          ],
        ),
        actions: [
          TextButton.icon(
            onPressed: () => Navigator.pop(ctx, 'exit'),
            icon: const Icon(Icons.logout),
            label: const Text('Exit to login page'),
          ),
          FilledButton.icon(
            onPressed: () => Navigator.pop(ctx, 'retry'),
            icon: const Icon(Icons.qr_code_scanner),
            label: const Text('Scan QR again'),
          ),
        ],
      ),
    );
    if (!mounted) return;
    if (choice == 'exit') {
      exitToNurseLogin(context);
    } else if (choice == 'retry') {
      await _scan(method);
    }
  }

  Future<void> _loadMedicines() async {
    setState(() => _loadError = null);
    try {
      final meds = await NurseService.getApprovedMedicines(widget.patient.id);
      final given = await NurseService.getTodayAdministrations(widget.patient.id);
      if (!mounted) return;
      setState(() {
        _meds = meds;
        _givenToday = given;
      });
    } catch (e) {
      if (mounted) setState(() => _loadError = '$e');
    }
  }

  Future<void> _dispense(ApprovedMedicine med) async {
    final done = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Dispense ${med.name}'),
        content: Text(
          'Patient: ${widget.patient.name} (${widget.patient.wardRoomNo})\n'
          'Dose: ${med.doseText}\n'
          'Route: ${med.route.isEmpty ? '-' : med.route}\n'
          'Frequency: ${med.frequency.isEmpty ? '-' : med.frequency}${med.prn ? ' (PRN)' : ''}\n\n'
          'Give the medication to the patient, then press OK / Done.',
          style: const TextStyle(fontSize: 15, height: 1.4),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton.icon(
            style: FilledButton.styleFrom(backgroundColor: const Color(0xFF116D37)),
            onPressed: () => Navigator.pop(ctx, true),
            icon: const Icon(Icons.check),
            label: const Text('OK / Done'),
          ),
        ],
      ),
    );
    if (done != true || !mounted) return;

    setState(() => _saving.add(med.key));
    try {
      final at = await NurseService.recordAdministration(
        nurse: widget.nurse,
        patientId: widget.patient.id,
        patientName: widget.patient.name,
        med: med,
        scan: _verifiedScan!,
        method: _verifiedMethod!,
      );
      if (!mounted) return;
      setState(() => _givenToday[med.key] = at);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: const Color(0xFF116D37),
          content: Text('${med.name} recorded at ${formatNurseDateTime(at)}'),
        ),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not save: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving.remove(med.key));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF4F8F6),
      appBar: AppBar(
        title: Text(_unlocked ? 'Secure Dispensing' : 'Verify Patient Wristband'),
        backgroundColor: Colors.teal.shade700,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            tooltip: 'Exit to login page',
            icon: const Icon(Icons.logout),
            onPressed: () => exitToNurseLogin(context),
          ),
        ],
      ),
      body: _unlocked ? _unlockedView() : _lockedView(),
    );
  }

  // ------------------------------------------------------------ locked
  Widget _lockedView() {
    return Center(
      child: SingleChildScrollView(
        padding: Responsive.pagePadding(context),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Icon(Icons.lock, size: 72, color: Colors.teal.shade700),
              const SizedBox(height: 14),
              Text(
                'Scan ${widget.patient.name}\'s wristband',
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 6),
              Text(
                'Ward ${widget.patient.wardRoomNo}\nMedication is locked until the QR code matches this patient.',
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.black54, fontSize: 15),
              ),
              const SizedBox(height: 28),
              if (_busy)
                const Center(child: CircularProgressIndicator())
              else ...[
                if (_deviceCameraAvailable)
                  ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.teal.shade700,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                    onPressed: () => _scan(ScanMethod.phoneCamera),
                    icon: const Icon(Icons.qr_code_scanner),
                    label: const Text('Scan with device camera',
                        style: TextStyle(fontSize: 17)),
                  ),
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                  ),
                  onPressed: () => _scan(ScanMethod.piCamera),
                  icon: const Icon(Icons.camera),
                  label: const Text('Scan with Raspberry Pi camera',
                      style: TextStyle(fontSize: 17)),
                ),
                const SizedBox(height: 12),
                TextButton.icon(
                  onPressed: () => exitToNurseLogin(context),
                  icon: const Icon(Icons.logout),
                  label: const Text('Exit to login page'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  // ---------------------------------------------------------- unlocked
  Widget _unlockedView() {
    // Group medicines by pharmacist approval (newest first).
    final groups = <String, List<ApprovedMedicine>>{};
    for (final m in _meds) {
      groups.putIfAbsent(m.verificationId, () => []).add(m);
    }

    return RefreshIndicator(
      onRefresh: _loadMedicines,
      child: ListView(
        padding: Responsive.pagePadding(context),
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFFD9FBE4),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Row(
              children: [
                const Icon(Icons.verified_user, color: Color(0xFF116D37), size: 36),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'Wristband verified: ${widget.patient.name} (${widget.patient.wardRoomNo})\n'
                    'via ${_verifiedMethod!.label} at ${formatNurseDateTime(_verifiedAt)}',
                    style: const TextStyle(
                      color: Color(0xFF0E4F2A),
                      fontWeight: FontWeight.w600,
                      height: 1.35,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          const Text('Pharmacist-Approved Medication',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          if (_loadError != null)
            Text('Could not load medication: $_loadError',
                style: const TextStyle(color: Colors.red))
          else if (_busy)
            const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (_meds.isEmpty)
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text('No medication has been approved by the pharmacist for this patient.'),
            )
          else ...[
            // Only the latest pharmacist approval is the active regimen.
            _approvalCard(groups.values.first, active: true),
            if (groups.length > 1)
              Card(
                margin: const EdgeInsets.symmetric(vertical: 8),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                child: ExpansionTile(
                  leading: const Icon(Icons.history),
                  title: Text('Previous approvals (${groups.length - 1})'),
                  subtitle: const Text('View only - replaced by the latest approval'),
                  childrenPadding: const EdgeInsets.symmetric(horizontal: 8),
                  children: groups.values
                      .skip(1)
                      .map((g) => _approvalCard(g, active: false))
                      .toList(),
                ),
              ),
          ],
          const SizedBox(height: 24),
        ],
      ),
    );
  }

  Widget _approvalCard(List<ApprovedMedicine> meds, {required bool active}) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.event_available, size: 18, color: Colors.teal.shade700),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    '${active ? 'Current - ' : ''}Approved by pharmacist: ${formatNurseDateTime(meds.first.approvedAt)}',
                    style: TextStyle(
                      fontWeight: FontWeight.w700,
                      color: Colors.teal.shade900,
                    ),
                  ),
                ),
              ],
            ),
            const Divider(),
            ...meds.map((m) => _medRow(m, canDispense: active)),
          ],
        ),
      ),
    );
  }

  Widget _medRow(ApprovedMedicine med, {required bool canDispense}) {
    final givenAt = _givenToday[med.key];
    final saving = _saving.contains(med.key);

    Widget trailing;
    if (!canDispense) {
      trailing = givenAt != null
          ? const Icon(Icons.check_circle, color: Color(0xFF1DB954))
          : const SizedBox.shrink();
    } else if (saving) {
      trailing = const SizedBox(
        width: 28,
        height: 28,
        child: CircularProgressIndicator(strokeWidth: 3),
      );
    } else if (givenAt != null) {
      trailing = Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          const Icon(Icons.check_circle, color: Color(0xFF1DB954), size: 34),
          Text(
            'Given ${givenAt.hour.toString().padLeft(2, '0')}:${givenAt.minute.toString().padLeft(2, '0')}',
            style: const TextStyle(
              fontSize: 12,
              color: Color(0xFF116D37),
              fontWeight: FontWeight.w600,
            ),
          ),
          InkWell(
            onTap: () => _dispense(med),
            child: const Padding(
              padding: EdgeInsets.only(top: 2),
              child: Text('Give next dose',
                  style: TextStyle(fontSize: 11, decoration: TextDecoration.underline)),
            ),
          ),
        ],
      );
    } else {
      trailing = ElevatedButton(
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF116D37),
          foregroundColor: Colors.white,
        ),
        onPressed: () => _dispense(med),
        child: const Text('Dispense'),
      );
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        med.name,
                        style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
                      ),
                    ),
                    if (med.prn) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.orange.shade100,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: const Text('PRN', style: TextStyle(fontSize: 11)),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  '${med.doseText}  •  ${med.route.isEmpty ? '-' : med.route}  •  ${med.frequency.isEmpty ? '-' : med.frequency}',
                  style: const TextStyle(color: Colors.black54),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          trailing,
        ],
      ),
    );
  }
}
