import 'dart:io';

import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';

import '../models/image_verification_result.dart';
import '../services/api_client.dart' show baseUrl, ApiException;
import '../services/camera_capture_service.dart';
import '../services/image_verification_service.dart';
import '../services/streak_store.dart';
import '../widgets/exercise_streak_badge.dart';
import 'smol_diagnostics_screen.dart';

/// 이미지 인증 화면.
///
/// 흐름: (인증 타입/운동 종류 선택) → 카메라 촬영 → 미리보기 → 서버 업로드 → 결과 표시.
/// 카메라 캡처(CameraCaptureService)와 API 호출(VerificationApi)은 서로 분리되어 있다.
class ImageVerificationScreen extends StatefulWidget {
  const ImageVerificationScreen({super.key});

  @override
  State<ImageVerificationScreen> createState() => _ImageVerificationScreenState();
}

class _ImageVerificationScreenState extends State<ImageVerificationScreen> {
  static const _types = <String, String>{
    'water': '물',
    'exercise': '운동',
    'study': '공부',
    'wake_up': '기상',
  };
  // task별 안내 문구(선택 시 상단 힌트).
  static const _typeHints = <String, String>{
    'water': '물이 잘 보이도록 촬영해 주세요.',
    'exercise': '운동 동작·기구·공간이 보이도록 촬영해 주세요.',
    'study': '책·노트·학습 화면이 보이도록 촬영해 주세요.',
    'wake_up': '기상 후 현재 상태를 촬영해 인증해 주세요. (얼굴 식별이 아니라 기상 상황 확인)',
  };
  static const _activityTypes = <String, String>{
    'gym': '헬스장',
    'home_workout': '홈트',
  };

  String _verificationType = 'water';
  String _activityType = 'gym';

  File? _image;
  bool _loading = false;
  ImageVerificationResult? _result;
  String? _error;

  /// 운동 인증 성공 시 계산된 연속 일수(스트릭). null 이면 배지 미표시.
  int? _streak;

  bool get _isExercise => _verificationType == 'exercise';

  Future<void> _capture({bool fromGallery = false}) async {
    setState(() {
      _error = null;
      _result = null;
      _streak = null;
    });
    try {
      File? file;
      if (fromGallery) {
        file = await cameraCaptureService.pickFromGallery();
      } else {
        final granted = await _ensureCameraPermission();
        if (!granted) {
          setState(() => _error = '카메라 권한이 필요합니다. 설정에서 권한을 허용해 주세요.');
          return;
        }
        file = await cameraCaptureService.captureImage();
      }
      if (file != null) {
        setState(() => _image = file);
      }
    } catch (e) {
      setState(() => _error = '이미지를 가져오지 못했습니다: $e');
    }
  }

  Future<bool> _ensureCameraPermission() async {
    final status = await Permission.camera.status;
    if (status.isGranted) return true;
    final result = await Permission.camera.request();
    return result.isGranted;
  }

