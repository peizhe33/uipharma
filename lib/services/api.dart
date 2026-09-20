import 'dart:convert';
import 'package:http/http.dart' as http;

/// Response wrapper for the Python SmartPharma backend.
///
/// The backend returns BOTH a plain-text `answer` (the assembled
/// pharmacist-facing prose) AND a structured `report` (machine-readable
/// fields like alerts, references, monitoring, etc).
///
/// Flutter screens should:
///   - Use [answer] as plain text for the AI Explanation & Citations panel.
///   - Use [report], [preprocessingAlerts], or [retrieved] for structured
///     UI elements (severity widgets, citation lists, etc).
class SmartPharmaResponse {
  final String question;
  final String answer;                       // plain-text pharmacist output
  final Map<String, dynamic> report;         // structured report object
  final List<Map<String, dynamic>> preprocessingAlerts;
  final List<Map<String, dynamic>> retrieved;
  final bool ragFailure;
  final double elapsedSeconds;

  SmartPharmaResponse({
    required this.question,
    required this.answer,
    required this.report,
    required this.preprocessingAlerts,
    required this.retrieved,
    required this.ragFailure,
    required this.elapsedSeconds,
  });

  factory SmartPharmaResponse.fromJson(Map<String, dynamic> json) {
    final reportRaw = json['report'];
    final Map<String, dynamic> report = reportRaw is Map<String, dynamic>
        ? reportRaw
        : <String, dynamic>{};

    List<Map<String, dynamic>> _asListOfMaps(dynamic v) {
      if (v is List) {
        return v.whereType<Map>().map((m) => Map<String, dynamic>.from(m)).toList();
      }
      return const [];
    }

    return SmartPharmaResponse(
      question: json['question'] as String? ?? '',
      // CRITICAL FIX: answer is a plain string. Never JSON-encode the report
      // into the answer field - screens that read `.answer` expect prose.
      answer: json['answer'] as String? ?? '',
      report: report,
      preprocessingAlerts: _asListOfMaps(json['preprocessing_alerts']),
      retrieved: _asListOfMaps(json['retrieved']),
      ragFailure: json['rag_failure'] as bool? ?? false,
      elapsedSeconds: (json['elapsed_s'] as num?)?.toDouble() ?? 0.0,
    );
  }

  // Convenience accessors for the structured report fields.
  String get assessment => report['assessment']?.toString() ?? '';
  List<String> get alerts => _stringList(report['alerts']);
  List<String> get references => _stringList(report['references']);
  List<String> get recommendations => _stringList(report['recommendations']);
  List<dynamic> get monitoring => (report['monitoring'] as List?) ?? const [];
  List<String> get interactions => _stringList(report['interactions']);

  static List<String> _stringList(dynamic v) {
    if (v is List) return v.map((e) => e.toString()).toList();
    return const [];
  }

  /// Interpret the "Verification:" line in the plain-text answer.
  bool get isVerified {
    final lines = answer.split('\n');
    for (final line in lines) {
      final trimmed = line.trim();
      if (trimmed.toLowerCase().startsWith('verification:')) {
        final value =
            trimmed.substring('verification:'.length).trim().toLowerCase();
        return value.contains('diagnosis is accurate');
      }
    }
    return false;
  }
}

/// Client that talks to the Python SmartPharma RAG backend.
class SmartPharmaApi {
  // Point this at the laptop running the backend on the LAN.
  // - Same machine (Chrome / Windows desktop): use 'http://127.0.0.1:5009'
  // - Android phone on same Wi-Fi: use 'http://<laptop-LAN-IP>:5009'
  //   (run `ipconfig` on the laptop and copy the IPv4 address)
  // LOCAL (running Flutter on same laptop as backend):
 // static const String _baseUrl = 'https://stingy-gibberish-backtalk.ngrok-free.dev';
    static const String _baseUrl = 'https://aweigh-olene-nomothetic.ngrok-free.dev';
  // LAN (running Flutter on phone/another device, same WiFi):
  //static const String _baseUrl = 'http://172.20.10.3:5009';

  Future<SmartPharmaResponse> verifyPrescription(
    String prompt, {
    int? age,
    String? section,
    int? k,
    Map<String, dynamic>? patient,
    Map<String, dynamic>? vitals,
    Map<String, dynamic>? labs,
    String? diagnosis,
    List<Map<String, dynamic>>? prescribedMedicines,
  }) async {
    final uri = Uri.parse('$_baseUrl/ask');

    final Map<String, dynamic> body = {
      'question': prompt,
    };

    if (age != null) body['age'] = age;
    if (section != null && section.trim().isNotEmpty) body['section'] = section;
    if (k != null) body['k'] = k;
    if (patient != null) body['patient'] = patient;
    if (vitals != null) body['vitals'] = vitals;
    if (labs != null) body['labs'] = labs;
    if (diagnosis != null && diagnosis.isNotEmpty) body['diagnosis'] = diagnosis;
    if (prescribedMedicines != null) body['prescribed_medicines'] = prescribedMedicines;

    final res = await http.post(
      uri,
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );

    if (res.statusCode != 200) {
      // Safety net for the Windows file-permission error
      // (received_data.json write failing). Falls back to a local
      // rule-based check so verification can still complete on-device.
      if (_isBackendFilePermissionError(res.body)) {
        return _localRuleFallback(
          question: prompt,
          patient: patient,
          vitals: vitals,
          labs: labs,
          diagnosis: diagnosis,
          prescribedMedicines: prescribedMedicines ?? const [],
        );
      }
      throw Exception(
        'SmartPharma backend error (HTTP ${res.statusCode}): ${res.body}',
      );
    }

    final Map<String, dynamic> json =
        jsonDecode(res.body) as Map<String, dynamic>;
    return SmartPharmaResponse.fromJson(json);
  }

