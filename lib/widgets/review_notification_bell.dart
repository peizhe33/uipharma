import 'dart:async';

import 'package:flutter/material.dart';

import '../services/patient_supabase_service.dart';

class DoctorReviewNotificationBell extends StatefulWidget {
  const DoctorReviewNotificationBell({super.key});

  @override
  State<DoctorReviewNotificationBell> createState() =>
      _DoctorReviewNotificationBellState();
}

class _DoctorReviewNotificationBellState
    extends State<DoctorReviewNotificationBell> {
  List<Map<String, dynamic>> _items = [];
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _load();
    _timer = Timer.periodic(const Duration(seconds: 8), (_) => _load());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final items = await PatientSupabaseService.getDoctorReviewNotifications();
      if (mounted) setState(() => _items = items);
    } catch (_) {
      if (mounted) setState(() => _items = []);
    }
  }

  Future<void> _open() async {
    if (_items.isEmpty) return;

    if (_items.length == 1) {
      await _showDoctorReviewDialog(context, _items.first);
    } else {
      final selected = await showDialog<Map<String, dynamic>>(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Pharmacist Reviews'),
          insetPadding: const EdgeInsets.symmetric(
            horizontal: 16,
            vertical: 24,
          ),
          content: SizedBox(
            width: _dialogWidth(context, maxWidth: 420),
            child: ListView.separated(
              shrinkWrap: true,
              itemCount: _items.length,
              separatorBuilder: (_, _) => const Divider(height: 1),
              itemBuilder: (_, index) {
                final item = _items[index];
                return ListTile(
                  leading: const Icon(Icons.priority_high, color: Colors.red),
                  title: Text(
                    (item['patient_name'] ?? 'Unknown patient').toString(),
                  ),
                  subtitle: Text(_firstMedicineLine(item)),
                  onTap: () => Navigator.pop(context, item),
                );
              },
            ),
          ),
        ),
      );

      if (selected != null && mounted) {
        await _showDoctorReviewDialog(context, selected);
      }
    }

    await _load();
  }

  @override
  Widget build(BuildContext context) {
    return _NotificationPill(
      count: _items.length,
      icon: Icons.notifications_active,
      tooltip: 'Pharmacist review notifications',
      onTap: _open,
    );
  }
}

class PharmacistDecisionNotificationBell extends StatefulWidget {
  const PharmacistDecisionNotificationBell({super.key});

  @override
  State<PharmacistDecisionNotificationBell> createState() =>
      _PharmacistDecisionNotificationBellState();
}

class _PharmacistDecisionNotificationBellState
    extends State<PharmacistDecisionNotificationBell> {
  List<Map<String, dynamic>> _items = [];
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _load();
    _timer = Timer.periodic(const Duration(seconds: 8), (_) => _load());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final items =
          await PatientSupabaseService.getPharmacistDecisionNotifications();
      if (mounted) setState(() => _items = items);
    } catch (_) {
      if (mounted) setState(() => _items = []);
    }
  }

  Future<void> _open() async {
    if (_items.isEmpty) return;

    if (_items.length == 1) {
      await _showPharmacistDecisionDialog(context, _items.first);
    } else {
      final selected = await showDialog<Map<String, dynamic>>(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Doctor Rejections'),
          insetPadding: const EdgeInsets.symmetric(
            horizontal: 16,
            vertical: 24,
          ),
          content: SizedBox(
            width: _dialogWidth(context, maxWidth: 420),
            child: ListView.separated(
              shrinkWrap: true,
              itemCount: _items.length,
              separatorBuilder: (_, _) => const Divider(height: 1),
              itemBuilder: (_, index) {
                final item = _items[index];
                return ListTile(
                  leading: const Icon(Icons.cancel, color: Colors.red),
                  title: Text(
                    (item['patient_name'] ?? 'Unknown patient').toString(),
                  ),
                  subtitle: Text(_doctorDecisionText(item)),
                  onTap: () => Navigator.pop(context, item),
                );
              },
            ),
          ),
        ),
      );

      if (selected != null && mounted) {
        await _showPharmacistDecisionDialog(context, selected);
      }
    }

    await _load();
  }

  @override
  Widget build(BuildContext context) {
    return _NotificationPill(
      count: _items.length,
      icon: Icons.mark_email_unread,
      tooltip: 'Doctor rejection notifications',
      onTap: _open,
    );
  }
}

