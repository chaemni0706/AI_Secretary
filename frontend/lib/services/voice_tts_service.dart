import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';

import 'preference_store.dart';

/// TTS 재생 옵션.
///
/// flutter_tts 로 실제 제어 가능한 값은 [rate](속도)/[pitch](음높이)뿐이다.
/// [style]/[emotion] 은 현재 기기 TTS 엔진이 감정/말투 프로소디를 지원하지
/// 않으므로 재생에는 반영되지 않지만, 로그/향후 server_tts 확장을 위해 옵션에
/// 보존한다(값을 잃지 않는다).
class TtsOptions {
  /// 말하기 속도(flutter_tts 기준 0.0~1.0, 0.5 가 표준). null 이면 서비스 기본값.
  final double? rate;

  /// 음높이(1.0 이 표준).
  final double? pitch;

  /// 말투(assistant_tone). 재생 반영 X, 보존용.
  final String? style;

  /// 감정 힌트. 재생 반영 X, 보존용.
  final String? emotion;

  const TtsOptions({this.rate, this.pitch, this.style, this.emotion});

  /// 사용자 설정(PreferenceStore)에서 옵션을 만든다.
  ///
  /// 매핑(문서화된 한계): 기기 TTS 엔진은 말투/감정 프로소디를 지원하지 않으므로
  /// 말투는 "속도/음높이"의 미세 조정으로만 근사한다.
  ///  - tts_speed(slow/normal/fast) 가 1차 기준 속도(preferenceStore.ttsRate).
  ///  - response_length: short 는 조금 빠르게, detailed 는 조금 느리게.
  ///  - assistant_tone: concise 는 조금 빠르게, caring 은 조금 느리고 높게.
  factory TtsOptions.fromPreferences() {
    // 사용자가 고른 tts_speed 를 기준값으로 사용(없으면 0.5).
    double rate = preferenceStore.ttsRate;
    double pitch = 1.0;

    switch (preferenceStore.responseLength) {
      case 'short':
        rate += 0.05;
        break;
      case 'detailed':
      case 'long':
        rate -= 0.03;
        break;
    }
    switch (preferenceStore.assistantTone) {
      case 'concise':
      case 'professional':
        rate += 0.03;
        break;
      case 'caring':
        rate -= 0.03;
        pitch = 1.05;
        break;
      case 'formal':
      case 'polite':
        pitch = 0.98;
        break;
    }
    // 안전 범위로 클램프(너무 빠르거나 느려 알아듣기 힘든 것 방지).
    rate = rate.clamp(0.35, 0.65);

    return TtsOptions(
      rate: rate,
      pitch: pitch,
      style: preferenceStore.voiceStyle,
    );
  }
}

/// flutter_tts 를 감싸는 음성 출력 서비스(온디바이스 TTS).
///
/// 하루 브리핑 / 음성 챗봇 / 가짜 전화 알림 / 음성 일정 / 설정 미리듣기 화면이
/// 공용으로 사용한다. 모든 동작은 try-catch 로 보호되어 실패해도 앱이 죽지 않고,
/// 원인 분리를 위해 주요 지점마다 debugPrint 로그를 남긴다.
///
/// 공개 API(권장 이름): initialize() / speak(text, options) / stop() / dispose()
/// 기존 호출부 호환을 위해 init() 별칭을 유지한다.
class VoiceTtsService {
  final FlutterTts _flutterTts = FlutterTts();
  bool _initialized = false;

  /// 실제로 엔진에 적용된 언어. 한국어가 없으면 fallback 언어가 담긴다.
  String _selectedLanguage = 'ko-KR';

  /// 한국어 음성 데이터 사용 가능 여부(진단/안내용).
  bool _koreanAvailable = false;

  /// 마지막으로 적용된 속도/음높이(중복 setter 호출 최소화용).
  double _currentRate = 0.5;
  double _currentPitch = 1.0;

  /// 선택하려는 언어 우선순위. 앞에서부터 사용 가능한 첫 언어를 적용한다.
  static const List<String> _preferredLanguages = ['ko-KR', 'ko_KR', 'en-US'];

  String get selectedLanguage => _selectedLanguage;
  bool get koreanAvailable => _koreanAvailable;

