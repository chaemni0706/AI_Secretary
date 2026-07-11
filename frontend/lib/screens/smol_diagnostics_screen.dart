import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';

import '../services/smol_ondevice_verifier.dart';

/// **개발용(dev-only)** 온디바이스 SmolVLM ONNX 진단 화면.
///
/// 실기기(Galaxy Z Flip3 등)에서 SmolVLM ONNX 3종(q4f16)의 **session-load smoke** 를 수행한다.
/// - `getModelInfo`: 모델 파일 경로/존재/총 크기
/// - `isModelAvailable`: 필수 파일 존재 여부
/// - `warmup`: OrtSession 3종 로드 + input/output names + latency
/// - `verifyImage`: (현재 미구현 → fallback_required, 정상 동작 확인용)
///
/// **주의:** 실제 이미지 추론은 아직 미구현이다. 이 화면은 온디바이스 런타임 로드 검증용이며
/// 일반 사용자 플로우와 분리된 dev 도구다. 모델 파일(~356MB)은 앱 `filesDir/models/smolvlm/` 에 있어야 한다
/// (배치 방법은 루트 `SMOL_ONDEVICE_STATUS.md` 참조).
class SmolDiagnosticsScreen extends StatefulWidget {
  const SmolDiagnosticsScreen({super.key});

  @override
  State<SmolDiagnosticsScreen> createState() => _SmolDiagnosticsScreenState();
}

class _SmolDiagnosticsScreenState extends State<SmolDiagnosticsScreen> {
  static const _verifier = SmolOndeviceVerifier();
  String _output = '버튼을 눌러 온디바이스 SmolVLM 상태를 확인하세요.';
  bool _busy = false;

  // verifyImage spike 용 이미지 경로(앱 private dir 에 push 한 sample). getModelInfo 의 model_dir 참고.
  final _imgPathCtl = TextEditingController(
    text: '/data/user/0/com.example.frontend/files/models/smolvlm/sample.jpg',
  );

  final _encoder = const JsonEncoder.withIndent('  ');

  @override
  void dispose() {
    _imgPathCtl.dispose();
    super.dispose();
  }

  Future<void> _run(String label, Future<Object?> Function() action) async {
    setState(() {
      _busy = true;
      _output = '$label 실행 중...';
    });
    final sw = Stopwatch()..start();
    Object? result;
    String? error;
    try {
      result = await action();
    } catch (e) {
      error = e.toString();
    }
    sw.stop();
    if (!mounted) return;
    setState(() {
      _busy = false;
      final buf = StringBuffer()
        ..writeln('[$label]  (${sw.elapsedMilliseconds} ms)')
        ..writeln(error != null ? 'ERROR: $error' : _pretty(result));
      _output = buf.toString();
    });
  }

  String _pretty(Object? v) {
    try {
      return _encoder.convert(v);
    } catch (_) {
      return v.toString();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Smol 온디바이스 진단 (dev)')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              '온디바이스 SmolVLM ONNX 진단 (dev-only). warmup=session load, '
              'verifyImage=추론 spike(Level 1~4). 실제 인증은 서버 fallback.',
              style: TextStyle(fontSize: 12, color: Colors.grey),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilledButton(
                  onPressed: _busy ? null : () => _run('isModelAvailable', _verifier.isModelAvailable),
                  child: const Text('isModelAvailable'),
                ),
                FilledButton(
                  onPressed: _busy ? null : () => _run('getModelInfo', _verifier.getModelInfo),
                  child: const Text('getModelInfo'),
                ),
                FilledButton(
                  onPressed: _busy ? null : () => _run('warmup (OrtSession load)', _verifier.warmup),
                  child: const Text('warmup'),
                ),
              ],
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _imgPathCtl,
              style: const TextStyle(fontSize: 12),
              decoration: const InputDecoration(
                labelText: 'verifyImage 이미지 경로(앱 filesDir 권장)',
                isDense: true,
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 8),
            FilledButton.tonal(
              onPressed: _busy
                  ? null
                  : () => _run('verifyImage spike (L1~4)', () => _verifier.verifyImage(
                        imageFile: File(_imgPathCtl.text.trim()),
                        task: 'water',
                      )),
              child: const Text('verifyImage spike 실행'),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFF11161C),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: SingleChildScrollView(
                  child: SelectableText(
                    _output,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 12,
                      color: Color(0xFFD6E2F0),
                    ),
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
