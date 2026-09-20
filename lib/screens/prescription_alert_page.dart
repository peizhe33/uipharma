import 'dart:convert';
import 'dart:convert';

import 'package:flutter/material.dart';
import '../models/models.dart';
import '../services/patient_supabase_service.dart';
import '../widgets/responsive.dart';

enum AlertSeverity { high, medium, low }

enum AlertCategory { allergy, dosing, other }

class _AlertMatch {
  final AlertCategory category;
  final AlertSeverity severity;
  final String title;
  final String summary;
  final String issueType;

  const _AlertMatch({
    required this.category,
    required this.severity,
    required this.title,
    required this.summary,
    required this.issueType,
  });
}

class Citation {
  final String id;
  final String source;
  final String note;
  const Citation({required this.id, required this.source, required this.note});
}

class PrescriptionAlert {
  final AlertCategory category;
  final AlertSeverity severity;
  final String title;
  final String summary;
  final String details;
  final List<Citation> citations;

  PrescriptionAlert({
    required this.category,
    required this.severity,
    required this.title,
    required this.summary,
    required this.details,
    this.citations = const [],
  });
}

class PrescriptionAlertPage extends StatefulWidget {
  final Patient patient;
  final PatientVitals vitals;

  /// Doctor's original list:
  /// {'name','dose','unit','frequency','prn'}
  final List<Map<String, dynamic>> prescribedMeds;
  final List<Map<String, dynamic>> retrievedDocs;

  final String? verificationResult;

  /// Structured report from the backend (contains ai_suggestion, alerts, etc.)
  final Map<String, dynamic>? report;

  /// demoMode=true => show "(demo)" + placeholder citations
  /// demoMode=false => remove demo words (for future AI)
  final bool demoMode;

  const PrescriptionAlertPage({
    super.key,
    required this.patient,
    required this.vitals,
    required this.prescribedMeds,
    this.verificationResult,
    this.report,
    this.retrievedDocs = const [],
    this.demoMode = true,
  });

  @override
  State<PrescriptionAlertPage> createState() => _PrescriptionAlertPageState();
}

class _PrescriptionAlertPageState extends State<PrescriptionAlertPage> {
  List<PrescriptionAlert> _alerts = [];

  String? _selectedReason;
  String _decision = 'Use AI suggestion';
  final TextEditingController _otherReasonCtrl = TextEditingController();

  final Set<int> _expanded = {};

  late final List<TextEditingController> _aiNameCtrls;
  late final List<TextEditingController> _aiDoseCtrls;
  late final List<String> _aiUnits;
  late final List<String> _aiFreqs;
  late final List<bool> _aiPrn;

  late String _aiExplanation;
  late List<Citation> _aiCitations;

  /// Per-drug action label from the backend ai_suggestion
  /// ('continue', 'adjust', 'switch', 'discontinue')
  late final List<String> _aiActions;

  /// Per-drug rationale text from the backend ai_suggestion
  late final List<String> _aiRationales;

  /// Per-drug route from the backend ai_suggestion
  late final List<String> _aiRoutes;

  static const _doseUnits = [
    'g',
    'mg',
    'mcg',
    'mL',
    'tsp',
    'tbsp',
    'IU',
    'units',
    'mg/kg',
    'mcg/kg',
  ];

  static const _freqOptions = [
    'Once a day',
    'Twice a day',
    'Three times a day',
    'Every 4 hours',
    'Every 6 hours',
    'Every 8 hours',
    'Every 12 hours',
    'Every 24 hours',
    'Every 48 hours',
    'Every 72 hours',
  ];

  static const _routeOptions = [
    'PO',
    'IV',
    'IM',
    'SC',
    'Topical',
    'Inhaled',
    'PR',
    'SL',
  ];

  /// Convert backend normalised frequency (q24H, q8H, etc.) to dropdown label.
  static String _backendFreqToDropdown(String freq) {
    final f = freq.trim().toUpperCase();
    const map = {
      'Q4H':  'Every 4 hours',
      'Q6H':  'Every 6 hours',
      'Q8H':  'Every 8 hours',
      'Q12H': 'Every 12 hours',
      'Q24H': 'Once a day',
      'Q48H': 'Every 48 hours',
      'Q72H': 'Every 72 hours',
    };
    if (map.containsKey(f)) return map[f]!;
    // Also handle the human-readable forms already in the dropdown
    for (final opt in _freqOptions) {
      if (opt.toLowerCase() == freq.toLowerCase()) return opt;
    }
    // Fallback: return as-is (will still display, just won't match dropdown)
    return freq;
  }

  String _demoTag(String s) => widget.demoMode ? '$s (demo)' : s;

