import 'package:flutter/material.dart';
import '../models/models.dart';
import '../widgets/review_notification_bell.dart';
import '../widgets/responsive.dart';

class PatientConditionDetailPage extends StatelessWidget {
  final Patient patient;
  final Map<String, dynamic> data;

  const PatientConditionDetailPage({
    super.key,
    required this.patient,
    required this.data,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Condition Detail"),
        actions: const [DoctorReviewNotificationBell()],
      ),

      body: Padding(
        padding: Responsive.pagePadding(context),
        child: ListView(
          children: [

            Text(
              "Patient: ${patient.name}",
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),

            const SizedBox(height: 16),

            _sectionTitle("Basic Info"),
            _item("Date", data['date']),
            _item("Condition", data['condition']),
            _item("Ward", data['ward_room_no']),
            _item("Age", data['age']),
            _item("Gender", data['gender']),

            const SizedBox(height: 12),

            _sectionTitle("Vital Signs"),
            _item("Temperature", data['temperature']),
            _item("Blood Pressure", data['blood_pressure']),
            _item("Heart Rate", data['heart_rate']),
            _item("SpO₂", data['oxygen_saturation']),
            _item("Urine Output", data['urine_output']),

            const SizedBox(height: 12),

            _sectionTitle("Lab Results"),
            _item("Creatinine", data['creatinine']),
            _item("eGFR", data['egfr']),
            _item("WBC", data['wbc']),
            _item("Lactate", data['lactate']),

            const SizedBox(height: 12),

            _sectionTitle("Clinical Notes"),
            _item("Allergy", data['allergy']),
            _item("Renal Function", data['renal_function']),
            _item("Pregnant", data['pregnant']?.toString()),
            _item("Dialysis", data['dialysis']?.toString()),
          ],
        ),
      ),
    );
  }
  Widget _sectionTitle(String title) {
  return Padding(
    padding: const EdgeInsets.only(top: 10, bottom: 6),
    child: Text(
      title,
      style: const TextStyle(
        fontSize: 16,
        fontWeight: FontWeight.bold,
        color: Colors.blue,
      ),
    ),
  );
}

Widget _item(String label, dynamic value) {
  return Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          "$label: ",
          style: const TextStyle(
            fontWeight: FontWeight.w600,
          ),
        ),
        Expanded(
          child: Text(
            value?.toString() ?? "-",
          ),
        ),
      ],
    ),
  );
}
}
