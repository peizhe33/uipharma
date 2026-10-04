import 'package:flutter/material.dart';
import '../models/models.dart';
import 'medication_recommendation_page.dart';
import '../widgets/responsive.dart';

class SepsisAssessmentPage extends StatefulWidget {
  final Patient patient;
  final PatientVitals vitals;

  const SepsisAssessmentPage({
    super.key,
    required this.patient,
    required this.vitals,
  });

  @override
  State<SepsisAssessmentPage> createState() => _SepsisAssessmentPageState();
}

class _SepsisAssessmentPageState extends State<SepsisAssessmentPage> {
  String _source = 'Unknown Source';

  bool _fever = false;
  bool _hypotension = false;
  bool _tachycardia = false;
  bool _reducedUrine = false;
  bool _elevatedLactate = false;
  bool _alteredMental = false;

  bool _aki = false;
  bool _poorPerfusion = false;
  bool _respiratoryFailure = false;

  bool get isSiti => widget.patient.name.toLowerCase().contains('siti nur aisyah');

  @override
  void initState() {
    super.initState();

    if (isSiti) {
      _source = 'Urinary Tract Infection';
      _fever = true;
      _hypotension = true;
      _tachycardia = true;
      _reducedUrine = true;
      _elevatedLactate = true;
      _alteredMental = true;
      _aki = true;
      _poorPerfusion = true;
      _respiratoryFailure = false;
    }
  }

  String get _clinicalImpression {
    final warningSigns = [
      if (_fever) 'fever',
      if (_hypotension) 'hypotension',
      if (_tachycardia) 'tachycardia',
      if (_reducedUrine) 'reduced urine output',
      if (_elevatedLactate) 'elevated lactate',
      if (_alteredMental) 'altered mental status',
    ];

    final organIssues = [
      if (_aki) 'acute kidney injury',
      if (_poorPerfusion) 'poor tissue perfusion',
      if (_respiratoryFailure) 'respiratory dysfunction',
    ];

    if (warningSigns.length >= 4 || organIssues.length >= 2) {
      return 'High-risk sepsis likely secondary to $_source. Urgent empiric antibiotics and close monitoring recommended.';
    }

    if (warningSigns.length >= 2) {
      return 'Possible sepsis. Further clinical review and monitoring recommended.';
    }

    return 'Sepsis not strongly suggested from the selected indicators.';
  }

  PatientVitals get updatedVitals {
    final sepsisText = '''
${widget.vitals.condition}

Sepsis Clinical Assessment:
Suspected Source of Infection: $_source

Sepsis Warning Signs:
Fever: ${_fever ? 'Yes' : 'No'}
Hypotension: ${_hypotension ? 'Yes' : 'No'}
Tachycardia: ${_tachycardia ? 'Yes' : 'No'}
Reduced Urine Output: ${_reducedUrine ? 'Yes' : 'No'}
Elevated Lactate: ${_elevatedLactate ? 'Yes' : 'No'}
Altered Mental Status: ${_alteredMental ? 'Yes' : 'No'}

Organ Dysfunction:
Acute Kidney Injury: ${_aki ? 'Yes' : 'No'}
Poor Tissue Perfusion: ${_poorPerfusion ? 'Yes' : 'No'}
Respiratory Dysfunction: ${_respiratoryFailure ? 'Yes' : 'No'}

Clinical Impression:
$_clinicalImpression
''';

    return PatientVitals(
      date: widget.vitals.date,
      temperature: widget.vitals.temperature,
      bloodPressure: widget.vitals.bloodPressure,
      heartRate: widget.vitals.heartRate,
      oxygenSaturation: widget.vitals.oxygenSaturation,
      urineOutput: widget.vitals.urineOutput,
      creatinine: widget.vitals.creatinine,
      egfr: widget.vitals.egfr,
      allergy: widget.vitals.allergy,
      renalFunction: widget.vitals.renalFunction,
      lactate: widget.vitals.lactate,
      wbc: widget.vitals.wbc,
      condition: sepsisText,
      pregnant: widget.vitals.pregnant,
      dialysis: widget.vitals.dialysis,
    );
  }