  @override
  void initState() {
    super.initState();

    debugPrint("=== INIT STATE ===");
    debugPrint("verificationResult: ${widget.verificationResult}");
    debugPrint(
      "verificationResult isEmpty: ${widget.verificationResult?.isEmpty}",
    );
    debugPrint("demoMode: ${widget.demoMode}");

    // ===== PRIORITY 1: Parse backend alerts if provided =====
    if (widget.verificationResult != null &&
        widget.verificationResult!.isNotEmpty) {
      debugPrint("Parsing backend alerts...");
      _alerts = _parseBackendAlerts(widget.verificationResult!);
      debugPrint("Parsed ${_alerts.length} alerts");
    } else {
      debugPrint("No backend alerts, generating demo/fallback alerts...");
      _alerts = _generateAlerts(
        patient: widget.patient,
        meds: widget.prescribedMeds,
        demoMode: widget.demoMode,
      );
    }

    debugPrint("Total alerts: ${_alerts.length}");
    for (int i = 0; i < _alerts.length; i++) {
      debugPrint("Alert $i: ${_alerts[i].title} (${_alerts[i].severity})");
    }

    final suggested = _buildAiSuggestion(widget.patient, widget.prescribedMeds);

    _aiNameCtrls = suggested
        .map((m) => TextEditingController(text: (m['name'] ?? '').toString()))
        .toList();
    _aiDoseCtrls = suggested
        .map((m) => TextEditingController(text: (m['dose'] ?? '').toString()))
        .toList();
    _aiUnits = suggested.map((m) => (m['unit'] ?? 'mg').toString()).toList();
    _aiFreqs = suggested
        .map((m) {
          final raw = (m['frequency'] ?? 'Once a day').toString();
          final mapped = _backendFreqToDropdown(raw);
          // If mapped value is not in dropdown options, fall back to first option
          return _freqOptions.contains(mapped) ? mapped : _freqOptions.first;
        })
        .toList();
    _aiPrn = suggested.map((m) => (m['prn'] ?? false) == true).toList();
    _aiActions = suggested
        .map((m) => (m['action'] ?? 'continue').toString())
        .toList();
    _aiRationales = suggested
        .map((m) => (m['rationale'] ?? '').toString())
        .toList();
    _aiRoutes = suggested
        .map((m) {
          final r = (m['route'] ?? 'PO').toString().toUpperCase();
          return _routeOptions.contains(r) ? r : 'PO';
        })
        .toList();

    _aiExplanation = _demoTag(
      "AI summary:\n"
      "• Reviewed patient profile, dose inputs, and recorded allergy information.\n"
      "• Generated allergy and dosing alerts based on rule/knowledge checks.\n"
      "• Suggested an alternative regimen where risk is high, but pharmacist approval is required.",
    );

    _aiCitations = widget.demoMode
        ? const [
            Citation(
              id: "[1]",
              source: "Local guideline / formulary (placeholder)",
              note: "Used to justify dose limit / contraindication checks.",
            ),
            Citation(
              id: "[2]",
              source: "Drug monograph / label (placeholder)",
              note: "Used to justify allergy/cross-sensitivity warnings.",
            ),
          ]
        : const [];
  }

  // Parse backend alerts from the plain-text AI answer without changing
  // the answer text shown in the AI Explanation & Citations box.
  List<PrescriptionAlert> _parseBackendAlerts(String answerText) {
    final parsedByIssue = <String, PrescriptionAlert>{};
    try {
      debugPrint("Raw answer input length: ${answerText.length}");

      for (final msg in _extractDoctorIssueLines(answerText)) {
        debugPrint("Processing alert: $msg");

        final match = _classifyAlert(msg);
        if (match == null) continue;
        final key = _alertIssueKey(msg, match);
        final alert = PrescriptionAlert(
          category: match.category,
          severity: match.severity,
          title: match.title,
          summary: match.summary,
          details: msg,
        );
        final existing = parsedByIssue[key];
        if (existing == null ||
            _severityRank(alert.severity) > _severityRank(existing.severity) ||
            (_severityRank(alert.severity) ==
                    _severityRank(existing.severity) &&
                alert.details.length > existing.details.length)) {
          parsedByIssue[key] = alert;
        }
      }

      debugPrint("Final parsed alerts: ${parsedByIssue.length}");
    } catch (e) {
      debugPrint("Error parsing alerts: $e");
    }
    return parsedByIssue.values.toList();
  }

  List<String> _extractDoctorIssueLines(String answerText) {
    final lines = <String>[];
    String currentDrug = '';
    for (final raw in answerText.split('\n')) {
      final line = _cleanAlertLine(raw);
      if (line.isEmpty || _isInfoOnlyLine(line)) continue;
      final sectionDrug = _drugFromSectionHeader(line);
      if (sectionDrug.isNotEmpty) {
        currentDrug = sectionDrug;
        continue;
      }
      if (_looksLikeDoctorPrescriptionIssue(line)) {
        if (currentDrug.isNotEmpty &&
            !_normalizeAlertText(line).contains(currentDrug)) {
          lines.add('$currentDrug: $line');
        } else {
          lines.add(line);
        }
      }
    }
    debugPrint("Extracted ${lines.length} alert lines from answer.");
    return lines;
  }

  String _cleanAlertLine(String raw) {
    return raw
        .trim()
        .replaceFirst(RegExp(r'^[\-\*\u2022\s]+'), '')
        .replaceAll('⚠ ', '')
        .replaceAll('⚠', '')
        .trim();
  }

  bool _isInfoOnlyLine(String line) {
    final upper = line.toUpperCase();
    final isSectionOrSummary =
        upper.startsWith('ASSESSMENT:') ||
        upper.startsWith('DIAGNOSIS:') ||
        upper.startsWith('RECOMMENDATION:') ||
        upper.startsWith('MONITORING:') ||
        upper.startsWith('VERIFICATION:') ||
        upper.startsWith('CLINICAL FLAGS:') ||
        upper.startsWith('ISSUES:');
    return upper.startsWith('INFO:') ||
        upper.startsWith('SPELL_CORRECTION') ||
        upper.startsWith('SPELL CORRECTION') ||
        isSectionOrSummary ||
        upper.contains('ASSESSMENT: SAFE') ||
        upper == 'ISSUES: NONE' ||
        upper == 'NONE' ||
        upper == 'RECOMMENDATION: CONTINUE';
  }

