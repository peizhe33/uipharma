import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'screens/doctor_patient_overview.dart';
import 'services/patient_database.dart';

class MyCustomScrollBehavior extends MaterialScrollBehavior {
  @override
  Set<PointerDeviceKind> get dragDevices => {
        PointerDeviceKind.touch,
        PointerDeviceKind.mouse,
        PointerDeviceKind.stylus,
        PointerDeviceKind.trackpad,
      };
}
void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // ✅ Initialize Supabase
  await Supabase.initialize(
    url: 'https://whgkrdzoicepntnxtuab.supabase.co',
    anonKey:
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndoZ2tyZHpvaWNlcG50bnh0dWFiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc0MDQ1NzksImV4cCI6MjA5Mjk4MDU3OX0.g_7CgDKZAzEW5LsbMWTpQhgsOMdszOk3o6CP_q5avzo',
  );

  // ✅ Initialize local database
  await PatientDatabase.instance.init();

  // ⚠️ ONLY UNCOMMENT IF YOU WANT TO RESET DATA ON APP START
  // await PatientDatabase.instance.clearAll();
  // await PatientDatabase.instance.seedDemoDataIfEmpty();

  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    final Color primaryBlue = Colors.blue.shade700;

    return MaterialApp(
      title: 'Doctor & Pharmacist Portal',
      debugShowCheckedModeBanner: false,
      scrollBehavior: MyCustomScrollBehavior(),
      builder: (context, child) {
        final mediaQuery = MediaQuery.of(context);
        final textScaleFactor =
            mediaQuery.textScaleFactor.clamp(0.9, 1.12).toDouble();
        return MediaQuery(
          data: mediaQuery.copyWith(
            textScaler: TextScaler.linear(textScaleFactor),
          ),
          child: child ?? const SizedBox.shrink(),
        );
      },

      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: primaryBlue,
          brightness: Brightness.light,
        ),
        scaffoldBackgroundColor: Colors.white,

        appBarTheme: AppBarTheme(
          backgroundColor: primaryBlue,
          foregroundColor: Colors.white,
          centerTitle: true,
          elevation: 4,
        ),

        floatingActionButtonTheme: FloatingActionButtonThemeData(
          backgroundColor: primaryBlue,
          foregroundColor: Colors.white,
        ),

        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: primaryBlue,
            foregroundColor: Colors.white,
          ),
        ),

        outlinedButtonTheme: OutlinedButtonThemeData(
          style: OutlinedButton.styleFrom(
            foregroundColor: primaryBlue,
          ),
        ),
      ),

      home: const PatientOverviewPage(),
    );
  }
}
