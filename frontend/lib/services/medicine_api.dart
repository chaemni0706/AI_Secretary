import 'dart:io';

import 'package:dio/dio.dart';

import '../models/medicine_ocr_models.dart';
import 'api_client.dart';

/// 약봉투 OCR / 복약 루틴 API 클라이언트.
///
///   POST /api/v1/medicine/analyze   (multipart, field name: file)
///   POST /api/v1/routines/medicine
///   GET  /api/v1/routines/medicine
///
/// 카메라 캡처(CameraCaptureService)와 분리되어 있으며, File 을 받아 업로드만 담당한다.
class MedicineApi {
  const MedicineApi();

  /// 촬영/선택한 약봉투 이미지를 분석 API로 업로드한다.
  Future<MedicineAnalysisResult> analyzeMedicineImage(File imageFile) async {
    final filename = imageFile.path.split(Platform.pathSeparator).last;
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(imageFile.path, filename: filename),
    });

    final data = await apiClient.postMultipart(
      '$apiPrefix/medicine/analyze',
      formData,
    );

    if (data is Map) {
      return MedicineAnalysisResult.fromJson(Map<String, dynamic>.from(data));
    }
    throw ApiException('예상치 못한 응답 형식입니다.', responseBody: data);
  }

  /// 사용자가 확인한 약 목록을 복약 루틴으로 저장한다.
  Future<List<MedicineRoutine>> createMedicineRoutines({
    required List<MedicineItem> medicines,
    required String startDate,
  }) async {
    final body = {
      'medicines': medicines.map((m) => m.toRoutineRequestJson()).toList(),
      'start_date': startDate,
    };

    final data = await apiClient.postData(
      '$apiPrefix/routines/medicine',
      body: body,
    );

    return _parseRoutines(data);
  }

  /// 저장된 복약 루틴 목록을 조회한다.
  Future<List<MedicineRoutine>> getMedicineRoutines() async {
    final data = await apiClient.getData('$apiPrefix/routines/medicine');
    return _parseRoutines(data);
  }

  List<MedicineRoutine> _parseRoutines(dynamic data) {
    if (data is Map && data['routines'] is List) {
      return (data['routines'] as List)
          .map((e) => MedicineRoutine.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
    }
    throw ApiException('예상치 못한 응답 형식입니다.', responseBody: data);
  }
}

/// 간편 접근용 전역 인스턴스.
const medicineApi = MedicineApi();
