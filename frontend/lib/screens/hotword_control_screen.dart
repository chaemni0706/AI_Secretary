import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../services/hotword_service.dart';

/// "포비" 음성 호출 켜기/끄기 테스트 화면.
///
/// 1단계(전경) 검증용: 이 화면(앱)이 열려 있는 동안 "포비 오늘 브리핑" 이라고
/// 말하면 브리핑을 읽어준다. 화면 꺼짐 상시 대기는 이후 포그라운드 서비스로 확장.
class HotwordControlScreen extends StatefulWidget {
  const HotwordControlScreen({super.key});

  @override
  State<HotwordControlScreen> createState() => _HotwordControlScreenState();
}

class _HotwordControlScreenState extends State<HotwordControlScreen> {
  bool _busy = false;
  String? _message;

  Future<void> _toggle(bool on) async {
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      if (on) {
        final ok = await hotwordService.start();
        _message = ok
            ? '대기 중이에요. "포비 오늘 브리핑" 이라고 말해보세요.'
            : '시작하지 못했어요. 마이크 권한 또는 모델 파일을 확인해주세요.';
      } else {
        await hotwordService.stop();
        _message = '음성 대기를 껐어요.';
      }
    } catch (e) {
      _message = '오류: $e';
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final running = hotwordService.isRunning;
    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          title: const Text('음성 비서 (포비)'),
        ),
        body: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
            children: [
              GlassCard(
                child: Row(
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: (running ? AppTheme.green : AppTheme.textSecondary)
                            .withValues(alpha: 0.14),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(
                        running ? Icons.mic : Icons.mic_off,
                        color: running ? AppTheme.green : AppTheme.textSecondary,
                      ),
                    ),
                    const SizedBox(width: 12),
                    const Expanded(
                      child: Text(
                        '"포비" 음성 호출',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                    ),
                    if (_busy)
                      const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    else
                      Switch(
                        value: running,
                        onChanged: (v) => _toggle(v),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              GlassCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _message ?? '스위치를 켜면 음성 대기를 시작합니다.',
                      style: const TextStyle(
                        fontSize: 14,
                        height: 1.5,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 10),
                    const Text(
                      '예) "포비 오늘 브리핑", "포비 오늘 하루 요약"\n'
                      '※ 처음 켤 때 음성 모델(~48MB)을 내려받아 잠시 걸릴 수 있어요.\n'
                      '※ 화면을 꺼도 대기하려면 배터리 최적화를 꺼주세요.',
                      style: TextStyle(
                        fontSize: 12,
                        height: 1.5,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
