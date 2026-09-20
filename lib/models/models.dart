/// Core patient info
class Patient {
  final String id;
  final String wardRoomNo;
  final String name;
  final String gender; // ✅ NEW
  final String age;
  final String height;
  final String weight;
  final String bloodType;

  Patient({
    required this.id,
    required this.wardRoomNo,
    required this.name,
    this.gender = '', // default for backward compatibility
    required this.age,
    required this.height,
    required this.weight,
    required this.bloodType,
  });

  // Serialization
  Map<String, dynamic> toJson() => {
    'id': id,
    'wardRoomNo': wardRoomNo,
    'name': name,
    'gender': gender,
    'age': age,
    'height': height,
    'weight': weight,
    'bloodType': bloodType,
  };

  factory Patient.fromJson(Map<String, dynamic> json) => Patient(
    id: json['id'] ?? '',
    wardRoomNo: json['wardRoomNo'] ?? '',
    name: json['name'] ?? '',
    gender: json['gender'] ?? '',
    age: json['age'] ?? '',
    height: json['height'] ?? '',
    weight: json['weight'] ?? '',
    bloodType: json['blood_type'] ?? '',
  );
}

/// One snapshot of patient's condition / vitals
class PatientVitals {
  final String date;
  final String temperature;
  final String bloodPressure;
  final String heartRate;
  final String oxygenSaturation;
  final String urineOutput;
  final String creatinine;
  final String egfr;

  final String allergy; // ✅ NEW
  final String renalFunction; // ✅ NEW

  final String lactate;
  final String wbc;
  final String condition;

  final bool pregnant;
  final bool dialysis;

  PatientVitals({
    required this.date,
    required this.temperature,
    required this.bloodPressure,
    required this.heartRate,
    required this.oxygenSaturation,
    required this.urineOutput,
    required this.creatinine,
    required this.egfr,
    this.allergy = '', // default for backward compatibility
    this.renalFunction = '', // default for backward compatibility
    required this.lactate,
    required this.wbc,
    required this.condition,
    this.pregnant = false, // default false
    this.dialysis = false, // default false
  });

  // Serialization
  Map<String, dynamic> toJson() => {
    'date': date,
    'temperature': temperature,
    'bloodPressure': bloodPressure,
    'heartRate': heartRate,
    'oxygenSaturation': oxygenSaturation,
    'urineOutput': urineOutput,
    'creatinine': creatinine,
    'egfr': egfr,
    'allergy': allergy,
    'renalFunction': renalFunction,
    'lactate': lactate,
    'wbc': wbc,
    'condition': condition,
    'pregnant': pregnant,  // ✅ must match field name
    'dialysis': dialysis,
  };

  factory PatientVitals.fromJson(Map<String, dynamic> json) => PatientVitals(
    date: json['date'] ?? '',
    temperature: json['temperature'] ?? '',
    bloodPressure: json['bloodPressure'] ?? '',
    heartRate: json['heartRate'] ?? '',
    oxygenSaturation: json['oxygenSaturation'] ?? '',
    urineOutput: json['urineOutput'] ?? '',
    creatinine: json['creatinine'] ?? '',
    egfr: json['egfr'] ?? '',
    allergy: json['allergy'] ?? '',
    renalFunction: json['renalFunction'] ?? '',
    lactate: json['lactate'] ?? '',
    wbc: json['wbc'] ?? '',
    condition: json['condition'] ?? '',
    pregnant: json['pregnant'] ?? false,  // ✅ must match field name
    dialysis: json['dialysis'] ?? false, 
  );
}

/// Record linking a patient to one vitals snapshot
class PatientConditionRecord {
  final String patientId;
  final PatientVitals vitals;

  PatientConditionRecord({required this.patientId, required this.vitals});

  // Serialization
  Map<String, dynamic> toJson() => {
    'patientId': patientId,
    'vitals': vitals.toJson(),
  };

  factory PatientConditionRecord.fromJson(Map<String, dynamic> json) =>
      PatientConditionRecord(
        patientId: json['patientId'] ?? '',
        vitals: PatientVitals.fromJson(json['vitals'] ?? {}),
      );
}

/// Doctor-accepted prescription queued for pharmacist verification
class FinalPrescription {
  final String id;
  final String patientId;
  final String patientName;
  final String wardRoomNo;
  final String date;
  final List<dynamic> medicines;

  final String medicine; // final chosen medicine (doctor or AI)
  final String doctorMedicine; // what doctor originally typed
  final String rationale; // AI explanation from doctor screen

  FinalPrescription({
    required this.id,
    required this.patientId,
    required this.patientName,
    required this.wardRoomNo,
    required this.date,
    required this.medicine,
    required this.doctorMedicine,
    required this.rationale,
    required this.medicines,
  });

  factory FinalPrescription.fromJson(Map<String, dynamic> json) {
  return FinalPrescription(
    id: json['id'] ?? '',
    patientId: json['patient_id'] ?? '',
    patientName: json['patient_name'] ?? '',
    wardRoomNo: json['ward_room_no'] ?? '',
    date: json['created_at'] ?? '',
    medicine: json['medicine'] ?? '',
    doctorMedicine: json['doctor_medicine'] ?? '',
    rationale: json['rationale'] ?? '',

    // 🔥 THIS IS WHERE YOUR JSONB GOES
    medicines: json['medicines'] ?? [],
  );
}
}

/// Pharmacist-verified plan (approved or pharmacist-edited dose)
class VerifiedPlan {
  final String patientId;
  final String? date;
  final List<Map<String, dynamic>> medicines;

  VerifiedPlan({
    required this.patientId,
    this.date,
    required this.medicines,
  });

  Map<String, dynamic> toJson() {
    return {
      'patient_id': patientId,
      'date': date,
      'medicines': medicines,
    };
  }

  factory VerifiedPlan.fromJson(Map<String, dynamic> json) {
    return VerifiedPlan(
      patientId: json['patient_id'] ?? '',
      date: json['created_at'],
      medicines: List<Map<String, dynamic>>.from(
        json['medicines'] ?? [],
      ),
    );
  }
}

/// AI rule check result for doctor's medicine
class MedicineCheckResult {
  final bool isCorrect;
  final String explanation;
  final List<String> suggestedMedicines;

  MedicineCheckResult({
    required this.isCorrect,
    required this.explanation,
    required this.suggestedMedicines,
  });
}

/// AI dose calculation result (for pharmacist demo)
class DoseCalcResult {
  final String doseText;
  final String explanation;

  DoseCalcResult({required this.doseText, required this.explanation});
}
