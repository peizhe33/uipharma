import 'package:flutter/material.dart';
import '../models/models.dart';
import '../services/patient_database.dart';
import 'current_condition_page.dart';
import 'doctor_id_page.dart';
import 'pharmacist_id_page.dart';
import 'feedback_page.dart';
import 'egfr_graph_page.dart';
import '../services/patient_supabase_service.dart';
import 'patient_condition_detail_page.dart';
import 'patient_view_page.dart';
import '../widgets/review_notification_bell.dart';
import '../widgets/responsive.dart';

class PatientOverviewPage extends StatelessWidget {
  const PatientOverviewPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF4F8F6),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => const FeedbackPage(),
            ),
          );
        },
        backgroundColor: const Color(0xFF116D37),
        icon: const Icon(Icons.flag, color: Colors.white),
        label: const Text(
          "Feedback",
          style: TextStyle(
            fontWeight: FontWeight.w700,
            color: Colors.white,
          ),
        ),
      ),

      body: SafeArea(
        child: Stack(
          children: [
            Center(
              child: SingleChildScrollView(
                padding: Responsive.pagePadding(context)
                    .add(const EdgeInsets.only(top: 6, bottom: 92)),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 760),
                  child: Column(
                    children: [
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    decoration: BoxDecoration(
                      color: const Color(0xFFD9FBE4),
                      borderRadius: BorderRadius.circular(30),
                    ),
                    child: const Text(
                      'SYSTEM ONLINE',
                      style: TextStyle(
                        color: Color(0xFF0E6F3C),
                        fontSize: 12,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1.5,
                      ),
                    ),
                  ),

                  SizedBox(height: Responsive.gap(context, 12)),

                  Text.rich(
                    TextSpan(
                      children: [
                        TextSpan(
                          text: 'SmartPharma ',
                          style: TextStyle(
                            color: Color(0xFF14233B),
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                        TextSpan(
                          text: 'Portal',
                          style: TextStyle(
                            color: Color(0xFF7A879C),
                            fontWeight: FontWeight.w300,
                          ),
                        ),
                      ],
                    ),
                    style: TextStyle(fontSize: Responsive.scale(context, 38)),
                    textAlign: TextAlign.center,
                  ),

                  SizedBox(height: Responsive.gap(context, 4)),

                  Text(
                    'Centralized Patient Management & Clinical Records',
                    style: TextStyle(
                      fontSize: Responsive.scale(context, 17),
                      color: Color(0xFF60728F),
                    ),
                    textAlign: TextAlign.center,
                  ),

                  SizedBox(height: Responsive.gap(context, 46)),

                  _menuCard(
                    context: context,
                    icon: Icons.search,
                    iconBackground: const Color(0xFFF0F4FA),
                    iconColor: Colors.blue,
                    title: 'Patient Database',
                    subtitle:
                        'Access existing medical history and active treatments.',
                    onPressed: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const DoctorIdGatePage(),
                      ),
                    ),
                  ),

                  SizedBox(height: Responsive.gap(context, 16)),

                  _menuCard(
                    context: context,
                    icon: Icons.person_outline,
                    iconBackground: const Color(0xFFE8F7F4),
                    iconColor: Colors.teal,
                    title: 'Patient View',
                    subtitle:
                        'Open the patient-facing medicine summary without clinician login.',
                    onPressed: () {
                      final controller = TextEditingController();
                      showDialog(
                        context: context,
                        builder: (_) => AlertDialog(
                          title: const Text('Open Patient View'),
                          content: TextField(
                            controller: controller,
                            autofocus: true,
                            decoration: const InputDecoration(
                              labelText: 'Patient ID',
                              hintText: 'e.g. PNEU001',
                            ),
                          ),
                          actions: [
                            TextButton(
                              onPressed: () => Navigator.pop(context),
                              child: const Text('Cancel'),
                            ),
                            FilledButton(
                              onPressed: () {
                                final id = controller.text.trim();
                                Navigator.pop(context);
                                if (id.isNotEmpty) {
                                  Navigator.push(
                                    context,
                                    PatientViewPage.route(id),
                                  );
                                }
                              },
                              child: const Text('Open'),
                            ),
                          ],
                        ),
                      );
                    },
                  ),

                  SizedBox(height: Responsive.gap(context, 16)),

                  _menuCard(
                    context: context,
                    icon: Icons.add,
                    iconBackground: const Color(0xFF116D37),
                    iconColor: Colors.white,
                    title: 'New Registration',
                    subtitle: 'Onboard a new patient and assign ward location.',
                    highlight: true,
                    onPressed: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const AddNewPatientPage(),
                      ),
                    ),
                  ),

                  SizedBox(height: Responsive.gap(context, 16)),

                  _menuCard(
                    context: context,
                    icon: Icons.medication,
                    iconBackground: const Color(0xFFF0F4FA),
                    iconColor: Colors.pinkAccent,
                    title: 'Pharmacist Portal',
                    subtitle:
                        'Inventory management and prescription verification.',
                    onPressed: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const PharmacistIdGatePage(),
                      ),
                    ),
                  ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _menuCard({
    required BuildContext context,
    required IconData icon,
    required Color iconBackground,
    required Color iconColor,
    required String title,
    required String subtitle,
    required VoidCallback onPressed,
    bool highlight = false,
  }) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(22),
        onTap: onPressed,
        child: Container(
          height: Responsive.scale(context, 108, min: 0.92),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(22),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.08),
                blurRadius: 14,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          child: Row(
            children: [
              if (highlight)
                Container(
                  width: 7,
                  height: double.infinity,
                  decoration: const BoxDecoration(
                    color: Color(0xFF116D37),
                    borderRadius: BorderRadius.only(
                      topLeft: Radius.circular(22),
                      bottomLeft: Radius.circular(22),
                    ),
                  ),
                ),

              Expanded(
                child: Padding(
                  padding: EdgeInsets.only(
                    left: highlight
                        ? Responsive.scale(context, 18, min: 0.8)
                        : Responsive.scale(context, 24, min: 0.72),
                    right: Responsive.scale(context, 20, min: 0.72),
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: Responsive.scale(context, 58, min: 0.82),
                        height: Responsive.scale(context, 58, min: 0.82),
                        decoration: BoxDecoration(
                          color: iconBackground,
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Icon(
                          icon,
                          color: iconColor,
                          size: Responsive.scale(context, 30, min: 0.86),
                        ),
                      ),

                      SizedBox(width: Responsive.scale(context, 20, min: 0.65)),

                      Expanded(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              title,
                              style: TextStyle(
                                fontSize: Responsive.scale(context, 20),
                                fontWeight: FontWeight.w800,
                                color: const Color(0xFF07112B),
                              ),
                            ),
                            SizedBox(height: Responsive.gap(context, 4)),
                            Text(
                              subtitle,
                              style: TextStyle(
                                fontSize: Responsive.scale(context, 15),
                                color: const Color(0xFF60728F),
                              ),
                            ),
                          ],
                        ),
                      ),

                      const Icon(
                        Icons.arrow_forward,
                        color: Color(0xFFC5CBD6),
                        size: 20,
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ===================================================================
// Add New Patient Page
// ===================================================================

class AddNewPatientPage extends StatefulWidget {
  const AddNewPatientPage({super.key});

  @override
  State<AddNewPatientPage> createState() => _AddNewPatientPageState();
}

class _AddNewPatientPageState extends State<AddNewPatientPage> {
  final _formKey = GlobalKey<FormState>();
  final _wardRoom = TextEditingController();
  final _name = TextEditingController();
  final _age = TextEditingController();
  final _height = TextEditingController();
  final _weight = TextEditingController();
  final _blood = TextEditingController();
  String _gender = 'Male';
  @override
  void dispose() {
    _wardRoom.dispose();
    _name.dispose();
    _age.dispose();
    _height.dispose();
    _weight.dispose();
    _blood.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;

    final p = Patient(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      wardRoomNo: _wardRoom.text.trim(),
      name: _name.text.trim(),
      gender: _gender,
      age: _age.text.trim(),
      height: _height.text.trim(),
      weight: _weight.text.trim(),
      bloodType: _blood.text.trim(),
    );

    try {
      await PatientSupabaseService.addPatient(p);

      PatientDatabase.instance.addPatient(p);

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Patient saved successfully')),
      );

      _wardRoom.clear();
      _name.clear();
      _age.clear();
      _height.clear();
      _weight.clear();
      _blood.clear();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error saving patient: $e')),
      );
    }
  }

  void _home() => Navigator.of(context).popUntil((r) => r.isFirst);

  @override
  Widget build(BuildContext context) {
    final compact = Responsive.isCompact(context);

    return Scaffold(
      backgroundColor: const Color(0xFFF4F8F6),
      body: SafeArea(
        child: Stack(
          children: [
            Center(
              child: SingleChildScrollView(
                padding: Responsive.pagePadding(context)
                    .add(const EdgeInsets.only(bottom: 24)),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 780),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  TextButton.icon(
                    onPressed: _home,
                    icon: const Icon(Icons.arrow_back, size: 16),
                    label: const Text('Back to Portal'),
                    style: TextButton.styleFrom(
                      foregroundColor: const Color(0xFF60728F),
                      textStyle: const TextStyle(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),

                  SizedBox(height: Responsive.gap(context, 6)),

                  Center(
                    child: Text(
                      'New Patient Registration',
                      style: TextStyle(
                        fontSize: Responsive.scale(context, 28),
                        fontWeight: FontWeight.w900,
                        color: const Color(0xFF14233B),
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ),

                  SizedBox(height: Responsive.gap(context, 28)),

                  Container(
                    padding: EdgeInsets.all(compact ? 20 : 40),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(compact ? 22 : 34),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.05),
                          blurRadius: 25,
                          offset: const Offset(0, 12),
                        ),
                      ],
                    ),
                    child: Form(
                      key: _formKey,
                      child: Column(
                        children: [
                          ResponsiveWrap(
                            minItemWidth: compact ? 250 : 300,
                            spacing: 18,
                            runSpacing: 18,
                            children: [
                              _modernField(
                                _name,
                                'Full Name',
                                'Full legal name',
                              ),
                              _modernField(
                                _wardRoom,
                                'Assigned Ward',
                                'e.g. Ward B-01',
                              ),
                            ],
                          ),

                          SizedBox(height: Responsive.gap(context, 24)),

                          ResponsiveWrap(
                            minItemWidth: compact ? 118 : 135,
                            spacing: 16,
                            runSpacing: 18,
                            children: [
                              _modernField(
                                _age,
                                'Age',
                                '',
                                kb: TextInputType.number,
                              ),
                              _genderField(),
                              _modernField(
                                _blood,
                                'Blood Type',
                                'O+',
                              ),
                              _modernField(
                                _height,
                                'Height (cm)',
                                '',
                                kb: TextInputType.number,
                              ),
                              _modernField(
                                _weight,
                                'Weight (kg)',
                                '',
                                kb: TextInputType.number,
                              ),
                            ],
                          ),

                          SizedBox(height: Responsive.gap(context, 38)),

                          SizedBox(
                            width: double.infinity,
                            height: 56,
                            child: ElevatedButton(
                              onPressed: () async => await _submit(),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: Colors.blue,
                                foregroundColor: Colors.white,
                                elevation: 4,
                                shadowColor: Colors.black26,
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(14),
                                ),
                              ),
                              child: const Text(
                                'Confirm & Register Patient',
                                style: TextStyle(
                                  fontSize: 17,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _modernField(
    TextEditingController c,
    String label,
    String hint, {
    TextInputType? kb,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w800,
            color: Color(0xFF34435A),
          ),
        ),
        const SizedBox(height: 14),
        TextFormField(
          controller: c,
          keyboardType: kb,
          textAlign: TextAlign.center,
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: const TextStyle(color: Color(0xFF7A879C)),
            filled: true,
            fillColor: const Color(0xFFF8FAFC),
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 16,
              vertical: 16,
            ),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(14),
              borderSide: const BorderSide(color: Color(0xFFE0E7EF)),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(14),
              borderSide: const BorderSide(color: Color(0xFFE0E7EF)),
            ),
            focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(
            color: Colors.blue,
            width: 1.4,
        ),
      ),
          ),
          validator: (v) =>
              (v == null || v.trim().isEmpty) ? 'Please enter $label' : null,
        ),
      ],
    );
  }

  Widget _genderField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        const Text(
          'Gender',
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w800,
            color: Color(0xFF34435A),
          ),
        ),
        const SizedBox(height: 14),
        DropdownButtonFormField<String>(
          initialValue: _gender,
          isExpanded: true,
          decoration: InputDecoration(
            filled: true,
            fillColor: const Color(0xFFF8FAFC),
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 16,
              vertical: 16,
            ),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(14),
              borderSide: const BorderSide(color: Color(0xFFE0E7EF)),
            ),
          ),
          items: const [
            DropdownMenuItem(value: 'Male', child: Text('Male')),
            DropdownMenuItem(value: 'Female', child: Text('Female')),
          ],
          onChanged: (value) {
            setState(() {
              _gender = value ?? 'Male';
            });
          },
        ),
      ],
    );
  }
}

// ===================================================================
// Patient List Page (unchanged)
// ===================================================================

class PatientListPage extends StatefulWidget {
  const PatientListPage({super.key});

  @override
  State<PatientListPage> createState() => _PatientListPageState();
}

class _PatientListPageState extends State<PatientListPage> {
  List<Patient> patients = [];
  bool isLoading = true;
  String _searchQuery = '';

  @override
  void initState() {
    super.initState();
    loadPatients();
  }

  Future<void> loadPatients() async {
    final data = await PatientSupabaseService.getPatients();

    setState(() {
      patients = data;
      isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final allPatients = patients;

    final filteredPatients = allPatients.where((p) {
      final q = _searchQuery.toLowerCase();
      return p.name.toLowerCase().contains(q) ||
          p.wardRoomNo.toLowerCase().contains(q);
    }).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Select Patient'),
        actions: const [DoctorReviewNotificationBell()],
      ),
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [Colors.blue.shade50, Colors.white],
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
          ),
        ),
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              child: TextField(
                onChanged: (v) => setState(() => _searchQuery = v),
                decoration: InputDecoration(
                  labelText: 'Search Patient',
                  prefixIcon: const Icon(Icons.search),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  filled: true,
                  fillColor: Colors.white,
                ),
              ),
            ),
            Expanded(
              child: patients.isEmpty
                  ? const Center(
                      child: Text(
                        "No patient found.",
                        style: TextStyle(fontSize: 16, color: Colors.black54),
                      ),
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.all(12),
                      itemCount: filteredPatients.length,
                      itemBuilder: (_, i) {
                        final p = filteredPatients[i];
                        return Card(
                          elevation: 3,
                          margin: const EdgeInsets.symmetric(vertical: 8),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: ListTile(
                            leading: CircleAvatar(
                              radius: 22,
                              backgroundColor: Colors.blue.shade100,
                              child: Icon(Icons.person,
                                  color: Colors.blue.shade700),
                            ),
                            title: Text(
                              p.name,
                              style: const TextStyle(
                                  fontSize: 18, fontWeight: FontWeight.w600),
                            ),
                            subtitle: Text(
                              'Ward: ${p.wardRoomNo}\n'
                              'Age: ${p.age} | ${p.height} cm | ${p.weight} kg\n'
                              'Blood Type: ${p.bloodType}',
                              style: const TextStyle(color: Colors.black54),
                            ),
                            isThreeLine: true,
                            trailing: Row(
  mainAxisSize: MainAxisSize.min,
  children: [
    IconButton(
      icon: const Icon(Icons.delete, color: Colors.red),
      onPressed: () async {

        final confirm = await showDialog<bool>(
          context: context,
          builder: (_) => AlertDialog(
            title: const Text('Delete Patient?'),
            content: Text(
              'Delete ${p.name} from Supabase?',
            ),
            actions: [
              TextButton(
                onPressed: () =>
                    Navigator.pop(context, false),
                child: const Text('Cancel'),
              ),

              ElevatedButton(
                onPressed: () =>
                    Navigator.pop(context, true),

                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.red,
                  foregroundColor: Colors.white,
                ),

                child: const Text('Delete'),
              ),
            ],
          ),
        );

        if (confirm == true) {

          try {
  await PatientSupabaseService.deletePatient(p.id);

  setState(() {
    patients.removeWhere((patient) => patient.id == p.id);
  });

  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text('${p.name} deleted from Supabase')),
  );
} catch (e) {
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text('Delete failed: $e')),
  );
}
        }
      },
    ),

    Icon(
      Icons.arrow_forward_ios,
      color: Colors.blue.shade600,
    ),
  ],
),
                            onTap: () => Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (_) => PatientActionsPage(patient: p),
                              ),
                            ),
                          ),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

