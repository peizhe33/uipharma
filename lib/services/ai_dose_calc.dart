import '../models/models.dart';

/// Demo-only dose calculation – returns a rough text dose.
/// Not clinical advice. Replace with your real AI integration.
DoseCalcResult calculateDemoDose({
  required Patient patient,
  required PatientVitals vitals,
  required String medicineName,
}) {
  final med = medicineName.toLowerCase();
  final double? weightKg =
      double.tryParse(patient.weight.replaceAll(RegExp(r'[^0-9.]'), ''));

  // crude defaults when weight missing
  final w = (weightKg == null || weightKg <= 0) ? 70.0 : weightKg;

  if (med.contains('ceftriaxone')) {
    final mg = (50 * w).clamp(0, 2000).round();
    final g = (mg / 1000).toStringAsFixed(1);
    return DoseCalcResult(
      doseText: '$g g IV every 24h',
      explanation:
          'Demo rule: ceftriaxone ~50 mg/kg/day (max 2 g). Calculated for ${w.toStringAsFixed(0)} kg.',
    );
  }

  if (med.contains('meropenem')) {
    final mg = (20 * w).round();
    final capped = mg > 1000 ? 1000 : mg;
    final g = (capped / 1000).toStringAsFixed(1);
    return DoseCalcResult(
      doseText: '$g g IV every 8h',
      explanation:
          'Demo rule: meropenem ~20 mg/kg q8h (cap ~1 g). Using ${w.toStringAsFixed(0)} kg.',
    );
  }

  if (med.contains('piperacillin') || med.contains('tazocin')) {
    return DoseCalcResult(
      doseText: '4.5 g IV every 6h',
      explanation:
          'Demo rule: adult piperacillin-tazobactam often 4.5 g IV q6h (teaching).',
    );
  }

  if (med.contains('paracetamol') || med.contains('acetaminophen')) {
    final mg = (15 * w).round();
    final capped = mg > 1000 ? 1000 : mg;
    return DoseCalcResult(
      doseText: '$capped mg PO/IV every 6h PRN',
      explanation:
          'Demo rule: paracetamol ~15 mg/kg q6h (cap 1 g). Using ${w.toStringAsFixed(0)} kg.',
    );
  }

  if (med.contains('labetalol')) {
    return DoseCalcResult(
      doseText: '20 mg IV bolus, then as per response',
      explanation: 'Demo rule: labetalol IV bolus commonly used in hypertensive crisis.',
    );
  }

  return DoseCalcResult(
    doseText: '—',
    explanation:
        'No demo rule defined for "$medicineName". Enter pharmacist dose manually.',
  );
}
