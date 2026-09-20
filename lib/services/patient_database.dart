import '../models/models.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';

/// In-memory database with persistent storage (shared_preferences).
class PatientDatabase {
  PatientDatabase._();
  static final PatientDatabase instance = PatientDatabase._();

  // Core patient + condition history
  final List<Patient> _patients = [];
  final List<PatientConditionRecord> _conditionHistory = [];

  // Doctor-accepted prescriptions queued for PHARMACIST verification
  final List<FinalPrescription> _toVerifyQueue = [];

  // Pharmacist-verified plans (approved or edited doses)
  final List<VerifiedPlan> _verifiedPlans = [];

  // Storage keys
  static const String _patientsKey = 'patients';
  static const String _conditionHistoryKey = 'conditionHistory';
  static const String _verifiedPlansKey = 'verifiedPlans';

  // Initialize (load from storage)
  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();

    // Load patients
    final patientsJson = prefs.getString(_patientsKey);
    if (patientsJson != null) {
      final List<dynamic> decoded = jsonDecode(patientsJson);
      _patients.addAll(
        decoded.map((p) => Patient.fromJson(p as Map<String, dynamic>)),
      );
    }

    // Load condition history
    final historyJson = prefs.getString(_conditionHistoryKey);
    if (historyJson != null) {
      final List<dynamic> decoded = jsonDecode(historyJson);
      _conditionHistory.addAll(
        decoded.map(
          (h) => PatientConditionRecord.fromJson(h as Map<String, dynamic>),
        ),
      );
    }

