import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'user_preferences_api.dart';

/// 앱 전역에서 공유하는 AI 개인화 설정 캐시.
///
/// 저장 대상(설정값 이름은 고정):
///  - 서버 연동(3종, /user/preferences 로 저장/조회):
///     assistant_tone(preferred_tone), response_length, nudge_strength(reminder_strength)
///  - 클라이언트 로컬 전용(2종, 백엔드 미저장 → shared_preferences 캐시):
///     tts_speed(slow|normal|fast), voice_style(friendly|calm|clear|energetic)
///
/// 영속성:
///  - 모든 값은 [SharedPreferences] 에 캐시된다. 앱 재실행/오프라인에서도
///    마지막 설정을 즉시 복원하고, 이후 서버 값으로 best-effort 동기화한다.
///
/// 즉시 반영:
///  - 설정 화면 저장 시 [updateLocal] → notifyListeners → 열려 있는 화면 갱신.
///  - 요청 생성부는 [userContext]/[voice] 빌더로 동일한 필드를 첨부한다.
class PreferenceStore extends ChangeNotifier {
  PreferenceStore._();
  static final PreferenceStore instance = PreferenceStore._();

  // ------ shared_preferences 키(고정) ------
  static const _kTone = 'pref_assistant_tone';
  static const _kLength = 'pref_response_length';
  static const _kNudge = 'pref_nudge_strength';
  static const _kTtsSpeed = 'pref_tts_speed';
  static const _kVoiceStyle = 'pref_voice_style';

  String userId = 'local-user';

  // 서버 연동 설정.
  String assistantTone = 'friendly'; // preferred_tone
  String responseLength = 'normal'; // short | normal | detailed
  String nudgeStrength = 'medium'; // low | medium | high

  // 클라이언트 로컬 전용 설정.
  String ttsSpeed = 'normal'; // slow | normal | fast
  String voiceStyle = 'friendly'; // friendly | calm | clear | energetic

  bool _loaded = false;
  bool get isLoaded => _loaded;

  /// nudge_strength(low/medium/high) 를 백엔드 reminder_strength 별칭으로 전달한다.
  String get reminderStrength => nudgeStrength;

  /// tts_speed(slow/normal/fast) → flutter_tts speech rate(0.0~1.0).
  /// TTS 재생 속도의 1차 기준값(말투에 따른 미세 조정은 TtsOptions 에서).
  double get ttsRate {
    switch (ttsSpeed) {
      case 'slow':
        return 0.4;
      case 'fast':
        return 0.62;
      case 'normal':
      default:
        return 0.5;
    }
  }

  /// 서버/로컬 요청에 첨부할 사용자 컨텍스트(설정값 이름 고정).
  /// 백엔드가 아직 소비하지 않아도 무해하며(미지의 필드 무시), 향후 계약 필드.
  Map<String, dynamic> get userContext => {
        'preferred_tone': assistantTone,
        'response_length': responseLength,
        'reminder_strength': reminderStrength,
      };

  /// TTS/음성 관련 옵션(voice / voice_options 공용).
  Map<String, dynamic> get voice => {
        'style': voiceStyle,
        'speed': ttsSpeed,
        'tone': assistantTone,
      };

  // --------------------------------------------------------------------- //
  // 로드 / 동기화
  // --------------------------------------------------------------------- //

  /// 앱 시작 시 1회 호출. 캐시를 먼저 복원(즉시/오프라인 대응)한 뒤,
  /// 서버 값으로 best-effort 동기화한다. 실패해도 조용히 캐시/기본값 사용.
  Future<void> ensureLoaded() async {
    if (_loaded) return;
    await _loadCache();
    _loaded = true;
    notifyListeners();
    await refresh();
  }

  /// 서버에서 3종 설정을 가져와 갱신하고 캐시에 반영한다.
  Future<void> refresh() async {
    try {
      final data = await UserPreferencesApi.fetch(userId: userId);
      final prefs = Map<String, dynamic>.from(data['preferences'] as Map);
      assistantTone = (prefs['assistant_tone'] as String?) ?? assistantTone;
      responseLength = (prefs['response_length'] as String?) ?? responseLength;
      nudgeStrength = (prefs['nudge_strength'] as String?) ?? nudgeStrength;
      _loaded = true;
      await _saveCache();
      debugPrint('[STYLE] PreferenceStore synced: '
          'tone=$assistantTone length=$responseLength nudge=$nudgeStrength '
          'ttsSpeed=$ttsSpeed voiceStyle=$voiceStyle');
      notifyListeners();
    } catch (e) {
      debugPrint('[STYLE] PreferenceStore server sync failed (using cache/defaults): $e');
    }
  }

