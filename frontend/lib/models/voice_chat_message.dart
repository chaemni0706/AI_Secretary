import '../services/voice_router_api.dart';

/// 음성 라우터 화면(voice_chat_screen)에서 사용하는 채팅 메시지 모델.
///
/// AI 메시지는 `POST /api/v1/voice/route` 의 결과([VoiceRouteResult])를 그대로
/// 들고 있어서, 화면이 intent 별로 카드를 다르게 그릴 수 있다.

enum ChatRole { user, assistant }

/// 채팅 말풍선 1개를 나타낸다.
class VoiceChatMessage {
  final ChatRole role;
  final String text;

  /// AI 메시지에 한해 라우팅 결과 전체를 담는다(사용자 메시지는 null).
  final VoiceRouteResult? route;

  const VoiceChatMessage({required this.role, required this.text, this.route});

  bool get isUser => role == ChatRole.user;
}

/// `/api/v1/emotion/analyze` 의 data 구조.
/// (온디바이스 감정 fallback 서비스들이 사용. voice_chat_screen 은 서버 라우터를
///  쓰지만, emotion_api / LocalEmotionClassifier 등은 이 구조를 그대로 사용한다.)
class EmotionAnalysis {
  final Emotion emotion;
  final Burden burden;
  final EmpathyStrategy empathyStrategy;
  final String coachingReply;
  final List<ScheduleSuggestion> scheduleSuggestions;
  final String ttsText;
  final String safetyNote;

  /// 분석 출처: "server"(기본) 또는 "on_device_rule"(온디바이스 분류기 fallback).
  final String source;

  const EmotionAnalysis({
    required this.emotion,
    required this.burden,
    required this.empathyStrategy,
    required this.coachingReply,
    required this.scheduleSuggestions,
    required this.ttsText,
    required this.safetyNote,
    this.source = 'server',
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
      source: (json['source'] ?? 'server').toString(),
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