  // --------------------------------------------------------------------- //
  // 초기화
  // --------------------------------------------------------------------- //

  /// 엔진 초기화(언어/속도/피치/볼륨 + 핸들러 등록). 최초 1회만 실제 초기화.
  Future<void> initialize() async {
    if (_initialized) return;

    try {
      debugPrint('TTS init started');

      await _selectLanguage();
      await _flutterTts.setSpeechRate(_currentRate);
      await _flutterTts.setPitch(_currentPitch);
      await _flutterTts.setVolume(1.0);

      // speak() 가 발화 완료까지 await 되도록 하여, 엔진이 발화를 조용히 드롭하거나
      // 바로 이어지는 호출에 잘리는 문제를 방지한다. (무음 원인 중 하나)
      await _flutterTts.awaitSpeakCompletion(true);

      // iOS: 무음 스위치 상태에서도 재생되도록 오디오 세션을 명시적으로 설정한다.
      if (!kIsWeb && Platform.isIOS) {
        await _flutterTts.setSharedInstance(true);
        await _flutterTts
            .setIosAudioCategory(IosTextToSpeechAudioCategory.playback, [
              IosTextToSpeechAudioCategoryOptions.allowBluetooth,
              IosTextToSpeechAudioCategoryOptions.allowBluetoothA2DP,
              IosTextToSpeechAudioCategoryOptions.mixWithOthers,
              IosTextToSpeechAudioCategoryOptions.defaultToSpeaker,
            ]);
      }

      _flutterTts.setStartHandler(() => debugPrint('TTS started'));
      _flutterTts.setCompletionHandler(() => debugPrint('TTS completed'));
      _flutterTts.setCancelHandler(() => debugPrint('TTS cancelled'));
      _flutterTts.setErrorHandler((message) {
        debugPrint('TTS error handler: $message');
      });

      await _logAvailableVoices();

      _initialized = true;
      debugPrint('TTS init completed');
    } catch (e) {
      debugPrint('TTS init error: $e');
    }
  }

  /// [initialize] 의 기존 이름 별칭(호환용).
  Future<void> init() => initialize();

  /// 우선순위(ko-KR → ko_KR → en-US)대로 사용 가능한 언어를 골라 적용한다.
  Future<void> _selectLanguage() async {
    try {
      final engine = await _flutterTts.getDefaultEngine;
      debugPrint('TTS engine selected: $engine');
    } catch (e) {
      debugPrint('TTS getDefaultEngine error: $e');
    }

    String? chosen;
    for (final lang in _preferredLanguages) {
      try {
        final available = await _flutterTts.isLanguageAvailable(lang);
        debugPrint('TTS isLanguageAvailable($lang) = $available');
        if (available == true) {
          chosen = lang;
          break;
        }
      } catch (e) {
        debugPrint('TTS isLanguageAvailable($lang) error: $e');
      }
    }

    _koreanAvailable = chosen == 'ko-KR' || chosen == 'ko_KR';
    _selectedLanguage = chosen ?? 'ko-KR';

    try {
      await _flutterTts.setLanguage(_selectedLanguage);
      debugPrint(
        'TTS language selected: $_selectedLanguage '
        '(korean available: $_koreanAvailable)',
      );
    } catch (e) {
      debugPrint('TTS setLanguage($_selectedLanguage) error: $e');
    }

    if (!_koreanAvailable) {
      debugPrint(
        'TTS WARNING: 한국어(ko-KR) 음성 데이터가 없습니다. '
        '기기 설정 > 언어 및 입력 > 텍스트 음성 변환(TTS)에서 '
        '한국어 음성 데이터를 설치하세요. 현재는 "$_selectedLanguage" 로 재생됩니다.',
      );
    }
  }

  Future<void> _logAvailableVoices() async {
    try {
      final voices = await _flutterTts.getVoices;
      debugPrint('TTS available voices: $voices');

      bool hasKo = false;
      if (voices is List) {
        for (final v in voices) {
          final s = v.toString().toLowerCase();
          if (s.contains('ko-kr') ||
              s.contains('ko_kr') ||
              s.contains('korea')) {
            hasKo = true;
            break;
          }
        }
      }
      debugPrint('TTS ko-KR voice available: $hasKo');

      final languages = await _flutterTts.getLanguages;
      debugPrint('TTS available languages: $languages');

      try {
        final engines = await _flutterTts.getEngines;
        debugPrint('TTS available engines: $engines');
      } catch (e) {
        debugPrint('TTS getEngines error: $e');
      }
    } catch (e) {
      debugPrint('TTS getVoices error: $e');
    }
  }