  bool _looksLikeDoctorPrescriptionIssue(String line) {
    final upper = line.toUpperCase();
    const markers = [
      'ALERT:',
      'CRITICAL',
      'WARNING',
      'UNSAFE',
      'INCORRECT',
      'CONTRAINDICAT',
      'CROSS-SENSITIVITY',
      'CROSS REACTIVITY',
      'CLASS OVERLAP',
      'THERAPEUTIC REDUNDANCY',
      'DUPLICATION',
      'INTERACTION',
      'NOT FIRST-LINE',
      'NOT ROUTINELY INDICATED',
      'NOT ROUTINELY USED',
      'NOT_INDICATED',
      'NOT INDICATED',
      'NOT LISTED',
      'NOT IN GUIDELINE',
      'RETRIEVAL FAILED',
      'SITE-RESTRICTED',
      'SITE RESTRICTED',
      'RESTRICTED ANTIBIOTIC',
      'DOES NOT MATCH',
      'FREQUENCY DOES NOT MATCH',
      'EXCEEDS MAXIMUM',
      'EXCEEDS RECOMMENDED',
      'PRN',
      'RENAL',
      'EGFR',
      'GFR',
      'CAUTION',
      'USE WITH CAUTION',
      'DOSE ADJUSTMENT NEEDED',
      'LIVER FAILURE',
      'PREGNANCY',
      'BREASTFEEDING',
      'G6PD',
      'TREATMENT FAILURE',
      'INAPPROPRIATE FOR',
    ];
    return markers.any(upper.contains);
  }

  bool _hasAny(String upper, List<String> words) =>
      words.any((word) => upper.contains(word));

  int _severityRank(AlertSeverity severity) {
    switch (severity) {
      case AlertSeverity.high:
        return 3;
      case AlertSeverity.medium:
        return 2;
      case AlertSeverity.low:
        return 1;
    }
  }

  String _normalizeAlertText(String text) {
    return text
        .toLowerCase()
        .replaceAll(RegExp(r'[^a-z0-9\s/-]'), ' ')
        .replaceAll(RegExp(r'\s+'), ' ')
        .trim();
  }

  String _drugFromSectionHeader(String line) {
    final match = RegExp(r'^---\s*(.+?)\s*---$').firstMatch(line.trim());
    if (match == null) return '';
    return _normalizeAlertText(match.group(1) ?? '');
  }

  String _alertDrugKey(String msg) {
    final normalized = _normalizeAlertText(msg);
    for (final med in widget.prescribedMeds) {
      final name = _normalizeAlertText((med['name'] ?? '').toString());
      if (name.isNotEmpty && normalized.contains(name)) return name;
    }
    final prefix = RegExp(r'^([a-z][a-z0-9/-]*)[: ]').firstMatch(normalized);
    return prefix?.group(1) ?? 'unknown';
  }

  String _alertIssueKey(String msg, _AlertMatch match) {
    final drug = _alertDrugKey(msg);
    if (match.issueType == 'class-overlap' ||
        match.issueType == 'duplication') {
      return match.issueType;
    }
    if (match.issueType == 'interaction' && drug == 'unknown') {
      return match.issueType;
    }
    return '${match.issueType}:$drug';
  }

