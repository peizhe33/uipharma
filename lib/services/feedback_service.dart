import 'package:supabase_flutter/supabase_flutter.dart';

class FeedbackService {
  final SupabaseClient _client = Supabase.instance.client;

  // CREATE (INSERT)
  Future<void> submitFeedback({
    required String message,
    String role = 'user',
  }) async {
    await _client.from('feedback').insert({
      'message': message,
      'role': role,
    });
  }

  // READ (optional - for later use)
  Future<List<Map<String, dynamic>>> getFeedback() async {
    final data = await _client
        .from('feedback')
        .select()
        .order('created_at', ascending: false);

    return List<Map<String, dynamic>>.from(data);
  }
}