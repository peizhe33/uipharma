import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';

/// Wristband scanner for the Raspberry Pi (Linux desktop build).
///
/// The Pi camera is only switched on while this screen is open:
/// - opening the screen starts `pi_scanner.py`, which reports the QR value on
///   its output and keeps the latest camera frame in a temp JPEG that is
///   shown here as a live preview;
/// - leaving the screen (code read, cancel, back) stops the script, which
///   closes the camera.
///
/// A USB barcode gun still works as well: it types into the hidden text field.
class PiScannerPage extends StatefulWidget {
  const PiScannerPage({super.key});

  @override
  State<PiScannerPage> createState() => _PiScannerPageState();
}

enum _CameraState { starting, scanning, error }

class _PiScannerPageState extends State<PiScannerPage> {
  static const Duration _previewInterval = Duration(milliseconds: 100);

  final TextEditingController _controller = TextEditingController();
  final FocusNode _focusNode = FocusNode();

  Process? _process;
  StreamSubscription<String>? _stdoutSub;
  StreamSubscription<String>? _stderrSub;
  Timer? _previewTimer;
  bool _previewBusy = false;
  DateTime? _previewStamp;
  Uint8List? _previewBytes;

  _CameraState _state = _CameraState.starting;
  String? _errorMessage;
  final List<String> _stderrTail = <String>[];

  /// True once the screen is closing; nothing may touch the UI after that.
  bool _closed = false;