double _dialogWidth(BuildContext context, {double maxWidth = 540}) {
  final screenWidth = MediaQuery.sizeOf(context).width;
  final availableWidth = screenWidth < 360
      ? screenWidth - 32
      : screenWidth - 64;
  return availableWidth.clamp(240.0, maxWidth).toDouble();
}

class _NotificationPill extends StatelessWidget {
  final int count;
  final IconData icon;
  final String tooltip;
  final VoidCallback onTap;

  const _NotificationPill({
    required this.count,
    required this.icon,
    required this.tooltip,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final hasItems = count > 0;

    return Padding(
      padding: const EdgeInsets.only(right: 10),
      child: Tooltip(
        message: tooltip,
        child: InkWell(
          borderRadius: BorderRadius.circular(999),
          onTap: hasItems ? onTap : null,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 250),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: hasItems ? Colors.red.shade600 : Colors.white24,
              borderRadius: BorderRadius.circular(999),
              border: Border.all(
                color: hasItems ? Colors.white : Colors.white38,
                width: 1.2,
              ),
              boxShadow: hasItems
                  ? [
                      BoxShadow(
                        color: Colors.red.withValues(alpha: 0.35),
                        blurRadius: 12,
                        offset: const Offset(0, 3),
                      ),
                    ]
                  : null,
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon, color: Colors.white, size: 22),
                if (hasItems) ...[
                  const SizedBox(width: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 7,
                      vertical: 2,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text(
                      count.toString(),
                      style: TextStyle(
                        color: Colors.red.shade700,
                        fontWeight: FontWeight.w900,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

Future<void> _showDoctorReviewDialog(
  BuildContext context,
  Map<String, dynamic> item,
) async {
  final reasonController = TextEditingController();
  final patientId = (item['patient_id'] ?? '').toString();
  final latestCondition =
      await PatientSupabaseService.getLatestPatientCondition(patientId);
  var medicines = _latestMedicineList(_medicinesFrom(item));

  if (!context.mounted) return;

  await showDialog<void>(
    context: context,
    builder: (dialogContext) {
      String decision = 'approved';
      bool saving = false;

      return StatefulBuilder(
        builder: (context, setDialogState) {
          Future<void> submit() async {
            final reason = reasonController.text.trim();
            if (decision == 'rejected' && reason.isEmpty) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Please write the rejection reason'),
                ),
              );
              return;
            }

            setDialogState(() => saving = true);
            try {
              await PatientSupabaseService.submitDoctorReviewDecision(
                reviewId: (item['id'] ?? '').toString(),
                prescriptionId: (item['prescription_id'] ?? '').toString(),
                status: decision,
                medicines: medicines,
                doctorReason: reason.isEmpty
                    ? 'Doctor approved the revised prescription.'
                    : reason,
              );

              if (dialogContext.mounted) Navigator.pop(dialogContext);
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      decision == 'approved'
                          ? 'Approved. Saved to verified list.'
                          : 'Rejected. Reason sent to pharmacist.',
                    ),
                  ),
                );
              }
            } catch (e) {
              setDialogState(() => saving = false);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('Unable to send decision: $e')),
              );
            }
          }

          return AlertDialog(
            insetPadding: const EdgeInsets.symmetric(
              horizontal: 16,
              vertical: 24,
            ),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
            ),
            title: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.red.shade50,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(
                    Icons.notification_important,
                    color: Colors.red.shade700,
                  ),
                ),
                const SizedBox(width: 10),
                const Expanded(child: Text('Pharmacist Sent Review')),
              ],
            ),
            content: SizedBox(
              width: _dialogWidth(context),
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _InfoBlock(
                      title: 'Patient',
                      lines: [
                        (item['patient_name'] ?? '-').toString(),
                        'Patient ID: $patientId',
                      ],
                    ),
                    _InfoBlock(
                      title: 'Patient Condition',
                      lines: [_conditionText(latestCondition)],
                    ),
                    _InfoBlock(
                      title: 'Pharmacist Reason',
                      lines: [_pharmacistReason(medicines)],
                    ),
                    _EditablePrescriptionCard(
                      medicines: medicines,
                      onChanged: (updated) => medicines = updated,
                    ),
                    const SizedBox(height: 8),
                    SegmentedButton<String>(
                      segments: const [
                        ButtonSegment(
                          value: 'approved',
                          icon: Icon(Icons.check_circle_outline),
                          label: Text('Approve'),
                        ),
                        ButtonSegment(
                          value: 'rejected',
                          icon: Icon(Icons.cancel_outlined),
                          label: Text('Reject'),
                        ),
                      ],
                      selected: {decision},
                      onSelectionChanged: saving
                          ? null
                          : (value) {
                              setDialogState(() {
                                decision = value.first;
                              });
                            },
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: reasonController,
                      minLines: 2,
                      maxLines: 4,
                      decoration: InputDecoration(
                        labelText: decision == 'approved'
                            ? 'Approval note (optional)'
                            : 'Reason for rejecting pharmacist response',
                        border: const OutlineInputBorder(),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: saving ? null : () => Navigator.pop(dialogContext),
                child: const Text('Later'),
              ),
              ElevatedButton.icon(
                onPressed: saving ? null : submit,
                icon: saving
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.send),
                label: const Text('Send Decision'),
              ),
            ],
          );
        },
      );
    },
  );

  reasonController.dispose();
}

