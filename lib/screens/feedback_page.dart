import 'package:flutter/material.dart';
import 'package:pj/services/feedback_service.dart';
import '../widgets/responsive.dart';

class FeedbackPage extends StatefulWidget {
  const FeedbackPage({super.key});

  @override
  State<FeedbackPage> createState() => _FeedbackPageState();
}

class _FeedbackPageState extends State<FeedbackPage> {
  final List<String> _roles = [
  'doctor',
  'pharmacist',
  'staff',
  ];
  String? _selectedRole;
  String? _selectedCategory;
  final TextEditingController _feedbackController = TextEditingController();

  final List<String> _issueCategories = [
    'Data Error/Inaccuracy',
    'UI/Layout Issue',
    'Workflow Suggestion',
    'Performance Lag',
    'General Comment',
  ];

  void _submitFeedback() async {

  if (_selectedRole == null) {
  ScaffoldMessenger.of(context).showSnackBar(
    const SnackBar(content: Text("Please select a role")),
  );
  return;
  }
  
  if (_selectedCategory == null || _feedbackController.text.trim().isEmpty) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Please select a category and enter feedback.'),
      ),
    );
    return;
  }

  try {
    await FeedbackService().submitFeedback(
      message:
          "[${_selectedCategory!}] ${_feedbackController.text.trim()}",
      role: _selectedRole!,
    );

    _feedbackController.clear();

    setState(() {
      _selectedRole = null;
      _selectedCategory = null;
    });

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (BuildContext context) {
        return AlertDialog(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(15),
          ),
          title: Row(
            children: [
              Icon(Icons.check_circle, color: Colors.green.shade600),
              const SizedBox(width: 10),
              const Text("Success!"),
            ],
          ),
          content: const Text(
            "Feedback has been sent successfully, thank you for your input.",
          ),
          actions: <Widget>[
            TextButton(
              child: const Text('Close',
                  style: TextStyle(color: Colors.blue)),
              onPressed: () {
                Navigator.of(context).pop();
                Navigator.of(context).pop();
              },
            ),
          ],
        );
      },
    );
  } catch (e) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text("Error: $e")),
    );
  }
}

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          "User Feedback",
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        ),
        backgroundColor: Colors.blue.shade700,
      ),
      body: Padding(
        padding: Responsive.pagePadding(context),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "Select Role:",
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
            ),

            const SizedBox(height: 8),

            DropdownButtonFormField<String>(
              value: _selectedRole,
              hint: const Text("Choose role"),
              decoration: InputDecoration(
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 15,
                  vertical: 10,
                ),
              ),
              items: _roles.map((role) {
                return DropdownMenuItem(
                  value: role,
                  child: Text(role),
                );
              }).toList(),
              onChanged: (value) {
                setState(() {
                  _selectedRole = value;
                });
              },
            ),
            const Text(
              "Issue Category:",
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            DropdownButtonFormField<String>(
              decoration: InputDecoration(
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 15,
                  vertical: 10,
                ),
              ),
              hint: const Text("Select an issue category"),
              value: _selectedCategory,
              items: _issueCategories.map((String category) {
                return DropdownMenuItem<String>(
                  value: category,
                  child: Text(category),
                );
              }).toList(),
              onChanged: (String? newValue) {
                setState(() {
                  _selectedCategory = newValue;
                });
              },
            ),
            const SizedBox(height: 20),
            const Text(
              "Feedback/Comments:",
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            Expanded(
              child: TextField(
                controller: _feedbackController,
                maxLines: null,
                expands: true,
                textAlignVertical: TextAlignVertical.top,
                decoration: InputDecoration(
                  hintText: "Enter your feedback or suggestion here...",
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                  alignLabelWithHint: true,
                ),
                keyboardType: TextInputType.multiline,
              ),
            ),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _submitFeedback,
                icon: const Icon(Icons.send),
                label: const Padding(
                  padding: EdgeInsets.symmetric(vertical: 15.0),
                  child: Text(
                    "Submit Feedback",
                    style: TextStyle(fontSize: 18),
                  ),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.blue.shade600,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  elevation: 5,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
