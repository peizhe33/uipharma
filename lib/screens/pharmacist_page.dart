import 'package:flutter/material.dart';
import '../models/models.dart';
import 'dose_verification_page.dart';
import 'doctor_patient_overview.dart'; // <-- NEW import for Doctor home
import 'package:supabase_flutter/supabase_flutter.dart';
import '../widgets/review_notification_bell.dart';

class PharmacistPage extends StatefulWidget {
  final String pharmacistId;

  const PharmacistPage({super.key, required this.pharmacistId});

  @override
  State<PharmacistPage> createState() => _PharmacistPageState();
}

class _PharmacistPageState extends State<PharmacistPage> {
  late String pharmacistId;

  @override
  void initState() {
    super.initState();
    pharmacistId = widget.pharmacistId;
  }

  String searchToBeVerified = '';
  String searchVerified = '';
  final supabase = Supabase.instance.client;

  Future<Patient> fetchPatientById(String id) async {
    final res = await Supabase.instance.client
        .from('patients')
        .select()
        .eq('id', id)
        .single();

    return Patient.fromJson(res);
  }

  Future<List<Map<String, dynamic>>> fetchPending() async {
    final supabase = Supabase.instance.client;

    final res = await supabase
        .from('prescriptions')
        .select()
        .order('created_at', ascending: false);

    return List<Map<String, dynamic>>.from(res).where((item) {
      final status = (item['status'] ?? '').toString();
      return status == 'pending_verification';
    }).toList();
  }

  Future<List<Map<String, dynamic>>> fetchVerified() async {
    final res = await supabase
        .from('prescription_verifications')
        .select()
        .order('created_at', ascending: false);

    return List<Map<String, dynamic>>.from(res).where((item) {
      final status = (item['status'] ?? '').toString();
      return status == 'approved';
    }).toList();
  }

  String _medicineNames(Map<String, dynamic> item) {
    final medicines = item['medicines'];
    if (medicines is! List) return 'No medicine details';
    return medicines
        .map((m) {
          if (m is! Map) return '';
          final name =
              (m['pharmacist_suggested_medicine'] ??
                      m['name'] ??
                      'Unknown medicine')
                  .toString();
          final dose = (m['pharmacist_suggested_dose'] ?? m['dose'] ?? '')
              .toString();
          final unit = (m['pharmacist_suggested_unit'] ?? m['unit'] ?? '')
              .toString();
          final route = (m['pharmacist_suggested_route'] ?? m['route'] ?? '')
              .toString();
          return '$name $dose$unit $route'.trim();
        })
        .where((text) => text.isNotEmpty)
        .join(', ');
  }

  String _pendingStatusText(String status) {
    if (status == 'pharmacist_rejected') {
      return 'Under approval by doctor. Waiting for the doctor decision.';
    }
    if (status == 'doctor_rejected') {
      return 'Doctor responded. Please open the notification to review.';
    }
    return 'Ready for pharmacist verification.';
  }