  _AlertMatch? _classifyAlert(String msg) {
    final upper = msg.toUpperCase();

    if (_isInfoOnlyLine(msg)) return null;

    final isDose = _hasAny(upper, [
      'DOSE ALERT',
      'DOSE:',
      'DOSAGE',
      'INCORRECT DOSAGE',
      'DOES NOT MATCH GUIDELINE TARGET',
      'FREQUENCY DOES NOT MATCH',
      'EXCEEDS MAXIMUM',
      'EXCEEDS RECOMMENDED',
    ]);
    final isAllergy = _hasAny(upper, [
      'ALLERGY',
      'CROSS-SENSITIVITY',
      'CROSS REACTIVITY',
      'HYPERSENSITIVITY',
    ]);

    // RED: very serious / critical doctor-prescription problems.
    if (isAllergy && !_hasAny(upper, ['MILD', 'RASH', 'LOW SEVERITY'])) {
      return const _AlertMatch(
        category: AlertCategory.allergy,
        severity: AlertSeverity.high,
        title: 'Allergy Alert',
        summary: 'Potential allergy contraindication detected',
        issueType: 'allergy',
      );
    }

    if (_hasAny(upper, [
      'CRITICAL',
      'VERY HIGH',
      'CONTRAINDICATED',
      'ABSOLUTE CONTRAINDICATION',
      'PRN ALERT',
      'PRN_INAPPROPRIATE',
      'RESTRICTED ANTIBIOTIC',
      'SITE-RESTRICTED',
      'SITE RESTRICTED',
      'DOES NOT PENETRATE KIDNEY TISSUE',
      'INAPPROPRIATE FOR',
      'TREATMENT FAILURE IS LIKELY',
      'EXCEEDS MAXIMUM',
      'EXCEEDS RECOMMENDED MAXIMUM',
      'GFR BELOW 30',
      'EGFR BELOW 30',
      'EGFR < 30',
      'SEVERE RENAL',
      'LIVER FAILURE',
      'PREGNANCY',
      'BREASTFEEDING',
      'G6PD',
      'SEVERE HARM',
      'PATIENT DEATH',
      'FATAL',
    ])) {
      return _AlertMatch(
        category: isDose ? AlertCategory.dosing : AlertCategory.other,
        severity: AlertSeverity.high,
        title: isDose ? 'Maximum Dose Exceeded' : 'Critical Safety Alert',
        summary: isDose
            ? 'Dose exceeds the maximum safe limit'
            : 'Prescription may cause serious patient harm',
        issueType: isDose ? 'dose' : 'critical',
      );
    }

    // ORANGE: middle serious warnings requiring pharmacist/doctor review.
    if (isDose ||
        _hasAny(upper, [
          'WARNING',
          'CLASS OVERLAP',
          'THERAPEUTIC REDUNDANCY',
          'DUPLICATION',
          'INTERACTION',
          'NOT FIRST-LINE',
          'NOT ROUTINELY INDICATED',
          'NOT ROUTINELY USED',
          'NOT_INDICATED',
          'NOT INDICATED',
          'NEGATIVE_INDICATION',
          'NOT LISTED',
          'NOT IN GUIDELINE',
          'RETRIEVAL FAILED',
          'STEWARDSHIP CONCERN',
          'NEEDS REVIEW',
          'REQUIRES REVIEW',
        ])) {
      if (_hasAny(upper, ['CLASS OVERLAP', 'THERAPEUTIC REDUNDANCY'])) {
        return const _AlertMatch(
          category: AlertCategory.other,
          severity: AlertSeverity.medium,
          title: 'Class Overlap',
          summary: 'Therapeutic redundancy requires review',
          issueType: 'class-overlap',
        );
      }
      if (upper.contains('DUPLICATION')) {
        return const _AlertMatch(
          category: AlertCategory.other,
          severity: AlertSeverity.medium,
          title: 'Therapeutic Duplication',
          summary: 'Duplicate or overlapping therapy detected',
          issueType: 'duplication',
        );
      }
      if (upper.contains('INTERACTION')) {
        return const _AlertMatch(
          category: AlertCategory.other,
          severity: AlertSeverity.medium,
          title: 'Drug Interaction',
          summary: 'Potential interaction requires review',
          issueType: 'interaction',
        );
      }
      if (isDose) {
        final issueType = upper.contains('FREQUENCY') ? 'frequency' : 'dose';
        return _AlertMatch(
          category: AlertCategory.dosing,
          severity: AlertSeverity.medium,
          title: 'Incorrect Dosage',
          summary: 'Dose or frequency does not match guideline target',
          issueType: issueType,
        );
      }
      return const _AlertMatch(
        category: AlertCategory.other,
        severity: AlertSeverity.medium,
        title: 'Guideline Warning',
        summary: 'Drug choice is not first-line or not routinely indicated',
        issueType: 'guideline-warning',
      );
    }

    // YELLOW: lower-severity caution alerts. Blue/info-only lines are ignored.
    if (_hasAny(upper, [
      'MILD',
      'RASH',
      'CAUTION',
      'USE WITH CAUTION',
      'MONITOR',
      'RENAL ALERT',
      'RENAL DOSE ADJUSTMENT',
      'EGFR BELOW 60',
      'EGFR < 60',
      'DOSE ADJUSTMENT NEEDED',
      'LOW SEVERITY',
    ])) {
      return _AlertMatch(
        category: isAllergy ? AlertCategory.allergy : AlertCategory.other,
        severity: AlertSeverity.low,
        title: isAllergy ? 'Mild Allergy Caution' : 'Caution Alert',
        summary: isAllergy
            ? 'Mild cross-sensitivity or rash history requires caution'
            : 'Lower-severity caution requires review',
        issueType: isAllergy ? 'allergy' : 'caution',
      );
    }

    return null;
  }

  @override
  void dispose() {
    _otherReasonCtrl.dispose();
    for (final c in _aiNameCtrls) {
      c.dispose();
    }
    for (final c in _aiDoseCtrls) {
      c.dispose();
    }
    super.dispose();
  }

  void _goHome() {
    Navigator.of(context).popUntil((route) => route.isFirst);
  }

  String _safeAllergyText(Patient patient) {
    final dyn = patient as dynamic;
    dynamic raw;
    try {
      raw = dyn.allergyDetails;
    } catch (_) {}
    try {
      raw ??= dyn.allergyDetail;
    } catch (_) {}
    try {
      raw ??= dyn.allergy;
    } catch (_) {}
    try {
      raw ??= dyn.allergies;
    } catch (_) {}
    try {
      raw ??= dyn.allergyHistory;
    } catch (_) {}
    try {
      raw ??= dyn.allergyNotes;
    } catch (_) {}
    return (raw ?? '').toString().toLowerCase();
  }

  List<Map<String, dynamic>> _buildAiSuggestion(
    Patient patient,
    List<Map<String, dynamic>> doctorMeds,
  ) {
    // ===== PRIORITY 1: Use backend ai_suggestion from report if available =====
    final report = widget.report;
    if (report != null && report['ai_suggestion'] is List) {
      final backendSuggestions =
          (report['ai_suggestion'] as List).cast<Map<String, dynamic>>();
      if (backendSuggestions.isNotEmpty) {
        debugPrint("Using backend ai_suggestion (${backendSuggestions.length} drugs)");
        return backendSuggestions.map((s) {
          return {
            'name': s['name'] ?? '',
            'dose': (s['dose'] ?? '').toString(),
            'unit': s['unit'] ?? 'mg',
            'frequency': s['frequency'] ?? 'Once a day',
            'route': s['route'] ?? 'PO',
            'prn': s['prn'] ?? false,
            'action': s['action'] ?? 'continue',
            'rationale': s['rationale'] ?? '',
          };
        }).toList();
      }
    }

    // ===== PRIORITY 2: Fallback to client-side demo logic =====
    debugPrint("No backend ai_suggestion, falling back to demo logic");
    final allergyText = _safeAllergyText(patient);

    final out = <Map<String, dynamic>>[];
    for (final med in doctorMeds) {
      final name = (med['name'] ?? '').toString();
      final lower = name.toLowerCase();

      if (allergyText.contains('penicillin') &&
          (lower.contains('amoxic') ||
              lower.contains('ampic') ||
              lower.contains('penicillin') ||
              lower.contains('clox'))) {
        out.add({
          'name': widget.demoMode
              ? 'Azithromycin (AI suggested)'
              : 'Azithromycin',
          'dose': '500',
          'unit': 'mg',
          'frequency': 'Once a day',
          'route': med['route'] ?? 'PO',
          'prn': false,
          'action': 'switch',
          'rationale': 'Switched from penicillin-class drug due to documented allergy.',
        });
      } else {
        out.add({
          'name': med['name'],
          'dose': med['dose'],
          'unit': med['unit'],
          'frequency': med['frequency'],
          'route': med['route'] ?? 'PO',
          'prn': med['prn'] ?? false,
          'action': 'continue',
          'rationale': '',
        });
      }
    }
    return out;
  }

