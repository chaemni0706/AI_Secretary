import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../models/booking_message_model.dart';
import '../services/booking_message_api.dart';
import '../services/api_client.dart';

class BookingMessageScreen extends StatefulWidget {
  const BookingMessageScreen({super.key});

  @override
  State<BookingMessageScreen> createState() => _BookingMessageScreenState();
}

class _BookingMessageScreenState extends State<BookingMessageScreen> {
  int _toneIndex = 0;
  bool _loading = false;
  String? _error;
  BookingMessageModel? _model;

  // UI 말투 라벨 → 백엔드 style.tone 값.
  static const _tones = ['정중하게', '간결하게', '친근하게'];
  static const _toneValues = ['polite', 'formal', 'casual'];

  // 예약 대상(데모 기본값). 입력 폼이 붙기 전까지 사용.
  static const _category = 'hospital';
  static const _purpose = '진료 예약';
  static const _preferredTime = '10:00';

  String get _targetDate {
    final d = DateTime.now().add(const Duration(days: 1));
    return '${d.year}-${_two(d.month)}-${_two(d.day)}';
  }

  static String _two(int n) => n.toString().padLeft(2, '0');

  @override
  void initState() {
    super.initState();
    _generate();
  }

  Future<void> _generate() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final model = await bookingMessageApi.generate(
        category: _category,
        targetDate: _targetDate,
        preferredTime: _preferredTime,
        purpose: _purpose,
        tone: _toneValues[_toneIndex],
      );
      if (!mounted) return;
      setState(() {
        _model = model;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '메시지 생성에 실패했습니다. ($e)';
        _loading = false;
      });
    }
  }

  void _copy(String text) {
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text('메시지가 복사되었습니다'),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        backgroundColor: AppTheme.dark,
      ),
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
          title: const Text('예약 메시지'),
        ),
        body: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 80),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildTargetCard(),
              const SizedBox(height: 16),
              _buildToneSelector(),
              const SizedBox(height: 16),
              _buildMessageCard(),
              if (!_loading &&
                  _error == null &&
                  (_model?.alternatives.isNotEmpty ?? false)) ...[
                const SizedBox(height: 16),
                _buildAlternatives(),
              ],
              const SizedBox(height: 16),
              _buildActionButtons(context),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTargetCard() {
    final d = DateTime.now().add(const Duration(days: 1));
    return GlassCard(
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppTheme.teal.withOpacity(0.12),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(Icons.local_hospital_outlined,
                color: AppTheme.teal, size: 22),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '병원 · 진료 예약',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  '${d.month}월 ${d.day}일 오전 10:00',
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildToneSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.only(left: 4, bottom: 10),
          child: Text(
            '말투',
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
            ),
          ),
        ),
        Row(
          children: List.generate(_tones.length, (i) {
            final isSelected = i == _toneIndex;
            return Expanded(
              child: Padding(
                padding:
                    EdgeInsets.only(right: i < _tones.length - 1 ? 8 : 0),
                child: GestureDetector(
                  // 말투 변경 시 새 tone 으로 재생성.
                  onTap: _loading
                      ? null
                      : () {
                          setState(() => _toneIndex = i);
                          _generate();
                        },
                  child: Container(
                    padding: const EdgeInsets.symmetric(vertical: 11),
                    decoration: BoxDecoration(
                      color: isSelected
                          ? AppTheme.blue
                          : Colors.white.withOpacity(0.65),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: isSelected
                            ? AppTheme.blue
                            : AppTheme.separator,
                      ),
                      boxShadow: isSelected
                          ? TossShadow.glow(AppTheme.blue, alpha: 0.25, blur: 8, offset: const Offset(0, 3))
                          : null,
                    ),
                    child: Text(
                      _tones[i],
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color:
                            isSelected ? Colors.white : AppTheme.textSecondary,
                      ),
                    ),
                  ),
                ),
              ),
            );
          }),
        ),
      ],
    );
  }

  Widget _buildMessageCard() {
    final msg = _model?.generatedMessage ?? '';
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Row(
                children: [
                  Icon(Icons.auto_awesome, color: AppTheme.purple, size: 16),
                  SizedBox(width: 6),
                  Text(
                    'AI 생성 메시지',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                ],
              ),
              GestureDetector(
                onTap: _loading ? null : _generate,
                child: Row(
                  children: [
                    if (_loading)
                      const SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: AppTheme.blue),
                      )
                    else
                      const Icon(Icons.refresh, size: 16, color: AppTheme.blue),
                    const SizedBox(width: 4),
                    const Text(
                      '다시 생성',
                      style: TextStyle(
                        fontSize: 13,
                        color: AppTheme.blue,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppTheme.background.withOpacity(0.6),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.separator),
            ),
            child: _loading
                ? const Center(
                    child: Padding(
                      padding: EdgeInsets.symmetric(vertical: 8),
                      child: CircularProgressIndicator(),
                    ),
                  )
                : _error != null
                    ? Column(
                        children: [
                          Text(
                            _error!,
                            style: const TextStyle(
                                fontSize: 13, color: AppTheme.textSecondary),
                          ),
                          const SizedBox(height: 8),
                          FilledButton(
                            onPressed: _generate,
                            style: FilledButton.styleFrom(
                                backgroundColor: AppTheme.blue),
                            child: const Text('다시 시도'),
                          ),
                        ],
                      )
                    : Text(
                        msg,
                        style: const TextStyle(
                          fontSize: 15,
                          color: AppTheme.textPrimary,
                          height: 1.6,
                        ),
                      ),
          ),
          if (!_loading && _error == null && msg.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(
              '${msg.length}자 · 문자/카카오톡으로 보낼 수 있어요',
              style: const TextStyle(
                fontSize: 11,
                color: AppTheme.textSecondary,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildAlternatives() {
    final alts = _model!.alternatives;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.only(left: 4, bottom: 8),
          child: Text(
            '대안 문장',
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
            ),
          ),
        ),
        ...alts.map((a) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: GlassCard(
                padding: const EdgeInsets.all(12),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Text(
                        a,
                        style: const TextStyle(
                          fontSize: 13,
                          color: AppTheme.textPrimary,
                          height: 1.5,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    GestureDetector(
                      onTap: () => _copy(a),
                      child: const Icon(Icons.content_copy,
                          size: 16, color: AppTheme.textSecondary),
                    ),
                  ],
                ),
              ),
            )),
      ],
    );
  }

  Widget _buildActionButtons(BuildContext context) {
    final msg = _model?.generatedMessage ?? '';
    final canCopy = !_loading && _error == null && msg.isNotEmpty;
    return Column(
      children: [
        SizedBox(
          width: double.infinity,
          child: FilledButton.icon(
            onPressed: canCopy ? () => _copy(msg) : null,
            icon: const Icon(Icons.content_copy, size: 18),
            label: const Text('복사하기',
                style:
                    TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
            style: FilledButton.styleFrom(
              backgroundColor: AppTheme.blue,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14)),
            ),
          ),
        ),
        const SizedBox(height: 10),
        SizedBox(
          width: double.infinity,
          child: TextButton.icon(
            onPressed: () {},
            icon: const Icon(Icons.edit_outlined, size: 18),
            label: const Text('직접 수정하기',
                style:
                    TextStyle(fontSize: 15, fontWeight: FontWeight.w500)),
            style: TextButton.styleFrom(
              foregroundColor: AppTheme.textSecondary,
              padding: const EdgeInsets.symmetric(vertical: 12),
            ),
          ),
        ),
      ],
    );
  }
}
