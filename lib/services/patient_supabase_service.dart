import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/models.dart';

class PatientSupabaseService {
  static final _client = Supabase.instance.client;

  static Future<void> addPatient(Patient p) async {
    await _client.from('patients').insert({
      'id': p.id,
      'ward_room_no': p.wardRoomNo,
      'name': p.name,
      'gender': p.gender,
      'age': p.age,
      'height': p.height,
      'weight': p.weight,
      'blood_type': p.bloodType,
    });
  }
  static Future<List<Patient>> getPatients() async {
    final data = await _client.from('patients').select();

    return (data as List).map((e) {
      return Patient(
        id: e['id'],
        wardRoomNo: e['ward_room_no'],
        name: e['name'],
        gender: e['gender'] ?? '',
        age: e['age'],
        height: e['height'],
        weight: e['weight'],
        bloodType: e['blood_type'],
      );
    }).toList();
  }

  static Future<Patient?> getPatientById(String patientId) async {
    final data = await _client
        .from('patients')
        .select()
        .eq('id', patientId)
        .maybeSingle();
    if (data == null) return null;
    return Patient(
      id: data['id'],
      wardRoomNo: data['ward_room_no'],
      name: data['name'],
      gender: data['gender'] ?? '',
      age: data['age'],
      height: data['height'],
      weight: data['weight'],
      bloodType: data['blood_type'],
    );
  }

  // =========================
  // WHERE: BY WARD
  // =========================
  static Future<List<Patient>> getPatientsByWard(String ward) async {
    final data = await _client
        .from('patients')
        .select()
        .eq('ward_room_no', ward);

    return (data as List).map((e) {
      return Patient(
        id: e['id'],
        wardRoomNo: e['ward_room_no'],
        name: e['name'],
        gender: e['gender'] ?? '',
        age: e['age'],
        height: e['height'],
        weight: e['weight'],
        bloodType: e['blood_type'],
      );
    }).toList();
  }

  static Future<String?> getPatientNameById(String patientId) async {
    final data = await _client
        .from('patients')
        .select('name')
        .eq('id', patientId.trim())
        .maybeSingle();

    final name = data?['name'];
    if (name is String && name.trim().isNotEmpty) {
      return name.trim();
    }
    return null;
  }

