// dose_verification_page.dart
import 'package:flutter/material.dart';
import '../models/models.dart';
import '../widgets/review_notification_bell.dart';
import '../widgets/responsive.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:uuid/uuid.dart';
import 'patient_condition_detail_page.dart';

/// Detail page opened from "To be verified"
class DoseVerificationPage extends StatefulWidget {
  final String pharmacistId;

  final FinalPrescription queueItem;
  final Patient patient;
  final PatientVitals? vitals;

  const DoseVerificationPage({
    super.key,
    required this.queueItem,
    required this.patient,
    required this.pharmacistId,
    this.vitals,
  });

  @override
  State<DoseVerificationPage> createState() => _DoseVerificationPageState();
}

class _DoseVerificationPageState extends State<DoseVerificationPage> {
  final TextEditingController _rejectionReason = TextEditingController();
  final TextEditingController _suggestedMedicine = TextEditingController();
  final TextEditingController _suggestedDose = TextEditingController();
  final TextEditingController _suggestedFrequency = TextEditingController();
  final TextEditingController _suggestedRoute = TextEditingController();
  bool _suggestedPrn = false;
  final Uuid uuid = const Uuid();
  final Map<int, TextEditingController> _doseControllers = {};
  final Map<int, TextEditingController> _freqControllers = {};
  final Map<int, String> _medicineStatus = {};
  final List<Map<String, dynamic>> _verifiedMeds = [];

  @override
  void initState() {
    super.initState();

    final medicines = widget.queueItem.medicines;

    for (int i = 0; i < medicines.length; i++) {
      final med = medicines[i];

      _doseControllers[i] = TextEditingController(text: med['dose'].toString());

      _freqControllers[i] = TextEditingController(
        text: med['frequency'].toString(),
      );

      _medicineStatus[i] = 'pending';

      _verifiedMeds.add({
        "name": med['name'],
        "dose": med['dose'],
        "unit": med['unit'] ?? 'mg',
        "frequency": med['frequency'],
        "route": med['route'] ?? 'PO',
        "prn": med['prn'] ?? false,
        "status": "pending",
        "pharmacist_rejection_reason": "",
        "pharmacist_suggested_medicine": med['name'],
        "pharmacist_suggested_dose": med['dose'],
        "pharmacist_suggested_unit": med['unit'] ?? 'mg',
        "pharmacist_suggested_frequency": med['frequency'],
        "pharmacist_suggested_route": med['route'] ?? 'PO',
      });
    }

    if (medicines.isNotEmpty) {
      _suggestedMedicine.text = medicines.first['name'].toString();
      _suggestedDose.text =
          '${medicines.first['dose']}${medicines.first['unit'] ?? ''}';
    }
  }

  @override
  void dispose() {
    _rejectionReason.dispose();
    _suggestedMedicine.dispose();
    _suggestedDose.dispose();
    _suggestedFrequency.dispose();
    _suggestedRoute.dispose();

    for (final c in _doseControllers.values) {
      c.dispose();
    }

    for (final c in _freqControllers.values) {
      c.dispose();
    }

    super.dispose();
  }

  bool get _hasRejectedMedicine =>
      _verifiedMeds.any((med) => med['status'] == 'rejected');

  List<Map<String, dynamic>> _approvedMedicineBundle(String reviewedAt) {
    return _verifiedMeds.map((med) {
      return {
        ...med,
        'status': 'approved',
        'pharmacist_decision': 'approved',
        'pharmacist_reviewed_at': reviewedAt,
      };
    }).toList();
  }

  List<Map<String, dynamic>> _rejectedMedicineBundle({
    required String reason,
    required String suggestedMedicine,
    required String suggestedDose,
    required String reviewedAt,
  }) {
    return _verifiedMeds.map((med) {
      final rejectedByPharmacist = med['status'] == 'rejected';

      return {
        ...med,
        'status': rejectedByPharmacist ? 'rejected' : 'included_for_review',
        'bundle_status': 'pharmacist_rejected',
        'pharmacist_rejection_reason': reason,
        if (rejectedByPharmacist) ...{
          'pharmacist_suggested_medicine': suggestedMedicine,
          'pharmacist_suggested_dose': suggestedDose,
          'pharmacist_suggested_unit': med['unit'] ?? 'mg',
          'pharmacist_suggested_frequency': med['frequency'] ?? '',
          'pharmacist_suggested_route': med['route'] ?? 'PO',
        },
        'pharmacist_reviewed_at': reviewedAt,
      };
    }).toList();
  }