  /// 설정 화면 저장 직후 호출 — 서버 재조회 없이 즉시 반영 + 캐시 저장.
  void updateLocal({
    String? assistantTone,
    String? responseLength,
    String? nudgeStrength,
    String? ttsSpeed,
    String? voiceStyle,
  }) {
    if (assistantTone != null) this.assistantTone = assistantTone;
    if (responseLength != null) this.responseLength = responseLength;
    if (nudgeStrength != null) this.nudgeStrength = nudgeStrength;
    if (ttsSpeed != null) this.ttsSpeed = ttsSpeed;
    if (voiceStyle != null) this.voiceStyle = voiceStyle;
    _loaded = true;
    debugPrint('[STYLE] PreferenceStore updated: '
        'tone=${this.assistantTone} length=${this.responseLength} '
        'nudge=${this.nudgeStrength} ttsSpeed=${this.ttsSpeed} '
        'voiceStyle=${this.voiceStyle}');
    // 캐시는 비동기로 저장(실패해도 앱 흐름 방해 없음).
    _saveCache();
    notifyListeners();
  }

  // --------------------------------------------------------------------- //
  // 로컬 fallback 문구 스타일링(서버/LLM 없이 template 수준)
  // --------------------------------------------------------------------- //

  /// reminder_strength 에 따라 알림/안내 문구 강도를 조절한다.
  /// gentle/low → 부드럽게, strong/high → 강하게. 그 외는 원문 유지.
  String applyReminderStrength(String text) {
    final t = text.trim();
    if (t.isEmpty) return t;
    switch (nudgeStrength) {
      case 'high':
      case 'strong':
        return '$t 꼭 잊지 마세요!';
      case 'low':
      case 'gentle':
        return '$t 여유 될 때 확인해 주세요.';
      default:
        return t;
    }
  }

  /// response_length 가 short 면 첫 문장만 남겨 간결화한다(로컬 fallback용).
  String applyLength(String text) {
    if (responseLength != 'short') return text;
    final idx = text.indexOf(RegExp(r'[.!?。]'));
    if (idx > 0 && idx + 1 < text.length) {
      return text.substring(0, idx + 1).trim();
    }
    return text;
  }

  // --------------------------------------------------------------------- //
  // shared_preferences 캐시
  // --------------------------------------------------------------------- //

  Future<void> _loadCache() async {
    try {
      final sp = await SharedPreferences.getInstance();
      assistantTone = sp.getString(_kTone) ?? assistantTone;
      responseLength = sp.getString(_kLength) ?? responseLength;
      nudgeStrength = sp.getString(_kNudge) ?? nudgeStrength;
      ttsSpeed = sp.getString(_kTtsSpeed) ?? ttsSpeed;
      voiceStyle = sp.getString(_kVoiceStyle) ?? voiceStyle;
      debugPrint('[STYLE] PreferenceStore cache restored: '
          'tone=$assistantTone length=$responseLength nudge=$nudgeStrength '
          'ttsSpeed=$ttsSpeed voiceStyle=$voiceStyle');
    } catch (e) {
      debugPrint('[STYLE] PreferenceStore cache load failed: $e');
    }
  }

  Future<void> _saveCache() async {
    try {
      final sp = await SharedPreferences.getInstance();
      await sp.setString(_kTone, assistantTone);
      await sp.setString(_kLength, responseLength);
      await sp.setString(_kNudge, nudgeStrength);
      await sp.setString(_kTtsSpeed, ttsSpeed);
      await sp.setString(_kVoiceStyle, voiceStyle);
    } catch (e) {
      debugPrint('[STYLE] PreferenceStore cache save failed: $e');
    }
  }
}

/// 짧은 접근용 전역 인스턴스.
final preferenceStore = PreferenceStore.instance;
