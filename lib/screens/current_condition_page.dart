import 'package:flutter/material.dart';
import '../models/models.dart';
import '../services/patient_database.dart';
import 'medication_recommendation_page.dart';
import '../services/patient_supabase_service.dart';
import '../widgets/review_notification_bell.dart';
import '../widgets/responsive.dart';

class CurrentConditionPage extends StatefulWidget {
  final Patient patient;
  const CurrentConditionPage({super.key, required this.patient});

  @override
  State<CurrentConditionPage> createState() => _CurrentConditionPageState();
}

class _CurrentConditionPageState extends State<CurrentConditionPage> {
  final _formKey = GlobalKey<FormState>();

  final _date = TextEditingController();
  final _temp = TextEditingController();
  final _bp = TextEditingController();
  final _hr = TextEditingController();
  final _spo2 = TextEditingController();
  final _urine = TextEditingController();
  final _cr = TextEditingController();
  final _egfr = TextEditingController();
  String? _latestEgfr;
  String? _latestEgfrDate;
  final _allergy = TextEditingController();
  final _renalFn = TextEditingController();

  final _lact = TextEditingController();
  final _wbc = TextEditingController();
  final _cond = TextEditingController();

  bool _isPregnant = false;
  bool _onDialysis = false;

  Future<void> _fetchLatestEgfrFromSupabase() async {
    final result = await PatientSupabaseService.getLatestEgfr(
      widget.patient.id.toString(),
    );

    if (!mounted) return;

    setState(() {
      _latestEgfr =
          result?['result']?.toString() ?? result?['value']?.toString();

      _latestEgfrDate = result?['recorded_at']?.toString();
    });
  }

  Future<void> _loadLatestCondition() async {
    final data =
        await PatientSupabaseService.getLatestPatientCondition(
      widget.patient.id,
    );

    if (!mounted || data == null) return;

    setState(() {
      _date.text = data['date']?.toString() ?? '';
      _temp.text = data['temperature']?.toString() ?? '';
      _bp.text = data['blood_pressure']?.toString() ?? '';
      _hr.text = data['heart_rate']?.toString() ?? '';
      _spo2.text = data['oxygen_saturation']?.toString() ?? '';
      _urine.text = data['urine_output']?.toString() ?? '';
      _cr.text = data['creatinine']?.toString() ?? '';
      _egfr.text = data['egfr']?.toString() ?? '';

      _allergy.text = data['allergy']?.toString() ?? '';
      _renalFn.text = data['renal_function']?.toString() ?? '';

      _lact.text = data['lactate']?.toString() ?? '';
      _wbc.text = data['wbc']?.toString() ?? '';
      _cond.text = data['condition']?.toString() ?? '';

      _isPregnant = data['pregnant'] ?? false;
      _onDialysis = data['dialysis'] ?? false;
    });
  }

