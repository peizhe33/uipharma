import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/patient_supabase_service.dart';

class PatientViewPage extends StatefulWidget {
  final String patientId;
  final String? patientName;

  const PatientViewPage({
    super.key,
    required this.patientId,
    this.patientName,
  });

  static Route<void> route(String patientId, {String? patientName}) {
    // TODO: real patient access control should be added here later,
    // for example by a short patient-specific code or secure link token.
    // This entry point is intentionally separate from doctor/pharmacist checks.
    return MaterialPageRoute<void>(
      settings: RouteSettings(name: '/patient-view/$patientId'),
      builder: (_) => PatientViewPage(
        patientId: patientId,
        patientName: patientName,
      ),
    );
  }

  @override
  State<PatientViewPage> createState() => _PatientViewPageState();
}

class _PatientViewPageState extends State<PatientViewPage> {
  late Future<List<FinalPrescription>> _prescriptionsFuture;

  @override
  void initState() {
    super.initState();
    _prescriptionsFuture = PatientSupabaseService.getVerifiedPrescriptionsForPatient(
      widget.patientId,
    );
  }

  List<Map<String, dynamic>> _medicinesFor(FinalPrescription prescription) {
    final raw = prescription.medicines;

    return raw
        .map((item) {
          if (item is Map) {
            return Map<String, dynamic>.from(item);
          }
          return <String, dynamic>{};
        })
        .where((map) => map.isNotEmpty)
        .toList();
  }

  String _normalizedName(String value) {
    return value
        .trim()
        .split(RegExp(r'\s+'))
        .map((part) {
          if (part.isEmpty) return part;
          return part[0].toUpperCase() + part.substring(1).toLowerCase();
        })
        .join(' ');
  }

  String _medicineName(Map<String, dynamic> med) {
    final value = med['name'];
    if (value is String && value.trim().isNotEmpty) {
      return _normalizedName(value);
    }
    return 'Medicine';
  }

  String _normalizeDose(String rawDose, String rawUnit) {
    final dose = rawDose
        .trim()
        .replaceAll(RegExp(r'\s+'), ' ')
        .toLowerCase()
        .replaceAll(RegExp(r'\s*mg\s*$'), '')
        .replaceAll(RegExp(r'\s*g\s*$'), '')
        .replaceAll(RegExp(r'\s*ml\s*$'), '')
        .trim();

    final unit = rawUnit.trim();
    if (dose.isEmpty && unit.isEmpty) return 'Dose not listed';
    if (dose.isEmpty) return unit;
    if (unit.isEmpty) return dose;
    return '$dose $unit';
  }

  String _medicineDose(Map<String, dynamic> med) {
    final rawDose = (med['dose'] ?? med['amount'] ?? '').toString();
    final rawUnit = (med['unit'] ?? '').toString();
    return _normalizeDose(rawDose, rawUnit);
  }

  String _frequencyText(Map<String, dynamic> med) {
    final candidates = [
      med['frequency'],
      med['when_to_take'],
      med['how_to_take'],
      med['timing'],
      med['instructions'],
      med['route'],
    ];

    for (final candidate in candidates) {
      final value = candidate?.toString().trim();
      if (value != null && value.isNotEmpty) {
        return value;
      }
    }

    return 'As prescribed';
  }

  IconData _frequencyIcon(String frequency) {
    final value = frequency.toLowerCase();
    if (value.contains('morning') || value.contains('breakfast')) {
      return Icons.wb_sunny_outlined;
    }
    if (value.contains('night') || value.contains('bedtime') || value.contains('evening')) {
      return Icons.nightlight_outlined;
    }
    return Icons.schedule_outlined;
  }

  bool _isHiddenMedication(Map<String, dynamic> med) {
    final statusValues = [
      med['status'],
      med['medication_status'],
      med['medicationStatus'],
      med['safety_status'],
      med['safetyStatus'],
    ];
    final statusText = statusValues
        .where((value) => value != null)
        .map((value) => value.toString().trim().toLowerCase())
        .join(' ');

    if (RegExp(r'\b(flagged|rejected|unsafe|pending|blocked|contraindicated)\b')
        .hasMatch(statusText)) {
      return true;
    }

    final alertValues = [
      med['pending_safety_alert'],
      med['pendingSafetyAlert'],
      med['safety_alert'],
      med['safetyAlert'],
      med['safety_alerts'],
      med['safetyAlerts'],
      med['allergy_warning'],
      med['allergy_alert'],
      med['warning'],
      med['contraindication'],
    ];

    return alertValues.any((value) {
      if (value == null) return false;
      final text = value.toString().trim().toLowerCase();
      return text.isNotEmpty &&
          text != 'none' &&
          text != 'false' &&
          text != 'no' &&
          text != 'n/a';
    });
  }

  List<String> _patientDetails(Map<String, dynamic> med) {
    final details = <String>[];

    void addDetail(String label, dynamic value) {
      final text = value?.toString().trim() ?? '';
      if (text.isEmpty || details.any((detail) => detail.endsWith(': $text'))) {
        return;
      }
      details.add('$label: $text');
    }

    addDetail('How to take it', med['how_to_take'] ?? med['howToTake']);
    addDetail('Timing', med['when_to_take'] ?? med['whenToTake'] ?? med['timing']);
    addDetail(
      'Doctor\'s notes',
      med['doctor_notes'] ?? med['doctorNotes'] ?? med['doctor_instruction'] ?? med['doctorInstructions'],
    );
    addDetail(
      'Dosage notes',
      med['dosage_notes'] ?? med['dosageNotes'] ?? med['dose_notes'] ?? med['doseNotes'],
    );
    addDetail('Instructions', med['instructions']);
    addDetail(
      'Special instructions',
      med['special_instructions'] ?? med['specialInstructions'] ?? med['intake_instructions'],
    );

    return details;
  }

