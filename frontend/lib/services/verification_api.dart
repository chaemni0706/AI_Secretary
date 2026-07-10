import 'dart:io';

import 'package:dio/dio.dart';

import '../models/verification_result.dart';
import 'api_client.dart';

/// 이미지 인증 API 클라이언트.
///
/// 통합 인증 도메인의 VLM 이미지 인증 엔드포인트를 호출한다:
///   POST /api/v1/verification/image/water
///   POST /api/v1/verification/image/exercise   (activity_type 필수)
///   POST /api/v1/verification/image/study
///
/// 카메라 캡처(CameraCaptureService)와 분리되어 있으며, File 을 받아 업로드만 담당한다.
class VerificationApi {
  const VerificationApi();

  static const Set<String> imageVerificationTypes = {
    'water',
    'exercise',
    'study',
  };

  /// 촬영/선택한 이미지 파일을 인증 타입별 엔드포인트로 업로드한다.
  ///
  /// - [verificationType]: water | exercise | study
  /// - [imageFile]: 카메라/갤러리에서 얻은 파일
  /// - [activityType]: exercise 일 때 필수 (gym | home_workout 등)
  Future<VerificationResult> submitImageVerification({
    required String verificationType,
    required File imageFile,
    String? activityType,
  }) async {
    if (!imageVerificationTypes.contains(verificationType)) {
      throw ApiException('지원하지 않는 인증 타입입니다: $verificationType');
    }
    if (verificationType == 'exercise' &&
        (activityType == null || activityType.isEmpty)) {
      throw ApiException('운동 인증에는 activity_type(gym/home_workout)이 필요합니다.');
    }

    final filename = imageFile.path.split(Platform.pathSeparator).last;
    final formData = FormData.fromMap({
      if (activityType != null && activityType.isNotEmpty)
        'activity_type': activityType,
      'file': await MultipartFile.fromFile(imageFile.path, filename: filename),
    });

    final data = await apiClient.postMultipart(
      '$apiPrefix/verification/image/$verificationType',
      formData,
    );

    if (data is Map) {
      return VerificationResult.fromData(Map<String, dynamic>.from(data));
    }
    throw ApiException('예상치 못한 응답 형식입니다.', responseBody: data);
  }
}

/// 간편 접근용 전역 인스턴스.
const verificationApi = VerificationApi();
