import 'package:flutter/material.dart';

import '../models/schedule_model.dart';
import '../services/api_client.dart';
import '../services/assistant_text_sanitizer.dart';
import '../services/dashboard_api.dart';
import '../services/schedule_api.dart';
import '../services/preference_store.dart';
import '../services/voice_api.dart';
import '../services/voice_stt_service.dart';
import '../services/voice_tts_service.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';

/// 음성 기반 AI 일정 생성 화면.
///
/// 흐름: 마이크 → speech_to_text 인식 → 인식 문장 표시
///      → POST /ai/schedule/parse (input_type=voice) → 일정 초안 카드
///      → 등록 → POST /local/schedules/from-draft → TTS "일정이 등록됐어요".
class VoiceScheduleScreen extends StatefulWidget {
  const VoiceScheduleScreen({super.key});

  @override
  State<VoiceScheduleScreen> createState() => _VoiceScheduleScreenState();
}

class _VoiceScheduleScreenState extends State<VoiceScheduleScreen> {
  final VoiceSttService _stt = VoiceSttService();
  final VoiceTtsService _tts = VoiceTtsService();

  bool _isListening = false;
  bool _isParsing = false;
  bool _isSaving = false;
  bool _saved = false;

  String _recognizedText = '';
  ParseResult? _parseResult;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _tts.init();
  }

  @override
  void dispose() {
    _stt.cancel();
    _tts.dispose();
    super.dispose();
  }

  // --------------------------------------------------------------------- //
  // 상태 헬퍼
  // --------------------------------------------------------------------- //
  String get _statusText {
    if (_isSaving) return '일정을 등록 중이에요...';
    if (_isParsing) return '일정 정보를 분석 중...';
    if (_isListening) return '듣는 중...';
    if (_saved) return '일정이 등록됐어요';
    if (_parseResult != null) return '인식 완료';
    return '마이크를 누르고 말씀해주세요';
  }

  String _nowIso() {
    final now = DateTime.now();
    final o = now.timeZoneOffset;
    final sign = o.isNegative ? '-' : '+';
    final hh = o.inHours.abs().toString().padLeft(2, '0');
    final mm = (o.inMinutes.abs() % 60).toString().padLeft(2, '0');
    final base = now.toIso8601String().split('.').first; // 밀리초 제거
    return '$base$sign$hh:$mm';
  }

  // --------------------------------------------------------------------- //
  // 1) 음성 인식
  // --------------------------------------------------------------------- //
  Future<void> _startListening() async {
    // 다시 말하기 겸용: 기존 상태 초기화
    setState(() {
      _errorMessage = null;
      _parseResult = null;
      _recognizedText = '';
      _saved = false;
    });

    final granted = await _stt.ensureMicPermission();
    if (!granted) {
      setState(() => _errorMessage = '마이크 권한이 필요해요.');
      return;
    }

    final ready = await _stt.init(
      onStatus: (s) {
        // 인식이 끝나면(status: done/notListening) 자동으로 파싱 트리거
        if ((s == 'done' || s == 'notListening') && _isListening) {
          _onListeningFinished();
        }
      },
      onError: (_) {
        if (mounted && _isListening) {
          setState(() => _isListening = false);
        }
      },
    );
    if (!ready) {
      setState(() => _errorMessage = '음성 인식을 사용할 수 없어요. 기기 설정을 확인해주세요.');
      return;
    }

    setState(() => _isListening = true);
    await _stt.listen(
      onResult: (r) {
        setState(() => _recognizedText = r.text);
      },
      localeId: 'ko_KR',
    );
  }

  Future<void> _onListeningFinished() async {
    if (!_isListening) return;
    setState(() => _isListening = false);

    final text = _recognizedText.trim();
    if (text.isEmpty) {
      setState(() => _errorMessage = '음성을 인식하지 못했어요. 다시 말해주세요.');
      return;
    }
    await _parse(text);
  }

  Future<void> _stopListening() async {
    await _stt.stop();
    await _onListeningFinished();
  }

  // --------------------------------------------------------------------- //
  // 2) 일정 파싱
  // --------------------------------------------------------------------- //
  Future<void> _parse(String text) async {
    setState(() {
      _isParsing = true;
      _errorMessage = null;
    });
    try {
      await preferenceStore.ensureLoaded();
      final result = await scheduleApi.parse(
        text,
        inputType: 'voice',
        currentDatetime: _nowIso(),
        assistantTone: preferenceStore.assistantTone,
        responseLength: preferenceStore.responseLength,
        reminderStrength: preferenceStore.reminderStrength,
      );
      setState(() {
        _parseResult = result;
        _isParsing = false;
      });
      final phrase = sanitizeAssistantText(
        result.ttsText,
        fallback: '일정 정보를 정리했어요. 등록할까요?',
      );
      await _speak(phrase);
    } on ApiException catch (e) {
      setState(() {
        _isParsing = false;
        _errorMessage = (e.statusCode == null)
            ? '서버에 연결할 수 없어요. 백엔드가 실행 중인지 확인해주세요.'
            : '일정 정보를 정확히 이해하지 못했어요. 날짜와 시간을 포함해서 다시 말해주세요.';
      });
    } catch (_) {
      setState(() {
        _isParsing = false;
        _errorMessage = '일정 정보를 정확히 이해하지 못했어요. 날짜와 시간을 포함해서 다시 말해주세요.';
      });
    }
  }

  // --------------------------------------------------------------------- //
  // 3) 일정 저장
  // --------------------------------------------------------------------- //
  Future<void> _register() async {
    final result = _parseResult;
    if (result == null) return;

    setState(() {
      _isSaving = true;
      _errorMessage = null;
    });
    try {
      await scheduleApi.createFromDraft(
        result.scheduleDraft,
        intent: result.intent,
        inputType: 'voice',
      );
      // 홈/캘린더 대시보드 새로고침 트리거(다른 저장 경로와 동일하게).
      triggerDashboardRefresh();
      setState(() {
        _isSaving = false;
        _saved = true;
      });
      await _speak('일정이 등록됐어요.');
    } on ApiException catch (e) {
      setState(() {
        _isSaving = false;
        _errorMessage = (e.statusCode == null)
            ? '서버에 연결할 수 없어요. 백엔드가 실행 중인지 확인해주세요.'
            : '일정을 저장하지 못했어요. 다시 시도해주세요.';
      });
    } catch (_) {
      setState(() {
        _isSaving = false;
        _errorMessage = '일정을 저장하지 못했어요. 다시 시도해주세요.';
      });
    }
  }

  /// /voice/tts 응답 규칙(server_tts/flutter_tts/오류 fallback)에 따라 재생.
  /// 재생 엔진은 온디바이스 flutter_tts([_tts])를 재사용한다.
  Future<void> _speak(String text) async {
    await voiceApi.speak(_tts, text, source: 'voice_schedule');
  }

  // --------------------------------------------------------------------- //
  // UI
  // --------------------------------------------------------------------- //
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('음성으로 일정 만들기'),
        backgroundColor: Colors.transparent,
        foregroundColor: AppTheme.textPrimary,
        elevation: 0,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 12),
              _buildMicButton(),
              const SizedBox(height: 12),
              Text(
                _statusText,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 20),
              if (_recognizedText.isNotEmpty) _buildRecognizedCard(),
              if (_parseResult != null) ...[
                const SizedBox(height: 12),
                _buildDraftCard(_parseResult!),
              ],
              if (_errorMessage != null) ...[
                const SizedBox(height: 12),
                _buildErrorCard(_errorMessage!),
              ],
              if (_saved) ...[
                const SizedBox(height: 12),
                _buildSavedCard(),
              ],
              const SizedBox(height: 20),
              _buildActions(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMicButton() {
    final active = _isListening;
    final busy = _isParsing || _isSaving;
    return Center(
      child: GestureDetector(
        onTap: busy
            ? null
            : (active ? _stopListening : _startListening),
        child: Container(
          width: 108,
          height: 108,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: active
                ? AppTheme.red.withOpacity(0.12)
                : AppTheme.blue.withOpacity(0.12),
            border: Border.all(
              color: active ? AppTheme.red : AppTheme.blue,
              width: 2,
            ),
          ),
          child: busy
              ? const Padding(
                  padding: EdgeInsets.all(34),
                  child: CircularProgressIndicator(strokeWidth: 3),
                )
              : Icon(
                  active ? Icons.stop_rounded : Icons.mic_rounded,
                  size: 48,
                  color: active ? AppTheme.red : AppTheme.blue,
                ),
        ),
      ),
    );
  }

  Widget _buildRecognizedCard() {
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('인식된 문장',
              style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textSecondary)),
          const SizedBox(height: 6),
          Text(_recognizedText,
              style: const TextStyle(
                  fontSize: 16, color: AppTheme.textPrimary, height: 1.4)),
        ],
      ),
    );
  }

  Widget _buildDraftCard(ParseResult r) {
    final d = r.scheduleDraft;
    final registerable = r.isRegisterable;
    String v(dynamic x) => (x == null || '$x'.isEmpty) ? '-' : '$x';
    final timeText = (d['start_time'] == null)
        ? '-'
        : '${d['start_time']}${d['end_time'] != null ? ' ~ ${d['end_time']}' : ''}';

    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.auto_awesome, size: 18, color: AppTheme.purple),
              const SizedBox(width: 6),
              const Text('AI가 정리한 일정',
                  style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary)),
              const Spacer(),
              if (r.isTodo) const PillBadge(label: '할 일', color: AppTheme.teal),
            ],
          ),
          const SizedBox(height: 12),
          _row('제목', v(d['title'])),
          _row('날짜', _dateRangeText(d)),
          _row('시간', timeText),
          _row('카테고리', _categoryLabel(d['category'])),
          _row('장소', v(d['location'])),
          if (!registerable) ...[
            const SizedBox(height: 10),
            Text(
              _missingHint(r.missingFields),
              style: const TextStyle(fontSize: 12, color: AppTheme.orange),
            ),
          ],
        ],
      ),
    );
  }

  /// 초안의 날짜 표시. 기간 일정이면 "시작 ~ 종료". 종료일은 end_date 키
  /// 또는 memo 의 `end_date:` 토큰(서버 파싱 결과)에서 읽는다.
  String _dateRangeText(Map<String, dynamic> d) {
    final date = d['date'];
    if (date == null || '$date'.isEmpty) return '-';
    final endRaw = (d['end_date'] != null && '${d['end_date']}'.isNotEmpty)
        ? '${d['end_date']}'
        : ScheduleModel.endDateFromMemo(d['memo']?.toString());
    if (endRaw != null && endRaw.isNotEmpty && endRaw.compareTo('$date') > 0) {
      return '$date ~ $endRaw';
    }
    return '$date';
  }

  Widget _row(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 64,
            child: Text(label,
                style: const TextStyle(
                    fontSize: 13, color: AppTheme.textSecondary)),
          ),
          Expanded(
            child: Text(value,
                style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary)),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorCard(String message) {
    return GlassCard(
      color: AppTheme.red.withOpacity(0.08),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: AppTheme.red, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(message,
                style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary)),
          ),
        ],
      ),
    );
  }

  Widget _buildSavedCard() {
    return GlassCard(
      color: AppTheme.green.withOpacity(0.10),
      child: Row(
        children: const [
          Icon(Icons.check_circle, color: AppTheme.green, size: 20),
          SizedBox(width: 10),
          Text('일정이 등록됐어요.',
              style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary)),
        ],
      ),
    );
  }

  Widget _buildActions() {
    final canRegister =
        _parseResult != null && _parseResult!.isRegisterable && !_saved;
    final busy = _isListening || _isParsing || _isSaving;

    return Row(
      children: [
        Expanded(
          child: ElevatedButton.icon(
            onPressed: (canRegister && !busy) ? _register : null,
            icon: const Icon(Icons.check),
            label: const Text('등록하기'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.blue,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14)),
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: OutlinedButton.icon(
            onPressed: busy ? null : _startListening,
            icon: const Icon(Icons.refresh),
            label: const Text('다시 말하기'),
            style: OutlinedButton.styleFrom(
              foregroundColor: AppTheme.blue,
              side: const BorderSide(color: AppTheme.blue),
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14)),
            ),
          ),
        ),
      ],
    );
  }

  String _missingHint(List<String> missing) {
    if (missing.contains('date') && missing.contains('time')) {
      return '날짜와 시간을 알려주세요. 예: "내일 오후 2시에 병원 예약"';
    }
    if (missing.contains('date')) return '날짜를 알려주세요.';
    if (missing.contains('time')) return '시간을 알려주세요.';
    return '조금 더 자세히 말씀해주세요.';
  }

  String _categoryLabel(dynamic category) {
    const map = {
      'hospital': '병원',
      'meeting': '회의',
      'beauty': '미용',
      'restaurant': '식당',
      'school': '학교/수업',
      'exercise': '운동',
      'shopping': '장보기',
      'study': '학습',
      'personal': '개인',
      'meal': '식사',
      'work': '업무',
      'health': '건강',
    };
    if (category == null || '$category'.isEmpty) return '-';
    return map[category] ?? '$category';
  }
}
