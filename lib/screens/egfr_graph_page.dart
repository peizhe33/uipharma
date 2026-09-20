import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import '../models/models.dart';
import '../services/patient_supabase_service.dart';
import '../widgets/review_notification_bell.dart';
import '../widgets/responsive.dart';

class EgfrGraphPage extends StatefulWidget {
  final Patient patient;

  const EgfrGraphPage({
    super.key,
    required this.patient,
  });

  @override
  State<EgfrGraphPage> createState() => _EgfrGraphPageState();
}

class _EgfrGraphPageState extends State<EgfrGraphPage> {
  bool isLoading = true;
  List<Map<String, dynamic>> egfrRecords = [];

  @override
  void initState() {
    super.initState();
    loadEgfr();
  }

  Future<void> loadEgfr() async {
    final data = await PatientSupabaseService.getEgfrHistory(
      widget.patient.id,
    );

    setState(() {
      egfrRecords = data;
      isLoading = false;
    });
  }

  DateTime _parseDate(dynamic date) {
    return DateTime.parse(date.toString());
  }

  double _parseValue(dynamic value) {
    return double.tryParse(value.toString()) ?? 0;
  }

  @override
  Widget build(BuildContext context) {
    egfrRecords.sort(
      (a, b) => _parseDate(a['recorded_at'])
          .compareTo(_parseDate(b['recorded_at'])),
    );

    final spots = List.generate(
      egfrRecords.length,
      (i) => FlSpot(
        i.toDouble(),
        _parseValue(egfrRecords[i]['value']),
      ),
    );

    return Scaffold(
      appBar: AppBar(
        title: Text('${widget.patient.name} eGFR History'),
        centerTitle: true,
        actions: const [DoctorReviewNotificationBell()],
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : egfrRecords.isEmpty
              ? const Center(child: Text('No eGFR records found'))
              : Padding(
                  padding: Responsive.pagePadding(context),
                  child: Column(
                    children: [
                      Card(
                        child: ListTile(
                          title: Text(
                            widget.patient.name,
                            style: const TextStyle(
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          subtitle: Text(
                            'ID: ${widget.patient.id}\nWard Room No.: ${widget.patient.wardRoomNo}',
                          ),
                        ),
                      ),

                      SizedBox(height: Responsive.gap(context, 20)),

                      SizedBox(
                        height: Responsive.isCompact(context) ? 230 : 300,
                        child: LineChart(
                          LineChartData(
                            minY: 0,
                            gridData: const FlGridData(show: true),
                            borderData: FlBorderData(show: true),
                            titlesData: FlTitlesData(
                              topTitles: const AxisTitles(
                                sideTitles: SideTitles(showTitles: false),
                              ),
                              rightTitles: const AxisTitles(
                                sideTitles: SideTitles(showTitles: false),
                              ),
                              leftTitles: const AxisTitles(
                                axisNameWidget: Text('eGFR'),
                                sideTitles: SideTitles(
                                  showTitles: true,
                                  reservedSize: 40,
                                ),
                              ),
                              bottomTitles: AxisTitles(
                                axisNameWidget: const Text('Date'),
                                sideTitles: SideTitles(
                                  showTitles: true,
                                  reservedSize: 40,
                                  interval: 1,
                                  getTitlesWidget: (value, meta) {
                                    final index = value.toInt();

                                    if (index < 0 ||
                                        index >= egfrRecords.length) {
                                      return const SizedBox();
                                    }

                                    final date = egfrRecords[index]
                                            ['recorded_at']
                                        .toString()
                                        .split('T')[0];

                                    return Text(
                                      date.substring(5),
                                      style: const TextStyle(fontSize: 10),
                                    );
                                  },
                                ),
                              ),
                            ),
                            lineBarsData: [
                              LineChartBarData(
                                spots: spots,
                                isCurved: true,
                                barWidth: 3,
                                dotData: const FlDotData(show: true),
                              ),
                            ],
                          ),
                        ),
                      ),

                      SizedBox(height: Responsive.gap(context, 20)),

                      Expanded(
                        child: ListView.builder(
                          itemCount: egfrRecords.length,
                          itemBuilder: (context, index) {
                            final item = egfrRecords[index];

                            return Card(
                              child: ListTile(
                                title: Text('eGFR: ${item['value']}'),
                                subtitle: Text(
                                  'Date: ${item['recorded_at'].toString().split('T')[0]}',
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
