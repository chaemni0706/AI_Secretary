import 'package:flutter/foundation.dart';
import 'user_preferences_api.dart';

/// 앱 전역에서 공유하는 AI 음성 스타일(말투/응답 길이/리마인드 강도) 캐시.
///
/// 설정 화면에서 저장하면 [updateLocal] 로 즉시 갱신되고, 채팅·음성 일정 등
/// 응답 생성 요청은 이 캐시 값을 함께 보낸다. 그래서 사용자가 말투를 바꾸면
/// 같은 입력이라도 백엔드가 그 말투로 tts_text 를 생성한다.
class PreferenceStore extends ChangeNotifier {
  PreferenceStore._();
  static final PreferenceStore instance = PreferenceStore._();

  String userId = 'local-user';
  String assistantTone = 'friendly';
  String responseLength = 'normal';
  String nudgeStrength = 'medium';

  bool _loaded = false;
  bool get isLoaded => _loaded;

  /// nudge_strength(low/medium/high) 를 백엔드 reminder_strength 별칭으로 그대로
  /// 전달한다. build_style_profile 이 두 표기를 모두 해석한다.
  String get reminderStrength => nudgeStrength;

  /// 앱 시작 시 1회 로드. 실패해도 기본값으로 조용히 동작한다.
  Future<void> ensureLoaded() async {
    if (_loaded) return;
    await refresh();
  }

  Future<void> refresh() async {
    try {
      final data = await UserPreferencesApi.fetch(userId: userId);
      final prefs = Map<String, dynamic>.from(data['preferences'] as Map);
      assistantTone = (prefs['assistant_tone'] as String?) ?? assistantTone;
      responseLength = (prefs['response_length'] as String?) ?? responseLength;
      nudgeStrength = (prefs['nudge_strength'] as String?) ?? nudgeStrength;
      _loaded = true;
      debugPrint('[STYLE] PreferenceStore loaded: '
          'tone=$assistantTone length=$responseLength nudge=$nudgeStrength');
      notifyListeners();
    } catch (e) {
      debugPrint('[STYLE] PreferenceStore load failed (using defaults): $e');
    }
  }

  /// 설정 화면 저장 직후 호출 — 서버 재조회 없이 즉시 반영.
  void updateLocal({String? assistantTone, String? responseLength, String? nudgeStrength}) {
    if (assistantTone != null) this.assistantTone = assistantTone;
    if (responseLength != null) this.responseLength = responseLength;
    if (nudgeStrength != null) this.nudgeStrength = nudgeStrength;
    _loaded = true;
    debugPrint('[STYLE] PreferenceStore updated: '
        'tone=${this.assistantTone} length=${this.responseLength} nudge=${this.nudgeStrength}');
    notifyListeners();
  }
}

/// 짧은 접근용 전역 인스턴스.
final preferenceStore = PreferenceStore.instance;