Future<void> _showPharmacistDecisionDialog(
  BuildContext context,
  Map<String, dynamic> item,
) async {
  final reasonController = TextEditingController();
  final patientId = (item['patient_id'] ?? '').toString();
  final latestCondition =
      await PatientSupabaseService.getLatestPatientCondition(patientId);
  var medicines = _latestMedicineList(_medicinesFrom(item));

  if (!context.mounted) return;

  await showDialog<void>(
    context: context,
    builder: (dialogContext) {
      String decision = 'approved';
      bool saving = false;

      return StatefulBuilder(
        builder: (context, setDialogState) {
          Future<void> submit() async {
            final reason = reasonController.text.trim();
            

            setDialogState(() => saving = true);
            try {
              await PatientSupabaseService.submitPharmacistReviewDecision(
                reviewId: (item['id'] ?? '').toString(),
                prescriptionId: (item['prescription_id'] ?? '').toString(),
                status: decision,
                medicines: medicines,
                pharmacistReason: reason.isEmpty
                    ? 'Pharmacist approved the revised prescription.'
                    : reason,
              );

              if (dialogContext.mounted) Navigator.pop(dialogContext);
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      decision == 'approved'
                          ? 'Approved. Saved to verified list.'
                          : 'Response sent back to doctor for review.',
                    ),
                  ),
                );
              }
            } catch (e) {
              setDialogState(() => saving = false);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('Unable to send response: $e')),
              );
            }
          }

          return AlertDialog(
            insetPadding: const EdgeInsets.symmetric(
              horizontal: 16,
              vertical: 24,
            ),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
            ),
            title: Row(
              children: [
                Icon(Icons.report_problem, color: Colors.red.shade700),
                const SizedBox(width: 10),
                const Expanded(child: Text('Doctor Rejected')),
              ],
            ),
            content: SizedBox(
              width: _dialogWidth(context),
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _InfoBlock(
                      title: 'Patient',
                      lines: [
                        (item['patient_name'] ?? '-').toString(),
                        'Patient ID: $patientId',
                      ],
                    ),
                    _InfoBlock(
                      title: 'Patient Condition',
                      lines: [_conditionText(latestCondition)],
                    ),
                    _InfoBlock(
                      title: 'Doctor Decision Reason',
                      lines: [_doctorReason(medicines)],
                    ),
                    _EditablePrescriptionCard(
                      medicines: medicines,
                      onChanged: (updated) => medicines = updated,
                    ),
                    const SizedBox(height: 8),
                    SegmentedButton<String>(
                      segments: const [
                        ButtonSegment(
                          value: 'approved',
                          icon: Icon(Icons.check_circle_outline),
                          label: Text('Approve'),
                        ),
                        ButtonSegment(
                          value: 'rejected',
                          icon: Icon(Icons.cancel_outlined),
                          label: Text('Reject'),
                        ),
                      ],
                      selected: {decision},
                      onSelectionChanged: saving
                          ? null
                          : (value) {
                              setDialogState(() => decision = value.first);
                            },
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: reasonController,
                      minLines: 2,
                      maxLines: 4,
                      decoration: InputDecoration(
                        labelText: decision == 'approved'
                            ? 'Approval note (optional)'
                            : 'Reason for rejecting doctor response',
                        border: const OutlineInputBorder(),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: saving ? null : () => Navigator.pop(dialogContext),
                child: const Text('Later'),
              ),
              ElevatedButton.icon(
                onPressed: saving ? null : submit,
                icon: saving
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.send),
                label: const Text('Send Response'),
              ),
            ],
          );
        },
      );
    },
  );

  reasonController.dispose();
}