  bool _isBackendFilePermissionError(String body) {
    final lower = body.toLowerCase();
    return lower.contains('permission denied') ||
        lower.contains('errno 13') ||
        lower.contains('received_data.json') ||
        lower.contains('rule_based_output.json');
  }

  /// Local rule-based fallback that runs entirely in the Flutter app
  /// when the backend cannot complete the request. Builds a structured
  /// report so downstream screens see the same shape as a real backend
  /// response, plus a plain-text `answer` so screens that scan text for
  /// alert keywords still work.
  SmartPharmaResponse _localRuleFallback({
    required String question,
    Map<String, dynamic>? patient,
    Map<String, dynamic>? vitals,
    Map<String, dynamic>? labs,
    String? diagnosis,
    required List<Map<String, dynamic>> prescribedMedicines,
  }) {
    final alerts = <String>[];
    final recommendations = <String>[];

    final allergy = (vitals?['allergy_details'] ?? '').toString().toLowerCase();
    final egfr = double.tryParse((labs?['egfr'] ?? '').toString());

    for (final med in prescribedMedicines) {
      final name = (med['name'] ?? '').toString();
      final lowerName = name.toLowerCase();
      final unit = (med['unit'] ?? '').toString().toLowerCase();
      final dose = double.tryParse((med['dose'] ?? '').toString());

      if ((allergy.contains('penicillin') || allergy.contains('amoxicillin')) &&
          (lowerName.contains('amoxicillin') ||
              lowerName.contains('amoxiclav') ||
              lowerName.contains('augmentin') ||
              lowerName.contains('penicillin'))) {
        alerts.add(
          'ALLERGY ALERT: Patient has recorded penicillin/amoxicillin allergy; $name may be unsafe.',
        );
      }

      if (dose != null && unit == 'mg' && dose >= 2000) {
        alerts.add(
          'DOSE ALERT: $name dose appears high from local fallback rules. Please review maximum dose and frequency.',
        );
      }
    }

    if (egfr != null && egfr < 60) {
      alerts.add(
        'RENAL ALERT: eGFR is below 60. Review renal dose adjustment and monitoring.',
      );
    }

    if (alerts.isEmpty) {
      recommendations.add(
        'No major local fallback alerts detected. Continue pharmacist verification as usual.',
      );
    } else {
      recommendations.add(
        'Review the highlighted alert(s), patient condition, allergy record, renal function, and prescribed dose.',
      );
    }
    recommendations.add(
      'Backend was unavailable. Local rule-based fallback used. Fix backend for full guideline retrieval.',
    );

    final report = <String, dynamic>{
      'assessment': alerts.isEmpty
          ? 'Local fallback check completed: no major alerts detected.'
          : 'Local fallback check completed: review required.',
      'diagnosis_enriched': diagnosis ?? '',
      'patient': patient ?? const {},
      'alerts': alerts,
      'recommendations': recommendations,
      'clinical_flags': alerts,
      'detailed_findings': const [
        'The SmartPharma backend returned an error.',
        'This fallback result is generated inside the Flutter app so verification can continue on this device.',
      ],
      'references': <String>[],
      'monitoring': <dynamic>[],
      'interactions': <String>[],
      'rag_failure': true,
    };

    // Build the plain-text answer the same way the backend would, so
    // downstream screens that read `.answer` show readable prose, NOT a
    // JSON blob (avoids the "Unexpected token 'A'" parsing failure).
    final buf = StringBuffer();
    buf.writeln('Assessment: ${report['assessment']}');
    if ((diagnosis ?? '').isNotEmpty) {
      buf.writeln('Diagnosis: $diagnosis');
    }
    if (alerts.isNotEmpty) {
      buf.writeln('\nClinical Flags:');
      for (final a in alerts) {
        buf.writeln('  - $a');
      }
    }
    if (recommendations.isNotEmpty) {
      buf.writeln('\nRecommendations:');
      for (final r in recommendations) {
        buf.writeln('  - $r');
      }
    }

    return SmartPharmaResponse(
      question: question,
      answer: buf.toString().trim(),
      report: report,
      preprocessingAlerts: const [],
      retrieved: const [],
      ragFailure: true,
      elapsedSeconds: 0,
    );
  }
}