  List<PrescriptionAlert> _generateAlerts({
    required Patient patient,
    required List<Map<String, dynamic>> meds,
    required bool demoMode,
  }) {
    final List<PrescriptionAlert> out = [];
    final allergyText = _safeAllergyText(patient);

    final demoAllergyCites = demoMode
        ? const [
            Citation(
              id: "[2]",
              source: "Drug monograph / label (placeholder)",
              note: "Cross-sensitivity / allergy warning support.",
            ),
          ]
        : const <Citation>[];

    final demoDoseCites = demoMode
        ? const [
            Citation(
              id: "[1]",
              source: "Local guideline / formulary (placeholder)",
              note: "Maximum daily dose / dose limit support.",
            ),
          ]
        : const <Citation>[];

    for (final med in meds) {
      final name = (med['name'] ?? '').toString().toLowerCase();
      final doseStr = (med['dose'] ?? '').toString();
      final unit = (med['unit'] ?? '').toString().toLowerCase();

      if (allergyText.contains('penicillin') &&
          (name.contains('amoxic') ||
              name.contains('ampic') ||
              name.contains('penicillin') ||
              name.contains('clox'))) {
        out.add(
          PrescriptionAlert(
            category: AlertCategory.allergy,
            severity: AlertSeverity.high,
            title: _demoTag('Allergy: Cross-sensitivity warning'),
            summary: _demoTag(
              'Severe allergy alert example for prototype demonstration.',
            ),
            details: _demoTag(
              'Explanation: Patient record suggests a relevant allergy. '
              'This medication may increase risk of allergic reaction. '
              'Pharmacist should verify allergy history and consider alternatives.',
            ),
            citations: demoAllergyCites,
          ),
        );
      }

      final dose = double.tryParse(doseStr);
      if (dose != null && unit == 'mg' && dose >= 2000) {
        out.add(
          PrescriptionAlert(
            category: AlertCategory.dosing,
            severity: AlertSeverity.medium,
            title: _demoTag('Dose: Exceeds recommended daily limit'),
            summary: _demoTag(
              'Dosing alert example for prototype demonstration.',
            ),
            details: _demoTag(
              'Explanation: Entered dose crosses a demo threshold. '
              'In production, this should be computed against drug-specific maximum daily dose and patient factors.',
            ),
            citations: demoDoseCites,
          ),
        );
      }
    }

    return out;
  }

  // UI helpers
  Color _severityBorder(AlertSeverity s) {
    switch (s) {
      case AlertSeverity.high:
        return Colors.red.shade700;
      case AlertSeverity.medium:
        return Colors.orange.shade700;
      case AlertSeverity.low:
        return Colors.yellow.shade800;
    }
  }

  Color _severityFill(AlertSeverity s) {
    switch (s) {
      case AlertSeverity.high:
        return Colors.red.shade100;
      case AlertSeverity.medium:
        return Colors.orange.shade100;
      case AlertSeverity.low:
        return Colors.yellow.shade100;
    }
  }

  IconData _categoryIcon(AlertCategory c) {
    switch (c) {
      case AlertCategory.allergy:
        return Icons.warning_amber_rounded;
      case AlertCategory.dosing:
        return Icons.medication_outlined;
      case AlertCategory.other:
        return Icons.info_outline;
    }
  }

  String _severityLabel(AlertSeverity s) {
    switch (s) {
      case AlertSeverity.high:
        return 'RED';
      case AlertSeverity.medium:
        return 'ORANGE';
      case AlertSeverity.low:
        return 'YELLOW';
    }
  }

  bool get _hasVeryHigh => _alerts.any((a) => a.severity == AlertSeverity.high);

  bool get _isAllCorrect => _alerts.isEmpty;

  bool get _canSaveConfirm {
    if (_alerts.isEmpty) return true;
    if (_selectedReason == null) return false;
    if (_selectedReason == 'Others (Please specify)' &&
        _otherReasonCtrl.text.trim().isEmpty)
      return false;
    return true;
  }

  String _formatRxLine(Map<String, dynamic> med) {
    final name = (med['name'] ?? '').toString().trim();
    final dose = (med['dose'] ?? '').toString().trim();
    final unit = (med['unit'] ?? '').toString().trim();
    final freq = (med['frequency'] ?? '').toString().trim();
    final route = (med['route'] ?? '').toString().trim();
    final prn = med['prn'] == true;
    final routeText = route.isEmpty ? '' : ' $route';
    return "$name $dose$unit$routeText - $freq${prn ? ' (PRN)' : ''}";
  }

