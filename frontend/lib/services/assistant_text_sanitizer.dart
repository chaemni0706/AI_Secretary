/// AI 응답/음성 문구를 화면 표시·TTS 재생 전에 다듬는 방어 유틸.
///
/// 배경: 음성 파이프라인(STT→라우팅→TTS)에서 드물게 인코딩 손상이나 빈
/// 응답이 흘러들어와 깨진 문장이 노출되는 문제가 보고됐다. 여기서는 프로그램이
/// "확실히" 깨졌다고 판단할 수 있는 경우만 정리한다:
///   - 유니코드 대체 문자(U+FFFD)  — 인코딩 손상 신호
///   - 고립된 한글 자모(정상 음절이 아닌 낱자 ㄱ/ㅏ 등)
///   - 빈/공백뿐인 문자열
/// 위 경우를 제거·정리하고, 결과가 비면 안전한 기본 문구로 대체한다.
///
/// 주의: "읹" 처럼 문법상은 이상하지만 유효한 한글 음절로 이뤄진 오인식은
/// 기계적으로 구분할 수 없어 여기서 걸러내지 않는다(런타임/STT 단계 이슈).
library;

const String kAssistantFallbackText = '요청을 확인했어요. 다시 한 번 말씀해 주세요.';

/// 고립 한글 자모(초성/중성/종성 낱자, 호환 자모, 확장 자모) 매칭.
final RegExp _isolatedJamo =
    RegExp(r'[ᄀ-ᇿ㄰-㆏ꥠ-꥿ힰ-퟿]');

/// 표시/재생용으로 AI 문구를 정리한다. 손상이 심해 내용이 사라지면 [fallback].
String sanitizeAssistantText(
  String? raw, {
  String fallback = kAssistantFallbackText,
}) {
  if (raw == null) return fallback;
  var s = raw.replaceAll('�', ''); // 대체 문자 제거
  s = s.replaceAll(_isolatedJamo, ''); // 고립 자모 제거
  s = s.replaceAll(RegExp(r'\s+'), ' ').trim();
  return s.isEmpty ? fallback : s;
}
