import 'dart:io';

import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';

import '../core/utils/ledger_date.dart';
import '../models/medicine_ocr_models.dart';
import '../services/api_client.dart' show baseUrl, ApiException;
import '../services/camera_capture_service.dart';
import '../services/medicine_api.dart';

/// 약봉투 OCR 분석 화면.
///
/// 흐름: 카메라 촬영/갤러리 선택 → 미리보기 → 서버 분석 요청 → 결과 표시
///      → (사용자 확인) → 시작일 입력 → 복약 루틴 저장 요청 → 저장 결과 표시.
/// 카메라 캡처(CameraCaptureService)와 API 호출(MedicineApi)은 서로 분리되어 있다.
class MedicineOcrScreen extends StatefulWidget {
  const MedicineOcrScreen({super.key});

  @override
  State<MedicineOcrScreen> createState() => _MedicineOcrScreenState();
}

class _MedicineOcrScreenState extends State<MedicineOcrScreen> {
  File? _image;
  bool _analyzing = false;
  bool _saving = false;
  MedicineAnalysisResult? _analysis;
  List<MedicineRoutine>? _savedRoutines;
  String? _error;

  late final TextEditingController _startDateController;

  @override
  void initState() {
    super.initState();
    _startDateController = TextEditingController(text: yyyyMmDd(DateTime.now()));
  }

  @override
  void dispose() {
    _startDateController.dispose();
    super.dispose();
  }

  Future<void> _capture({bool fromGallery = false}) async {
    setState(() {
      _error = null;
      _analysis = null;
      _savedRoutines = null;
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

  Future<void> _analyze() async {
    final image = _image;
    if (image == null) {
      setState(() => _error = '먼저 약봉투 사진을 촬영하거나 선택해 주세요.');
      return;
    }
    setState(() {
      _analyzing = true;
      _error = null;
      _analysis = null;
      _savedRoutines = null;
    });
    try {
      final result = await medicineApi.analyzeMedicineImage(image);
      if (!mounted) return;
      setState(() {
        _analysis = result;
        if (result.dispensedDate != null && result.dispensedDate!.isNotEmpty) {
          _startDateController.text = result.dispensedDate!;
        }
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = '분석 중 오류가 발생했습니다: $e');
    } finally {
      if (mounted) setState(() => _analyzing = false);
    }
  }

  Future<void> _saveAsRoutine() async {
    final analysis = _analysis;
    if (analysis == null || analysis.medicines.isEmpty) return;
    final startDate = _startDateController.text.trim();
    if (startDate.isEmpty) {
      setState(() => _error = '복약 시작일을 입력해 주세요.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final routines = await medicineApi.createMedicineRoutines(
        medicines: analysis.medicines,
        startDate: startDate,
      );
      if (!mounted) return;
      setState(() => _savedRoutines = routines);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = '루틴 저장 중 오류가 발생했습니다: $e');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('약봉투 OCR 분석')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _serverHint(),
            const SizedBox(height: 16),
            _preview(),
            const SizedBox(height: 12),
            _captureButtons(),
            const SizedBox(height: 12),
            _analyzeButton(),
            const SizedBox(height: 16),
            if (_error != null) _errorCard(_error!),
            if (_analysis != null) ..._analysisSection(_analysis!),
            if (_savedRoutines != null) ..._savedRoutinesSection(_savedRoutines!),
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
    child: Text(
      t,
      style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
    ),
  );

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
                  Icon(
                    Icons.photo_camera_outlined,
                    size: 40,
                    color: Colors.grey,
                  ),
                  SizedBox(height: 8),
                  Text(
                    '촬영한 약봉투 사진이 여기에 표시됩니다',
                    style: TextStyle(color: Colors.grey),
                  ),
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
            onPressed: (_analyzing || _saving) ? null : () => _capture(),
            icon: const Icon(Icons.photo_camera),
            label: const Text('카메라 촬영'),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: OutlinedButton.icon(
            onPressed: (_analyzing || _saving)
                ? null
                : () => _capture(fromGallery: true),
            icon: const Icon(Icons.photo_library_outlined),
            label: const Text('갤러리'),
          ),
        ),
      ],
    );
  }