  Map<String, dynamic> _aiMedAt(int i) {
    return {
      'name': _aiNameCtrls[i].text.trim(),
      'dose': _aiDoseCtrls[i].text.trim(),
      'unit': _aiUnits[i],
      'frequency': _aiFreqs[i],
      'route': _aiRoutes[i],
      'prn': _aiPrn[i],
    };
  }

  Future<void> _saveAndConfirm() async {
    if (!_canSaveConfirm) return;

    final chosen = _decision == 'Use Doctor prescription'
        ? widget.prescribedMeds
        : List.generate(_aiNameCtrls.length, (i) => _aiMedAt(i));

    final reason = _alerts.isEmpty
        ? "No issues detected (auto-approved)"
        : (_selectedReason == 'Others (Please specify)')
        ? _otherReasonCtrl.text.trim()
        : _selectedReason!;

    final rationale = StringBuffer()
      ..writeln("Override reason: $reason")
      ..writeln(_aiExplanation)
      ..writeln("Alerts:")
      ..writeln(
        _alerts.isEmpty
            ? "None"
            : _alerts.map((a) => "• ${a.title}: ${a.details}").join("\n"),
      );

    try {
      await PatientSupabaseService.addPrescription(
        patientId: widget.patient.id,
        patientName: widget.patient.name,
        wardRoomNo: widget.patient.wardRoomNo,
        medicines: chosen,
        rationale: rationale.toString(),
        date: DateTime.now().toIso8601String(),
      );

      debugPrint("✅ Prescription saved successfully");

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Saved! Added to Pharmacist "To be verified" list.'),
        ),
      );

