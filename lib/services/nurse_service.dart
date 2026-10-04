import 'package:supabase_flutter/supabase_flutter.dart';

/// Logged-in nurse (from the `nurses` table).
class NurseSession {
  final String id;
  final String code;
  final String name;

  const NurseSession({required this.id, required this.code, required this.name});
}

/// Where the wristband QR was read from.
enum ScanMethod { phoneCamera, piCamera }

extension ScanMethodDb on ScanMethod {
  String get dbValue =>
      this == ScanMethod.phoneCamera ? 'phone_camera' : 'pi_camera';
  String get label =>
      this == ScanMethod.phoneCamera ? 'Device camera' : 'Raspberry Pi camera';
}

/// Result of checking a scanned wristband against the selected patient.
class QrMatchResult {
  final bool matched;
  final String scanLogId;
  final String scannedValue;

  /// When the QR belongs to a different patient, their name/ward (for safety).
  final String? otherPatientLabel;

  const QrMatchResult({
    required this.matched,
    required this.scanLogId,
    required this.scannedValue,
    this.otherPatientLabel,
  });
}

/// One medicine the pharmacist approved, ready to be dispensed.
class ApprovedMedicine {
  final String verificationId;
  final String? prescriptionId;
  final int index;
  final DateTime? approvedAt;
  final String name;
  final String dose;
  final String unit;
  final String route;
  final String frequency;
  final bool prn;

  const ApprovedMedicine({
    required this.verificationId,
    required this.prescriptionId,
    required this.index,
    required this.approvedAt,
    required this.name,
    required this.dose,
    required this.unit,
    required this.route,
    required this.frequency,
    required this.prn,
  });

  /// "500 mg" — avoids "10mg mg" when the dose already contains the unit.
  String get doseText {
    final d = dose.trim();
    if (d.isEmpty) return unit;
    final hasLetters = RegExp(r'[a-zA-Z]').hasMatch(d);
    return hasLetters || unit.isEmpty ? d : '$d $unit';
  }

  String get key => '$verificationId#$index';
}

class NurseService {
  static SupabaseClient get _client => Supabase.instance.client;

  /// Statuses in `prescription_verifications` that mean the pharmacist
  /// (and doctor, after any revision) approved the prescription.
  static const approvedStatuses = [
    'approved',
    'doctor_approved',
    'doctor_approved_read',
  ];

  static Future<NurseSession?> login(String nurseCode) async {
    final res = await _client
        .from('nurses')
        .select('id, nurse_code, name')
        .eq('nurse_code', nurseCode)
        .maybeSingle();
    if (res == null) return null;
    return NurseSession(
      id: res['id'] as String,
      code: res['nurse_code'] as String,
      name: (res['name'] ?? '') as String,
    );
  }

  /// Compares the scanned value with the patient's `qr_uuid` and saves the
  /// attempt (match or mismatch) to `qr_scan_logs`.
  static Future<QrMatchResult> verifyWristband({
    required NurseSession nurse,
    required String patientId,
    required String patientName,
    required String scannedValue,
    required ScanMethod method,
  }) async {
    final scanned = scannedValue.trim();

    final patient = await _client
        .from('patients')
        .select('qr_uuid')
        .eq('id', patientId)
        .maybeSingle();
    final expected = (patient?['qr_uuid'] ?? '').toString();

    final matched =
        expected.isNotEmpty && scanned.toLowerCase() == expected.toLowerCase();

    String? otherLabel;
    if (!matched && _looksLikeUuid(scanned)) {
      final other = await _client
          .from('patients')
          .select('name, ward_room_no')
          .eq('qr_uuid', scanned.toLowerCase())
          .maybeSingle();
      if (other != null) {
        otherLabel = '${other['name']} (${other['ward_room_no']})';
      }
    }

    final log = await _client
        .from('qr_scan_logs')
        .insert({
          'nurse_id': nurse.id,
          'nurse_code': nurse.code,
          'patient_id': patientId,
          'patient_name': patientName,
          'expected_qr_uuid': expected.isEmpty ? null : expected,
          'scanned_value': scanned,
          'matched': matched,
          'scan_method': method.dbValue,
        })
        .select('id')
        .single();

    return QrMatchResult(
      matched: matched,
      scanLogId: log['id'] as String,
      scannedValue: scanned,
      otherPatientLabel: otherLabel,
    );
  }

