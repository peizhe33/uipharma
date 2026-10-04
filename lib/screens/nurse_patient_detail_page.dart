import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/nurse_service.dart';
import '../services/patient_supabase_service.dart';
import '../widgets/responsive.dart';
import 'nurse_dispense_page.dart';
import 'patient_condition_detail_page.dart';

/// Patient details for the nurse: profile + every recorded current-condition
/// entry by date, with the "Dispense Medication" action.
class NursePatientDetailPage extends StatefulWidget {
  final NurseSession nurse;
  final Patient patient;

  const NursePatientDetailPage({
    super.key,
    required this.nurse,
    required this.patient,
  });

  @override
  State<NursePatientDetailPage> createState() => _NursePatientDetailPageState();
}

class _NursePatientDetailPageState extends State<NursePatientDetailPage> {
  late Future<List<Map<String, dynamic>>> _conditions;

  @override
  void initState() {
    super.initState();
    _conditions = PatientSupabaseService.getPatientConditions(widget.patient.id);
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.patient;

    return Scaffold(
      backgroundColor: const Color(0xFFF4F8F6),
      appBar: AppBar(
        title: const Text('Patient Details'),
        backgroundColor: Colors.teal.shade700,
        foregroundColor: Colors.white,
      ),
      bottomNavigationBar: SafeArea(
        minimum: const EdgeInsets.fromLTRB(16, 8, 16, 16),
        child: SizedBox(
          height: 58,
          child: ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF116D37),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            ),
            icon: const Icon(Icons.medication_liquid, size: 26),
            label: const Text(
              'Dispense Medication',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => NurseDispensePage(nurse: widget.nurse, patient: p),
              ),
            ),
          ),
        ),
      ),
      body: ListView(
        padding: Responsive.pagePadding(context),
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(18),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(p.name,
                    style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 18,
                  runSpacing: 6,
                  children: [
                    _chip(Icons.bed, 'Ward ${p.wardRoomNo}'),
                    _chip(Icons.person, '${p.gender.isEmpty ? '-' : p.gender}, ${p.age} y'),
                    _chip(Icons.height, '${p.height} cm'),
                    _chip(Icons.monitor_weight, '${p.weight} kg'),
                    _chip(Icons.bloodtype, 'Blood ${p.bloodType}'),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 22),
          const Text('Condition Records by Date',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 10),
          FutureBuilder<List<Map<String, dynamic>>>(
            future: _conditions,
            builder: (context, snap) {
              if (snap.connectionState != ConnectionState.done) {
                return const Padding(
                  padding: EdgeInsets.all(24),
                  child: Center(child: CircularProgressIndicator()),
                );
              }
              if (snap.hasError) {
                return Text('Could not load records: ${snap.error}');
              }
              final data = snap.data ?? [];
              if (data.isEmpty) {
                return const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('No condition records yet.'),
                );
              }
              return Column(
                children: data.map((item) => _conditionCard(item)).toList(),
              );
            },
          ),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  Widget _chip(IconData icon, String text) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 18, color: Colors.teal.shade700),
          const SizedBox(width: 4),
          Text(text, style: const TextStyle(fontSize: 15)),
        ],
      );

  Widget _conditionCard(Map<String, dynamic> item) {
    String v(String k) {
      final x = item[k];
      return (x == null || x.toString().trim().isEmpty) ? '-' : x.toString();
    }

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => PatientConditionDetailPage(
              patient: widget.patient,
              data: item,
              showDoctorBell: false,
            ),
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Date: ${v('date')}',
                        style: const TextStyle(
                            fontSize: 16, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 6),
                    Text(
                      'Temp ${v('temperature')}  |  BP ${v('blood_pressure')}  |  '
                      'HR ${v('heart_rate')}  |  SpO₂ ${v('oxygen_saturation')}',
                      style: const TextStyle(color: Colors.black87),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Condition: ${v('condition')}   Allergy: ${v('allergy')}',
                      style: const TextStyle(color: Colors.black54),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right),
            ],
          ),
        ),
      ),
    );
  }
}
