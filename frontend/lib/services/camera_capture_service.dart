import 'dart:io';

import 'package:image_picker/image_picker.dart';

/// 카메라 캡처 전용 서비스.
///
/// 인증 API 호출 로직과 **분리**되어 있다. 촬영 결과 파일(File)은
/// (1) 이미지 인증 API 업로드, (2) 추후 온디바이스 소형 VLM 입력 등 어디에나 재사용할 수 있다.
/// 즉 "캡처"는 "판정/업로드"를 알지 못하며, 순수하게 이미지 파일만 만든다.
class CameraCaptureService {
  CameraCaptureService({ImagePicker? picker}) : _picker = picker ?? ImagePicker();

  final ImagePicker _picker;

  /// Z Flip3 후면 카메라로 촬영해 파일을 반환한다. 사용자가 취소하면 null.
  ///
  /// - [imageQuality] 85: 화질/용량 균형 (업로드·온디바이스 추론 모두 무난)
  /// - [maxWidth] 1280: 긴 변 축소로 업로드/추론 속도 확보
  Future<File?> captureImage({
    int imageQuality = 85,
    double maxWidth = 1280,
    CameraDevice preferredCameraDevice = CameraDevice.rear,
  }) async {
    final XFile? shot = await _picker.pickImage(
      source: ImageSource.camera,
      imageQuality: imageQuality,
      maxWidth: maxWidth,
      preferredCameraDevice: preferredCameraDevice,
    );
    if (shot == null) return null;
    return File(shot.path);
  }

  /// 갤러리에서 이미지 선택 (테스트/대체 입력용). 동일하게 File 을 반환한다.
  Future<File?> pickFromGallery({
    int imageQuality = 85,
    double maxWidth = 1280,
  }) async {
    final XFile? shot = await _picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: imageQuality,
      maxWidth: maxWidth,
    );
    if (shot == null) return null;
    return File(shot.path);
  }
}

/// 간편 접근용 전역 인스턴스.
final cameraCaptureService = CameraCaptureService();