  @override
  void initState() {
    super.initState();

    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await _loadLatestCondition();

      if (_cond.text.isEmpty) {
        _autofillForThisPatient();
      }

      await _fetchLatestEgfrFromSupabase();
    });
  }

  void _autofillForThisPatient() {
  final history =
      PatientDatabase.instance.historyForPatient(widget.patient.id);

  if (history.isNotEmpty) {
    _applyVitals(history.last.vitals);
    return;
  }

  if (widget.patient.id == 'PNEU001' ||
      widget.patient.name == 'Ahmad Firdaus Bin Rahman') {
    final v = PatientVitals(
      date: _today(),
      temperature: '39.1',
      bloodPressure: '88/56',
      heartRate: '118',
      oxygenSaturation: '89',
      urineOutput: '28',
      creatinine: '1.8',
      egfr: '42',
      allergy: 'Penicillin',
      renalFunction: 'Mildly impaired',
      lactate: '3.1',
      wbc: '18',
      condition:
          'Community-acquired pneumonia...',
      pregnant: false,
      dialysis: false,
    );

    _applyVitals(v);
    return;
  }

  if (widget.patient.name.toLowerCase().contains('siti nur aisyah')) {
    final v = PatientVitals(
      date: _today(),
      temperature: '39.2',
      bloodPressure: '92/58',
      heartRate: '122',
      oxygenSaturation: '93',
      urineOutput: '25',
      creatinine: '2.0',
      egfr: '35',
      allergy: 'None',
      renalFunction: 'Impaired / AKI risk',
      lactate: '3.6',
      wbc: '18',
      condition:
          'Suspected sepsis...',
      pregnant: false,
      dialysis: false,
    );

    _applyVitals(v);
    return;
  }

  if (widget.patient.name.toLowerCase().contains('daniel hakim')) {
    final v = PatientVitals(
      date: _today(),
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
      condition:
          'Suspected pulmonary embolism...',
      pregnant: false,
      dialysis: false,
    );

    _applyVitals(v);
    return;
  }


  }

  void _applyVitals(PatientVitals v) {
    _date.text = v.date;
    _temp.text = v.temperature;
    _bp.text = v.bloodPressure;
    _hr.text = v.heartRate;
    _spo2.text = v.oxygenSaturation;
    _urine.text = v.urineOutput;
    _cr.text = v.creatinine;
    _egfr.text = v.egfr;

    _allergy.text = v.allergy;
    _renalFn.text = v.renalFunction;

    _lact.text = v.lactate;
    _wbc.text = v.wbc;
    _cond.text = v.condition;
    _isPregnant = v.pregnant;
    _onDialysis = v.dialysis;
  }

  String _today() => DateTime.now().toIso8601String().split('T').first;

  @override
  void dispose() {
    _date.dispose();
    _temp.dispose();
    _bp.dispose();
    _hr.dispose();
    _spo2.dispose();
    _urine.dispose();
    _cr.dispose();
    _egfr.dispose();
    _allergy.dispose();
    _renalFn.dispose();
    _lact.dispose();
    _wbc.dispose();
    _cond.dispose();
    super.dispose();
  }

  void _home() => Navigator.of(context).popUntil((r) => r.isFirst);

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;

    final v = PatientVitals(
      date: _date.text.trim(),
      temperature: _temp.text.trim(),
      bloodPressure: _bp.text.trim(),
      heartRate: _hr.text.trim(),
      oxygenSaturation: _spo2.text.trim(),
      urineOutput: _urine.text.trim(),
      creatinine: _cr.text.trim(),
      egfr: _egfr.text.trim(),
      allergy: _allergy.text.trim(),
      renalFunction: _renalFn.text.trim(),
      lactate: _lact.text.trim(),
      wbc: _wbc.text.trim(),
      condition: _cond.text.trim(),
      pregnant: _isPregnant,
      dialysis: _onDialysis,
    );

    PatientDatabase.instance.addConditionRecord(
      PatientConditionRecord(patientId: widget.patient.id, vitals: v),
    );

    await PatientSupabaseService.addEgfrResult(
      patientId: widget.patient.id,
      value: _egfr.text.trim(),
      recordedAt: _date.text.trim(),
    );

    await PatientSupabaseService.addCurrentCondition(
      patient: widget.patient,
      vitals: v,
    );

    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => MedicationRecommendationPage(
          patient: widget.patient,
          vitals: v,
        ),
      ),
    );
  }

  Widget _vField(TextEditingController c, String label, {TextInputType? kb}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: TextFormField(
        controller: c,
        keyboardType: kb,
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
        ),
        validator: (v) =>
            (v == null || v.trim().isEmpty) ? 'Please enter $label' : null,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.patient;
    final compact = Responsive.isCompact(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text("Patient's Current Condition"),
        centerTitle: true,
        actions: const [DoctorReviewNotificationBell()],
      ),
      body: SafeArea(
        child: Padding(
          padding: Responsive.pagePadding(context),
          child: Form(
            key: _formKey,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Center(
                    child: Text(
                      "Patient's Current Condition",
                      style:
                          TextStyle(fontSize: 26, fontWeight: FontWeight.bold),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Card(
                    elevation: 2,
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: ResponsiveTwoColumn(
                        breakpoint: 560,
                        gap: 12,
                        left: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Name: ${p.name}'),
                            Text('Ward Room No.: ${p.wardRoomNo}'),
                            Text('Gender: ${p.gender}'),
                            Text('Age: ${p.age}'),
                            Text('Height: ${p.height} cm'),
                            Text('Weight: ${p.weight} kg'),
                            Text('Blood Type: ${p.bloodType}'),
                          ],
                        ),
                        right: Align(
                          alignment: compact
                              ? Alignment.centerLeft
                              : Alignment.centerRight,
                          child: Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: Colors.blue.shade50,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: Colors.blue),
                            ),
                            child: Column(
                              children: [
                                const Text(
                                  "Latest eGFR",
                                  style: TextStyle(fontWeight: FontWeight.bold),
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  _latestEgfr ?? "--",
                                  style: const TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  _latestEgfrDate != null
                                      ? "Date: ${_latestEgfrDate!.split('T')[0]}"
                                      : "Date: --",
                                  style: const TextStyle(fontSize: 12),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  _vField(_date, 'Date (e.g. 2025-11-10)'),
                  _vField(_temp, 'Temperature (°C)', kb: TextInputType.number),
                  _vField(_bp, 'Blood Pressure (e.g. 120/80 mmHg)'),
                  _vField(_hr, 'Heart Rate (bpm)', kb: TextInputType.number),
                  _vField(_spo2, 'Oxygen Saturation (SpO₂ %)',
                      kb: TextInputType.number),
                  _vField(_urine, 'Urine Output (mL/hr)',
                      kb: TextInputType.number),
                  _vField(_cr, 'Creatinine (mg/dL)',
                      kb: TextInputType.number),
                  _vField(_egfr, 'eGFR (mL/min/1.73m²)',
                      kb: TextInputType.number),
                  _vField(_allergy, 'Allergy details'),
                  _vField(_renalFn, 'Renal function'),
                  CheckboxListTile(
                    value: _isPregnant,
                    onChanged: widget.patient.gender == 'Male'
                        ? null
                        : (v) => setState(() => _isPregnant = v ?? false),
                    title: const Text('Pregnant'),
                    controlAffinity: ListTileControlAffinity.leading,
                  ),
                  CheckboxListTile(
                    value: _onDialysis,
                    onChanged: (v) {
                      setState(() => _onDialysis = v ?? false);
                    },
                    title: const Text('On Dialysis'),
                    controlAffinity: ListTileControlAffinity.leading,
                  ),
                  _vField(_lact, 'Lactate (mmol/L)',
                      kb: TextInputType.number),
                  _vField(_wbc, 'WBC (10⁹/L)', kb: TextInputType.number),
                  TextFormField(
                    controller: _cond,
                    maxLines: 3,
                    decoration: const InputDecoration(
                      labelText: 'Diagnosis',
                      border: OutlineInputBorder(),
                    ),
                    validator: (v) => (v == null || v.trim().isEmpty)
                        ? 'Please describe the patient condition'
                        : null,
                  ),
                  const SizedBox(height: 24),
                  ResponsiveTwoColumn(
                    breakpoint: 520,
                    gap: 12,
                    left: ElevatedButton(
                      onPressed: _submit,
                      child: const Padding(
                        padding: EdgeInsets.symmetric(vertical: 14),
                        child: Text('Submit', style: TextStyle(fontSize: 18)),
                      ),
                    ),
                    right: OutlinedButton(
                      onPressed: _home,
                      child: const Padding(
                        padding: EdgeInsets.symmetric(vertical: 14),
                        child: Text('Home', style: TextStyle(fontSize: 18)),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// -----------------------------
// DEMO SCENARIOS (NO diabetes/hypertension)
// -----------------------------
class _Scenario {
  final String condition;
  final String temperature;
  final String bloodPressure;
  final String heartRate;
  final String oxygenSaturation;
  final String urineOutput;
  final String creatinine;
  final String egfr;
  final String allergy;
  final String renalFunction;
  final String lactate;
  final String wbc;

  const _Scenario({
    required this.condition,
    required this.temperature,
    required this.bloodPressure,
    required this.heartRate,
    required this.oxygenSaturation,
    required this.urineOutput,
    required this.creatinine,
    required this.egfr,
    required this.allergy,
    required this.renalFunction,
    required this.lactate,
    required this.wbc,
  });
}

class _ScenarioLibrary {
  static const List<_Scenario> _scenarios = [
    _Scenario(
      condition: 'Community-acquired pneumonia (suspected bacterial)',
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
    ),
    _Scenario(
      condition: 'Urinary tract infection / pyelonephritis',
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
    ),
    _Scenario(
      condition: 'Cellulitis / skin and soft tissue infection',
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
    ),
    _Scenario(
      condition: 'Suspected sepsis (bacterial source)',
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
    ),
    _Scenario(
      condition: 'Post-operative immobilization with high clot risk',
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
    ),
    _Scenario(
      condition: 'Suspected deep vein thrombosis (leg swelling/pain)',
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
    ),
    _Scenario(
      condition: 'Suspected pulmonary embolism (acute shortness of breath)',
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
    ),
    _Scenario(
      condition: 'Acute coronary syndrome (chest pain, high risk)',
      temperature: '37.1',
      bloodPressure: '148/92',
      heartRate: '96',
      oxygenSaturation: '98',
      urineOutput: '55',
      creatinine: '1.2',
      egfr: '70',
      allergy: 'None',
      renalFunction: 'Normal',
      lactate: '1.5',
      wbc: '10',
    ),
  ];

  static _Scenario pickScenario(String patientId) {
    final seed = patientId.codeUnits.fold<int>(0, (a, b) => a + b);
    return _scenarios[seed % _scenarios.length];
  }
}