  /// Medicines approved in the pharmacist portal, newest approval first.
  static Future<List<ApprovedMedicine>> getApprovedMedicines(
    String patientId,
  ) async {
    final rows = await _client
        .from('prescription_verifications')
        .select('id, prescription_id, medicines, status, created_at')
        .eq('patient_id', patientId)
        .inFilter('status', approvedStatuses)
        .order('created_at', ascending: false);

    final result = <ApprovedMedicine>[];
    for (final row in rows as List) {
      final meds = row['medicines'];
      if (meds is! List) continue;
      for (var i = 0; i < meds.length; i++) {
        final m = meds[i];
        if (m is! Map) continue;
        final medStatus = (m['status'] ?? 'approved').toString();
        if (medStatus == 'rejected') continue;
        result.add(
          ApprovedMedicine(
            verificationId: row['id'] as String,
            prescriptionId: row['prescription_id'] as String?,
            index: i,
            approvedAt: DateTime.tryParse((row['created_at'] ?? '').toString()),
            name: (m['name'] ?? '-').toString(),
            dose: (m['dose'] ?? '').toString(),
            unit: (m['unit'] ?? '').toString(),
            route: (m['route'] ?? '').toString(),
            frequency: (m['frequency'] ?? '').toString(),
            prn: m['prn'] == true,
          ),
        );
      }
    }
    return result;
  }

  /// Administrations recorded today for this patient, keyed by
  /// ApprovedMedicine.key, value = latest administered time.
  static Future<Map<String, DateTime>> getTodayAdministrations(
    String patientId,
  ) async {
    final now = DateTime.now();
    final startOfDay = DateTime(now.year, now.month, now.day).toUtc();
    final rows = await _client
        .from('medication_administrations')
        .select('verification_id, medicine_index, administered_at')
        .eq('patient_id', patientId)
        .gte('administered_at', startOfDay.toIso8601String())
        .order('administered_at', ascending: true);

    final map = <String, DateTime>{};
    for (final r in rows as List) {
      final at = DateTime.tryParse((r['administered_at'] ?? '').toString());
      if (at == null) continue;
      map['${r['verification_id']}#${r['medicine_index']}'] = at.toLocal();
    }
    return map;
  }

  /// Final audit write when the nurse presses OK/Done. Returns the timestamp.
  static Future<DateTime> recordAdministration({
    required NurseSession nurse,
    required String patientId,
    required String patientName,
    required ApprovedMedicine med,
    required QrMatchResult scan,
    required ScanMethod method,
  }) async {
    final row = await _client
        .from('medication_administrations')
        .insert({
          'nurse_id': nurse.id,
          'nurse_code': nurse.code,
          'patient_id': patientId,
          'patient_name': patientName,
          'prescription_id': med.prescriptionId,
          'verification_id': med.verificationId,
          'medicine_index': med.index,
          'medicine_name': med.name,
          'dose': med.dose,
          'unit': med.unit,
          'route': med.route,
          'frequency': med.frequency,
          'qr_scan_log_id': scan.scanLogId,
          'scanned_qr_uuid': scan.scannedValue,
          'scan_method': method.dbValue,
        })
        .select('administered_at')
        .single();
    return DateTime.parse(row['administered_at'] as String).toLocal();
  }

  static bool _looksLikeUuid(String v) => RegExp(
        r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
      ).hasMatch(v);
}

/// "15 Jun 2026, 13:08" without needing the intl package.
String formatNurseDateTime(DateTime? dt) {
  if (dt == null) return '-';
  final d = dt.toLocal();
  const months = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
  ];
  String two(int n) => n.toString().padLeft(2, '0');
  return '${d.day} ${months[d.month - 1]} ${d.year}, ${two(d.hour)}:${two(d.minute)}';
}