class _InfoBlock extends StatelessWidget {
  final String title;
  final List<String> lines;

  const _InfoBlock({required this.title, required this.lines});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFE0E7EF)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontWeight: FontWeight.w900,
              color: Color(0xFF334155),
            ),
          ),
          const SizedBox(height: 6),
          ...lines.map(
            (line) => Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(line.isEmpty ? '-' : line),
            ),
          ),
        ],
      ),
    );
  }
}

class _EditablePrescriptionCard extends StatefulWidget {
  final List<Map<String, dynamic>> medicines;
  final ValueChanged<List<Map<String, dynamic>>> onChanged;

  const _EditablePrescriptionCard({
    required this.medicines,
    required this.onChanged,
  });

  @override
  State<_EditablePrescriptionCard> createState() =>
      _EditablePrescriptionCardState();
}

class _EditablePrescriptionCardState extends State<_EditablePrescriptionCard> {
  late List<Map<String, dynamic>> _items;
  final Map<int, TextEditingController> _nameControllers = {};
  final Map<int, TextEditingController> _doseControllers = {};
  final Map<int, String> _decisions = {};

  static const _baseUnits = ['mg', 'g', 'ml', 'IU', 'mcg'];
  static const _baseFrequencies = [
    'Once a day',
    'Twice a day',
    'Three times a day',
    'Every 6 hours',
    'Every 8 hours',
  ];

  @override
  void initState() {
    super.initState();
    _items = _latestMedicineList(widget.medicines);
    for (var i = 0; i < _items.length; i++) {
      _nameControllers[i] = TextEditingController(
        text: (_items[i]['name'] ?? '').toString(),
      );
      _doseControllers[i] = TextEditingController(
        text: (_items[i]['dose'] ?? '').toString(),
      );
    }
    widget.onChanged(_copyItems());
  }

