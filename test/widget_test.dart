import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pj/models/models.dart';
import 'package:pj/screens/prescription_alert_page.dart';

void main() {
  testWidgets('NOT_INDICATED guideline issue triggers an orange alert', (
    tester,
  ) async {
    const verificationResult = '''
AI Explanation & Citations (demo)
Assessment: Prescription appears appropriate. Standard monitoring.
Diagnosis: Acute mastoiditis

--- cefazolin ---
Assessment: Unsafe
Issues:
- NOT_INDICATED - cefazolin is NOT listed in the UMMC structured guideline for 'Acute mastoiditis'. Preferred regimen: co-amoxiclav [1].
Recommendation: Discontinuation is required due to the NOT INDICATED status [1].

--- paracetamol (supportive care) ---
Assessment: Safe
Issues: None
Recommendation: Continue
''';

    await tester.pumpWidget(
      MaterialApp(
        home: PrescriptionAlertPage(
          patient: Patient(
            id: 'p1',
            wardRoomNo: 'A1',
            name: 'Test Patient',
            age: '30',
            height: '170',
            weight: '70',
            bloodType: 'O+',
          ),
          vitals: PatientVitals(
            date: '2026-06-08',
            temperature: '37',
            bloodPressure: '120/80',
            heartRate: '80',
            oxygenSaturation: '98',
            urineOutput: 'normal',
            creatinine: '70',
            egfr: '90',
            lactate: '1',
            wbc: '8',
            condition: 'Acute mastoiditis',
          ),
          prescribedMeds: const [
            {
              'name': 'cefazolin',
              'dose': '1',
              'unit': 'g',
              'frequency': 'Every 8 hours',
              'prn': false,
            },
            {
              'name': 'paracetamol',
              'dose': '1',
              'unit': 'g',
              'frequency': 'Every 6 hours',
              'prn': true,
            },
          ],
          verificationResult: verificationResult,
        ),
      ),
    );

    expect(find.textContaining('ORANGE'), findsOneWidget);
    expect(find.textContaining('Guideline Warning'), findsOneWidget);
    expect(find.text('No issues detected.'), findsNothing);
  });
}