  void _continue() {
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (_) => MedicationRecommendationPage(
          patient: widget.patient,
          vitals: updatedVitals,
        ),
      ),
    );
  }

  Widget _checkBox(String title, bool value, Function(bool?) onChanged) {
    return CheckboxListTile(
      title: Text(title),
      value: value,
      onChanged: onChanged,
      controlAffinity: ListTileControlAffinity.leading,
    );
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.patient;
    final v = widget.vitals;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Sepsis Clinical Assessment'),
        centerTitle: true,
      ),
      body: Padding(
        padding: Responsive.pagePadding(context),
        child: ListView(
          children: [
            Text(
              p.name,
              style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
            ),
            Text('Ward Room No.: ${p.wardRoomNo}'),
            Text('Age: ${p.age}'),
            Text('Gender: ${p.gender}'),

            const SizedBox(height: 24),

            const Text(
              'Current Clinical Data',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            Text('Temperature: ${v.temperature} °C'),
            Text('Blood Pressure: ${v.bloodPressure}'),
            Text('Heart Rate: ${v.heartRate} bpm'),
            Text('Urine Output: ${v.urineOutput} mL/hr'),
            Text('Lactate: ${v.lactate} mmol/L'),
            Text('WBC: ${v.wbc} ×10⁹/L'),
            Text('Creatinine: ${v.creatinine} mg/dL'),
            Text('Renal Function: ${v.renalFunction}'),

            const SizedBox(height: 24),

            const Text(
              'Suspected Source of Infection',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            DropdownButtonFormField<String>(
              initialValue: _source,
              decoration: const InputDecoration(
                border: OutlineInputBorder(),
              ),
              items: const [
                DropdownMenuItem(value: 'Urinary Tract Infection', child: Text('Urinary Tract Infection')),
                DropdownMenuItem(value: 'Respiratory Infection', child: Text('Respiratory Infection')),
                DropdownMenuItem(value: 'Skin / Soft Tissue Infection', child: Text('Skin / Soft Tissue Infection')),
                DropdownMenuItem(value: 'Abdominal Infection', child: Text('Abdominal Infection')),
                DropdownMenuItem(value: 'Unknown Source', child: Text('Unknown Source')),
              ],
              onChanged: (value) {
                setState(() {
                  _source = value ?? 'Unknown Source';
                });
              },
            ),

            const SizedBox(height: 24),

            const Text(
              'Sepsis Warning Signs',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            _checkBox('Fever (>38°C)', _fever, (v) => setState(() => _fever = v ?? false)),
            _checkBox('Hypotension', _hypotension, (v) => setState(() => _hypotension = v ?? false)),
            _checkBox('Tachycardia', _tachycardia, (v) => setState(() => _tachycardia = v ?? false)),
            _checkBox('Reduced Urine Output', _reducedUrine, (v) => setState(() => _reducedUrine = v ?? false)),
            _checkBox('Elevated Lactate', _elevatedLactate, (v) => setState(() => _elevatedLactate = v ?? false)),
            _checkBox('Altered Mental Status / Lethargy', _alteredMental, (v) => setState(() => _alteredMental = v ?? false)),

            const SizedBox(height: 24),

            const Text(
              'Organ Dysfunction',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            _checkBox('Acute Kidney Injury', _aki, (v) => setState(() => _aki = v ?? false)),
            _checkBox('Poor Tissue Perfusion', _poorPerfusion, (v) => setState(() => _poorPerfusion = v ?? false)),
            _checkBox('Respiratory Dysfunction', _respiratoryFailure, (v) => setState(() => _respiratoryFailure = v ?? false)),

            const SizedBox(height: 24),

            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Colors.orange.shade50,
                border: Border.all(color: Colors.orange),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                _clinicalImpression,
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
              ),
            ),

            const SizedBox(height: 30),

            ElevatedButton(
              onPressed: _continue,
              child: const Padding(
                padding: EdgeInsets.symmetric(vertical: 14),
                child: Text('Continue', style: TextStyle(fontSize: 18)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