  // --------------------------------------------------------------------- //
  // 재생
  // --------------------------------------------------------------------- //

  /// 텍스트를 읽는다. 재생 전 기존 음성을 항상 정지해(두 번째 재생 겹침/무음 방지)
  /// 새 발화를 시작한다.
  ///
  /// [options] 가 없으면 사용자 설정(PreferenceStore)에서 속도/음높이를 유도한다.
  /// 텍스트가 비어 있으면 재생하지 않고 false 를 반환한다(안내는 호출부 책임).
  ///
  /// 반환값: 재생을 시작했으면 true, (빈 텍스트 등으로) 재생하지 않았으면 false.
  Future<bool> speak(String text, {TtsOptions? options}) async {
    final trimmed = text.trim();
    debugPrint('TTS speak called: "$trimmed"');

    // 빈 텍스트는 재생하지 않는다(무의미한 발화/무음 버튼 방지).
    if (trimmed.isEmpty) {
      debugPrint('TTS text is empty -> skip playback');
      return false;
    }

    try {
      if (!_initialized) {
        await initialize();
      }

      final opts = options ?? TtsOptions.fromPreferences();
      // style/emotion 은 엔진 미반영(로그만). 한계는 문서/주석에 명시.
      if (opts.style != null || opts.emotion != null) {
        debugPrint(
          'TTS style/emotion preserved (engine does NOT apply): '
          'style=${opts.style} emotion=${opts.emotion}',
        );
      }

      // 속도/음높이 반영(변경된 경우에만 setter 호출).
      final rate = opts.rate ?? _currentRate;
      final pitch = opts.pitch ?? _currentPitch;
      if (rate != _currentRate) {
        _currentRate = rate;
        await _flutterTts.setSpeechRate(rate);
      }
      if (pitch != _currentPitch) {
        _currentPitch = pitch;
        await _flutterTts.setPitch(pitch);
      }
      debugPrint('TTS lang=$_selectedLanguage rate=$rate pitch=$pitch');

      // 이전 발화 정지 후 새로 시작(겹침/두 번째 재생 실패 방지).
      await _flutterTts.stop();

      final dynamic result;
      if (!kIsWeb && Platform.isAndroid) {
        // Android: focus:true 로 오디오 포커스를 요청해 미디어 볼륨으로 재생.
        result = await _flutterTts.speak(trimmed, focus: true);
      } else {
        result = await _flutterTts.speak(trimmed);
      }
      debugPrint('TTS speak result: $result (result==1 이면 재생 시작)');
      return true;
    } catch (e) {
      debugPrint('TTS error: $e');
      return false;
    }
  }

  Future<void> stop() async {
    try {
      debugPrint('TTS stop called');
      await _flutterTts.stop();
    } catch (e) {
      debugPrint('TTS stop error: $e');
    }
  }

  Future<void> pause() async {
    try {
      debugPrint('TTS pause called');
      await _flutterTts.pause();
    } catch (e) {
      debugPrint('TTS pause error: $e');
    }
  }

  Future<void> setSpeechRate(double rate) async {
    try {
      _currentRate = rate;
      await _flutterTts.setSpeechRate(rate);
    } catch (e) {
      debugPrint('TTS setSpeechRate error: $e');
    }
  }

  Future<void> setPitch(double pitch) async {
    try {
      _currentPitch = pitch;
      await _flutterTts.setPitch(pitch);
    } catch (e) {
      debugPrint('TTS setPitch error: $e');
    }
  }

  Future<void> setVolume(double volume) async {
    try {
      await _flutterTts.setVolume(volume);
    } catch (e) {
      debugPrint('TTS setVolume error: $e');
    }
  }

  /// 리소스 정리(진행 중 발화 정지).
  void dispose() {
    stop();
  }
}
