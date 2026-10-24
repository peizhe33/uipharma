import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/nurse_service.dart';
import '../services/patient_supabase_service.dart';
import 'nurse_id_page.dart';
import 'nurse_patient_detail_page.dart';
import '../widgets/osk_text_field.dart';

/// Patient queue shown after nurse login.
class NursePatientListPage extends StatefulWidget {
  final NurseSession nurse;

  const NursePatientListPage({super.key, required this.nurse});

  @override
  State<NursePatientListPage> createState() => _NursePatientListPageState();
}

class _NursePatientListPageState extends State<NursePatientListPage> {
  List<Patient> _patients = [];
  bool _loading = true;
  String? _error;
  String _query = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await PatientSupabaseService.getPatients();
      data.sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
      if (!mounted) return;
      setState(() => _patients = data);
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final q = _query.toLowerCase();
    final filtered = _patients
        .where((p) =>
            p.name.toLowerCase().contains(q) ||
            p.wardRoomNo.toLowerCase().contains(q))
        .toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Nurse Console'),
        backgroundColor: Colors.teal.shade700,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh),
            onPressed: _load,
          ),
          IconButton(
            tooltip: 'Log out',
            icon: const Icon(Icons.logout),
            onPressed: () => exitToNurseLogin(context),
          ),
        ],
      ),
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [Colors.teal.shade50, Colors.white],
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
          ),
        ),
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
              child: Row(
                children: [
                  Icon(Icons.badge, size: 18, color: Colors.teal.shade700),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      'Logged in: ${widget.nurse.name.isEmpty ? widget.nurse.code : '${widget.nurse.name} (${widget.nurse.code})'}',
                      style: TextStyle(
                        color: Colors.teal.shade900,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              child: OskTextField(
                onChanged: (v) => setState(() => _query = v),
                decoration: InputDecoration(
                  labelText: 'Search patient or ward',
                  prefixIcon: const Icon(Icons.search),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                  filled: true,
                  fillColor: Colors.white,
                ),
              ),
            ),
            Expanded(child: _body(filtered)),
          ],
        ),
      ),
    );
  }

  Widget _body(List<Patient> filtered) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text('Could not load patients:\n$_error', textAlign: TextAlign.center),
        ),
      );
    }
    if (filtered.isEmpty) {
      return const Center(
        child: Text('No patient found.',
            style: TextStyle(fontSize: 16, color: Colors.black54)),
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.builder(
        padding: const EdgeInsets.all(12),
        itemCount: filtered.length,
        itemBuilder: (_, i) {
          final p = filtered[i];
          return Card(
            elevation: 3,
            margin: const EdgeInsets.symmetric(vertical: 6),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            child: ListTile(
              leading: CircleAvatar(
                radius: 22,
                backgroundColor: Colors.teal.shade100,
                child: Icon(Icons.person, color: Colors.teal.shade700),
              ),
              title: Text(
                p.name,
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
              ),
              subtitle: Text(
                'Ward: ${p.wardRoomNo}  |  Age: ${p.age}  |  Blood: ${p.bloodType}',
                style: const TextStyle(color: Colors.black54),
              ),
              trailing: Icon(Icons.arrow_forward_ios, color: Colors.teal.shade600),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) =>
                      NursePatientDetailPage(nurse: widget.nurse, patient: p),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