  // =========================
  // SEARCH: BY NAME
  // =========================
  static Future<List<Patient>> searchPatients(String query) async {
    final data = await _client
        .from('patients')
        .select()
        .ilike('name', '%$query%');

    return (data as List).map((e) {
      return Patient(
        id: e['id'],
        wardRoomNo: e['ward_room_no'],
        name: e['name'],
        gender: e['gender'] ?? '',
        age: e['age'],
        height: e['height'],
        weight: e['weight'],
        bloodType: e['blood_type'],
      );
    }).toList();
  }
  static Future<List<Map<String, dynamic>>> getPatientHistory(String patientId) async {
    final data = await _client
        .from('patient_history')
        .select()
        .eq('patient_id', patientId)
        .order('date', ascending: false);

    return List<Map<String, dynamic>>.from(data);
  }
  static Future<void> addPatientHistory({
  required String patientId,
  required double temperature,
  required String bloodPressure,
  required int heartRate,
  required int spo2,
  required String condition,
}) async {
  await _client.from('patient_history').insert({
    'patient_id': patientId,
    'created_at': DateTime.now().toIso8601String(),
    'temperature': temperature,
    'blood_pressure': bloodPressure,
    'heart_rate': heartRate,
    'spo2': spo2,
    'condition': condition,
  });
}

static Future<List<Map<String, dynamic>>> getEgfrHistory(String patientId) async {

  print('======================');
  print('PATIENT ID: $patientId');

  final data = await _client
      .from('lab_results')
      .select('*')
      .eq('patient_id', patientId.trim())
      .order('recorded_at', ascending: false);

  print('SUPABASE RESULT: $data');
  print('======================');

  return List<Map<String, dynamic>>.from(data);
}

static Future<Map<String, dynamic>?> getLatestEgfr(String patientId) async {
  final data = await _client
      .from('lab_results')
      .select()
      .eq('patient_id', patientId)
      .eq('test_type', 'eGFR')
      .order('recorded_at', ascending: false)
      .limit(1);

  if (data.isEmpty) return null;
  return data.first;
}
static Future<List<Map<String, dynamic>>> getAllEgfrHistory() async {
  final data = await _client
      .from('lab_results')
      .select('*')
      .order('patient_id', ascending: true)
      .order('recorded_at', ascending: true);

  return List<Map<String, dynamic>>.from(data);
}

static Future<void> seedAhmadPneumoniaPatient() async {
  const patientId = 'PNEU001';

  final existing = await _client
      .from('patients')
      .select()
      .eq('id', patientId)
      .maybeSingle();

  if (existing != null) return;

  await _client.from('patients').insert({
    'id': patientId,
    'ward_room_no': 'C214',
    'name': 'Ahmad Firdaus Bin Rahman',
    'gender': 'Male',
    'age': '72',
    'height': '168',
    'weight': '64',
    'blood_type': 'O+',
  });
}

static Future<void> seedSepsisPatient() async {
  const patientId = 'SEPSIS001';

  final existing = await _client
      .from('patients')
      .select()
      .eq('id', patientId)
      .maybeSingle();

  if (existing != null) return;

  await _client.from('patients').insert({
    'id': patientId,
    'ward_room_no': 'B315',
    'name': 'Siti Nur Aisyah',
    'gender': 'Female',
    'age': '67',
    'height': '158',
    'weight': '59',
    'blood_type': 'A+',
  });
}

static Future<void> deletePatient(String patientId) async {
  final deleted = await _client
      .from('patients')
      .delete()
      .eq('id', patientId)
      .select();

  if (deleted.isEmpty) {
    throw Exception('No patient deleted. Check patient ID or Supabase delete permission.');
  }
}

static Future<void> addCurrentCondition({
  required Patient patient,
  required PatientVitals vitals,
}) async {
  await _client.from('patient_current_conditions').insert({
    'patient_id': patient.id,
    'patient_name': patient.name,
    'ward_room_no': patient.wardRoomNo,
    'gender': patient.gender,
    'age': patient.age,
    'height': patient.height,
    'weight': patient.weight,
    'blood_type': patient.bloodType,

    'date': vitals.date,
    'temperature': vitals.temperature,
    'blood_pressure': vitals.bloodPressure,
    'heart_rate': vitals.heartRate,
    'oxygen_saturation': vitals.oxygenSaturation,
    'urine_output': vitals.urineOutput,
    'creatinine': vitals.creatinine,
    'egfr': vitals.egfr,
    'allergy': vitals.allergy,
    'renal_function': vitals.renalFunction,
    'pregnant': vitals.pregnant,
    'dialysis': vitals.dialysis,
    'lactate': vitals.lactate,
    'wbc': vitals.wbc,
    'condition': vitals.condition,
    'created_at': DateTime.now().toIso8601String(),
  });
}

static Future<List<Map<String, dynamic>>> getPatientConditions(
    String patientId,
) async {

  final response = await _client
      .from('patient_current_conditions')
      .select()
      .eq('patient_id', patientId)
      .order('date', ascending: false);

  return List<Map<String, dynamic>>.from(response);
}

static Future<void> addEgfrResult({
  required String patientId,
  required String value,
  required String recordedAt,
}) async {
  await _client.from('lab_results').insert({
    'patient_id': patientId,
    'test_type': 'eGFR',
    'value': double.tryParse(value) ?? 0,
    'recorded_at': recordedAt,
    'unit': 'mL/min/1.73m²',
  });
}

static Future<void> deleteEgfrResult(String id) async {
  await _client.from('lab_results').delete().eq('id', id);
}

static Future<void> addFinalPrescription({
  required String patientId,
  required String patientName,
  required String wardRoomNo,
  required String medicine,
  required String doctorMedicine,
  required String rationale,
  required String date,
}) async {
  await _client.from('final_prescriptions').insert({
    'patient_id': patientId,
    'patient_name': patientName,
    'ward_room_no': wardRoomNo,
    'medicine': medicine,
    'doctor_medicine': doctorMedicine,
    'rationale': rationale,
    'created_at': date,
  });
}

static Future<List<FinalPrescription>> getVerifiedPrescriptionsForPatient(
  String patientId,
) async {
  final data = await _client
      .from('prescriptions')
      .select()
      .eq('patient_id', patientId.trim())
      .eq('status', 'verified')
      .order('created_at', ascending: false);

  return (data as List)
      .map((row) => FinalPrescription.fromJson(row))
      .toList();
}

static Future<void> addPrescription({
  required String patientId,
  required String patientName,
  required String wardRoomNo,
  required List<Map<String, dynamic>> medicines,
  required String rationale,
  required String date,
}) async {
  final client = Supabase.instance.client;

  await client.from('prescriptions').insert({
    'patient_id': patientId,
    'patient_name': patientName,
    'ward_room_no': wardRoomNo,
    'medicines': medicines,
    'rationale': rationale,
    'created_at': date,

    // 🔥 THIS IS THE KEY LINE YOU ARE MISSING
    'status': 'pending_verification',
  });
}

static Future<List<Map<String, dynamic>>> getDoctorReviewNotifications() async {
  final data = await _client
      .from('prescription_verifications')
      .select()
      .eq('status', 'pharmacist_rejected')
      .order('created_at', ascending: false);

  return List<Map<String, dynamic>>.from(data);
}

static Future<List<Map<String, dynamic>>> getPharmacistDecisionNotifications() async {
  final data = await _client
      .from('prescription_verifications')
      .select()
      .order('created_at', ascending: false);

  return List<Map<String, dynamic>>.from(data).where((item) {
    final status = (item['status'] ?? '').toString();
    return status == 'doctor_rejected';
  }).toList();
}

static Future<Map<String, dynamic>?> getLatestPatientCondition(String patientId) async {
  final data = await _client
      .from('patient_current_conditions')
      .select()
      .eq('patient_id', patientId)
      .order('created_at', ascending: false)
      .limit(1);

  if (data.isEmpty) return null;
  return Map<String, dynamic>.from(data.first);
}

static Future<void> submitDoctorReviewDecision({
  String? reviewId,
  required String prescriptionId,
  required String status,
  required List<Map<String, dynamic>> medicines,
  required String doctorReason,
}) async {
  final approved = status == 'approved';
  final normalizedStatus = approved ? 'approved' : 'doctor_rejected';

  final updatedMedicines = medicines.map((med) {
    return {
      ...med,
      'status': approved ? 'approved' : 'rejected',
      'doctor_decision': approved ? 'doctor_approved' : 'doctor_rejected',
      'doctor_reason': doctorReason,
      'doctor_decided_at': DateTime.now().toIso8601String(),
    };
  }).toList();

  var verificationUpdate = _client
      .from('prescription_verifications')
      .update({
        'status': normalizedStatus,
        'medicines': updatedMedicines,
      });

  if (reviewId != null && reviewId.isNotEmpty) {
    await verificationUpdate.eq('id', reviewId);
  } else {
    await verificationUpdate
        .eq('prescription_id', prescriptionId)
        .eq('status', 'pharmacist_rejected');
  }

  await _client
      .from('prescriptions')
      .update({
        'status': approved ? 'verified' : 'doctor_rejected',
        'medicines': updatedMedicines,
      })
      .eq('id', prescriptionId);
}

static Future<void> submitPharmacistReviewDecision({
  String? reviewId,
  required String prescriptionId,
  required String status,
  required List<Map<String, dynamic>> medicines,
  required String pharmacistReason,
}) async {
  final approved = status == 'approved';
  final normalizedStatus = approved ? 'approved' : 'pharmacist_rejected';

  final updatedMedicines = medicines.map((med) {
    return {
      ...med,
      'status': approved ? 'approved' : 'rejected',
      'pharmacist_decision': approved
          ? 'pharmacist_approved_doctor_response'
          : 'pharmacist_rejected_doctor_response',
      'pharmacist_rejection_reason': pharmacistReason,
      'pharmacist_reviewed_at': DateTime.now().toIso8601String(),
    };
  }).toList();

  var verificationUpdate = _client
      .from('prescription_verifications')
      .update({
        'status': normalizedStatus,
        'medicines': updatedMedicines,
      });

  if (reviewId != null && reviewId.isNotEmpty) {
    await verificationUpdate.eq('id', reviewId);
  } else {
    await verificationUpdate
        .eq('prescription_id', prescriptionId)
        .eq('status', 'doctor_rejected');
  }

  await _client
      .from('prescriptions')
      .update({
        'status': approved ? 'verified' : 'pharmacist_rejected',
        'medicines': updatedMedicines,
      })
      .eq('id', prescriptionId);
}

static Future<void> markPharmacistDecisionRead({
  required String prescriptionId,
  required String currentStatus,
  required List<Map<String, dynamic>> medicines,
}) async {
  final readStatus = currentStatus == 'doctor_approved'
      ? 'doctor_approved_read'
      : 'doctor_rejected_read';

  await _client
      .from('prescription_verifications')
      .update({
        'status': readStatus,
        'medicines': medicines,
      })
      .eq('prescription_id', prescriptionId)
      .eq('status', currentStatus);
}

}
