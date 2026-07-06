/// 음성 챗봇 화면에서 사용하는 채팅 메시지 및 감정 분석 모델.
///
/// 감정 분석 관련 모델은 백엔드 `POST /api/v1/emotion/analyze` 의
/// 공통 응답 `{ success, message, data }` 중 `data` 구조에 맞춘 것이다.

/// 메시지 발신자 구분.
enum ChatRole { user, assistant }

/// 채팅 말풍선 1개를 나타낸다.
class VoiceChatMessage {
  final ChatRole role;
  final String text;

  /// AI 메시지에 한해 감정 분석 결과를 함께 담는다(사용자 메시지는 null).
  final EmotionAnalysis? analysis;

  /// AI 메시지에 한해 "음성으로 듣기" 대상 문장을 담는다.
  final String? ttsText;

  const VoiceChatMessage({
    required this.role,
    required this.text,
    this.analysis,
    this.ttsText,
  });

  bool get isUser => role == ChatRole.user;
}

/// `/api/v1/emotion/analyze` 의 data 구조.
class EmotionAnalysis {
  final Emotion emotion;
  final Burden burden;
  final EmpathyStrategy empathyStrategy;
  final String coachingReply;
  final List<ScheduleSuggestion> scheduleSuggestions;
  final String ttsText;
  final String safetyNote;

  const EmotionAnalysis({
    required this.emotion,
    required this.burden,
    required this.empathyStrategy,
    required this.coachingReply,
    required this.scheduleSuggestions,
    required this.ttsText,
    required this.safetyNote,
  });

  factory EmotionAnalysis.fromJson(Map<String, dynamic> json) {
    final suggestions = (json['schedule_suggestions'] as List?) ?? const [];
    return EmotionAnalysis(
      emotion: Emotion.fromJson(
        (json['emotion'] as Map<String, dynamic>?) ?? const {},
      ),
      burden: Burden.fromJson(
        (json['burden'] as Map<String, dynamic>?) ?? const {},
      ),
      empathyStrategy: EmpathyStrategy.fromJson(
        (json['empathy_strategy'] as Map<String, dynamic>?) ?? const {},
      ),
      coachingReply: (json['coaching_reply'] ?? '').toString(),
      scheduleSuggestions: suggestions
          .map((e) => ScheduleSuggestion.fromJson(e as Map<String, dynamic>))
          .toList(),
      ttsText: (json['tts_text'] ?? '').toString(),
      safetyNote: (json['safety_note'] ?? '').toString(),
    );
  }
}

class Emotion {
  final String label; // tired, happy, ...
  final String intensity; // low | medium | high
  final double confidence;

  const Emotion({
    required this.label,
    required this.intensity,
    required this.confidence,
  });

  factory Emotion.fromJson(Map<String, dynamic> json) {
    return Emotion(
      label: (json['label'] ?? '').toString(),
      intensity: (json['intensity'] ?? '').toString(),
      confidence: (json['confidence'] ?? 0).toDouble(),
    );
  }
}

class Burden {
  final String level; // low | medium | high
  final String reason;

  const Burden({required this.level, required this.reason});

  factory Burden.fromJson(Map<String, dynamic> json) {
    return Burden(
      level: (json['level'] ?? '').toString(),
      reason: (json['reason'] ?? '').toString(),
    );
  }
}

class EmpathyStrategy {
  final String type;
  final String description;

  const EmpathyStrategy({required this.type, required this.description});

  factory EmpathyStrategy.fromJson(Map<String, dynamic> json) {
    return EmpathyStrategy(
      type: (json['type'] ?? '').toString(),
      description: (json['description'] ?? '').toString(),
    );
  }
}

class ScheduleSuggestion {
  final String type; // reschedule_todo | rest | ...
  final String? targetId;
  final String suggestedStartTime; // ISO8601
  final String suggestedEndTime; // ISO8601
  final String reason;

  const ScheduleSuggestion({
    required this.type,
    required this.targetId,
    required this.suggestedStartTime,
    required this.suggestedEndTime,
    required this.reason,
  });

  factory ScheduleSuggestion.fromJson(Map<String, dynamic> json) {
    return ScheduleSuggestion(
      type: (json['type'] ?? '').toString(),
      targetId: json['target_id']?.toString(),
      suggestedStartTime: (json['suggested_start_time'] ?? '').toString(),
      suggestedEndTime: (json['suggested_end_time'] ?? '').toString(),
      reason: (json['reason'] ?? '').toString(),
    );
  }

  /// "HH:mm" 형태의 시작 시각(표시용).
  String get startHhmm => _hhmm(suggestedStartTime);

  /// "HH:mm" 형태의 종료 시각(표시용).
  String get endHhmm => _hhmm(suggestedEndTime);

  static String _hhmm(String iso) {
    final dt = DateTime.tryParse(iso);
    if (dt == null) return '';
    final h = dt.hour.toString().padLeft(2, '0');
    final m = dt.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }
}
