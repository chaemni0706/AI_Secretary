import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';

/// flutter_tts 를 감싸는 음성 출력 서비스.
///
/// 하루 브리핑 / 음성 챗봇 / 가짜 전화 알림 화면이 공용으로 사용한다.
/// 모든 동작은 try-catch 로 보호되어 실패해도 앱이 크래시되지 않으며,
/// 원인 분리를 위해 주요 지점마다 debugPrint 로그를 남긴다.
class VoiceTtsService {
  final FlutterTts _flutterTts = FlutterTts();
  bool _initialized = false;

  /// 실제로 엔진에 적용된 언어. 한국어가 없으면 fallback 언어가 담긴다.
  String _selectedLanguage = 'ko-KR';

  /// 한국어 음성 데이터 사용 가능 여부(진단/안내용).
  bool _koreanAvailable = false;

  /// 선택하려는 언어 우선순위. 앞에서부터 사용 가능한 첫 언어를 적용한다.
  static const List<String> _preferredLanguages = ['ko-KR', 'ko_KR', 'en-US'];

  /// 현재 적용된 언어(외부 확인용).
  String get selectedLanguage => _selectedLanguage;

  /// 한국어 TTS 사용 가능 여부(외부 확인용).
  bool get koreanAvailable => _koreanAvailable;

  /// 엔진 초기화(언어/속도/피치/볼륨 + 핸들러 등록).
  Future<void> init() async {
    if (_initialized) return;

    try {
      debugPrint('TTS init started');

      // 사용 가능한 언어를 확인하고, 한국어가 없으면 안전하게 fallback 한다.
      await _selectLanguage();
      await _flutterTts.setSpeechRate(0.5);
      await _flutterTts.setPitch(1.0);
      await _flutterTts.setVolume(1.0);

      // speak() 가 발화 완료까지 await 되도록 하여, 엔진이 발화를 조용히 드롭하거나
      // 바로 이어지는 호출에 잘리는 문제를 방지한다. (무음 원인 중 하나)
      await _flutterTts.awaitSpeakCompletion(true);

      // iOS: 무음(무음 스위치) 상태에서도 재생되도록 오디오 세션을 명시적으로 설정한다.
      // 이 설정이 없으면 아이폰에서 소리가 전혀 안 나는 경우가 많다. (web 은 제외)
      if (!kIsWeb && Platform.isIOS) {
        await _flutterTts.setSharedInstance(true);
        await _flutterTts.setIosAudioCategory(
          IosTextToSpeechAudioCategory.playback,
          [
            IosTextToSpeechAudioCategoryOptions.allowBluetooth,
            IosTextToSpeechAudioCategoryOptions.allowBluetoothA2DP,
            IosTextToSpeechAudioCategoryOptions.mixWithOthers,
            IosTextToSpeechAudioCategoryOptions.defaultToSpeaker,
          ],
        );
      }

      _flutterTts.setStartHandler(() {
        debugPrint('TTS started');
      });
      _flutterTts.setCompletionHandler(() {
        debugPrint('TTS completed');
      });
      _flutterTts.setCancelHandler(() {
        debugPrint('TTS cancelled');
      });
      _flutterTts.setErrorHandler((message) {
        debugPrint('TTS error handler: $message');
      });

      // ko-KR 음성 데이터가 있는지 점검(플랫폼별 반환 형태가 달라 방어적으로 처리).
      await _logAvailableVoices();

      _initialized = true;
      debugPrint('TTS init completed');
    } catch (e) {
      debugPrint('TTS init error: $e');
    }
  }

  /// 우선순위(ko-KR → ko_KR → en-US)대로 사용 가능한 언어를 골라 적용한다.
  ///
  /// 한국어가 없으면 조용히 실패하지 않도록 en-US 로 fallback 하고,
  /// 한국어 TTS 데이터 설치가 필요하다는 안내 로그를 남긴다.
  Future<void> _selectLanguage() async {
    // 선택된 엔진을 함께 로그로 남겨 진단을 돕는다.
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

    // 아무 것도 확인되지 않으면(일부 기기/엔진은 isLanguageAvailable 미지원)
    // 최소한 ko-KR 을 시도한다.
    _selectedLanguage = chosen ?? 'ko-KR';

    try {
      await _flutterTts.setLanguage(_selectedLanguage);
      debugPrint('TTS language selected: $_selectedLanguage '
          '(korean available: $_koreanAvailable)');
    } catch (e) {
      debugPrint('TTS setLanguage($_selectedLanguage) error: $e');
    }

    if (!_koreanAvailable) {
      debugPrint('TTS WARNING: 한국어(ko-KR) 음성 데이터가 없습니다. '
          '기기 설정 > 언어 및 입력 > 텍스트 음성 변환(TTS)에서 '
          '한국어 음성 데이터를 설치하세요. 현재는 "$_selectedLanguage" 로 재생됩니다.');
    }
  }

  /// 사용 가능한 음성 목록과 ko-KR 존재 여부를 로그로 남긴다.
  Future<void> _logAvailableVoices() async {
    try {
      final voices = await _flutterTts.getVoices;
      debugPrint('TTS available voices: $voices');

      bool hasKo = false;
      if (voices is List) {
        for (final v in voices) {
          final s = v.toString().toLowerCase();
          if (s.contains('ko-kr') || s.contains('ko_kr') || s.contains('korea')) {
            hasKo = true;
            break;
          }
        }
      }
      debugPrint('TTS ko-KR voice available: $hasKo');

      final languages = await _flutterTts.getLanguages;
      debugPrint('TTS available languages: $languages');

      // 사용 가능한 TTS 엔진 목록 (Android). 한국어 엔진 미설치 진단용.
      try {
        final engines = await _flutterTts.getEngines;
        debugPrint('TTS available engines: $engines');
      } catch (e) {
        debugPrint('TTS getEngines error: $e');
      }
    } catch (e) {
      // getVoices/getLanguages 는 일부 기기/엔진에서 미지원일 수 있다.
      debugPrint('TTS getVoices error: $e');
    }
  }

  /// 텍스트를 읽는다. 재생 전 기존 음성을 정지한다.
  ///
  /// 텍스트가 비어 있으면 조용히 종료하지 않고 안내 문구를 읽어
  /// "버튼을 눌렀는데 아무 반응이 없다"는 상황을 방지한다.
  Future<void> speak(String text) async {
    var trimmed = text.trim();
    debugPrint('TTS speak called: "$trimmed"');

    if (trimmed.isEmpty) {
      debugPrint('TTS text is empty -> 안내 문구로 대체');
      trimmed = '읽어드릴 내용이 없습니다.';
    }

    try {
      if (!_initialized) {
        await init();
      }
      debugPrint('TTS language selected: $_selectedLanguage');
      await _flutterTts.stop();

      // Android: focus:true 로 오디오 포커스를 요청해 미디어 볼륨으로 재생되도록 한다.
      // (다른 앱의 소리를 잠시 낮추고 TTS 를 미디어 스트림으로 내보낸다.)
      final dynamic result;
      if (!kIsWeb && Platform.isAndroid) {
        result = await _flutterTts.speak(trimmed, focus: true);
      } else {
        result = await _flutterTts.speak(trimmed);
      }
      debugPrint('TTS speak result: $result (result==1 이면 재생 시작)');
    } catch (e) {
      debugPrint('TTS error: $e');
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
      await _flutterTts.setSpeechRate(rate);
    } catch (e) {
      debugPrint('TTS setSpeechRate error: $e');
    }
  }

  Future<void> setPitch(double pitch) async {
    try {
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

  void dispose() {
    stop();
  }
}
