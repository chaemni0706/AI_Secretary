import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../services/api_client.dart';
import '../services/user_preferences_api.dart';

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

  Map<String, List<Map<String, String>>> _options = {};
  final Map<String, String> _selected = {
    'assistant_tone': 'friendly',
    'response_length': 'normal',
    'nudge_strength': 'medium',
  };

  static const _sectionTitles = {
    'assistant_tone': 'AI 비서 말투',
    'response_length': '응답 길이',
    'nudge_strength': '리마인드 강도',
  };

  @override
  void initState() {
    super.initState();
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
      );
      if (!mounted) return;
      final ttsText = (result['tts_text'] as String?) ?? '설정을 저장했습니다.';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(ttsText),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
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
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          backgroundColor: AppTheme.red,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('저장에 실패했습니다. ($e)'),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          backgroundColor: AppTheme.red,
        ),
      );
    } finally {
      if (mounted) setState(() => _saving = false);
    }
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
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 11),
                decoration: BoxDecoration(
                  color: isSelected ? AppTheme.blue : Colors.white.withOpacity(0.65),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: isSelected ? AppTheme.blue : AppTheme.separator,
                  ),
                  boxShadow: isSelected
                      ? [
                          BoxShadow(
                            color: AppTheme.blue.withOpacity(0.25),
                            blurRadius: 8,
                            offset: const Offset(0, 3),
                          )
                        ]
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
                color: Colors.white.withOpacity(0.7),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.chevron_left,
                  color: AppTheme.textPrimary, size: 26),
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
                          Text(_error!,
                              style: const TextStyle(color: AppTheme.textSecondary)),
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
                            ],
                          ),
                        ),
                        const SizedBox(height: 20),
                        SizedBox(
                          width: double.infinity,
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
                  ),
      ),
    );
  }
}
