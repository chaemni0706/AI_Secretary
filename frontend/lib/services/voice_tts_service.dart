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

  /// 엔진 초기화(언어/속도/피치/볼륨 + 핸들러 등록).
  Future<void> init() async {
    if (_initialized) return;

    try {
      debugPrint('TTS init started');

      await _flutterTts.setLanguage('ko-KR');
      debugPrint('TTS language set: ko-KR');
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
  Future<void> speak(String text) async {
    final trimmed = text.trim();
    debugPrint('TTS speak called: $trimmed');

    if (trimmed.isEmpty) {
      debugPrint('TTS text is empty');
      return;
    }

    try {
      if (!_initialized) {
        await init();
      }
      await _flutterTts.stop();
      final result = await _flutterTts.speak(trimmed);
      debugPrint('TTS speak result: $result');
    } catch (e) {
      debugPrint('TTS speak error: $e');
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
