import 'package:flutter/material.dart';
import '../models/models.dart';
import '../widgets/review_notification_bell.dart';

/// Shows all verified (approved) plans for a single patient
class VerifiedHistoryPage extends StatelessWidget {
  final String patientId;
  final String patientName;
  final List<VerifiedPlan> entries;

  const VerifiedHistoryPage({
    super.key,
    required this.patientId,
    required this.patientName,
    required this.entries,
  });

  void _goHome(BuildContext context) {
    Navigator.of(context).popUntil((route) => route.isFirst);
  }

  @override
  Widget build(BuildContext context) {
    final list = entries.reversed.toList(); // newest first
    return Scaffold(
      appBar: AppBar(
        title: Text('$patientName — Verified History'),
        actions: const [PharmacistDecisionNotificationBell()],
      ),
      body: list.isEmpty
          ? const Center(child: Text('No verified entries yet.'))
          : ListView.builder(
              itemCount: list.length,
              itemBuilder: (_, i) {
                final e = list[i];
                return Card(
                  margin:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  child: ListTile(
                    title: Text(
                      e.medicines.isNotEmpty
                          ? (e.medicines[0]['name'] ?? 'Unknown medicine')
                          : 'No medicine',
                    ),
                    subtitle: Text(
                      'Date: ${e.date ?? 'No date'}',
                    ),
                  ),
                );
              },
            ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(12.0),
          child: SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: () => _goHome(context),
              child: const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text('Home'),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
