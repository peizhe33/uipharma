import 'package:flutter/material.dart';
import '../models/models.dart';
import '../services/patient_supabase_service.dart';
import 'egfr_history_page.dart';
import '../widgets/review_notification_bell.dart';
import '../widgets/responsive.dart';

class DoctorPatientHistoryPage extends StatefulWidget {
  final Patient patient;

  const DoctorPatientHistoryPage({super.key, required this.patient});

  @override
  State<DoctorPatientHistoryPage> createState() =>
      _DoctorPatientHistoryPageState();
}

class _DoctorPatientHistoryPageState
    extends State<DoctorPatientHistoryPage> {
  List<Map<String, dynamic>> records = [];
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    loadHistory();
  }

  Future<void> loadHistory() async {
  final vitals = await PatientSupabaseService.getPatientHistory(
    widget.patient.id,
  );

  setState(() {
    records = vitals;
    isLoading = false;
  });
}

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Patient's History"),
        centerTitle: true,
        actions: const [DoctorReviewNotificationBell()],
      ),
      body: Padding(
        padding: Responsive.pagePadding(context),
        child: Column(
          children: [
            Text(
              "History for ${widget.patient.name}",
              style: const TextStyle(
                  fontSize: 22, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),

            Expanded(
              child: isLoading
                  ? const Center(child: CircularProgressIndicator())
                  : records.isEmpty
                      ? const Center(child: Text('No history records yet'))
                      : ListView.builder(
                          itemCount: records.length,
                          itemBuilder: (_, i) {
                            final v = records[i];
                            return Card(
                                margin: const EdgeInsets.symmetric(vertical: 6.0),
                                child: Padding(
                                  padding: const EdgeInsets.all(12.0),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        'Date: ${v['date']}',
                                        style: const TextStyle(
                                            fontSize: 18, fontWeight: FontWeight.w600),
                                      ),
                                      const SizedBox(height: 6),
                                      Text('Temperature: ${v['temperature']} °C'),
                                      Text('Blood Pressure: ${v['blood_pressure']}'),
                                      Text('Heart Rate: ${v['heart_rate']} bpm'),
                                      Text('SpO₂: ${v['oxygen_saturation']} %'),
                                      Text(
                                        'Condition: ${v['condition']}',
                                        style: const TextStyle(fontStyle: FontStyle.italic),
                                      ),
                                    ],
                                  ),
                                ),
                              );
                            }
                        ),
            ),
            const SizedBox(height: 20),

            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => EgfrHistoryPage(
                        patient: widget.patient,
                      ),
                    ),
                  );
                },
                child: const Text("View eGFR History"),
              ),
            ),

            const SizedBox(height: 16),

            SizedBox(
              width: double.infinity,
              child: OutlinedButton(
                onPressed: () =>
                    Navigator.of(context).popUntil((r) => r.isFirst),
                child: const Padding(
                  padding: EdgeInsets.symmetric(vertical: 14.0),
                  child: Text('Home', style: TextStyle(fontSize: 18)),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
