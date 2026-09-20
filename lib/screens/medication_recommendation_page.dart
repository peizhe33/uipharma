import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/models.dart';
import 'prescription_alert_page.dart';
import '../services/api.dart';
import '../widgets/responsive.dart';

class MedicationRecommendationPage extends StatefulWidget {
  final Patient patient;
  final PatientVitals vitals;

  const MedicationRecommendationPage({
    super.key,
    required this.patient,
    required this.vitals,
  });

  @override
  State<MedicationRecommendationPage> createState() =>
      _MedicationRecommendationPageState();
}

class _MedicationRecommendationPageState
    extends State<MedicationRecommendationPage> {
  final TextEditingController _medicineController = TextEditingController();
  final TextEditingController _doseController = TextEditingController();

  final List<Map<String, dynamic>> _prescribedMeds = [];
  final bool _demoMode = false;
  bool _isVerifying = false;
  String? _verificationResult;

  String _selectedDoseUnit = 'mg';
  bool _useWhenRequired = false;
  String _selectedFrequency = 'Once a day';
  String _selectedRoute = 'PO';

  @override
  void dispose() {
    _medicineController.dispose();
    _doseController.dispose();
    super.dispose();
  }

  void _goHome() {
    Navigator.of(context).popUntil((route) => route.isFirst);
  }

  Widget _info(String k, String v) => Padding(
    padding: const EdgeInsets.only(bottom: 6),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          flex: 4,
          child: Text(
            '$k:',
            style: const TextStyle(fontWeight: FontWeight.w500),
          ),
        ),
        Expanded(flex: 6, child: Text(v)),
      ],
    ),
  );

  Widget _buildDoseUnitDropdown() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      decoration: BoxDecoration(
        border: Border.all(color: Colors.grey, width: 0.5),
        borderRadius: BorderRadius.circular(4),
      ),
      child: DropdownButton<String>(
        value: _selectedDoseUnit,
        underline: const SizedBox(),
        items: const [
          'g',
          'mg',
          'mcg',
          'mL',
          'tsp',
          'tbsp',
          'IU',
          'units',
          'mg/kg',
          'mcg/kg',
        ].map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
        onChanged: (val) => setState(() => _selectedDoseUnit = val!),
      ),
    );
  }

  Widget _buildFrequencyDropdown() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      decoration: BoxDecoration(
        border: Border.all(color: Colors.grey, width: 0.5),
        borderRadius: BorderRadius.circular(4),
      ),
      child: DropdownButton<String>(
        value: _selectedFrequency,
        isExpanded: true,
        underline: const SizedBox(),
        items: [
          'Once a day',
          'Twice a day',
          'Three times a day',
          'Every 6 hours',
          'Every 8 hours',
        ].map((f) => DropdownMenuItem(value: f, child: Text(f))).toList(),
        onChanged: (val) => setState(() => _selectedFrequency = val!),
      ),
    );
  }

  Widget _buildEntryRow(String label, Widget input) {
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth < 420) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(fontWeight: FontWeight.w500)),
              const SizedBox(height: 6),
              input,
            ],
          );
        }

        return Row(
          children: [
            SizedBox(
              width: 130,
              child: Text(
                label,
                style: const TextStyle(fontWeight: FontWeight.w500),
              ),
            ),
            Expanded(child: input),
          ],
        );
      },
    );
  }

  Widget _buildRouteDropdown() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      decoration: BoxDecoration(
        border: Border.all(color: Colors.grey, width: 0.5),
        borderRadius: BorderRadius.circular(4),
      ),
      child: DropdownButton<String>(
        value: _selectedRoute,
        isExpanded: true,
        underline: const SizedBox(),
        items: [
          'PO',
          'IV',
          'IM',
          'SC',
          'Topical',
          'Inhaled',
          'PR',
          'SL',
        ].map((r) => DropdownMenuItem(value: r, child: Text(r))).toList(),
        onChanged: (val) => setState(() => _selectedRoute = val!),
      ),
    );
  }

  void _addPrescription() {
    if (_medicineController.text.trim().isEmpty ||
        _doseController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please fill medicine name and dose')),
      );
      return;
    }

    setState(() {
      _prescribedMeds.add({
        'name': _medicineController.text.trim(),
        'dose': _doseController.text.trim(),
        'unit': _selectedDoseUnit,
        'frequency': _selectedFrequency,
        'route': _selectedRoute,
        'prn': _useWhenRequired,
      });

      _medicineController.clear();
      _doseController.clear();
      _selectedDoseUnit = 'mg';
      _selectedFrequency = 'Once a day';
      _selectedRoute = 'PO';
      _useWhenRequired = false;

      _verificationResult = null;
    });
  }

  Future<void> _verifyMedicine() async {
    if (_prescribedMeds.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No prescribed drugs to verify')),
      );
      return;
    }

    setState(() {
      _isVerifying = true;
      _verificationResult = null;
    });

    // =========================
    // DEMO MODE (FAKE RESULT)
    // =========================
    if (_demoMode) {
      // Build meds text for display in the fake output
      final meds = _prescribedMeds
          .map(
            (m) =>
                "${m['name']} ${m['dose']}${m['unit']} ${m['route'] ?? 'PO'} ${m['frequency']}${m['prn'] ? ' PRN' : ''}",
          )
          .join("; ");

      final p = widget.patient;
      final v = widget.vitals;

      // Simple rule-based fake alerts (just for demo)
      final allergyText = (v.allergy ?? '').toLowerCase();
      final hasPenicillinAllergy =
          allergyText.contains('penicillin') ||
          allergyText.contains('amoxicillin');

      final mentionsAmox = meds.toLowerCase().contains('amoxicillin');
      final mentionsCoamox =
          meds.toLowerCase().contains('amoxiclav') ||
          meds.toLowerCase().contains('co-amoxiclav') ||
          meds.toLowerCase().contains('augmentin');

      final alerts = <String>[
        if (hasPenicillinAllergy && (mentionsAmox || mentionsCoamox))
          "Allergy alert: Reported penicillin/amoxicillin allergy; prescribed drug may be contraindicated.",
        if ((v.egfr ?? '').toString().trim().isNotEmpty &&
            (v.egfr ?? '').toString().toLowerCase().contains('low'))
          "Renal alert: eGFR flagged as low; consider dose/interval adjustment for renally cleared drugs.",
        if (_prescribedMeds.length >= 4)
          "Polypharmacy alert: Multiple drugs prescribed; review for interactions and duplication.",
      ];

      final recs = <String>[
        if (alerts.isEmpty)
          "No high-risk issues detected in demo rules. Proceed with standard monitoring.",
        if (alerts.isNotEmpty)
          "Review the highlighted alert(s) and confirm indication, allergy history, renal function, and monitoring plan.",
        "Confirm final decision with pharmacist/doctor before administration (demo).",
      ];

      final fakeResult =
          """
DEMO RESULT (NO AI CONNECTED)

1) Overall assessment: ${alerts.isEmpty ? "Safe (demo check)" : "Needs review (demo check)"}

2) Alerts:
${alerts.isEmpty ? "- None detected by demo rules." : alerts.map((e) => "- $e").join("\n")}

3) Recommendations:
${recs.map((e) => "- $e").join("\n")}

Patient: ${p.name} (${p.age}y, ${p.gender}), Ward/Room: ${p.wardRoomNo}
Condition: ${v.condition}
Prescribed: $meds
""";

      if (!mounted) return;

      setState(() => _verificationResult = fakeResult);

      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => PrescriptionAlertPage(
            patient: widget.patient,
            vitals: widget.vitals,
            prescribedMeds: List<Map<String, dynamic>>.from(_prescribedMeds),
            verificationResult: fakeResult,
            retrievedDocs: const [], // NEW
            demoMode: true,
          ),
        ),
      );

      // stop here (skip the real AI call)
      if (mounted) setState(() => _isVerifying = false);
      return;
    }

    try {
      final api = SmartPharmaApi();

      final p = widget.patient;
      final v = widget.vitals;

      // Short question (no embedded patient data)
      final question =
          "Verify the safety and appropriateness of the prescribed medications "
          "for this patient based on UMMC Antimicrobial Guidelines.";

      // Build structured patient data
      final patientData = {
        'name': p.name,
        'id': p.id,
        'ward_room': p.wardRoomNo,
        'gender': p.gender,
        'height': p.height,
        'weight': p.weight,
        'blood_type': p.bloodType,
      };

      final vitalsData = {
        'date': v.date,
        'temperature': v.temperature,
        'blood_pressure': v.bloodPressure,
        'heart_rate': v.heartRate,
        'spo2': v.oxygenSaturation,
        'urine_output': v.urineOutput,
        'allergy_details': v.allergy,
        'renal_function': v.renalFunction,
      };

      final labsData = {
        'creatinine': v.creatinine,
        'egfr': v.egfr,
        'lactate': v.lactate,
        'wbc': v.wbc,
      };

      // Call backend with structured data
      final resp = await api.verifyPrescription(
        question,
        age: int.tryParse(p.age),
        k: 5,
        patient: patientData,
        vitals: vitalsData,
        labs: labsData,
        diagnosis: v.condition,
        prescribedMedicines: _prescribedMeds,
      );

      if (!mounted) return;

      setState(() => _verificationResult = resp.answer);

      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => PrescriptionAlertPage(
            patient: widget.patient,
            vitals: widget.vitals,
            prescribedMeds: List<Map<String, dynamic>>.from(_prescribedMeds),
            verificationResult: resp.answer,
            report: resp.report,
            retrievedDocs: const [],
            demoMode: false,
          ),
        ),
      );
    } catch (e) {
      debugPrint('VERIFY ERROR: $e');
      setState(() => _verificationResult = 'Verification failed: $e');
    } finally {
      if (mounted) setState(() => _isVerifying = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.patient;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Medication Recommendation Page'),
        centerTitle: true,
        actions: [
          TextButton.icon(
            onPressed: _goHome,
            icon: const Icon(Icons.home, color: Colors.white),
            label: const Text('Home', style: TextStyle(color: Colors.white)),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: Padding(
        padding: Responsive.pagePadding(context),
        child: ListView(
          children: [
            const Text(
              'Patient Information:',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            _info('Name', p.name),
            _info('Ward Room No.', p.wardRoomNo),
            _info('Gender', p.gender),
            _info('Age', p.age),
            _info('Height', '${p.height} cm'),
            _info('Weight', '${p.weight} kg'),
            _info('Blood Type', p.bloodType),
            const SizedBox(height: 16),
            const Divider(),
            const SizedBox(height: 12),
            const Text(
              'Medicine Required (typed by doctor):',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 16),

            ResponsiveTwoColumn(
              breakpoint: 760,
              gap: 16,
              leftFlex: 5,
              rightFlex: 4,
              left: Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.black, width: 1.5),
                ),
                child: Column(
                  children: [
                    _buildEntryRow(
                      'Drug Name :',
                      TextField(
                        controller: _medicineController,
                        decoration: const InputDecoration(
                          isDense: true,
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    _buildEntryRow(
                      'Dose :',
                      Row(
                        children: [
                          SizedBox(
                            width: 80,
                            child: TextFormField(
                              controller: _doseController,
                              keyboardType:
                                  const TextInputType.numberWithOptions(
                                    decimal: true,
                                  ),
                              inputFormatters: [
                                FilteringTextInputFormatter.allow(
                                  RegExp(r'^\d*\.?\d{0,2}'),
                                ),
                              ],
                              decoration: const InputDecoration(
                                isDense: true,
                                border: OutlineInputBorder(),
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          _buildDoseUnitDropdown(),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                    _buildEntryRow('Frequency :', _buildFrequencyDropdown()),
                    const SizedBox(height: 12),
                    _buildEntryRow('Route :', _buildRouteDropdown()),
                    const SizedBox(height: 12),
                    _buildEntryRow(
                      'Use only when required :',
                      Checkbox(
                        value: _useWhenRequired,
                        onChanged: (val) =>
                            setState(() => _useWhenRequired = val ?? false),
                      ),
                    ),
                    const SizedBox(height: 20),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        OutlinedButton(
                          onPressed: _addPrescription,
                          child: const Text('Prescribe'),
                        ),
                        const SizedBox(width: 10),
                        TextButton(
                          onPressed: () {
                            _medicineController.clear();
                            _doseController.clear();
                            setState(() {
                              _selectedDoseUnit = 'mg';
                              _selectedFrequency = 'Once a day';
                              _selectedRoute = 'PO';
                              _useWhenRequired = false;
                            });
                          },
                          child: const Text(
                            'Cancel',
                            style: TextStyle(color: Colors.grey),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              right: Container(
                height: 360,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.black, width: 1.5),
                ),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text(
                          'Prescribed drug(s)',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                          ),
                        ),
                        IconButton(
                          onPressed: () {
                            setState(() {
                              _prescribedMeds.clear();
                              _verificationResult = null;
                            });
                          },
                          icon: const Icon(Icons.delete_outline, size: 20),
                        ),
                      ],
                    ),
                    const Divider(color: Colors.black, thickness: 1),
                    Expanded(
                      child: ListView(
                        children: _prescribedMeds.asMap().entries.map((entry) {
                          int index = entry.key;
                          var med = entry.value;

                          return Padding(
                            padding: const EdgeInsets.symmetric(vertical: 4),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Expanded(
                                  child: Text(
                                    "${med['name']} ${med['dose']}${med['unit']} ${med['route'] ?? 'PO'} - ${med['frequency']}${med['prn'] ? ' (PRN)' : ''}",
                                    style: const TextStyle(fontSize: 14),
                                  ),
                                ),
                                IconButton(
                                  icon: const Icon(
                                    Icons.delete,
                                    size: 18,
                                    color: Colors.red,
                                  ),
                                  onPressed: () {
                                    setState(() {
                                      _prescribedMeds.removeAt(index);
                                    });
                                  },
                                ),
                              ],
                            ),
                          );
                        }).toList(),
                      ),
                    ),
                    const SizedBox(height: 8),

                    ElevatedButton(
                      onPressed: _isVerifying ? null : _verifyMedicine,
                      child: _isVerifying
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Text('Verify'),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}