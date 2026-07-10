import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../models/reservation_model.dart';
import '../services/reservation_api.dart';
import '../services/schedule_api.dart';
import '../services/api_client.dart';
import '../services/dashboard_api.dart';
import 'booking_message_screen.dart';

/// 예약 조건(데모 기본값).
///
/// 실제 화면에 입력 폼이 붙기 전까지는 이 기본값으로 예약 후보를 요청한다.
/// (백엔드 `/reservations/candidates/from-store` 는 title/location 을 받지 않으므로,
///  그 두 값은 저장 시 schedule_draft 를 만들 때만 사용한다.)
class _BookingRequest {
  final String title;
  final String category;
  final String? location;
  final int durationMinutes;
  final String preferredStartTime;
  final String preferredEndTime;
  final String priority;
  final String date; // YYYY-MM-DD

  const _BookingRequest({
    required this.title,
    required this.category,
    required this.date,
    this.location,
    this.durationMinutes = 60,
    this.preferredStartTime = '18:00',
    this.preferredEndTime = '21:00',
    this.priority = 'medium',
  });
}

class BookingRecommendScreen extends StatefulWidget {
  const BookingRecommendScreen({super.key});

  @override
  State<BookingRecommendScreen> createState() => _BookingRecommendScreenState();
}

class _BookingRecommendScreenState extends State<BookingRecommendScreen> {
  late final _BookingRequest _request;