  Future<void> _approvePlan() async {
    try {
      final supabase = Supabase.instance.client;
      final reviewedAt = DateTime.now().toIso8601String();

      if (_hasRejectedMedicine) {
        final reason = _rejectionReason.text.trim();
        final suggestedMedicine = _suggestedMedicine.text.trim();
        final suggestedDose = _suggestedDose.text.trim();

        if (reason.isEmpty ||
            suggestedMedicine.isEmpty ||
            suggestedDose.isEmpty) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text(
                'Please enter rejection reason, suggested medicine, and suggested dosage.',
              ),
            ),
          );
          return;
        }

        final reviewMeds = _rejectedMedicineBundle(
          reason: reason,
          suggestedMedicine: suggestedMedicine,
          suggestedDose: suggestedDose,
          reviewedAt: reviewedAt,
        );

        await supabase.from('prescription_verifications').insert({
          'prescription_id': widget.queueItem.id,
          'patient_id': widget.queueItem.patientId,
          'patient_name': widget.patient.name,
          'pharmacist_id': widget.pharmacistId,
          'medicines': reviewMeds,
          'status': 'pharmacist_rejected',
          'created_at': reviewedAt,
        });

        await supabase
            .from('prescriptions')
            .update({'status': 'pharmacist_rejected'})
            .eq('id', widget.queueItem.id);