    // Load verified plans
    final plansJson = prefs.getString(_verifiedPlansKey);
    if (plansJson != null) {
      final List<dynamic> decoded = jsonDecode(plansJson);
      _verifiedPlans.addAll(
        decoded.map((p) => VerifiedPlan.fromJson(p as Map<String, dynamic>)),
      );
    }
  }

  // Save to storage
  Future<void> _savePatients() async {
    final prefs = await SharedPreferences.getInstance();
    final jsonStr = jsonEncode(_patients.map((p) => p.toJson()).toList());
    await prefs.setString(_patientsKey, jsonStr);
  }

  Future<void> _saveConditionHistory() async {
    final prefs = await SharedPreferences.getInstance();
    final jsonStr =
        jsonEncode(_conditionHistory.map((h) => h.toJson()).toList());
    await prefs.setString(_conditionHistoryKey, jsonStr);
  }

  Future<void> _saveVerifiedPlans() async {
    final prefs = await SharedPreferences.getInstance();
    final jsonStr = jsonEncode(_verifiedPlans.map((p) => p.toJson()).toList());
    await prefs.setString(_verifiedPlansKey, jsonStr);
  }

  // ---------- Patients ----------
  List<Patient> get patients => List.unmodifiable(_patients);

  Future<void> addPatient(Patient p) async {
    _patients.add(p);
    await _savePatients();
  }

  // Helper: fetch patient by id
  Patient? patientById(String id) => _patients.cast<Patient?>().firstWhere(
        (p) => p?.id == id,
        orElse: () => null,
      );

  // ---------- Condition history ----------
  Future<void> addConditionRecord(PatientConditionRecord r) async {
    _conditionHistory.add(r);
    await _saveConditionHistory();
  }

  List<PatientConditionRecord> historyForPatient(String id) =>
      _conditionHistory.where((r) => r.patientId == id).toList();

  // ---------- Pharmacist queues ----------
  List<FinalPrescription> get toVerifyQueue => List.unmodifiable(_toVerifyQueue);

  void enqueueForVerification(FinalPrescription rx) => _toVerifyQueue.add(rx);

  void removeFromQueue(String id) =>
      _toVerifyQueue.removeWhere((e) => e.id == id);

  // ---------- Verified plans ----------
  List<VerifiedPlan> get verifiedPlans => List.unmodifiable(_verifiedPlans);

  Future<void> addVerifiedPlan(VerifiedPlan vp) async {
    _verifiedPlans.add(vp);
    await _saveVerifiedPlans();
  }

  // ---------- Seed demo data ----------
  Future<void> seedDemoDataIfEmpty() async {
    if (_patients.isNotEmpty) return; // prevent duplicate seeding

    // 1) Seed patients
    final demoPatients = <Patient>[
      Patient(
        id: 'P001',
        wardRoomNo: 'A101',
        name: 'See Seng Hong',
        gender: 'Male',
        age: '22',
        height: '160',
        weight: '78',
        bloodType: 'O+',
      ),
      Patient(
        id: 'P002',
        wardRoomNo: 'A102',
        name: 'Nur Aisyah',
        gender: 'Female',
        age: '32',
        height: '162',
        weight: '60',
        bloodType: 'A+',
      ),
      Patient(
        id: 'P003',
        wardRoomNo: 'B201',
        name: 'Lim Wei Jian',
        gender: 'Male',
        age: '60',
        height: '168',
        weight: '72',
        bloodType: 'B+',
      ),
      Patient(
        id: 'P004',
        wardRoomNo: 'B202',
        name: 'Siti Khadijah',
        gender: 'Female',
        age: '28',
        height: '158',
        weight: '55',
        bloodType: 'AB+',
      ),
      Patient(
        id: 'P005',
        wardRoomNo: 'C301',
        name: 'Arjun Kumar',
        gender: 'Male',
        age: '50',
        height: '175',
        weight: '85',
        bloodType: 'O-',
      ),
      Patient(
        id: 'P006',
        wardRoomNo: 'C302',
        name: 'Tan Mei Ling',
        gender: 'Female',
        age: '70',
        height: '155',
        weight: '50',
        bloodType: 'A-',
      ),
      Patient(
        id: 'P007',
        wardRoomNo: 'D401',
        name: 'Muhammad Haziq',
        gender: 'Male',
        age: '22',
        height: '172',
        weight: '68',
        bloodType: 'B-',
      ),
    ];

    _patients.addAll(demoPatients);
    await _savePatients();

    // 2) Seed conditions (ALL PATIENTS, no diabetes/hypertension)
    final demoConditions = <PatientConditionRecord>[
      PatientConditionRecord(
        patientId: 'P001',
        vitals: PatientVitals(
          date: '2025-11-01',
          temperature: '38.6',
          bloodPressure: '118/76',
          heartRate: '105',
          oxygenSaturation: '92',
          urineOutput: '40',
          creatinine: '1.2',
          egfr: '75',
          allergy: 'None',
          renalFunction: 'Normal',
          lactate: '1.8',
          wbc: '15',
          condition: 'Community-acquired pneumonia (suspected bacterial)',
        ),
      ),
      PatientConditionRecord(
        patientId: 'P002',
        vitals: PatientVitals(
          date: '2025-11-02',
          temperature: '38.2',
          bloodPressure: '124/78',
          heartRate: '98',
          oxygenSaturation: '98',
          urineOutput: '55',
          creatinine: '1.1',
          egfr: '82',
          allergy: 'None',
          renalFunction: 'Normal',
          lactate: '1.4',
          wbc: '13',
          condition: 'Urinary tract infection / pyelonephritis',
        ),
      ),
      PatientConditionRecord(
        patientId: 'P003',
        vitals: PatientVitals(
          date: '2025-11-03',
          temperature: '38.0',
          bloodPressure: '122/80',
          heartRate: '96',
          oxygenSaturation: '97',
          urineOutput: '50',
          creatinine: '1.0',
          egfr: '88',
          allergy: 'Penicillin (rash)',
          renalFunction: 'Normal',
          lactate: '1.2',
          wbc: '14',
          condition: 'Cellulitis / skin and soft tissue infection',
        ),
      ),
      PatientConditionRecord(
        patientId: 'P004',
        vitals: PatientVitals(
          date: '2025-11-04',
          temperature: '39.2',
          bloodPressure: '92/58',
          heartRate: '122',
          oxygenSaturation: '93',
          urineOutput: '25',
          creatinine: '2.0',
          egfr: '35',
          allergy: 'None',
          renalFunction: 'Impaired (AKI risk)',
          lactate: '3.6',
          wbc: '18',
          condition: 'Suspected sepsis (bacterial source)',
        ),
      ),
      PatientConditionRecord(
        patientId: 'P005',
        vitals: PatientVitals(
          date: '2025-11-05',
          temperature: '37.0',
          bloodPressure: '120/75',
          heartRate: '84',
          oxygenSaturation: '98',
          urineOutput: '60',
          creatinine: '1.0',
          egfr: '90',
          allergy: 'None',
          renalFunction: 'Normal',
          lactate: '1.0',
          wbc: '8',
          condition: 'Post-operative immobilization with high clot risk',
        ),
      ),
      PatientConditionRecord(
        patientId: 'P006',
        vitals: PatientVitals(
          date: '2025-11-06',
          temperature: '37.2',
          bloodPressure: '126/80',
          heartRate: '92',
          oxygenSaturation: '97',
          urineOutput: '55',
          creatinine: '1.1',
          egfr: '78',
          allergy: 'None',
          renalFunction: 'Normal',
          lactate: '1.2',
          wbc: '9',
          condition: 'Suspected deep vein thrombosis (leg swelling/pain)',
        ),
      ),
      PatientConditionRecord(
        patientId: 'P007',
        vitals: PatientVitals(
          date: '2025-11-07',
          temperature: '37.4',
          bloodPressure: '110/70',
          heartRate: '118',
          oxygenSaturation: '89',
          urineOutput: '45',
          creatinine: '1.3',
          egfr: '62',
          allergy: 'None',
          renalFunction: 'Mild impairment',
          lactate: '2.3',
          wbc: '11',
          condition: 'Suspected pulmonary embolism (acute shortness of breath)',
        ),
      ),
    ];

    _conditionHistory.addAll(demoConditions);
    await _saveConditionHistory();
  }

  // ---------- Clear all ----------
  Future<void> clearAll() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_patientsKey);
    await prefs.remove(_conditionHistoryKey);
    await prefs.remove(_verifiedPlansKey);

    _patients.clear();
    _conditionHistory.clear();
    _toVerifyQueue.clear();
    _verifiedPlans.clear();
  }
}
