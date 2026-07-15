import '../models/voice_chat_message.dart';
import 'local_emotion_classifier.dart';

/// (Deprecated) 온디바이스 감정 공감 fallback.
///
/// 로직은 [LocalEmotionClassifier] 로 통합되었다. 기존 호출부 호환을 위해
/// 얇은 위임만 남겨둔다. 신규 코드는 [LocalEmotionClassifier.classify] 를 쓴다.
@Deprecated('Use LocalEmotionClassifier.classify')
class LocalEmotion {
  static EmotionAnalysis analyze(String text) =>
      LocalEmotionClassifier.classify(text);
}