        if (!mounted) return;

        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Rejection sent to doctor for review.')),
        );

        Navigator.pop(context, true);
        return;
      }

      final approvedMeds = _approvedMedicineBundle(reviewedAt);

      await supabase.from('prescription_verifications').insert({
        'prescription_id': widget.queueItem.id,
        'patient_id': widget.queueItem.patientId,
        'patient_name': widget.patient.name,
        'pharmacist_id': widget.pharmacistId,
        'medicines': approvedMeds, // JSONB stores full prescription bundle
        'status': 'approved',
        'created_at': reviewedAt,
      });

      await supabase
          .from('prescriptions')
          .update({'status': 'verified', 'medicines': approvedMeds})
          .eq('id', widget.queueItem.id);

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Prescription verified successfully')),
      );

      Navigator.pop(context, true);
    } catch (e) {
      if (!mounted) return;

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.patient;
    final v = widget.vitals;
    final medicines = widget.queueItem.medicines;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Pharmacist Dose Verification'),
        centerTitle: true,
        backgroundColor: Colors.blue.shade700,
        elevation: 4,
        actions: const [PharmacistDecisionNotificationBell()],
      ),
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Colors.blue.shade50, Colors.white],
          ),
        ),
        child: Padding(
          padding: Responsive.pagePadding(context),
          child: ListView(
            children: [
              // Patient + med summary
              Card(
                elevation: 2,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(12.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Patient Information',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),

                      Text(
                        p.name,
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: Colors.black87,
                        ),
                      ),
                      const SizedBox(height: 4),

                      Text(
                        'Ward: ${p.wardRoomNo}   Age: ${p.age}   Wt: ${p.weight} kg',
                        style: const TextStyle(color: Colors.black54),
                      ),

                      Text(
                        'Blood type: ${p.bloodType}',
                        style: const TextStyle(color: Colors.black54),
                      ),

                      const SizedBox(height: 10),

                      ElevatedButton.icon(
                        icon: const Icon(Icons.medical_information),
                        label: const Text('Patient Condition'),
                        onPressed: () async {
                          final latest = await Supabase.instance.client
                              .from('patient_current_conditions')
                              .select()
                              .eq('patient_id', p.id)
                              .order('created_at', ascending: false)
                              .limit(1)
                              .maybeSingle();

                          if (!context.mounted) return;

                          if (latest == null) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text("No condition record found"),
                              ),
                            );
                            return;
                          }

                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => PatientConditionDetailPage(
                                patient: p,
                                data: latest,
                              ),
                            ),
                          );
                        },
                      ),
                    ],
                  ),
                ),
              ),

              Card(
                elevation: 2,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(12.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Prescription Details',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 10),

                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: List.generate(medicines.length, (index) {
                          final m = medicines[index];

                          return Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '${m['name']}',
                                style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 15,
                                ),
                              ),

                              const SizedBox(height: 10),

                              ResponsiveTwoColumn(
                                breakpoint: 460,
                                gap: 8,
                                leftFlex: 2,
                                left: TextField(
                                  controller: _doseControllers[index],
                                  enabled: false,
                                  decoration: const InputDecoration(
                                    labelText: 'Dose',
                                    border: OutlineInputBorder(),
                                  ),
                                ),
                                right: DropdownButtonFormField<String>(
                                  initialValue: _verifiedMeds[index]['unit'],
                                  items: ['mg', 'g', 'ml', 'IU', 'mcg']
                                      .map(
                                        (u) => DropdownMenuItem(
                                          value: u,
                                          child: Text(u),
                                        ),
                                      )
                                      .toList(),
                                  onChanged: null,
                                  decoration: const InputDecoration(
                                    labelText: 'Unit',
                                    border: OutlineInputBorder(),
                                  ),
                                ),
                              ),

                              const SizedBox(height: 8),

                              DropdownButtonFormField<String>(
                                initialValue: _verifiedMeds[index]['frequency'],
                                items:
                                    [
                                          'Once a day',
                                          'Twice a day',
                                          'Three times a day',
                                          'Every 6 hours',
                                          'Every 8 hours',
                                        ]
                                        .map(
                                          (f) => DropdownMenuItem(
                                            value: f,
                                            child: Text(f),
                                          ),
                                        )
                                        .toList(),
                                onChanged: null,
                                decoration: const InputDecoration(
                                  labelText: 'Frequency',
                                  border: OutlineInputBorder(),
                                ),
                              ),

                              const SizedBox(height: 8),

                              DropdownButtonFormField<String>(
                                initialValue: _verifiedMeds[index]['route'],
                                items:
                                    [
                                          'PO',
                                          'IV',
                                          'IM',
                                          'SC',
                                          'Topical',
                                          'Inhaled',
                                          'PR',
                                          'SL',
                                        ]
                                        .map(
                                          (r) => DropdownMenuItem(
                                            value: r,
                                            child: Text(r),
                                          ),
                                        )
                                        .toList(),
                                onChanged: null,
                                decoration: const InputDecoration(
                                  labelText: 'Route',
                                  border: OutlineInputBorder(),
                                ),
                              ),

                              CheckboxListTile(
                                contentPadding: EdgeInsets.zero,
                                title: const Text("PRN (As needed)"),
                                value: _verifiedMeds[index]['prn'] ?? false,
                                onChanged: null,
                              ),

                              const SizedBox(height: 8),

                              if (_medicineStatus[index] != null)
                                Text(
                                  'Status: ${_medicineStatus[index]}',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    color: _medicineStatus[index] == 'approved'
                                        ? Colors.green
                                        : Colors.red,
                                  ),
                                ),

                              const SizedBox(height: 10),

                              ResponsiveTwoColumn(
                                breakpoint: 420,
                                gap: 8,
                                left: ElevatedButton(
                                  onPressed: () {
                                    setState(() {
                                      _medicineStatus[index] = 'approved';
                                      _verifiedMeds[index]['status'] =
                                          'approved';
                                    });
                                  },
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: Colors.green,
                                    foregroundColor: Colors.white,
                                  ),
                                  child: const Text('Approve'),
                                ),
                                right: ElevatedButton(
                                  onPressed: () {
                                    setState(() {
                                      _medicineStatus[index] = 'rejected';
                                      _verifiedMeds[index]['status'] =
                                          'rejected';
                                      _suggestedMedicine.text =
                                          _verifiedMeds[index]['name']
                                              .toString();
                                      _suggestedDose.text =
                                          '${_verifiedMeds[index]['dose']}${_verifiedMeds[index]['unit'] ?? ''}';

                                      _suggestedFrequency.text =
                                          _verifiedMeds[index]['frequency'] ??
                                          '';
                                      _suggestedRoute.text =
                                          _verifiedMeds[index]['route'] ?? '';
                                    });
                                  },
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: Colors.red,
                                    foregroundColor: Colors.white,
                                  ),
                                  child: const Text('Reject'),
                                ),
                              ),

                              const SizedBox(height: 12),
                              const Divider(),
                            ],
                          );
                        }),
                      ),

                      const Divider(height: 20),

                      Text(
                        'Doctor originally typed: ${widget.queueItem.doctorMedicine}',
                        style: const TextStyle(color: Colors.black54),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 12),

              // (REMOVED AI suggested alternative medicines section)

              // Condition snapshot (if available)
              if (v != null)
                Card(
                  elevation: 2,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(12.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Condition Snapshot',
                          style: TextStyle(
                            fontWeight: FontWeight.w600,
                            color: Colors.black87,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          'Date: ${v.date}',
                          style: const TextStyle(color: Colors.black54),
                        ),
                        Text(
                          'Temp: ${v.temperature} °C   BP: ${v.bloodPressure}   HR: ${v.heartRate}',
                          style: const TextStyle(color: Colors.black54),
                        ),
                        Text(
                          'SpO₂: ${v.oxygenSaturation}%   Lactate: ${v.lactate} mmol/L',
                          style: const TextStyle(color: Colors.black54),
                        ),
                        Text(
                          'WBC: ${v.wbc} ×10⁹/L   Cr: ${v.creatinine} mg/dL   eGFR: ${v.egfr}',
                          style: const TextStyle(color: Colors.black54),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Condition: ${v.condition}',
                          style: const TextStyle(color: Colors.black54),
                        ),
                      ],
                    ),
                  ),
                ),

              const SizedBox(height: 12),

              if (_hasRejectedMedicine)
                Card(
                  elevation: 3,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  color: Colors.red.shade50,
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(
                              Icons.notification_important,
                              color: Colors.red.shade700,
                            ),
                            const SizedBox(width: 8),
                            const Text(
                              'Reject & Notify Doctor',
                              style: TextStyle(
                                fontWeight: FontWeight.w800,
                                fontSize: 16,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 10),
                        TextField(
                          controller: _rejectionReason,
                          minLines: 2,
                          maxLines: 4,
                          decoration: const InputDecoration(
                            labelText: 'Reason for rejection',
                            hintText:
                                'Explain why this prescription cannot be accepted.',
                            border: OutlineInputBorder(),
                            filled: true,
                            fillColor: Colors.white,
                          ),
                        ),
                        const SizedBox(height: 10),
                        ResponsiveTwoColumn(
                          breakpoint: 520,
                          gap: 10,
                          left: TextField(
                            controller: _suggestedMedicine,
                            decoration: const InputDecoration(
                              labelText: 'Suggested medicine',
                              border: OutlineInputBorder(),
                              filled: true,
                              fillColor: Colors.white,
                            ),
                          ),
                          right: TextField(
                            controller: _suggestedDose,
                            decoration: const InputDecoration(
                              labelText: 'Suggested dosage',
                              hintText: 'e.g. 500 mg twice a day',
                              border: OutlineInputBorder(),
                              filled: true,
                              fillColor: Colors.white,
                            ),
                          ),
                        ),
                        const SizedBox(height: 10),

                        TextField(
                          controller: _suggestedFrequency,
                          decoration: const InputDecoration(
                            labelText: 'Suggested frequency',
                            border: OutlineInputBorder(),
                            filled: true,
                            fillColor: Colors.white,
                          ),
                        ),

                        const SizedBox(height: 10),

                        TextField(
                          controller: _suggestedRoute,
                          decoration: const InputDecoration(
                            labelText: 'Suggested route',
                            border: OutlineInputBorder(),
                            filled: true,
                            fillColor: Colors.white,
                          ),
                        ),

                        CheckboxListTile(
                          title: const Text("PRN (As needed)"),
                          value: _suggestedPrn,
                          onChanged: (val) {
                            setState(() {
                              _suggestedPrn = val ?? false;
                            });
                          },
                        ),
                      ],
                    ),
                  ),
                ),

              const SizedBox(height: 20),

              // Buttons
              ResponsiveTwoColumn(
                breakpoint: 520,
                gap: 12,
                left: ElevatedButton(
                  onPressed: () {
                    setState(() {
                      _rejectionReason.clear();
                      _suggestedMedicine.clear();
                      _suggestedDose.clear();
                      _suggestedFrequency.clear();
                      _suggestedRoute.clear();
                      _suggestedPrn = false;
                    });
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.grey.shade400,
                    foregroundColor: Colors.black87,
                    elevation: 4,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  child: const Padding(
                    padding: EdgeInsets.symmetric(vertical: 12),
                    child: Text(
                      'Clear',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                  ),
                ),
                right: ElevatedButton(
                  onPressed: _approvePlan,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blue.shade600,
                    foregroundColor: Colors.white,
                    elevation: 4,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  child: const Padding(
                    padding: EdgeInsets.symmetric(vertical: 12),
                    child: Text(
                      'Confirm & Save / Send',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                  ),
                ),
              ),

              const SizedBox(height: 16),
              const Text(
                'Prototype only — not medical advice.',
                style: TextStyle(
                  fontSize: 12,
                  fontStyle: FontStyle.italic,
                  color: Colors.black54,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