  @override
  void dispose() {
    for (final controller in _nameControllers.values) {
      controller.dispose();
    }
    for (final controller in _doseControllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  List<Map<String, dynamic>> _copyItems() =>
      _items.map((item) => Map<String, dynamic>.from(item)).toList();

  List<String> _optionsWithCurrent(List<String> base, String current) {
    if (current.isEmpty || base.contains(current)) return base;
    return [current, ...base];
  }

  void _update(int index, String key, dynamic value) {
    setState(() {
      _items[index][key] = value;
      if (key == 'name') {
        _items[index]['pharmacist_suggested_medicine'] = value;
      } else if (key == 'dose') {
        _items[index]['pharmacist_suggested_dose'] = value;
      } else if (key == 'unit') {
        _items[index]['pharmacist_suggested_unit'] = value;
      } else if (key == 'frequency') {
        _items[index]['pharmacist_suggested_frequency'] = value;
      }
    });
    widget.onChanged(_copyItems());
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFE0E7EF)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Prescription Details',
            style: TextStyle(
              fontWeight: FontWeight.w900,
              color: Color(0xFF334155),
            ),
          ),
          const SizedBox(height: 10),
          if (_items.isEmpty)
            const Text('No prescription details found.')
          else
            ...List.generate(_items.length, (index) {
              final item = _items[index];
              final isRejected =
                item['status'] == 'rejected';

              final unit = (item['unit'] ?? 'mg').toString();
              final frequency = (item['frequency'] ?? 'Once a day').toString();
              final currentDecision = _decisions[index] ?? 'approved';

              if (!isRejected) {
                return Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.green.shade50,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.green),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item['name'] ?? '',
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Text(
                        '${item['dose']} ${item['unit']} • ${item['frequency']}',
                      ),
                      const SizedBox(height: 8),
                      const Row(
                        children: [
                          Icon(Icons.check_circle, color: Colors.green),
                          SizedBox(width: 6),
                          Text('Approved by Pharmacist'),
                        ],
                      ),
                    ],
                  ),
                );
              }
              return Padding(
                padding: EdgeInsets.only(top: index == 0 ? 0 : 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    TextField(
                      controller: _nameControllers[index],
                      decoration: const InputDecoration(
                        labelText: 'Medicine',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      onChanged: (value) => _update(index, 'name', value),
                    ),
                    const SizedBox(height: 8),
                    LayoutBuilder(
                      builder: (context, constraints) {
                        final doseField = TextField(
                          controller: _doseControllers[index],
                          decoration: const InputDecoration(
                            labelText: 'Dose',
                            border: OutlineInputBorder(),
                            isDense: true,
                          ),
                          onChanged: (value) => _update(index, 'dose', value),
                        );
                        final unitField = DropdownButtonFormField<String>(
                          initialValue: unit,
                          isExpanded: true,
                          items: _optionsWithCurrent(_baseUnits, unit)
                              .map(
                                (value) => DropdownMenuItem(
                                  value: value,
                                  child: Text(value),
                                ),
                              )
                              .toList(),
                          onChanged: (value) =>
                              _update(index, 'unit', value ?? unit),
                          decoration: const InputDecoration(
                            labelText: 'Unit',
                            border: OutlineInputBorder(),
                            isDense: true,
                          ),
                        );

                        if (constraints.maxWidth < 320) {
                          return Column(
                            children: [
                              doseField,
                              const SizedBox(height: 8),
                              unitField,
                            ],
                          );
                        }

                        return Row(
                          children: [
                            Expanded(flex: 2, child: doseField),
                            const SizedBox(width: 8),
                            Expanded(child: unitField),
                          ],
                        );
                      },
                    ),
                    const SizedBox(height: 8),
                    DropdownButtonFormField<String>(
                      initialValue: frequency,
                      isExpanded: true,
                      items: _optionsWithCurrent(_baseFrequencies, frequency)
                          .map(
                            (value) => DropdownMenuItem(
                              value: value,
                              child: Text(value),
                            ),
                          )
                          .toList(),
                      onChanged: (value) =>
                          _update(index, 'frequency', value ?? frequency),
                      decoration: const InputDecoration(
                        labelText: 'Frequency',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                    ),
                    CheckboxListTile(
                      contentPadding: EdgeInsets.zero,
                      dense: true,
                      title: const Text('PRN (As needed)'),
                      value: item['prn'] == true,
                      onChanged: (value) =>
                          _update(index, 'prn', value ?? false),
                    ),

                    const SizedBox(height: 8),

                    SegmentedButton<String>(
                      segments: const [
                        ButtonSegment(
                          value: 'approved',
                          icon: Icon(Icons.check_circle_outline),
                          label: Text('Approve'),
                        ),
                        ButtonSegment(
                          value: 'rejected',
                          icon: Icon(Icons.cancel_outlined),
                          label: Text('Reject'),
                        ),
                      ],
                      selected: {_decisions[index] ?? 'approved'},
                      onSelectionChanged: (value) {
                        setState(() {
                          _decisions[index] = value.first;
                        });
                      },
                    ),
                  ],
                ),
              );
            }),
        ],
      ),
    );
  }
}