      Navigator.of(context).pop();
    } catch (e) {
      debugPrint("❌ Supabase save error: $e");

      if (!mounted) return;

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Save failed: $e')));
    }
  }

  Widget _rxListBox(String title, List<Map<String, dynamic>> meds) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        border: Border.all(color: Colors.black12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 6),
          ...meds.map((m) => Text("• ${_formatRxLine(m)}")),
        ],
      ),
    );
  }

  Widget _aiExplanationBox() {
    // ✅ Prefer real backend output if provided; fallback to demo text
    final String text =
        (widget.verificationResult != null &&
            widget.verificationResult!.trim().isNotEmpty)
        ? _formatVerificationResult(widget.verificationResult!)
        : _aiExplanation;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: Colors.green.shade50,
        border: Border.all(color: Colors.black12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            widget.demoMode
                ? 'AI Explanation & Citations (demo)'
                : 'AI Explanation & Citations',
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 6),

          // ✅ long text friendly
          SelectableText(text, style: const TextStyle(fontSize: 13)),
          const SizedBox(height: 8),
          if (_aiCitations.isNotEmpty &&
              (widget.verificationResult == null ||
                  widget.verificationResult!.isEmpty)) ...[
            const Text(
              'References:',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 4),
            ..._aiCitations.map(
              (c) => Text(
                "${c.id} ${c.source} — ${c.note}",
                style: const TextStyle(fontSize: 12),
              ),
            ),
          ] else if (widget.verificationResult == null ||
              widget.verificationResult!.isEmpty) ...[
            const Text('References: (None)', style: TextStyle(fontSize: 12)),
          ],
        ],
      ),
    );
  }

  /// Format the backend response for display. The backend returns the
  /// pharmacist-facing text already pre-formatted in the `answer` field,
  /// so we pass it through unchanged. We only attempt JSON parsing if the
  /// input clearly looks like JSON (starts with '{').
  String _formatVerificationResult(String text) {
    final trimmed = text.trim();
    if (!trimmed.startsWith('{')) {
      // Already plain text from the backend - just return it as-is.
      return text;
    }
    try {
      final Map<String, dynamic> data = jsonDecode(trimmed);

      final StringBuffer buffer = StringBuffer();

      // Add assessment
      if (data.containsKey('assessment')) {
        buffer.writeln("Assessment: ${data['assessment']}");
        buffer.writeln("");
      }

      // Add diagnosis
      if (data.containsKey('diagnosis_enriched')) {
        buffer.writeln("Diagnosis: ${data['diagnosis_enriched']}");
        buffer.writeln("");
      }

      // Add NLP confidence
      if (data.containsKey('nlp_confidence')) {
        buffer.writeln("NLP Confidence: ${data['nlp_confidence']}");
        buffer.writeln("");
      }

      // Add clinical flags
      if (data.containsKey('clinical_flags') &&
          (data['clinical_flags'] as List).isNotEmpty) {
        buffer.writeln("Clinical Flags:");
        for (var flag in data['clinical_flags']) {
          buffer.writeln("  • $flag");
        }
        buffer.writeln("");
      }

      // Add recommendations
      if (data.containsKey('recommendations') &&
          (data['recommendations'] as List).isNotEmpty) {
        buffer.writeln("Recommendations:");
        for (var rec in data['recommendations']) {
          buffer.writeln("  $rec");
        }
        buffer.writeln("");
      }

      // Add detailed findings
      if (data.containsKey('detailed_findings') &&
          (data['detailed_findings'] as List).isNotEmpty) {
        buffer.writeln("Detailed Findings:");
        for (var finding in data['detailed_findings']) {
          buffer.writeln("  • $finding");
        }
      }

      return buffer.toString().isNotEmpty ? buffer.toString() : text;
    } catch (e) {
      debugPrint("Error formatting verification result: $e");
      return text;
    }
  }

  Widget _aiEditableBox() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: Colors.blueGrey.shade50,
        border: Border.all(color: Colors.black12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            widget.demoMode
                ? 'AI suggestion (editable) (demo)'
                : 'AI suggestion (editable)',
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          for (int i = 0; i < _aiNameCtrls.length; i++) ...[
            // Action badge row
            if (_aiActions[i] != 'continue') ...[
              _actionBadge(_aiActions[i]),
              const SizedBox(height: 4),
            ],
            // Rationale text
            if (_aiRationales[i].isNotEmpty) ...[
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                decoration: BoxDecoration(
                  color: _actionBgColor(_aiActions[i]),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  _aiRationales[i],
                  style: TextStyle(
                    fontSize: 12,
                    fontStyle: FontStyle.italic,
                    color: _actionTextColor(_aiActions[i]),
                  ),
                ),
              ),
              const SizedBox(height: 6),
            ],
            // Drug name + dose + unit row
            ResponsiveWrap(
              minItemWidth: 110,
              spacing: 8,
              runSpacing: 8,
              children: [
                TextField(
                  controller: _aiNameCtrls[i],
                  decoration: InputDecoration(
                    labelText: 'Drug',
                    isDense: true,
                    border: const OutlineInputBorder(),
                    enabled: _aiActions[i] != 'discontinue',
                  ),
                  style: _aiActions[i] == 'discontinue'
                      ? const TextStyle(
                          decoration: TextDecoration.lineThrough,
                          color: Colors.red,
                        )
                      : null,
                ),
                TextField(
                  controller: _aiDoseCtrls[i],
                  decoration: InputDecoration(
                    labelText: 'Dose',
                    isDense: true,
                    border: const OutlineInputBorder(),
                    enabled: _aiActions[i] != 'discontinue',
                  ),
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                ),
                DropdownButtonFormField<String>(
                  value: _aiUnits[i],
                  isDense: true,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Unit',
                    border: OutlineInputBorder(),
                  ),
                  items: _doseUnits
                      .map((u) => DropdownMenuItem(value: u, child: Text(u)))
                      .toList(),
                  onChanged: _aiActions[i] == 'discontinue'
                      ? null
                      : (v) => setState(() => _aiUnits[i] = v ?? 'mg'),
                ),
              ],
            ),
            const SizedBox(height: 8),
            // Frequency + Route + PRN row
            ResponsiveWrap(
              minItemWidth: 130,
              spacing: 8,
              runSpacing: 8,
              children: [
                DropdownButtonFormField<String>(
                  value: _aiFreqs[i],
                  isDense: true,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Frequency',
                    border: OutlineInputBorder(),
                  ),
                  items: _freqOptions
                      .map((f) => DropdownMenuItem(value: f, child: Text(f)))
                      .toList(),
                  onChanged: _aiActions[i] == 'discontinue'
                      ? null
                      : (v) =>
                          setState(() => _aiFreqs[i] = v ?? 'Once a day'),
                ),
                DropdownButtonFormField<String>(
                  value: _aiRoutes[i],
                  isDense: true,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Route',
                    border: OutlineInputBorder(),
                  ),
                  items: _routeOptions
                      .map((r) => DropdownMenuItem(value: r, child: Text(r)))
                      .toList(),
                  onChanged: _aiActions[i] == 'discontinue'
                      ? null
                      : (v) => setState(() => _aiRoutes[i] = v ?? 'PO'),
                ),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text('PRN'),
                    Checkbox(
                      value: _aiPrn[i],
                      onChanged: _aiActions[i] == 'discontinue'
                          ? null
                          : (v) => setState(() => _aiPrn[i] = v ?? false),
                    ),
                  ],
                ),
              ],
            ),
            const Divider(height: 18),
          ],
        ],
      ),
    );
  }

  Widget _actionBadge(String action) {
    final label = action.toUpperCase();
    Color bg;
    Color fg;
    IconData icon;
    switch (action) {
      case 'discontinue':
        bg = Colors.red.shade100;
        fg = Colors.red.shade800;
        icon = Icons.cancel;
        break;
      case 'switch':
        bg = Colors.orange.shade100;
        fg = Colors.orange.shade800;
        icon = Icons.swap_horiz;
        break;
      case 'adjust':
        bg = Colors.blue.shade100;
        fg = Colors.blue.shade800;
        icon = Icons.tune;
        break;
      default:
        bg = Colors.green.shade100;
        fg = Colors.green.shade800;
        icon = Icons.check_circle;
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: fg),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(fontWeight: FontWeight.w700, color: fg, fontSize: 12)),
        ],
      ),
    );
  }

  Color _actionBgColor(String action) {
    switch (action) {
      case 'discontinue': return Colors.red.shade50;
      case 'switch': return Colors.orange.shade50;
      case 'adjust': return Colors.blue.shade50;
      default: return Colors.grey.shade50;
    }
  }

  Color _actionTextColor(String action) {
    switch (action) {
      case 'discontinue': return Colors.red.shade700;
      case 'switch': return Colors.orange.shade700;
      case 'adjust': return Colors.blue.shade700;
      default: return Colors.black54;
    }
  }

  Widget _alertCard(PrescriptionAlert a, bool expanded, int index) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: _severityFill(a.severity),
        border: Border.all(color: _severityBorder(a.severity), width: 1.2),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(_categoryIcon(a.category), color: _severityBorder(a.severity)),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        '${_severityLabel(a.severity)} — ${a.title}',
                        style: const TextStyle(fontWeight: FontWeight.bold),
                      ),
                    ),
                    TextButton(
                      onPressed: () {
                        setState(() {
                          expanded
                              ? _expanded.remove(index)
                              : _expanded.add(index);
                        });
                      },
                      child: Text(expanded ? 'Less' : 'Read more'),
                    ),
                  ],
                ),
                Text(a.summary),
                if (expanded) ...[
                  const SizedBox(height: 8),
                  Text(a.details, style: const TextStyle(fontSize: 13)),
                  if (a.citations.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    const Text(
                      'References:',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 4),
                    ...a.citations.map(
                      (c) => Text(
                        "${c.id} ${c.source} — ${c.note}",
                        style: const TextStyle(fontSize: 12),
                      ),
                    ),
                  ],
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _leftAlertPanel(Patient p, {required bool scrollable}) {
    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Patient: ${p.name}  |  Ward: ${p.wardRoomNo}',
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 10),
        _rxListBox('Doctor prescription', widget.prescribedMeds),
        const SizedBox(height: 10),
        _aiEditableBox(),
        const SizedBox(height: 10),
        _aiExplanationBox(),
        const SizedBox(height: 10),
        if (_alerts.isEmpty)
          const Center(child: Text('No alerts.'))
        else
          ...List.generate(_alerts.length, (i) {
            final a = _alerts[i];
            final expanded = _expanded.contains(i);
            return _alertCard(a, expanded, i);
          }),
      ],
    );

    return Padding(
      padding: const EdgeInsets.all(12),
      child: scrollable ? SingleChildScrollView(child: content) : content,
    );
  }

  Widget _rightDecisionPanel({required bool compact}) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: compact
            ? const Border(top: BorderSide(color: Colors.black54, width: 1.2))
            : const Border(left: BorderSide(color: Colors.black54, width: 1.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Please select:',
            style: TextStyle(fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 8),
          if (_alerts.isEmpty)
            Container(
              padding: const EdgeInsets.all(12),
              margin: const EdgeInsets.only(bottom: 10),
              decoration: BoxDecoration(
                color: Colors.green.shade100,
                border: Border.all(color: Colors.green, width: 1.2),
              ),
              child: const Row(
                children: [
                  Icon(Icons.check_circle, color: Colors.green),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'No issues detected. Prescription is safe to proceed.',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
            ),
          if (_alerts.isNotEmpty)
            DropdownButtonFormField<String>(
              value: _selectedReason,
              isExpanded: true,
              decoration: const InputDecoration(
                border: OutlineInputBorder(),
                isDense: true,
              ),
              items:
                  const [
                    'Choose a reason',
                    'Allergy not clinically relevant',
                    'Alert is recorded',
                    'Others (Please specify)',
                  ].map((s) {
                    return DropdownMenuItem(
                      value: s == 'Choose a reason' ? null : s,
                      child: Text(s),
                    );
                  }).toList(),
              onChanged: (val) => setState(() => _selectedReason = val),
            ),
          const SizedBox(height: 10),
          if (_alerts.isNotEmpty &&
              _selectedReason == 'Others (Please specify)') ...[
            TextField(
              controller: _otherReasonCtrl,
              decoration: const InputDecoration(
                labelText: 'Type reason here',
                border: OutlineInputBorder(),
                isDense: true,
              ),
            ),
            const SizedBox(height: 10),
          ],
          const Text(
            'Final Decision:',
            style: TextStyle(fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            value: _decision,
            isExpanded: true,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              isDense: true,
            ),
            items: const [
              'Use AI suggestion',
              'Use Doctor prescription',
              'Edit AI suggestion',
            ].map((s) => DropdownMenuItem(value: s, child: Text(s))).toList(),
            onChanged: (val) => setState(() => _decision = val!),
          ),
          SizedBox(height: compact ? 18 : 10),
          if (!compact) const Spacer(),
          ElevatedButton(
            onPressed: _canSaveConfirm ? _saveAndConfirm : null,
            child: const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('Save & Confirm'),
            ),
          ),
          const SizedBox(height: 10),
          OutlinedButton.icon(
            onPressed: _goHome,
            icon: const Icon(Icons.home),
            label: const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('Home'),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.patient;

    return Scaffold(
      appBar: AppBar(
        title: const Text('PRESCRIPTION ALERT'),
        centerTitle: true,
        actions: [
          TextButton.icon(
            onPressed: _goHome,
            icon: const Icon(Icons.home, color: Colors.white),
            label: const Text('Home', style: TextStyle(color: Colors.white)),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: Padding(
        padding: Responsive.pagePadding(context),
        child: Container(
          decoration: BoxDecoration(
            border: Border.all(color: Colors.black54, width: 1.2),
          ),
          child: Column(
            children: [
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 10,
                ),
                color: Colors.orange.shade600,
                child: Text(
                  _alerts.isEmpty
                      ? 'No issues detected.'
                      : _hasVeryHigh
                      ? 'For alerts categorized as RED severity, PLEASE SELECT THE REASON FOR OVERRIDING THE ALERT.'
                      : 'Prescription alerts detected. Please review.',
                  style: const TextStyle(
                    color: Colors.black,
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                  ),
                ),
              ),
              Expanded(
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    final compact = constraints.maxWidth < 760;

                    if (compact) {
                      return SingleChildScrollView(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            _leftAlertPanel(p, scrollable: false),
                            _rightDecisionPanel(compact: true),
                          ],
                        ),
                      );
                    }

                    return Row(
                      children: [
                        Expanded(
                          flex: 6,
                          child: _leftAlertPanel(p, scrollable: true),
                        ),
                        Expanded(
                          flex: 4,
                          child: _rightDecisionPanel(compact: false),
                        ),
                      ],
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}