  // ===== Home navigation helper =====
  void _goHome(BuildContext context) {
    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (_) => const PatientOverviewPage()),
      (route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text(
            "Pharmacist Console",
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
          ),
          backgroundColor: Colors.blue.shade700,
          actions: [
            const PharmacistDecisionNotificationBell(),
            IconButton(
              icon: const Icon(Icons.home),
              color: Colors.white,
              tooltip: 'Back to Doctor Home',
              onPressed: () => _goHome(context), // <-- HOME BUTTON
            ),
          ],
          bottom: const TabBar(
            indicatorColor: Colors.white,
            tabs: [
              Tab(text: "To be verified"),
              Tab(text: "Verified"),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            // ======== TAB 1: To be verified ========
            Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(8.0),
                  child: TextField(
                    onChanged: (v) => setState(() => searchToBeVerified = v),
                    decoration: InputDecoration(
                      labelText: "Search by patient name",
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                      prefixIcon: const Icon(Icons.search),
                    ),
                  ),
                ),

                Expanded(
                  child: FutureBuilder(
                    future: fetchPending(),
                    builder: (context, snapshot) {
                      if (snapshot.connectionState == ConnectionState.waiting) {
                        return const Center(child: CircularProgressIndicator());
                      }

                      if (snapshot.hasError) {
                        return Center(child: Text("Error: ${snapshot.error}"));
                      }

                      final queue = snapshot.data ?? [];

                      if (queue.isEmpty) {
                        return const Center(child: Text("No items to verify"));
                      }

                      return ListView.builder(
                        itemCount: queue.length,
                        itemBuilder: (context, i) {
                          final item = queue[i];

                          if (!item['patient_name'].toLowerCase().contains(
                            searchToBeVerified.toLowerCase(),
                          )) {
                            return const SizedBox.shrink();
                          }

                          final status = (item['status'] ?? '').toString();

                          return Card(
                            child: ListTile(
                              leading: const Icon(
                                Icons.pending_actions,
                                color: Colors.blue,
                              ),
                              title: Text(item['patient_name']),
                              subtitle: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(_medicineNames(item)),
                                  const SizedBox(height: 4),
                                  Text(
                                    _pendingStatusText(status),
                                    style: const TextStyle(
                                      color: Colors.black54,
                                    ),
                                  ),
                                ],
                              ),
                              onTap: () async {
                                final patientData = await fetchPatientById(
                                  item['patient_id'],
                                );

                                final result = await Navigator.push(
                                  context,
                                  MaterialPageRoute(
                                    builder: (_) => DoseVerificationPage(
                                      queueItem: FinalPrescription(
                                        id: item['id'].toString(),
                                        patientId: item['patient_id']
                                            .toString(),
                                        patientName: item['patient_name']
                                            .toString(),
                                        wardRoomNo: item['ward_room_no'] ?? '',
                                        medicine: item['medicines'][0]['name'],
                                        doctorMedicine:
                                            item['doctor_medicine'] ?? '',
                                        rationale: item['rationale'] ?? '',
                                        date: item['created_at'].toString(),
                                        medicines: item['medicines'] ?? [],
                                      ),
                                      patient: patientData,
                                      pharmacistId: widget.pharmacistId,
                                    ),
                                  ),
                                );

                                if (result == true) {
                                  setState(() {}); // refresh FutureBuilder
                                }
                              },
                            ),
                          );
                        },
                      );
                    },
                  ),
                ),
              ],
            ),

            // ======== TAB 2: Verified ========
            Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(8.0),
                  child: TextField(
                    onChanged: (v) => setState(() => searchVerified = v),
                    decoration: InputDecoration(
                      labelText: "Search by patient name",
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                      prefixIcon: const Icon(Icons.search),
                      hintText: "Type a name...",
                    ),
                  ),
                ),
                Expanded(
                  child: FutureBuilder(
                    future: fetchVerified(),
                    builder: (context, snapshot) {
                      if (snapshot.connectionState == ConnectionState.waiting) {
                        return const Center(child: CircularProgressIndicator());
                      }

                      if (snapshot.hasError) {
                        return Center(child: Text("Error: ${snapshot.error}"));
                      }

                      final data = snapshot.data ?? [];

                      if (data.isEmpty) {
                        return const Center(
                          child: Text("No verified prescriptions"),
                        );
                      }

                      return ListView.builder(
                        itemCount: data.length,
                        itemBuilder: (context, i) {
                          final item = data[i];

                          return Card(
                            child: ListTile(
                              leading: const Icon(
                                Icons.verified,
                                color: Colors.green,
                              ),
                              title: Text(item['patient_name']),
                              subtitle: Builder(
                                builder: (_) {
                                  try {
                                    final meds =
                                        List<Map<String, dynamic>>.from(
                                          item['medicines'] ?? [],
                                        );

                                    return Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: meds.map((m) {
                                        final dose = m['dose'] ?? '';
                                        final unit = m['unit'] ?? '';
                                        final frequency = m['frequency'] ?? '';
                                        final route = m['route'] ?? '';
                                        final prn = m['prn'] == true
                                            ? ' (PRN)'
                                            : '';
                                        final routeText =
                                            route.toString().isEmpty
                                            ? ''
                                            : ', $route';

                                        return Padding(
                                          padding: const EdgeInsets.only(
                                            top: 4,
                                          ),
                                          child: RichText(
                                            text: TextSpan(
                                              style: const TextStyle(
                                                color: Colors.black,
                                              ),
                                              children: [
                                                TextSpan(
                                                  text: '${m['name']}',
                                                  style: const TextStyle(
                                                    fontWeight: FontWeight.bold,
                                                  ),
                                                ),
                                                TextSpan(
                                                  text:
                                                      ' — $dose $unit$routeText, $frequency$prn',
                                                ),
                                              ],
                                            ),
                                          ),
                                        );
                                      }).toList(),
                                    );
                                  } catch (e) {
                                    return const Text('Invalid medicine data');
                                  }
                                },
                              ),
                            ),
                          );
                        },
                      );
                    },
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
