import 'dart:io';

import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';

import '../models/verification_result.dart';
import '../services/api_client.dart' show baseUrl, ApiException;
import '../services/camera_capture_service.dart';
import '../services/verification_api.dart';

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
  };
  static const _activityTypes = <String, String>{
    'gym': '헬스장',
    'home_workout': '홈트',
  };

  String _verificationType = 'water';
  String _activityType = 'gym';

  File? _image;
  bool _loading = false;
  VerificationResult? _result;
  String? _error;

  bool get _isExercise => _verificationType == 'exercise';

  Future<void> _capture({bool fromGallery = false}) async {
    setState(() {
      _error = null;
      _result = null;
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
    });
    try {
      final result = await verificationApi.submitImageVerification(
        verificationType: _verificationType,
        imageFile: image,
        activityType: _isExercise ? _activityType : null,
      );
      if (!mounted) return;
      setState(() => _result = result);
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
      appBar: AppBar(title: const Text('이미지 인증')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _serverHint(),
            const SizedBox(height: 12),
            _sectionTitle('인증 종류'),
            _typeSelector(),
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
          ],
        ),
      ),
    );
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
    return Row(
      children: [
        Expanded(
          child: FilledButton.icon(
            onPressed: _loading ? null : () => _capture(),
            icon: const Icon(Icons.photo_camera),
            label: const Text('카메라 촬영'),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: OutlinedButton.icon(
            onPressed: _loading ? null : () => _capture(fromGallery: true),
            icon: const Icon(Icons.photo_library_outlined),
            label: const Text('갤러리'),
          ),
        ),
      ],
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

  Widget _resultCard(VerificationResult r) {
    // secondary_review(비시각 맥락 확인 필요)는 verified 와 구분해 amber 로 표시(자동 확정 아님).
    final (color, icon) = r.needsSecondaryReview
        ? (const Color(0xFFF9A825), Icons.help_outline)
        : switch (r.result) {
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
            Text('타입: ${r.verificationType}  ·  판정: ${r.result}'
                '${r.score != null ? '  ·  점수: ${r.score}' : ''}'),
            if (r.needsSecondaryReview) ...[
              const SizedBox(height: 6),
              Text(
                '외관만으로는 확정이 어려워 추가 확인이 필요해요 (${r.reviewReason}).',
                style: const TextStyle(fontSize: 12, color: Color(0xFFF9A825)),
              ),
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