  @override
  Widget build(BuildContext context) {
    final patientName = widget.patientName?.trim();

    return Scaffold(
      backgroundColor: const Color(0xFFF5FBF8),
      appBar: AppBar(
        title: Text(
          patientName != null && patientName.isNotEmpty
              ? '$patientName\'s medicines'
              : 'My medicines',
        ),
        backgroundColor: Colors.teal.shade700,
        foregroundColor: Colors.white,
      ),
      body: FutureBuilder<List<FinalPrescription>>(
        future: _prescriptionsFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.error_outline_rounded, size: 52, color: Colors.red),
                    const SizedBox(height: 16),
                    const Text(
                      'We could not load your medicines right now.',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Please try again in a moment.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.grey.shade700),
                    ),
                  ],
                ),
              ),
            );
          }

          final prescriptions = snapshot.data ?? const <FinalPrescription>[];

          if (prescriptions.isEmpty) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.medical_information_outlined, size: 64, color: Colors.teal.shade400),
                    const SizedBox(height: 16),
                    Text(
                      'No medicines are ready to view yet.',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        color: Colors.grey.shade800,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Your care team will add verified medicines here once they are ready.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.grey.shade700, fontSize: 16),
                    ),
                  ],
                ),
              ),
            );
          }

          final items = <Map<String, dynamic>>[];
          final seen = <String>{};
          for (final prescription in prescriptions) {
            final meds = _medicinesFor(prescription);
            for (final med in meds) {
              if (_isHiddenMedication(med)) continue;
              final key = '${_medicineName(med).toLowerCase()}|${_medicineDose(med).toLowerCase()}';
              if (seen.add(key)) {
                items.add({
                  'prescription': prescription,
                  'medicine': med,
                });
              }
            }
          }

          if (items.isEmpty) {
            return const Center(child: Text('No verified medicines available yet.'));
          }

          return RefreshIndicator(
            onRefresh: () async {
              setState(() {
                _prescriptionsFuture = PatientSupabaseService.getVerifiedPrescriptionsForPatient(
                  widget.patientId,
                );
              });
            },
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 18, 16, 32),
              children: [
                _activeCountHeader(items.length),
                _sectionHeader('Your active medicines', Colors.teal.shade700),
                ...items.map(_medicineCard),
                const SizedBox(height: 6),
                _contactCareTeamButton(context),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _sectionHeader(String title, Color color) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8, top: 4),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        title,
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.w800,
          fontSize: 14,
        ),
      ),
    );
  }

  Widget _activeCountHeader(int count) {
    final label = count == 1 ? 'prescription' : 'prescriptions';
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Text(
        'You have $count active $label',
        style: TextStyle(
          color: Colors.grey.shade700,
          fontSize: 14,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _contactCareTeamButton(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: () {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Please contact your care team to request help or a refill.'),
          ),
        );
      },
      icon: const Icon(Icons.support_agent_outlined, size: 20),
      label: const Text('Contact Care Team'),
      style: OutlinedButton.styleFrom(
        foregroundColor: Colors.teal,
        side: BorderSide(color: Colors.teal.shade300),
        padding: const EdgeInsets.symmetric(vertical: 13),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    );
  }

  Widget _medicineCard(Map<String, dynamic> item) {
    final med = item['medicine'] as Map<String, dynamic>;

    final name = _medicineName(med);
    final dose = _medicineDose(med);
    final frequency = _frequencyText(med);
    final frequencyIcon = _frequencyIcon(frequency);
    final details = _patientDetails(med);

    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.teal.shade100),
        boxShadow: [
          BoxShadow(
            color: Colors.teal.withValues(alpha: 0.06),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          leading: Icon(
            Icons.check_circle_rounded,
            color: Colors.teal.shade600,
            size: 22,
          ),
          initiallyExpanded: false,
          title: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '$name • $dose',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: Colors.grey.shade900,
                  fontWeight: FontWeight.w800,
                  fontSize: 16,
                ),
              ),
              const SizedBox(height: 3),
              Row(
                children: [
                  Icon(frequencyIcon, color: Colors.teal.shade700, size: 16),
                  const SizedBox(width: 5),
                  Expanded(
                    child: Text(
                      frequency,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: Colors.grey.shade700,
                        fontSize: 12,
                        height: 1.2,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
          children: [
            if (details.isEmpty)
              Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Follow the directions provided by your care team.',
                  style: TextStyle(color: Colors.grey.shade700, height: 1.4),
                ),
              )
            else
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: details
                    .map(
                      (detail) => Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: Text(
                          detail,
                          style: TextStyle(
                            color: Colors.grey.shade800,
                            fontSize: 14,
                            height: 1.4,
                          ),
                        ),
                      ),
                    )
                    .toList(),
              ),
                    ],
        ),
      ),
    );
  }
}