List<Map<String, dynamic>> _medicinesFrom(Map<String, dynamic> item) {
  final raw = item['medicines'];
  if (raw is List) {
    return raw.map((entry) => Map<String, dynamic>.from(entry as Map)).toList();
  }
  return const [];
}

List<Map<String, dynamic>> _latestMedicineList(
  List<Map<String, dynamic>> medicines,
) {
  return medicines.map((med) {
    final name = _textOr(
      med['pharmacist_suggested_medicine'],
      med['name'],
      fallback: '-',
    );
    final dose = _textOr(med['pharmacist_suggested_dose'], med['dose']);
    final unit = _textOr(
      med['pharmacist_suggested_unit'],
      med['unit'],
      fallback: 'mg',
    );
    final frequency = _textOr(
      med['pharmacist_suggested_frequency'],
      med['frequency'],
      fallback: 'Once a day',
    );

    return {
      ...med,
      'status': med['status'] ?? 'approved',
      'name': name,
      'dose': dose,
      'unit': unit,
      'frequency': frequency,
      'prn': med['prn'] ?? false,
      'pharmacist_suggested_medicine': name,
      'pharmacist_suggested_dose': dose,
      'pharmacist_suggested_unit': unit,
      'pharmacist_suggested_frequency': frequency,
    };
  }).toList();
}

String _textOr(dynamic preferred, dynamic secondary, {String fallback = ''}) {
  final preferredText = (preferred ?? '').toString().trim();
  if (preferredText.isNotEmpty) return preferredText;
  final fallbackValue = (secondary ?? '').toString().trim();
  if (fallbackValue.isNotEmpty) return fallbackValue;
  return fallback;
}

String _firstMedicineLine(Map<String, dynamic> item) {
  final medicines = _latestMedicineList(_medicinesFrom(item));
  if (medicines.isEmpty) return 'Prescription review needed';
  return medicines
      .map((med) {
        return '${med['name'] ?? '-'} ${med['dose'] ?? ''}${med['unit'] ?? ''}';
      })
      .join(', ');
}

String _conditionText(Map<String, dynamic>? condition) {
  if (condition == null) return 'No latest condition found.';
  final lines = [
    'Date: ${condition['date'] ?? '-'}',
    'Condition: ${condition['condition'] ?? '-'}',
    'BP: ${condition['blood_pressure'] ?? '-'}  HR: ${condition['heart_rate'] ?? '-'}  SpO2: ${condition['oxygen_saturation'] ?? '-'}',
    'eGFR: ${condition['egfr'] ?? '-'}  Creatinine: ${condition['creatinine'] ?? '-'}',
  ];
  return lines.join('\n');
}

String _pharmacistReason(List<Map<String, dynamic>> medicines) {
  for (final med in medicines) {
    final reason = (med['pharmacist_rejection_reason'] ?? '').toString();
    if (reason.trim().isNotEmpty) return reason;
  }
  return 'No reason provided.';
}

String _doctorReason(List<Map<String, dynamic>> medicines) {
  for (final med in medicines) {
    final reason = (med['doctor_reason'] ?? '').toString();
    if (reason.trim().isNotEmpty) return reason;
  }
  return 'No reason provided.';
}

String _doctorDecisionText(Map<String, dynamic> item) {
  return 'Doctor rejected. Pharmacist response needed.';
}