  Widget _analyzeButton() {
    return SizedBox(
      width: double.infinity,
      child: FilledButton.icon(
        onPressed: (_analyzing || _saving || _image == null) ? null : _analyze,
        icon: _analyzing
            ? const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : const Icon(Icons.document_scanner_outlined),
        label: Text(_analyzing ? '분석 중...' : '약봉투 분석하기'),
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
            Expanded(
              child: Text(
                msg,
                style: const TextStyle(color: Color(0xFFC62828)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _analysisSection(MedicineAnalysisResult analysis) {
    return [
      _sectionTitle('분석 결과 (${analysis.medicines.length}건)'),
      if (analysis.warning.isNotEmpty) _warningCard(analysis.warning),
      const SizedBox(height: 8),
      ...analysis.medicines.map(_medicineCard),
      const SizedBox(height: 16),
      if (_savedRoutines == null) ...[
        _sectionTitle('복약 시작일 확인'),
        if (analysis.dispensedDateNote.isNotEmpty) ...[
          Text(
            analysis.dispensedDateNote,
            style: const TextStyle(fontSize: 11.5, color: Colors.grey),
          ),
          const SizedBox(height: 6),
        ],
        TextField(
          controller: _startDateController,
          decoration: const InputDecoration(
            border: OutlineInputBorder(),
            hintText: 'YYYY-MM-DD',
            labelText: '시작일 (조제일 자동 반영, 필요 시 직접 수정)',
          ),
        ),
        const SizedBox(height: 12),
        SizedBox(
          width: double.infinity,
          child: FilledButton.icon(
            onPressed: (_saving || analysis.medicines.isEmpty)
                ? null
                : _saveAsRoutine,
            icon: _saving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.check_circle_outline),
            label: Text(_saving ? '저장 중...' : '확인 후 복약 루틴으로 저장'),
          ),
        ),
      ],
      const SizedBox(height: 16),
    ];
  }

  Widget _warningCard(String warning) {
    return Card(
      color: const Color(0xFFFFF6E0),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            const Icon(Icons.info_outline, color: Color(0xFF9A7B00)),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                warning,
                style: const TextStyle(fontSize: 12.5, color: Color(0xFF9A7B00)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _medicineCard(MedicineItem m) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              m.medicineName,
              style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 8),
            _doseInfoRow(
              Icons.medication_outlined,
              '복용량',
              m.dose.isNotEmpty ? m.dose : '확인 필요',
            ),
            _doseInfoRow(
              Icons.repeat,
              '복용 횟수',
              m.frequencyPerDay != null ? '하루 ${m.frequencyPerDay}회' : '확인 필요',
            ),
            _doseInfoRow(
              Icons.event_repeat_outlined,
              '복용 기간',
              m.durationDays != null ? '${m.durationDays}일분' : '확인 필요',
            ),
            const SizedBox(height: 4),
            const Text(
              '복용 시간은 루틴 저장 시 자동으로 설정됩니다.',
              style: TextStyle(fontSize: 11, color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }

  Widget _doseInfoRow(IconData icon, String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 3),
      child: Row(
        children: [
          Icon(icon, size: 15, color: Colors.grey),
          const SizedBox(width: 6),
          Text(
            '$label  ',
            style: const TextStyle(fontSize: 12.5, color: Colors.grey),
          ),
          Text(
            value,
            style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }

  List<Widget> _savedRoutinesSection(List<MedicineRoutine> routines) {
    return [
      _sectionTitle('복약 루틴 저장 완료 (${routines.length}건)'),
      ...routines.map(
        (r) => Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  r.medicineName,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 4),
                Text(r.doseText, style: const TextStyle(fontSize: 13)),
                const SizedBox(height: 4),
                Text(
                  '매일 ${r.times.join(' / ')}',
                  style: const TextStyle(fontSize: 12, color: Colors.grey),
                ),
                const SizedBox(height: 2),
                Text(
                  '${r.startDate} ~ ${r.endDate}',
                  style: const TextStyle(fontSize: 12, color: Colors.grey),
                ),
              ],
            ),
          ),
        ),
      ),
    ];
  }
}