  Future<void> _submit() async {
    final image = _image;
    if (image == null) {
      setState(() => _error = '먼저 사진을 촬영하거나 선택해 주세요.');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
      _result = null;
      _streak = null;
    });
    try {
      // Smol **blocker-only** local-first → 아니면 서버 Qwen fallback(오케스트레이터).
      // 모델이 없는 일반 기기에선 Smol 이 inert → 서버 경로 그대로.
      final result = await imageVerificationService.verify(
        imageFile: image,
        task: _verificationType,
        activityType: _isExercise ? _activityType : null,
      );
      if (!mounted) return;
      // 운동 인증 성공 → 오늘 성공을 기록하고 연속 일수(스트릭) 계산.
      int? streak;
      if (_isExercise && result.finalResult == 'verified' && !result.needsRetake) {
        streak = await streakStore.recordSuccess('exercise');
      }
      if (!mounted) return;
      setState(() {
        _result = result;
        _streak = streak;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = '요청 중 오류가 발생했습니다: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('이미지 인증'),
        actions: [
          // dev-only: 온디바이스 SmolVLM ONNX session-load 진단(일반 사용자 플로우와 분리).
          if (kDebugMode)
            IconButton(
              tooltip: 'Smol 온디바이스 진단 (dev)',
              icon: const Icon(Icons.memory),
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const SmolDiagnosticsScreen()),
              ),
            ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _serverHint(),
            const SizedBox(height: 12),
            _sectionTitle('인증 종류'),
            _typeSelector(),
            if (_typeHints[_verificationType] != null) ...[
              const SizedBox(height: 6),
              Text(_typeHints[_verificationType]!,
                  style: const TextStyle(fontSize: 12, color: Colors.grey)),
            ],
            if (_isExercise) ...[
              const SizedBox(height: 12),
              _sectionTitle('운동 종류 (필수)'),
              _activitySelector(),
            ],
            const SizedBox(height: 16),
            _preview(),
            const SizedBox(height: 12),
            _captureButtons(),
            const SizedBox(height: 12),
            _submitButton(),
            const SizedBox(height: 16),
            if (_error != null) _errorCard(_error!),
            if (_result != null) _resultCard(_result!),
            if (_streak != null) ...[
              const SizedBox(height: 12),
              // 시연 팁: 배지를 길게 누르면 지난 6일을 성공 처리해
              // "7일 연속" 상태를 바로 재현할 수 있다(화면 표시는 없음).
              GestureDetector(
                onLongPress: _seedStreakDemo,
                child: ExerciseStreakBadge(streak: _streak!),
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// 시연용: 지난 6일을 성공 처리 → 오늘 인증 성공과 합쳐 "7일 연속"을 재현.
  Future<void> _seedStreakDemo() async {
    await streakStore.seedDemo('exercise', 6);
    final streak = await streakStore.currentStreak('exercise');
    if (!mounted) return;
    setState(() => _streak = streak);
  }

  Widget _serverHint() => Text(
        '서버: $baseUrl',
        style: const TextStyle(fontSize: 12, color: Colors.grey),
      );

  Widget _sectionTitle(String t) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(t, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
      );

  Widget _typeSelector() {
    return Wrap(
      spacing: 8,
      children: _types.entries.map((e) {
        final selected = _verificationType == e.key;
        return ChoiceChip(
          label: Text(e.value),
          selected: selected,
          onSelected: (_) => setState(() {
            _verificationType = e.key;
            _result = null;
            _error = null;
            _streak = null;
          }),
        );
      }).toList(),
    );
  }

  Widget _activitySelector() {
    return Wrap(
      spacing: 8,
      children: _activityTypes.entries.map((e) {
        final selected = _activityType == e.key;
        return ChoiceChip(
          label: Text(e.value),
          selected: selected,
          onSelected: (_) => setState(() => _activityType = e.key),
        );
      }).toList(),
    );
  }

  Widget _preview() {
    return Container(
      height: 240,
      width: double.infinity,
      decoration: BoxDecoration(
        color: const Color(0xFFF1F2F6),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFDADCE3)),
      ),
      clipBehavior: Clip.antiAlias,
      child: _image == null
          ? const Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.photo_camera_outlined, size: 40, color: Colors.grey),
                  SizedBox(height: 8),
                  Text('촬영한 사진이 여기에 표시됩니다', style: TextStyle(color: Colors.grey)),
                ],
              ),
            )
          : Image.file(_image!, fit: BoxFit.contain),
    );
  }

  Widget _captureButtons() {
    // 일반 사용자 인증은 **직접 촬영만** 허용(갤러리 업로드 금지 — 과거/타인 사진 방지).
    // 갤러리 선택은 kDebugMode 진단 화면에서만 유지된다.
    return SizedBox(
      width: double.infinity,
      child: FilledButton.icon(
        onPressed: _loading ? null : () => _capture(),
        icon: const Icon(Icons.photo_camera),
        label: const Text('카메라 촬영'),
      ),
    );
  }

  Widget _submitButton() {
    return SizedBox(
      width: double.infinity,
      child: FilledButton.icon(
        onPressed: (_loading || _image == null) ? null : _submit,
        icon: _loading
            ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
            : const Icon(Icons.verified_outlined),
        label: Text(_loading ? '인증 중...' : '인증 요청'),
      ),
    );
  }

  Widget _errorCard(String msg) {
    return Card(
      color: const Color(0xFFFDECEC),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            const Icon(Icons.error_outline, color: Color(0xFFC62828)),
            const SizedBox(width: 10),
            Expanded(child: Text(msg, style: const TextStyle(color: Color(0xFFC62828)))),
          ],
        ),
      ),
    );
  }

  Widget _resultCard(ImageVerificationResult r) {
    // 자동 인증 확정 불가(needsRetake)는 verified 와 구분해 amber 로 표시(자동 성공 아님 → 재촬영 안내).
    final (color, icon) = r.needsRetake
        ? (const Color(0xFFF9A825), Icons.camera_alt_outlined)
        : switch (r.finalResult) {
            'verified' => (const Color(0xFF2E7D32), Icons.check_circle),
            'retake_required' => (const Color(0xFFEF6C00), Icons.refresh),
            _ => (const Color(0xFFC62828), Icons.cancel),
          };
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: color),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    r.displayMessage,
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: color),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text('타입: ${r.task}  ·  판정: ${r.finalResult}'
                '${r.smolBlockerDetected ? '  ·  로컬(Smol) 감지' : ''}'
                '${r.score != null ? '  ·  점수: ${r.score}' : ''}'),
            if (r.needsRetake) ...[
              const SizedBox(height: 6),
              Text(
                r.smolBlockerDetected
                    ? '로컬 분석에서 인증 조건과 다른 단서가 감지됐어요. 과제에 맞는 장면이 잘 보이도록 다시 촬영해 주세요.'
                    : '사진상 물처럼 보이지만 물의 종류나 촬영 맥락을 확실히 판단하기 어려워 '
                        '자동 인증할 수 없어요. 다른 사진으로 다시 촬영해 주세요.',
                style: const TextStyle(fontSize: 12, color: Color(0xFFF9A825)),
              ),
              const SizedBox(height: 4),
              const Text('위 “카메라 촬영” 으로 다시 시도할 수 있어요.',
                  style: TextStyle(fontSize: 11, color: Color(0xFFB0812A))),
            ],
            if (r.reasons.isNotEmpty) ...[
              const SizedBox(height: 10),
              const Text('근거', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 4),
              ...r.reasons.map((m) => Padding(
                    padding: const EdgeInsets.only(bottom: 2),
                    child: Text('• $m', style: const TextStyle(fontSize: 13)),
                  )),
            ],
          ],
        ),
      ),
    );
  }
}