// ===================================================================
// Patient Actions Page (unchanged)
// ===================================================================

class PatientActionsPage extends StatelessWidget {
  final Patient patient;
  const PatientActionsPage({super.key, required this.patient});

  @override
  Widget build(BuildContext context) {
    void home() => Navigator.of(context).popUntil((r) => r.isFirst);
    final compact = Responsive.isCompact(context);

    final header = compact
        ? Column(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              _avatar(context),
              const SizedBox(height: 16),
              _patientTitle(context, centered: true),
            ],
          )
        : Row(
            children: [
              _avatar(context),
              const SizedBox(width: 28),
              Expanded(child: _patientTitle(context)),
            ],
          );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Patient Options'),
        centerTitle: true,
        backgroundColor: Colors.blue.shade600,
        foregroundColor: Colors.white,
        actions: const [DoctorReviewNotificationBell()],
      ),
      backgroundColor: const Color(0xFFF4F8F6),
      body: SafeArea(
        child: ResponsiveCenter(
          maxWidth: 1050,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              header,
              SizedBox(height: Responsive.gap(context, 36)),
              ResponsiveTwoColumn(
                gap: 22,
                left: _infoPanel(
                  context: context,
                  title: 'PHYSICAL PROFILE',
                  child: _profileGrid(context),
                ),
                right: _infoPanel(
                  context: context,
                  title: 'CLINICAL NAVIGATION',
                  child: Column(
                    children: [
                      _navButton(
                        text: "Patient's Current Condition",
                        icon: Icons.assignment_outlined,
                        onPressed: () => Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) =>
                                CurrentConditionPage(patient: patient),
                          ),
                        ),
                      ),
                      const SizedBox(height: 14),
                      _navButton(
                        text: "View Patient's History",
                        icon: Icons.history,
                        onPressed: () => Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => PatientHistoryPage(patient: patient),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              SizedBox(height: Responsive.gap(context, 24)),
              SizedBox(
                width: double.infinity,
                height: 52,
                child: ElevatedButton(
                  onPressed: home,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blue.shade600,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                  ),
                  child: const Text(
                    'Home',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _avatar(BuildContext context) {
    final size = Responsive.scale(context, 96, min: 0.78);
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: Colors.blue.shade600,
        borderRadius: BorderRadius.circular(Responsive.scale(context, 28)),
      ),
      child: Center(
        child: Text(
          patient.name.isNotEmpty ? patient.name[0].toUpperCase() : 'P',
          style: TextStyle(
            fontSize: Responsive.scale(context, 42),
            fontWeight: FontWeight.w900,
            color: Colors.white,
          ),
        ),
      ),
    );
  }

  Widget _patientTitle(BuildContext context, {bool centered = false}) {
    return Column(
      crossAxisAlignment:
          centered ? CrossAxisAlignment.center : CrossAxisAlignment.start,
      children: [
        Text(
          patient.name,
          style: TextStyle(
            fontSize: Responsive.scale(context, 36),
            fontWeight: FontWeight.w900,
            color: const Color(0xFF14233B),
          ),
          textAlign: centered ? TextAlign.center : TextAlign.start,
        ),
        const SizedBox(height: 4),
        Text(
          'ID: ${patient.id}  •  Ward Room No.: ${patient.wardRoomNo}',
          style: TextStyle(
            fontSize: Responsive.scale(context, 16),
            color: const Color(0xFF60728F),
            fontWeight: FontWeight.w600,
          ),
          textAlign: centered ? TextAlign.center : TextAlign.start,
        ),
      ],
    );
  }

  Widget _infoPanel({
    required BuildContext context,
    required String title,
    required Widget child,
  }) {
    return Container(
      padding: EdgeInsets.all(Responsive.isCompact(context) ? 20 : 28),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(Responsive.isCompact(context) ? 22 : 30),
        border: Border.all(color: const Color(0xFFE0E7EF)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w900,
              color: Color(0xFF9AA8BD),
              letterSpacing: 0.6,
            ),
          ),
          SizedBox(height: Responsive.gap(context, 24)),
          child,
        ],
      ),
    );
  }

  Widget _profileGrid(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final columns = constraints.maxWidth < 300 ? 1 : 2;
        final spacing = Responsive.isCompact(context) ? 10.0 : 14.0;
        final itemWidth =
            (constraints.maxWidth - (spacing * (columns - 1))) / columns;

        return Wrap(
          spacing: spacing,
          runSpacing: spacing,
          children: [
            _profileTile(context, 'Age', patient.age, itemWidth),
            _profileTile(
              context,
              'Blood',
              patient.bloodType,
              itemWidth,
              valueColor: Colors.red.shade700,
            ),
            _profileTile(context, 'Height', '${patient.height}cm', itemWidth),
            _profileTile(context, 'Weight', '${patient.weight}kg', itemWidth),
          ],
        );
      },
    );
  }

  Widget _profileTile(
    BuildContext context,
    String label,
    String value,
    double width, {
    Color valueColor = const Color(0xFF6F6575),
  }) {
    return SizedBox(
      width: width,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 16),
        decoration: BoxDecoration(
          color: const Color(0xFFF8FAFC),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0xFFE0E7EF)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Text(
              label,
              style: const TextStyle(
                fontSize: 14,
                color: Color(0xFF8EA0BA),
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 8),
            FittedBox(
              fit: BoxFit.scaleDown,
              child: Text(
                value,
                maxLines: 1,
                style: TextStyle(
                  fontSize: Responsive.scale(context, 30),
                  fontWeight: FontWeight.w900,
                  color: valueColor,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _navButton({
    required String text,
    required IconData icon,
    required VoidCallback onPressed,
  }) {
    return OutlinedButton.icon(
      onPressed: onPressed,
      icon: Icon(icon),
      style: OutlinedButton.styleFrom(
        minimumSize: const Size.fromHeight(56),
        alignment: Alignment.centerLeft,
        foregroundColor: Colors.black,
        side: const BorderSide(color: Color(0xFFE0E7EF)),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
        ),
      ),
      label: Align(
        alignment: Alignment.centerLeft,
        child: Text(
          text,
          style: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w800,
          ),
        ),
      ),
    );
  }
}
// ===================================================================
// Patient History Page
// ===================================================================

class PatientHistoryPage extends StatelessWidget {
  final Patient patient;

  const PatientHistoryPage({
    super.key,
    required this.patient,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF4F8F6),

      appBar: AppBar(
        title: const Text("Patient History"),
        backgroundColor: Colors.blue,
        foregroundColor: Colors.white,
        actions: const [DoctorReviewNotificationBell()],
      ),

      body: Padding(
        padding: Responsive.pagePadding(context),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [

            // Patient Information Card
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20),
              ),

              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    patient.name,
                    style: const TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                    ),
                  ),

                  const SizedBox(height: 12),

                  Text("Ward: ${patient.wardRoomNo}"),
                  Text("Age: ${patient.age}"),
                  Text("Blood Type: ${patient.bloodType}"),
                ],
              ),
            ),

            const SizedBox(height: 24),

            const Text(
              "Medical History",
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
              ),
            ),

            const SizedBox(height: 16),

            Expanded(
              child: FutureBuilder<List<Map<String, dynamic>>>(
                future: PatientSupabaseService.getPatientConditions(patient.id),
                builder: (context, snapshot) {
                  if (!snapshot.hasData) {
                    return const Center(child: CircularProgressIndicator());
                  }

                  final data = snapshot.data!;

                  if (data.isEmpty) {
                    return const Center(
                      child: Text("No medical history available yet."),
                    );
                  }

                  return ListView.builder(
                    itemCount: data.length,
                    itemBuilder: (context, index) {
                      final item = data[index];

                      return Card(
                        child: ListTile(
                          title: Text('Date: ${item['date'] ?? '-'}'),

                          trailing: const Icon(Icons.arrow_forward_ios),

                          onTap: () {
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (_) => PatientConditionDetailPage(
                                  patient: patient,
                                  data: item,
                                ),
                              ),
                            );
                          },
                        ),
                      );
                    },
                  );
                },
              ),
            ),

            const SizedBox(height: 24),

            SizedBox(
              width: double.infinity,
              height: 56,
              child: ElevatedButton(
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => EgfrGraphPage(patient: patient),
                    ),
                  );
                },

                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.blue,
                  foregroundColor: Colors.white,
                ),

                child: const Text(
                  "View eGFR History",
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