  bool _loading = true;
  String? _error;
  ReservationResult? _result;
  int? _selectedIndex;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _request = _BookingRequest(
      title: '미용실 커트',
      category: 'beauty',
      location: '강남 미용실',
      durationMinutes: 60,
      preferredStartTime: '13:00',
      preferredEndTime: '18:00',
      // 기본값은 '오늘'. 저장 후 홈(오늘 대시보드)에서 바로 확인되도록 한다.
      date: _todayYmd(),
    );
    _loadCandidates();
  }

  static String _two(int n) => n.toString().padLeft(2, '0');

  /// 오늘 날짜(YYYY-MM-DD).
  static String _todayYmd() {
    final now = DateTime.now();
    return '${now.year}-${_two(now.month)}-${_two(now.day)}';
  }

  Future<void> _loadCandidates() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await reservationApi.candidatesFromStore(
        targetDate: _request.date,
        durationMinutes: _request.durationMinutes,
        preferredStartTime: _request.preferredStartTime,
        preferredEndTime: _request.preferredEndTime,
        category: _request.category,
        userId: 'demo-user',
      );
      if (!mounted) return;
      // conflict=false 인 첫 후보를 기본 선택.
      int? firstSelectable;
      for (var i = 0; i < result.recommendedCandidates.length; i++) {
        if (!result.recommendedCandidates[i].conflict) {
          firstSelectable = i;
          break;
        }
      }
      setState(() {
        _result = result;
        _selectedIndex = firstSelectable;
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
        _error = '예약 후보를 불러오지 못했습니다. ($e)';
        _loading = false;
      });
    }
  }

  // ---- 시간/날짜 파싱 (HH:mm 또는 ISO datetime 모두 대응) --------------------

  String _hhmm(String s) {
    if (s.contains('T')) {
      final t = s.split('T')[1];
      return t.length >= 5 ? t.substring(0, 5) : t;
    }
    return s.length >= 5 ? s.substring(0, 5) : s;
  }

  String _dateOf(String s) {
    if (s.contains('T')) return s.split('T')[0];
    if (s.length >= 10 && s[4] == '-') return s.substring(0, 10);
    return _request.date; // 후보가 시간만 줄 경우 요청 날짜 사용
  }

  static const List<String> _weekdayKo = ['월', '화', '수', '목', '금', '토', '일'];

  String _formatDateKo(String ymd) {
    try {
      final d = DateTime.parse(ymd);
      final w = _weekdayKo[(d.weekday - 1) % 7];
      return '${d.month}월 ${d.day}일 ($w)';
    } catch (_) {
      return ymd;
    }
  }

  // ---- 캘린더 등록 ----------------------------------------------------------

  Future<void> _register() async {
    debugPrint('[BookingRecommend] calendar register button clicked');
    final result = _result;
    final idx = _selectedIndex;
    if (result == null || idx == null) {
      debugPrint('[BookingRecommend] no candidate selected -> abort');
      _snack('예약 시간을 먼저 선택해주세요.');
      return;
    }
    final cand = result.recommendedCandidates[idx];
    if (cand.conflict) {
      _snack('충돌이 있는 후보는 저장할 수 없습니다.');
      return;
    }

    setState(() => _saving = true);
    try {
      // 선택 후보 → schedule_draft 변환 (start/end 는 HH:mm 로 추출).
      final draft = <String, dynamic>{
        'title': _request.title,
        'date': _dateOf(cand.startTime),
        'start_time': _hhmm(cand.startTime),
        'end_time': _hhmm(cand.endTime),
        if (_request.location != null) 'location': _request.location,
        'category': _request.category,
        'priority': _request.priority,
        'source': 'ai',
      };

      debugPrint('[BookingRecommend] calling createFromDraft  draft=$draft');

      final saved = await scheduleApi.createFromDraft(
        draft,
        intent: 'create_schedule',
      );

      debugPrint(
        '[BookingRecommend] schedule saved successfully  id=${saved.id} '
        'date=${saved.date} ${saved.startTime}-${saved.endTime}',
      );

      // 홈 대시보드 새로고침 트리거.
      triggerDashboardRefresh();

      if (!mounted) return;
      setState(() => _saving = false);
      // 실제 저장된 날짜·시간을 명확히 보여준다(홈의 '오늘'과 다를 수 있으므로).
      _snack(
        '캘린더에 등록됨 · ${saved.date} ${saved.startTime ?? ''}'
        '${saved.endTime != null ? '–${saved.endTime}' : ''} · "${saved.title}"',
      );
      // 홈으로 돌아가 갱신된 대시보드를 보여준다.
      await Future.delayed(const Duration(milliseconds: 900));
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (e) {
      debugPrint('[BookingRecommend] schedule save failed (api): ${e.message}');
      if (!mounted) return;
      setState(() => _saving = false);
      _snack('일정 등록에 실패했습니다: ${e.message}');
    } catch (e) {
      debugPrint('[BookingRecommend] schedule save failed: $e');
      if (!mounted) return;
      setState(() => _saving = false);
      _snack('일정 등록에 실패했습니다: $e');
    }
  }

  void _snack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  // ---- build ---------------------------------------------------------------

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
          title: const Text('예약 후보 추천'),
        ),
        body: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 80),
          child: Column(
            children: [
              _buildRequestCard(),
              const SizedBox(height: 16),
              if (_loading)
                const Padding(
                  padding: EdgeInsets.only(top: 80),
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (_error != null)
                _buildError()
              else ...[
                _buildSlotsHeader(),
                const SizedBox(height: 10),
                ..._buildSlotCards(context),
                const SizedBox(height: 20),
                _buildActionButtons(context),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildError() {
    return Padding(
      padding: const EdgeInsets.only(top: 40),
      child: GlassCard(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            const Icon(
              Icons.cloud_off,
              color: AppTheme.textSecondary,
              size: 36,
            ),
            const SizedBox(height: 12),
            Text(
              _error ?? '예약 후보를 불러오지 못했습니다.',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 14, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 6),
            const Text(
              '백엔드 서버가 실행 중인지 확인하세요.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 14),
            FilledButton(
              onPressed: _loadCandidates,
              style: FilledButton.styleFrom(backgroundColor: AppTheme.blue),
              child: const Text('다시 시도'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRequestCard() {
    return GlassCard(
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppTheme.purple.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(
              Icons.content_cut,
              color: AppTheme.purple,
              size: 22,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _request.title,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  '${_formatDateKo(_request.date)} '
                  '${_request.preferredStartTime}~${_request.preferredEndTime} · '
                  '소요 ${_request.durationMinutes}분',
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          GestureDetector(
            onTap: _loading ? null : _loadCandidates,
            child: Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: AppTheme.textSecondary.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(
                Icons.refresh,
                color: AppTheme.textSecondary,
                size: 18,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSlotsHeader() {
    final count = _result?.recommendedCandidates.length ?? 0;
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          '추천 후보 $count',
          style: const TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w700,
            color: AppTheme.textPrimary,
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
          decoration: BoxDecoration(
            color: AppTheme.blue.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: const Text(
            '충돌 없는 시간대',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppTheme.blue,
            ),
          ),
        ),
      ],
    );
  }

  List<Widget> _buildSlotCards(BuildContext context) {
    final candidates = _result?.recommendedCandidates ?? const [];
    if (candidates.isEmpty) {
      return [
        const GlassCard(
          padding: EdgeInsets.symmetric(horizontal: 16, vertical: 18),
          child: Text(
            '추천 가능한 시간이 없습니다. 조건을 바꿔 다시 시도해 보세요.',
            style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
          ),
        ),
      ];
    }

    return List.generate(candidates.length, (i) {
      final c = candidates[i];
      final selectable = !c.conflict;
      final isSelected = i == _selectedIndex;
      return Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: GestureDetector(
          onTap: selectable ? () => setState(() => _selectedIndex = i) : null,
          child: Opacity(
            opacity: selectable ? 1.0 : 0.5,
            child: GlassCard(
              color: isSelected
                  ? AppTheme.blue.withValues(alpha: 0.08)
                  : Colors.white.withValues(alpha: 0.72),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      color: isSelected
                          ? AppTheme.blue
                          : AppTheme.textSecondary.withValues(alpha: 0.12),
                      shape: BoxShape.circle,
                    ),
                    child: Center(
                      child: Text(
                        '${i + 1}',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: isSelected
                              ? Colors.white
                              : AppTheme.textSecondary,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(
                              _formatDateKo(_dateOf(c.startTime)),
                              style: const TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w700,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                            const Spacer(),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 3,
                              ),
                              decoration: BoxDecoration(
                                color: isSelected
                                    ? AppTheme.blue
                                    : AppTheme.textSecondary.withValues(
                                        alpha: 0.1,
                                      ),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Text(
                                '${c.score}점',
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w700,
                                  color: isSelected
                                      ? Colors.white
                                      : AppTheme.textSecondary,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '${_hhmm(c.startTime)} – ${_hhmm(c.endTime)}',
                          style: TextStyle(
                            fontSize: 14,
                            color: isSelected
                                ? AppTheme.blue
                                : AppTheme.textPrimary,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Row(
                          children: [
                            Icon(
                              c.conflict
                                  ? Icons.error_outline
                                  : Icons.check_circle_outline,
                              size: 14,
                              color: c.conflict
                                  ? Colors.redAccent
                                  : AppTheme.green,
                            ),
                            const SizedBox(width: 5),
                            Expanded(
                              child: Text(
                                c.conflict ? '충돌 · 선택 불가' : c.reason,
                                style: TextStyle(
                                  fontSize: 12,
                                  color: c.conflict
                                      ? Colors.redAccent
                                      : AppTheme.green,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    });
  }

  Widget _buildActionButtons(BuildContext context) {
    return Column(
      children: [
        SizedBox(
          width: double.infinity,
          child: FilledButton.icon(
            onPressed: _saving ? null : _register,
            icon: _saving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.event_available, size: 18),
            label: Text(
              _saving ? '저장 중...' : '캘린더에 등록하기',
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
            ),
            style: FilledButton.styleFrom(
              backgroundColor: AppTheme.blue,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(14),
              ),
            ),
          ),
        ),
        const SizedBox(height: 10),
        SizedBox(
          width: double.infinity,
          child: OutlinedButton.icon(
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const BookingMessageScreen()),
            ),
            icon: const Icon(Icons.forum_outlined, size: 18),
            label: const Text(
              '예약 메시지 생성',
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
            ),
            style: OutlinedButton.styleFrom(
              foregroundColor: AppTheme.textPrimary,
              side: const BorderSide(color: AppTheme.separator, width: 1.5),
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(14),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
