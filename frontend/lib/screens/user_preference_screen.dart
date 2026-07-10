import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../services/api_client.dart';
import '../services/briefing_scheduler_service.dart';
import '../services/schedule_api.dart';
import '../services/user_preferences_api.dart';
import '../services/preference_store.dart';
import '../services/voice_tts_service.dart';

/// statusCode/요청 URI/응답 body 까지 포함한 상세 오류 문자열.
/// debugPrint 로그와 화면 표시(에러 카드/SnackBar)에 그대로 재사용한다.
String _describeApiError(ApiException e) {
  return '${e.message} (status=${e.statusCode}, uri=${e.requestUri}, '
      'body=${e.responseBody})';
}

/// AI 음성 응답 스타일 설정 화면.
///
/// 사용자가 여기서 직접 옵션을 선택하면(assistant_tone/response_length/
/// nudge_strength) 백엔드가 이후 tts_text 생성 시 반영한다. 음성 명령으로
/// 설정을 바꾸는 기능이 아니라, 순수 설정 화면(GET/PUT)이다.
class UserPreferenceScreen extends StatefulWidget {
  const UserPreferenceScreen({super.key});

  @override
  State<UserPreferenceScreen> createState() => _UserPreferenceScreenState();
}

class _UserPreferenceScreenState extends State<UserPreferenceScreen> {
  bool _loading = true;
  bool _saving = false;
  String? _error;

  final VoiceTtsService _tts = VoiceTtsService();

  @override
  void dispose() {
    _tts.dispose();
    super.dispose();
  }

  Map<String, List<Map<String, String>>> _options = {};
  final Map<String, String> _selected = {
    'assistant_tone': 'friendly',
    'response_length': 'normal',
    'nudge_strength': 'medium',
  };

  /// 'HH:mm' 자동 브리핑 시각. 빈 문자열이면 비활성화(additive).
  String _briefingTime = '';

  /// 일정 사전 알림 리드타임(분). 0이면 끔. 클라이언트 로컬 설정.
  int _leadMinutes = 30;

  /// 선택 가능한 리드타임 옵션(분 → 표시 라벨).
  static const List<(int, String)> _leadOptions = [
    (0, '끔'),
    (5, '5분 전'),
    (10, '10분 전'),
    (30, '30분 전'),
    (60, '1시간 전'),
    (120, '2시간 전'),
  ];

  static const _sectionTitles = {
    'assistant_tone': 'AI 비서 말투',
    'response_length': '응답 길이',
    'nudge_strength': '리마인드 강도',
  };

