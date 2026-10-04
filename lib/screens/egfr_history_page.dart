import 'package:flutter/material.dart';
import '../models/models.dart';
import '../services/patient_supabase_service.dart';
import '../widgets/review_notification_bell.dart';
import '../widgets/responsive.dart';

class EgfrHistoryPage extends StatefulWidget {
  final Patient patient;

  const EgfrHistoryPage({
    super.key,
    required this.patient,
  });

  @override
  State<EgfrHistoryPage> createState() => _EgfrHistoryPageState();
}

class _EgfrHistoryPageState extends State<EgfrHistoryPage> {
  List<Map<String, dynamic>> egfrRecords = [];
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    loadEgfr();
  }

  Future<void> loadEgfr() async {
    final data = await PatientSupabaseService.getEgfrHistory(widget.patient.id);

    print('Patient ID: ${widget.patient.id}');
    print('eGFR DATA: $data');
    
    setState(() {
      egfrRecords = data;
      isLoading = false;
    });
  }

  Color _egfrColor(double value) {
    if (value >= 90) return Colors.green;
    if (value >= 60) return Colors.blue;
    if (value >= 30) return Colors.orange;
    return Colors.red;
  }

  String _formatDate(dynamic date) {
    if (date == null) return '-';
    return date.toString().split('T')[0];
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF4F8F6),
      appBar: AppBar(
        title: const Text('eGFR History'),
        centerTitle: true,
        backgroundColor: Colors.blue,
        foregroundColor: Colors.white,
        actions: const [DoctorReviewNotificationBell()],
      ),
      body: Padding(
        padding: Responsive.pagePadding(context),
        child: Column(
          children: [
            Card(
              elevation: 2,
              child: ListTile(
                leading: CircleAvatar(
                  backgroundColor: Colors.blue,
                  child: Text(
                    widget.patient.name.isNotEmpty
                        ? widget.patient.name[0].toUpperCase()
                        : 'P',
                    style: const TextStyle(color: Colors.white),
                  ),
                ),
                title: Text(
                  widget.patient.name,
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                subtitle: Text(
                  'ID: ${widget.patient.id}\nWard Room No.: ${widget.patient.wardRoomNo}',
                ),
              ),
            ),

            const SizedBox(height: 20),

            Expanded(
              child: isLoading
                  ? const Center(child: CircularProgressIndicator())
                  : egfrRecords.isEmpty
                      ? const Center(
                          child: Text(
                            'No eGFR records found',
                            style: TextStyle(fontSize: 16),
                          ),
                        )
                      : ListView.builder(
                          itemCount: egfrRecords.length,
                          itemBuilder: (context, index) {
                            final item = egfrRecords[index];
                            final value =
                                double.tryParse(item['value'].toString()) ?? 0;

                            return Card(
                              margin: const EdgeInsets.only(bottom: 12),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(14),
                              ),
                              child: ListTile(
                                leading: CircleAvatar(
                                  backgroundColor: _egfrColor(value),
                                  child: const Icon(
                                    Icons.science,
                                    color: Colors.white,
                                  ),
                                ),
                                title: Text(
                                  'eGFR: ${item['value']} ${item['unit'] ?? 'mL/min/1.73m²'}',
                                  style: const TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 18,
                                  ),
                                ),
                                subtitle: Text(
                                  'Date: ${_formatDate(item['recorded_at'])}',
                                ),
                                trailing: IconButton(
                                icon: const Icon(Icons.delete, color: Colors.red),
                                onPressed: () async {
                                await PatientSupabaseService.deleteEgfrResult(item['id'].toString());
                                await loadEgfr();
    },
),
                              ),
                            );
                          },
                        ),
            ),

            SizedBox(
              width: double.infinity,
              height: 52,
              child: OutlinedButton(
                onPressed: () =>
                    Navigator.of(context).popUntil((r) => r.isFirst),
                child: const Text('Home'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
