import '../models/models.dart';

/// Very simplified demo rules – NOT clinical advice.
MedicineCheckResult checkMedicine(
  Patient patient,
  PatientVitals vitals,
  String doctorMedicine,
) {
  final med = doctorMedicine.toLowerCase();
  final cond = vitals.condition.toLowerCase();

  double? numOrNull(String s) =>
      double.tryParse(s.replaceAll(RegExp(r'[^0-9.]'), ''));
  final double? temp = numOrNull(vitals.temperature);
  final double? lactate = numOrNull(vitals.lactate);

  double? systolic;
  if (vitals.bloodPressure.contains('/')) {
    final parts = vitals.bloodPressure.split('/');
    if (parts.isNotEmpty) systolic = numOrNull(parts[0]);
  }

  bool containsAny(String text, List<String> opts) =>
      opts.any((o) => text.contains(o));

  final sepsisAntibiotics = [
    'piperacillin-tazobactam',
    'piperacillin',
    'tazocin',
    'meropenem',
    'ceftriaxone',
  ];
  final antipyretics = ['paracetamol', 'acetaminophen', 'ibuprofen'];
  final antihypertensives = ['labetalol', 'nifedipine', 'amlodipine'];

  final bool sepsisLike =
      cond.contains('sepsis') ||
      cond.contains('septic') ||
      ((temp ?? 0) >= 38 && (lactate ?? 0) >= 2);

  if (sepsisLike) {
    if (containsAny(med, sepsisAntibiotics)) {
      return MedicineCheckResult(
        isCorrect: true,
        explanation:
            'Sepsis-like picture; broad-spectrum IV antibiotic such as "$doctorMedicine" is reasonable in this demo.',
        suggestedMedicines: const [],
      );
    }
    return MedicineCheckResult(
      isCorrect: false,
      explanation:
          'Sepsis-like picture; demo expects early broad-spectrum IV antibiotics. "$doctorMedicine" may be inadequate.',
      suggestedMedicines: sepsisAntibiotics,
    );
  }

  final bool simpleFever = (temp ?? 0) >= 38 &&
      ((lactate == null) || lactate < 2) &&
      (cond.contains('viral') || cond.contains('flu') || cond.contains('fever'));

  if (simpleFever) {
    if (containsAny(med, antipyretics)) {
      return MedicineCheckResult(
        isCorrect: true,
        explanation:
            'Uncomplicated fever; antipyretic like "$doctorMedicine" is reasonable for symptom relief (demo).',
        suggestedMedicines: const [],
      );
    }
    return MedicineCheckResult(
      isCorrect: false,
      explanation:
          'Uncomplicated fever demo: expects simple antipyretics (e.g., paracetamol). "$doctorMedicine" not typical.',
      suggestedMedicines: antipyretics,
    );
  }

  final bool hypertensive = (systolic != null && systolic >= 180) ||
      cond.contains('hypertensive') ||
      cond.contains('hypertension');

  if (hypertensive) {
    if (containsAny(med, antihypertensives)) {
      return MedicineCheckResult(
        isCorrect: true,
        explanation:
            'Markedly elevated BP; antihypertensive like "$doctorMedicine" can be reasonable (teaching demo).',
        suggestedMedicines: const [],
      );
    }
    return MedicineCheckResult(
      isCorrect: false,
      explanation:
          'Hypertensive scenario demo: expects antihypertensives (e.g., labetalol). "$doctorMedicine" not typical.',
      suggestedMedicines: antihypertensives,
    );
  }

  return MedicineCheckResult(
    isCorrect: true,
    explanation:
        'Demo rules could not match; cannot say "$doctorMedicine" is wrong with limited data.',
    suggestedMedicines: const [],
  );
}