  @override
  void initState() {
    super.initState();
    _leadMinutes = preferenceStore.alertLeadMinutes;
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await UserPreferencesApi.fetch();
      final prefs = Map<String, dynamic>.from(data['preferences'] as Map);
      final options = Map<String, dynamic>.from(data['options'] as Map);
      if (!mounted) return;
      setState(() {
        for (final key in _selected.keys) {
          if (prefs[key] is String) _selected[key] = prefs[key] as String;
        }
        _briefingTime = (prefs['briefing_time'] as String?) ?? '';
        _options = options.map(
          (key, value) => MapEntry(
            key,
            (value as List)
                .map((e) => Map<String, String>.from(e as Map))
                .toList(),
          ),
        );
        _loading = false;
      });
      preferenceStore.updateLocal(
        assistantTone: _selected['assistant_tone'],
        responseLength: _selected['response_length'],
        nudgeStrength: _selected['nudge_strength'],
        briefingTime: _briefingTime,
      );
    } on ApiException catch (e) {
      debugPrint('[UserPreferenceScreen] load failed: ${_describeApiError(e)}');
      if (!mounted) return;
      setState(() {
        _error = _describeApiError(e);
        _loading = false;
      });
    } catch (e) {
      debugPrint('[UserPreferenceScreen] load failed (non-Api): $e');
      if (!mounted) return;
      setState(() {
        _error = '설정을 불러오지 못했습니다. ($e)';
        _loading = false;
      });
    }
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      final result = await UserPreferencesApi.update(
        assistantTone: _selected['assistant_tone'],
        responseLength: _selected['response_length'],
        nudgeStrength: _selected['nudge_strength'],
        briefingTime: _briefingTime,
      );
      // 저장 즉시 전역 캐시 갱신 → 이후 채팅/음성 요청이 새 말투를 사용.
      preferenceStore.updateLocal(
        assistantTone: _selected['assistant_tone'],
        responseLength: _selected['response_length'],
        nudgeStrength: _selected['nudge_strength'],
        briefingTime: _briefingTime,
      );
      // 자동 브리핑 알림도 즉시 재예약(빈 문자열이면 취소)한다.
      if (_briefingTime.isEmpty) {
        await briefingSchedulerService.cancel();
      } else {
        await briefingSchedulerService.scheduleDailyBriefing(_briefingTime);
      }
      // 일정 사전 알림 리드타임 저장 + 앞으로의 일정에 재예약(오프라인이면 스킵).
      preferenceStore.updateLocal(alertLeadMinutes: _leadMinutes);
      try {
        final schedules = await scheduleApi.list();
        await briefingSchedulerService.syncScheduleAlerts(
          schedules,
          leadMinutes: _leadMinutes,
        );
      } catch (e) {
        debugPrint('[UserPreferenceScreen] schedule alert re-sync failed: $e');
      }
      if (!mounted) return;
      final ttsText = (result['tts_text'] as String?) ?? '설정을 저장했습니다.';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(ttsText),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          backgroundColor: AppTheme.dark,
        ),
      );
    } on ApiException catch (e) {
      debugPrint('[UserPreferenceScreen] save failed: ${_describeApiError(e)}');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('저장에 실패했습니다: ${_describeApiError(e)}'),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          backgroundColor: AppTheme.red,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('저장에 실패했습니다. ($e)'),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          backgroundColor: AppTheme.red,
        ),
      );
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  /// 현재 선택을 저장한 뒤, 백엔드가 그 스타일로 만들어 준 tts_text 를 실제로
  /// 읽어 준다. "설정을 바꾸면 말투가 어떻게 들리는지" 바로 확인용.
  Future<void> _preview() async {
    setState(() => _saving = true);
    try {
      final result = await UserPreferencesApi.update(
        assistantTone: _selected['assistant_tone'],
        responseLength: _selected['response_length'],
        nudgeStrength: _selected['nudge_strength'],
      );
      preferenceStore.updateLocal(
        assistantTone: _selected['assistant_tone'],
        responseLength: _selected['response_length'],
        nudgeStrength: _selected['nudge_strength'],
      );
      final ttsText = (result['tts_text'] as String?)?.trim();
      await _tts.speak(
        (ttsText != null && ttsText.isNotEmpty)
            ? ttsText
            : '설정한 말투로 이렇게 안내해드릴게요.',
      );
    } on ApiException catch (e) {
      debugPrint(
        '[UserPreferenceScreen] preview failed: ${_describeApiError(e)}',
      );
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('미리듣기에 실패했습니다: ${e.message}')));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('미리듣기에 실패했습니다. ($e)')));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  /// 자동 브리핑 시각 설정 — 저장 시 [briefingSchedulerService] 가 로컬 알림을
  /// 재예약(빈 문자열이면 취소)한다.
  Widget _buildBriefingTimeSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.only(left: 4, bottom: 10),
          child: Text(
            '자동 브리핑',
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
            ),
          ),
        ),
        Row(
          children: [
            Expanded(
              child: GestureDetector(
                onTap: _saving ? null : _pickBriefingTime,
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 12,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.65),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppTheme.separator),
                  ),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.access_time_outlined,
                        size: 18,
                        color: AppTheme.textSecondary,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        _briefingTime.isEmpty ? '설정 안 함' : _briefingTime,
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            if (_briefingTime.isNotEmpty) ...[
              const SizedBox(width: 8),
              IconButton(
                onPressed: _saving
                    ? null
                    : () => setState(() => _briefingTime = ''),
                icon: const Icon(Icons.close, color: AppTheme.textSecondary),
                tooltip: '끄기',
              ),
            ],
          ],
        ),
      ],
    );
  }

  Future<void> _pickBriefingTime() async {
    final initial =
        _parseHhmm(_briefingTime) ?? const TimeOfDay(hour: 8, minute: 0);
    final picked = await showTimePicker(context: context, initialTime: initial);
    if (picked == null) return;
    setState(() {
      _briefingTime =
          '${picked.hour.toString().padLeft(2, '0')}:${picked.minute.toString().padLeft(2, '0')}';
    });
  }

  TimeOfDay? _parseHhmm(String value) {
    final m = RegExp(r'^([01]\d|2[0-3]):([0-5]\d)$').firstMatch(value.trim());
    if (m == null) return null;
    return TimeOfDay(
      hour: int.parse(m.group(1)!),
      minute: int.parse(m.group(2)!),
    );
  }

  /// 일정 사전 알림(리드타임) 설정 — 몇 분/시간 전에 전화형 알림을 울릴지 선택.
  Widget _buildAlertLeadSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.only(left: 4, bottom: 4),
          child: Text(
            '일정 사전 알림',
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
            ),
          ),
        ),
        const Padding(
          padding: EdgeInsets.only(left: 4, bottom: 10),
          child: Text(
            '일정 시작 전에 전화형 알림으로 미리 알려드려요.',
            style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
          ),
        ),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: _leadOptions.map((opt) {
            final (minutes, label) = opt;
            final isSelected = _leadMinutes == minutes;
            return GestureDetector(
              onTap: _saving
                  ? null
                  : () => setState(() => _leadMinutes = minutes),
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 11,
                ),
                decoration: BoxDecoration(
                  color: isSelected
                      ? AppTheme.blue
                      : Colors.white.withValues(alpha: 0.65),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: isSelected ? AppTheme.blue : AppTheme.separator,
                  ),
                ),
                child: Text(
                  label,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: isSelected ? Colors.white : AppTheme.textSecondary,
                  ),
                ),
              ),
            );
          }).toList(),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: _saving ? null : _runTestAlert,
          style: OutlinedButton.styleFrom(
            foregroundColor: AppTheme.purple,
            side: const BorderSide(color: AppTheme.purple),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          icon: const Icon(Icons.notifications_active_outlined, size: 18),
          label: const Text('테스트 알림 (10초 후)'),
        ),
      ],
    );
  }

  /// 데모용: 10초 뒤 전화형 사전 알림을 한 번 띄운다.
  Future<void> _runTestAlert() async {
    await briefingSchedulerService.scheduleTestAlert(seconds: 10);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('10초 뒤 테스트 알림이 울려요. (알림 권한 필요)'),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  Widget _buildOptionSection(String category) {
    final options = _options[category] ?? const [];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 10),
          child: Text(
            _sectionTitles[category] ?? category,
            style: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
            ),
          ),
        ),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: options.map((opt) {
            final code = opt['code']!;
            final label = opt['display_name'] ?? code;
            final isSelected = _selected[category] == code;
            return GestureDetector(
              onTap: _saving
                  ? null
                  : () => setState(() => _selected[category] = code),
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 11,
                ),
                decoration: BoxDecoration(
                  color: isSelected
                      ? AppTheme.blue
                      : Colors.white.withValues(alpha: 0.65),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: isSelected ? AppTheme.blue : AppTheme.separator,
                  ),
                  boxShadow: isSelected
                      ? TossShadow.glow(
                          AppTheme.blue,
                          alpha: 0.25,
                          blur: 8,
                          offset: const Offset(0, 3),
                        )
                      : null,
                ),
                child: Text(
                  label,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: isSelected ? Colors.white : AppTheme.textSecondary,
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          leading: GestureDetector(
            onTap: () => Navigator.pop(context),
            child: Container(
              margin: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.7),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.chevron_left,
                color: AppTheme.textPrimary,
                size: 26,
              ),
            ),
          ),
          title: const Text('AI 음성 스타일 설정'),
        ),
        body: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
            ? Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        _error!,
                        style: const TextStyle(color: AppTheme.textSecondary),
                      ),
                      const SizedBox(height: 12),
                      ElevatedButton(
                        onPressed: _load,
                        child: const Text('다시 시도'),
                      ),
                    ],
                  ),
                ),
              )
            : SingleChildScrollView(
                physics: const BouncingScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    GlassCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _buildOptionSection('assistant_tone'),
                          const SizedBox(height: 20),
                          _buildOptionSection('response_length'),
                          const SizedBox(height: 20),
                          _buildOptionSection('nudge_strength'),
                          const SizedBox(height: 20),
                          _buildBriefingTimeSection(),
                          const SizedBox(height: 20),
                          _buildAlertLeadSection(),
                        ],
                      ),
                    ),
                    const SizedBox(height: 20),
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: _saving ? null : _preview,
                            style: OutlinedButton.styleFrom(
                              foregroundColor: AppTheme.blue,
                              padding: const EdgeInsets.symmetric(vertical: 14),
                              side: const BorderSide(color: AppTheme.blue),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                              ),
                            ),
                            icon: const Icon(
                              Icons.volume_up_outlined,
                              size: 18,
                            ),
                            label: const Text('미리듣기'),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: ElevatedButton(
                            onPressed: _saving ? null : _save,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppTheme.blue,
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(vertical: 14),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                              ),
                            ),
                            child: _saving
                                ? const SizedBox(
                                    width: 20,
                                    height: 20,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: Colors.white,
                                    ),
                                  )
                                : const Text('저장'),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
      ),
    );
  }
}
