import 'package:flutter/material.dart';
import '../models/models.dart';
import '../services/patient_database.dart';
import '../widgets/responsive.dart';

/// Page to view and manage patient history
class RefreshHistoryPage extends StatefulWidget {
  final Patient patient;

  const RefreshHistoryPage({
    super.key,
    required this.patient,
  });

  @override
  State<RefreshHistoryPage> createState() => _RefreshHistoryPageState();
}

class _RefreshHistoryPageState extends State<RefreshHistoryPage> {
  late List<PatientConditionRecord> _history;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  void _loadHistory() {
    _history = PatientDatabase.instance.historyForPatient(widget.patient.id);
  }

  Future<void> _addNewRecord() async {
    final now = DateTime.now();
    final record = PatientConditionRecord(
      patientId: widget.patient.id,
      vitals: PatientVitals(
        date: '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}',
        temperature: '-',
        bloodPressure: '-',
        heartRate: '-',
        oxygenSaturation: '-',
        urineOutput: '-',
        creatinine: '-',
        egfr: '-',
        lactate: '-',
        wbc: '-',
        condition: '-',
      ),
    );

    await PatientDatabase.instance.addConditionRecord(record);
    setState(() {
      _loadHistory();
    });

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('New record added successfully.')),
      );
    }
  }
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Patient History'),
        centerTitle: true,
        backgroundColor: Colors.blue.shade700,
        elevation: 4,
      ),
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Colors.blue.shade50, Colors.white],
          ),
        ),
        child: Column(
          children: [
            // Patient Header Card
            Container(
              color: Colors.blue.shade700,
              padding: Responsive.pagePadding(context),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    widget.patient.name,
                    style: const TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Ward: ${widget.patient.wardRoomNo}   Age: ${widget.patient.age}   Weight: ${widget.patient.weight} kg',
                    style: const TextStyle(color: Colors.white70),
                  ),
                  Text(
                    'Blood Type: ${widget.patient.bloodType}',
                    style: const TextStyle(color: Colors.white70),
                  ),
                ],
              ),
            ),
            // History List
            Expanded(
              child: _history.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            Icons.history,
                            size: 64,
                            color: Colors.grey.shade400,
                          ),
                          const SizedBox(height: 16),
                          Text(
                            'No records yet',
                            style: TextStyle(
                              fontSize: 18,
                              color: Colors.grey.shade600,
                            ),
                          ),
                        ],
                      ),
                    )
                  : ListView.builder(
                      padding: Responsive.pagePadding(context),
                      itemCount: _history.length,
                      itemBuilder: (context, index) {
                        final record = _history[index];
                        final vitals = record.vitals;
                        return Card(
                          elevation: 2,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                          margin: const EdgeInsets.symmetric(vertical: 8),
                          child: ExpansionTile(
                            title: Text(
                              'Record: ${vitals.date}',
                              style: const TextStyle(
                                fontWeight: FontWeight.w600,
                                color: Colors.black87,
                              ),
                            ),
                            subtitle: Text(
                              'Condition: ${vitals.condition}',
                              style: const TextStyle(color: Colors.black54),
                            ),
                            children: [
                              Padding(
                                padding: const EdgeInsets.all(12),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    _buildVitalRow('Temperature', vitals.temperature, '°C'),
                                    _buildVitalRow('Blood Pressure', vitals.bloodPressure, 'mmHg'),
                                    _buildVitalRow('Heart Rate', vitals.heartRate, 'bpm'),
                                    _buildVitalRow('SpO₂', vitals.oxygenSaturation, '%'),
                                    _buildVitalRow('Urine Output', vitals.urineOutput, 'mL'),
                                    _buildVitalRow('Creatinine', vitals.creatinine, 'mg/dL'),
                                    _buildVitalRow('eGFR', vitals.egfr, 'mL/min'),
                                    _buildVitalRow('Lactate', vitals.lactate, 'mmol/L'),
                                    _buildVitalRow('WBC', vitals.wbc, '×10⁹/L'),
                                    const SizedBox(height: 8),
                                    Text(
                                      'Condition: ${vitals.condition}',
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w600,
                                        color: Colors.black87,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _addNewRecord,
        backgroundColor: Colors.blue.shade600,
        tooltip: 'Add New Record',
        child: const Icon(Icons.add, color: Colors.white),
      ),
    );
  }

  Widget _buildVitalRow(String label, String value, String unit) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: const TextStyle(
              color: Colors.black54,
              fontWeight: FontWeight.w500,
            ),
          ),
          Text(
            '$value $unit',
            style: const TextStyle(
              color: Colors.black87,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