  late final String _previewPath =
      '${Directory.systemTemp.path}${Platform.pathSeparator}'
      'smartpharma_preview_$pid.jpg';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _focusNode.requestFocus();
      _startCamera();
    });
  }

  @override
  void dispose() {
    _closed = true;
    _stopCamera();
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  // ---------------------------------------------------------------------------
  // Camera process
  // ---------------------------------------------------------------------------

  /// Finds pi_scanner.py: an explicit SMARTPHARMA_SCANNER path, the folder the
  /// app was started from, or a folder above the executable (a release build
  /// runs from <project>/build/linux/<arch>/release/bundle).
  static String? _findScannerScript() {
    final candidates = <String>[];
    final fromEnv = Platform.environment['SMARTPHARMA_SCANNER'];
    if (fromEnv != null && fromEnv.trim().isNotEmpty) {
      candidates.add(fromEnv.trim());
    }
    candidates.add('${Directory.current.path}/pi_scanner.py');
    var dir = File(Platform.resolvedExecutable).parent;
    for (var i = 0; i < 6; i++) {
      candidates.add('${dir.path}/pi_scanner.py');
      dir = dir.parent;
    }
    for (final path in candidates) {
      if (File(path).existsSync()) return path;
    }
    return null;
  }

  Future<void> _startCamera() async {
    _deletePreviewFile();

    final script = _findScannerScript();
    if (script == null) {
      _showError(
        'pi_scanner.py was not found.\n'
        'Start the app with ~/start_smartpharma.sh from the project folder.',
      );
      return;
    }

    final Process process;
    try {
      process = await Process.start(
        Platform.isWindows ? 'python' : 'python3',
        <String>['-u', script, '--once', '--preview-file', _previewPath],
        workingDirectory: File(script).parent.path,
      );
    } on ProcessException catch (e) {
      _showError('Could not start the camera script.\n${e.message}');
      return;
    }

    // The screen may have been closed while the process was starting.
    if (_closed || _state == _CameraState.error) {
      process.kill();
      return;
    }
    _process = process;

    _stdoutSub = process.stdout
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .listen(
          _handleScannerLine,
          onDone: () => _handleScannerExit(process),
        );
    _stderrSub = process.stderr
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .listen((line) {
      _stderrTail.add(line);
      if (_stderrTail.length > 6) _stderrTail.removeAt(0);
    });

    _previewTimer = Timer.periodic(_previewInterval, (_) => _refreshPreview());
  }

  void _handleScannerLine(String line) {
    if (_closed) return;
    if (line.startsWith('QR:')) {
      final value = line.substring(3).trim();
      if (value.isNotEmpty) _finishWith(value);
    } else if (line.startsWith('ERROR:')) {
      _showError(line.substring(6).trim());
    } else if (line.startsWith('READY')) {
      if (_state == _CameraState.starting) {
        setState(() => _state = _CameraState.scanning);
      }
    }
  }

  Future<void> _handleScannerExit(Process process) async {
    // Ignore a scanner we stopped on purpose.
    if (_closed || !identical(_process, process)) return;
    final code = await process.exitCode;
    if (_closed || !identical(_process, process)) return;
    final details =
        _stderrTail.isEmpty ? '' : '\n\n${_stderrTail.join('\n')}';
    _showError('The camera stopped unexpectedly (exit code $code).$details');
  }

  /// Stops the camera script and preview. Safe to call more than once.
  void _stopCamera() {
    _previewTimer?.cancel();
    _previewTimer = null;
    _stdoutSub?.cancel();
    _stdoutSub = null;
    _stderrSub?.cancel();
    _stderrSub = null;
    final process = _process;
    _process = null;
    process?.kill(); // SIGTERM: the script closes the camera cleanly.
    _deletePreviewFile();
  }

  void _deletePreviewFile() {
    try {
      final file = File(_previewPath);
      if (file.existsSync()) file.deleteSync();
    } catch (_) {
      // Nothing to clean up, or the scanner is replacing the file right now.
    }
  }

  Future<void> _refreshPreview() async {
    if (_previewBusy || _closed) return;
    _previewBusy = true;
    try {
      final file = File(_previewPath);
      if (!await file.exists()) return;
      final stamp = await file.lastModified();
      final previous = _previewStamp;
      if (previous != null && !stamp.isAfter(previous)) return;
      final bytes = await file.readAsBytes();
      if (_closed || _state == _CameraState.error || bytes.isEmpty) return;
      _previewStamp = stamp;
      setState(() {
        _previewBytes = bytes;
        _state = _CameraState.scanning;
      });
    } catch (_) {
      // The scanner was swapping the file; the next tick picks it up.
    } finally {
      _previewBusy = false;
    }
  }

  // ---------------------------------------------------------------------------
  // Results
  // ---------------------------------------------------------------------------

  void _finishWith(String value) {
    if (_closed) return;
    _closed = true;
    _stopCamera();
    Navigator.pop(context, value);
  }

  void _showError(String message) {
    if (_closed) return;
    _stopCamera();
    setState(() {
      _state = _CameraState.error;
      _errorMessage = message;
      _previewBytes = null;
    });
  }

  void _retry() {
    setState(() {
      _state = _CameraState.starting;
      _errorMessage = null;
      _previewBytes = null;
      _previewStamp = null;
      _stderrTail.clear();
    });
    _focusNode.requestFocus();
    _startCamera();
  }

  /// Input from a USB barcode gun (it types the code and presses Enter).
  void _handleSubmitted(String value) {
    final trimmedValue = value.trim();
    if (trimmedValue.isNotEmpty) {
      _finishWith(trimmedValue);
    } else {
      _focusNode.requestFocus();
    }
  }

  // ---------------------------------------------------------------------------
  // UI
  // ---------------------------------------------------------------------------

  String get _statusText {
    if (_state == _CameraState.error) return 'Camera is off.';
    if (_state == _CameraState.starting) return 'Starting camera...';
    return 'Camera on. Hold the QR code 10 to 30 cm from the lens.';
  }

  Widget _buildCameraArea() {
    if (_state == _CameraState.error) {
      return Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.videocam_off, color: Colors.white70, size: 56),
              const SizedBox(height: 12),
              Text(
                _errorMessage ?? 'Camera error',
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.white, fontSize: 15),
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _retry,
                icon: const Icon(Icons.refresh),
                label: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
    }

    final bytes = _previewBytes;
    if (bytes == null) {
      return const Center(
        child: CircularProgressIndicator(color: Colors.white),
      );
    }
    return Image.memory(
      bytes,
      fit: BoxFit.contain,
      gaplessPlayback: true,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.teal.shade900,
      body: SafeArea(
        child: Stack(
          children: [
            Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text(
                      'Please hold your wristband to the camera',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 26,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 20),
                    ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 720),
                      child: AspectRatio(
                        aspectRatio: 16 / 9,
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(16),
                          child: ColoredBox(
                            color: Colors.black,
                            child: _buildCameraArea(),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      _statusText,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: Colors.white70,
                        fontSize: 16,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            Positioned(
              right: 8,
              top: 8,
              child: IconButton(
                tooltip: 'Cancel scan',
                icon: const Icon(Icons.close, color: Colors.white, size: 32),
                onPressed: () => Navigator.pop(context),
              ),
            ),
            // Hidden field for a USB barcode gun, as in the original screen.
            Positioned(
              left: 0,
              top: 0,
              child: Opacity(
                opacity: 0.0,
                child: SizedBox(
                  width: 1,
                  height: 1,
                  child: TextField(
                    controller: _controller,
                    focusNode: _focusNode,
                    autofocus: true,
                    onSubmitted: _handleSubmitted,
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
