import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../services/smol_ondevice_verifier.dart';

/// **개발용(dev-only)** 온디바이스 SmolVLM ONNX 진단 화면.
///
/// 실기기(Galaxy Z Flip3 등)에서 SmolVLM ONNX 3종(q4f16)의 **session-load smoke** 를 수행한다.
/// - `getModelInfo`: 모델 파일 경로/존재/총 크기
/// - `isModelAvailable`: 필수 파일 존재 여부
/// - `warmup`: OrtSession 3종 로드 + input/output names + latency
/// - `verifyImage`: 추론 spike(L1~L4: vision/embed/decoder-step/padded no-cache gen)
/// - `imageTextGen`: 이미지→텍스트 생성 + task별 evidence 변환 spike
///   (image merge + 패딩 no-cache 생성 + detokenize + [SmolEvidenceParser] → Rule Engine 호환 payload)
///
/// **주의:** 실기기 이미지→텍스트 생성 + evidence 변환까지 검증됨(diagnostics-only spike). 단 evidence→Rule Engine
/// 자동 판정/앱 인증 연결은 미구현이며 실제 인증은 서버 fallback 이 담당한다(water local accept 금지 유지).
/// 이 화면은 온디바이스 런타임 검증용 dev 도구로
/// 일반 사용자 플로우와 분리돼 있다. 모델 파일(~356MB)은 앱 `filesDir/models/smolvlm/` 에 있어야 한다
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
  String _task = 'water'; // evidence 변환 대상 task(water/study/exercise)

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

  /// 갤러리에서 이미지 선택(dev). image_picker 는 선택 파일을 앱 캐시로 복사해 반환하므로
  /// 앱 프로세스가 바로 읽을 수 있다(실기기 data-dir EROFS / 외부 dir FUSE 격리 우회).
  Future<void> _pickFromGallery() async {
    try {
      final XFile? x = await ImagePicker().pickImage(source: ImageSource.gallery);
      if (x == null) return;
      if (!mounted) return;
      setState(() => _imgPathCtl.text = x.path);
    } catch (e) {
      if (!mounted) return;
      setState(() => _output = '갤러리 선택 실패: $e');
    }
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
            FilledButton.tonalIcon(
              onPressed: _busy ? null : _pickFromGallery,
              icon: const Icon(Icons.photo_library, size: 18),
              label: const Text('갤러리에서 이미지 선택 (EROFS/FUSE 우회)'),
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
            Row(
              children: [
                Expanded(
                  child: FilledButton.tonal(
                    onPressed: _busy
                        ? null
                        : () => _run('verifyImage spike (L1~4)', () => _verifier.verifyImage(
                              imageFile: File(_imgPathCtl.text.trim()),
                              task: 'water',
                            )),
                    child: const Text('verifyImage spike'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: FilledButton.tonal(
                    onPressed: _busy ? null : () => _run('L4 experiment (opt-level sweep)', _verifier.l4Experiment),
                    child: const Text('L4 experiment'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  const Text('evidence task: ', style: TextStyle(fontSize: 12, color: Colors.grey)),
                  const SizedBox(width: 8),
                  SegmentedButton<String>(
                    segments: const [
                      ButtonSegment(value: 'water', label: Text('water')),
                      ButtonSegment(value: 'study', label: Text('study')),
                      ButtonSegment(value: 'exercise', label: Text('exercise')),
                    ],
                    selected: {_task},
                    onSelectionChanged: _busy ? null : (s) => setState(() => _task = s.first),
                    style: const ButtonStyle(visualDensity: VisualDensity.compact),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 8),
            FilledButton(
              onPressed: _busy
                  ? null
                  : () => _run('image+text→evidence spike ($_task)', () => _verifier.imageTextGen(
                        imageFile: File(_imgPathCtl.text.trim()),
                        task: _task,
                      )),
              child: const Text('image+text→evidence (Rule Engine payload)'),
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
