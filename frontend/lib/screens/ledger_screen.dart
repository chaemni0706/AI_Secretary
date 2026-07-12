import 'dart:async';

import 'package:flutter/material.dart';
import '../core/utils/ledger_date.dart';
import '../data/ledger_notification_templates.dart';
import '../models/ledger_api_models.dart';
import '../models/ledger_mappers.dart';
import '../models/ledger_models.dart';
import '../models/mock_ledger_data.dart';
import '../services/api_client.dart';
import '../services/ledger_api.dart';
import '../services/ledger_notification_ingest_service.dart';
import '../services/ledger_notification_permission_service.dart';
import '../services/local_demo_notification_service.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/ledger_styles.dart';
import '../widgets/app_top_actions.dart';
import '../widgets/budget_segmented_control.dart';
import '../widgets/glass_card.dart';
import '../widgets/ledger_ai_briefing_card.dart';
import '../widgets/ledger_auto_detect_card.dart';
import '../widgets/ledger_calendar_grid.dart';
import '../widgets/ledger_transaction_row.dart';
import '../widgets/toss_motion_widgets.dart';
import 'ledger_report_screen.dart';

/// AI 가계부 메인 화면 — 소비 달력 홈 (API-first).
///
/// 현재 날짜 기준으로 백엔드 대시보드를 조회한다. 네트워크 실패(서버 미도달) 시에만
/// [MockLedgerData] 로 오프라인 데모 fallback 하며, 서버 오류/파싱 오류는 재시도
/// 버튼과 함께 표시한다. 기존 위젯/디자인은 그대로 재사용한다.
class LedgerScreen extends StatefulWidget {
  const LedgerScreen({super.key});

  @override
  State<LedgerScreen> createState() => _LedgerScreenState();
}

class _LedgerScreenState extends State<LedgerScreen> {
  static const _dow = ['일', '월', '화', '수', '목', '금', '토'];
  static const _userId = 'local-user';

  // --- 로딩/상태 -----------------------------------------------------------
  bool _loading = true;
  bool _submitting = false;
  bool _usingFallback = false;
  String? _errorMessage;

  /// AI 브리핑이 백그라운드 생성 중(pending)일 때 조용히 재조회할 남은 횟수.
  /// 사용자 조작(비 silent)으로 로드할 때마다 예산을 리셋한다(무한 폴링 방지).
  int _briefingPollsLeft = 0;

  late DateTime _focusedMonth; // 해당 월의 1일
  late DateTime _selectedDate; // 선택된 날짜(오늘 기준 시작)
  LedgerDashboardDto? _dashboard;

  /// 거래내역 탭용 '월 전체' 거래(선택 날짜에 한정하지 않음). 대시보드와 함께 로드한다.
  LedgerMonthTransactionsDto? _monthTx;

  // fallback(오프라인) 전용 로컬 대기 목록.
  final List<PendingTx> _localPending = List.of(MockLedgerData.initialPending);

  int _topTab = 0;
  late final PageController _pageController;

  /// 거래 mutation(등록/확정/수정/삭제) 성공마다 증가 → 리포트 탭 stale 판정용.
  int _refreshToken = 0;

  /// 네이티브(Android) 실시간 알림 구독. Android 외 플랫폼에선 null.
  StreamSubscription<dynamic>? _notifSub;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _focusedMonth = DateTime(now.year, now.month);
    _selectedDate = DateTime(now.year, now.month, now.day);
    _pageController = PageController(initialPage: _topTab);
    _loadDashboard();
    _startNativeListener();
  }

  @override
  void dispose() {
    _notifSub?.cancel();
    _pageController.dispose();
    super.dispose();
  }

  /// Android '알림 접근' 권한이 켜져 있으면, 네이티브에서 올라오는 결제/입금
  /// 알림을 자동으로 백엔드에 등록하고 대시보드를 재조회한다.
  void _startNativeListener() {
    _notifSub = ledgerNotificationPermission.listenAndIngest(
      userId: _userId,
      onIngested: (result) {
        if (!mounted) return;
        if (result.duplicate) {
          _snack('이미 등록된 거래예요');
        } else if (!result.isIgnored) {
          _snack('새 결제 알림을 가계부에 등록했어요');
        }
        _reloadAfterMutation();
      },
      onError: (_) {
        /* 실시간 감지 실패는 조용히 무시(수동 등록으로 대체 가능) */
      },
    );
  }

  int get _year => _focusedMonth.year;
  int get _month => _focusedMonth.month;
  int get _selectedDay => _selectedDate.day;

  bool get _usingApi => !_usingFallback && _dashboard != null;

  /// 리스트(거래내역) 탭용: 대시보드와 무관하게 빠른 월 거래내역만 있으면 실데이터로 본다.
  bool get _hasMonthTx => !_usingFallback && _monthTx != null;

  List<PendingTx> get _pendingList {
    if (_usingApi) return _dashboard!.pendingCards();
    if (_usingFallback) return _localPending;
    // 실데이터 모드지만 대시보드(대기 거래 포함)가 아직 로딩 중 → 잠깐 비워 둔다.
    return const [];
  }

  // --- 데이터 로드 ---------------------------------------------------------
  Future<void> _loadDashboard({bool silent = false}) async {
    if (!silent) {
      setState(() {
        _loading = true;
        _errorMessage = null;
      });
      _briefingPollsLeft = 5; // 사용자 조작 로드마다 폴링 예산 리셋.
    }
    // 대시보드(4초대)와 거래내역(수십 ms)을 '병렬로 기다리기'(Future.wait)면
    // 느린 쪽이 끝날 때까지 화면 전체가 스피너에 묶인다. 대신 두 요청을 독립적으로
    // 실행해, 빠른 거래내역이 오면 즉시 화면을 띄우고 느린 대시보드는 도착하는 대로
    // 달력 요약·브리핑을 채운다.
    //
    // 응답 유효성은 '요청한 월/날짜가 지금과 같은지'로 판정한다. (단조 토큰으로
    // 판정하면 시작 시 알림 리스너 등이 로드를 연달아 부를 때 먼저 온 응답이 모두
    // 폐기돼 화면이 안 채워지는 문제가 있었다. 같은 날짜의 중복 응답은 모두 반영하고
    // 진짜 오래된(다른 날짜) 응답만 버린다.)
    final reqMonth = _focusedMonth;
    final reqDate = _selectedDate;
    bool monthStale() =>
        !mounted ||
        reqMonth.year != _focusedMonth.year ||
        reqMonth.month != _focusedMonth.month;
    bool dashStale() => monthStale() || !sameDate(reqDate, _selectedDate);

    // (1) 월 전체 거래내역 — 빠름. 오면 즉시 로딩 해제 → 리스트 탭/화면이 바로 뜬다.
    ledgerApi
        .monthTransactions(userId: _userId, year: _year, month: _month)
        .then((tx) {
      if (monthStale()) return;
      setState(() {
        _monthTx = tx;
        _usingFallback = false;
        _errorMessage = null;
        _loading = false;
      });
    }).catchError((Object e) {
      if (monthStale()) return;
      _handleLoadError(e);
    });

    // (2) 대시보드 — 느림(브리핑 생성). 오면 달력 요약을 채우고 개별 로더만 해제.
    ledgerApi
        .dashboard(
          userId: _userId,
          year: _year,
          month: _month,
          selectedDate: reqDate,
        )
        .then((d) {
      if (dashStale()) return;
      setState(() {
        _dashboard = d;
        _usingFallback = false;
        _errorMessage = null;
        _loading = false;
      });
      _maybePollBriefing();
    }).catchError((Object e) {
      if (dashStale()) return;
      _handleLoadError(e);
    });
  }

  /// AI 브리핑이 아직 백그라운드 생성 중이면, 잠시 후 조용히 다시 조회해서
  /// 준비된 AI 문장으로 교체한다(예산 소진 시 중단 → 무한 폴링 방지).
  void _maybePollBriefing() {
    if (_dashboard?.briefingPending != true) return;
    if (_briefingPollsLeft <= 0) return;
    _briefingPollsLeft--;
    Future.delayed(const Duration(seconds: 3), () {
      if (mounted && _dashboard?.briefingPending == true) {
        _refreshDashboardOnly();
      }
    });
  }

  /// 브리핑 폴링 전용: 거래내역은 건드리지 않고 대시보드만 강제 새로고침한다.
  /// (전체 _loadDashboard 는 거래내역까지 재조회해 리스트가 들썩이므로 사용하지 않는다.
  ///  또 프론트 30초 캐시를 건너뛰어야 백그라운드로 준비된 최신 AI 문장을 받는다.)
  void _refreshDashboardOnly() {
    final reqMonth = _focusedMonth;
    final reqDate = _selectedDate;
    ledgerApi
        .dashboard(
          userId: _userId,
          year: _year,
          month: _month,
          selectedDate: reqDate,
          forceRefresh: true,
        )
        .then((d) {
      if (!mounted ||
          reqMonth.year != _focusedMonth.year ||
          reqMonth.month != _focusedMonth.month ||
          !sameDate(reqDate, _selectedDate)) {
        return;
      }
      setState(() => _dashboard = d);
      _maybePollBriefing();
    }).catchError((Object _) {
      /* 폴링 실패는 조용히 무시(다음 로드에서 다시 시도) */
    });
  }

  /// 로드 실패 처리. 네트워크 오류(서버 미도달)이고 아직 실데이터가 하나도 없으면
  /// 오프라인 데모(fallback)로 전환한다. 이미 실데이터가 있으면 그대로 유지한다.
  void _handleLoadError(Object e) {
    if (!mounted) return;
    if (e is ApiException) {
      if (e.isNetworkError) {
        if (_dashboard == null && _monthTx == null) {
          setState(() {
            _usingFallback = true;
            _dashboard = null;
            _monthTx = null;
            _errorMessage = null;
            _loading = false;
          });
        } else {
          setState(() => _loading = false);
        }
      } else {
        setState(() {
          _errorMessage = e.message;
          _loading = false;
        });
      }
    } else if (e is FormatException) {
      setState(() {
        _errorMessage = '응답 형식 오류: ${e.message}';
        _loading = false;
      });
    } else {
      setState(() {
        _errorMessage = '알 수 없는 오류가 발생했어요.';
        _loading = false;
      });
    }
  }

  /// mutation 성공 후: refreshToken 을 올려 리포트 탭을 stale 로 만들고 대시보드 재조회.
  Future<void> _reloadAfterMutation() {
    _refreshToken++;
    return _loadDashboard(silent: true);
  }

  /// 리포트 내부 월 이동 → 홈(달력)과 월을 동기화(단일 source of truth).
  void _onReportMonthChanged(DateTime m) {
    if (m.year == _focusedMonth.year && m.month == _focusedMonth.month) return;
    final lastDay = lastDayOfMonth(m.year, m.month);
    final day = _selectedDate.day.clamp(1, lastDay);
    setState(() {
      _focusedMonth = DateTime(m.year, m.month);
      _selectedDate = DateTime(m.year, m.month, day);
    });
    _loadDashboard(silent: true);
  }

  // --- 날짜/월 이동 --------------------------------------------------------
  void _onSelectDate(DateTime date) {
    if (sameDate(date, _selectedDate)) return;
    setState(() => _selectedDate = date);
    if (_usingApi || (!_usingFallback && !_loading)) {
      _loadDashboard(silent: true);
    }
  }

  void _onChangeMonth(int delta) {
    final next = DateTime(_focusedMonth.year, _focusedMonth.month + delta);
    // 선택 날짜를 새 월 범위 안으로 보정(예: 31일 → 2월 이동 시 28/29일).
    final lastDay = lastDayOfMonth(next.year, next.month);
    final day = _selectedDate.day.clamp(1, lastDay);
    setState(() {
      _focusedMonth = next;
      _selectedDate = DateTime(next.year, next.month, day);
    });
    _loadDashboard();
  }

  // --- 임의 금융 알림 보내기 (실제 등록) -----------------------------------
  /// 템플릿 선택 / 직접 입력 다이얼로그를 열고, 확정 시 실제 등록으로 넘긴다.
  Future<void> _openNotificationComposer() async {
    if (_submitting) return;
    final controller = TextEditingController();
    try {
      final text = await showDialog<String>(
        context: context,
        builder: (ctx) {
          String? chosen;
          return StatefulBuilder(
            builder: (ctx, setLocal) {
              return AlertDialog(
                title: const Text('금융 알림 보내기'),
                content: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        '카드·은행 알림처럼 보이는 문구를 보내면 서버가 분석해 거래로 등록해요.',
                        style: TextStyle(fontSize: 12.5, height: 1.4),
                      ),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: TextButton.icon(
                          onPressed: () => ledgerNotificationPermission
                              .openPermissionSettings(),
                          style: TextButton.styleFrom(
                            padding: EdgeInsets.zero,
                            minimumSize: const Size(0, 32),
                            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                          ),
                          icon: const Icon(
                            Icons.notifications_active_outlined,
                            size: 16,
                          ),
                          label: const Text(
                            '실시간 자동 감지 설정 열기 (Android)',
                            style: TextStyle(fontSize: 12),
                          ),
                        ),
                      ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: [
                          for (final t in ledgerNotificationTemplates)
                            ChoiceChip(
                              label: Text(t.label),
                              selected: chosen == t.text,
                              onSelected: (_) => setLocal(() {
                                chosen = t.text;
                                controller.text = t.text;
                                controller.selection = TextSelection.collapsed(
                                  offset: controller.text.length,
                                );
                              }),
                            ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: controller,
                        minLines: 1,
                        maxLines: 3,
                        decoration: const InputDecoration(
                          labelText: '알림 원문',
                          hintText: '[카드사] 상호 12,000원 승인',
                        ),
                      ),
                    ],
                  ),
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(ctx),
                    child: const Text('취소'),
                  ),
                  TextButton(
                    onPressed: () {
                      final v = controller.text.trim();
                      if (v.isEmpty) return;
                      Navigator.pop(ctx, v);
                    },
                    child: const Text('등록'),
                  ),
                ],
              );
            },
          );
        },
      );
      if (text == null || text.trim().isEmpty) return;
      await _sendNotification(text.trim());
    } finally {
      controller.dispose();
    }
  }

  /// 원문 알림 텍스트를 백엔드로 보내 실제 DB 거래로 등록한다.
  /// (프론트는 파싱하지 않는다. 서버 미도달 시 mock 추가 없이 안내만 한다.)
  ///
  /// 시연 UX: 먼저 로컬 알림을 상단에 띄워 "진짜 알림이 온 것처럼" 보이게 하되,
  /// 실제 등록의 source of truth 는 백엔드다. 알림 표시 실패가 등록 실패로
  /// 이어지지 않도록 완전히 분리한다.
  Future<void> _sendNotification(String text) async {
    if (_submitting) return;
    setState(() => _submitting = true);

    // 1) 보여주기용 로컬 알림(실패해도 등록에 영향 없음).
    final display = _splitForDisplay(text);
    await localDemoNotifications.showFinanceNotification(
      title: display.$1,
      body: display.$2,
    );

    try {
      // 2) 알림 원문은 항상 단일 진입점(ingest service)을 통해 백엔드로 전달한다.
      //    향후 Android NotificationListenerService 수신분도 같은 경로로 연결된다.
      final result = await ledgerNotificationIngest.ingestRawNotification(
        text: text,
        source: 'manual_demo',
        userId: _userId,
        receivedAt: DateTime.now(),
      );
      if (result.duplicate) {
        _snack('이미 등록된 알림이에요');
      } else if (result.isIgnored) {
        _snack('광고·안내 알림으로 판단해 등록하지 않았어요.');
      } else {
        _snack('금융 알림을 감지해 가계부에 등록했어요');
      }
      await _reloadAfterMutation();
    } on ApiException catch (e) {
      _snack(e.isNetworkError ? '서버 연결 후 다시 시도해 주세요' : '등록 실패: ${e.message}');
    } catch (_) {
      _snack('알림 등록 중 오류가 발생했어요.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  /// 알림 표시용으로만 제목/본문을 나눈다(거래 파싱 아님, 순수 표시 목적).
  /// '[카드사] 본문' 형태면 대괄호를 제목으로, 아니면 '금융 알림'을 제목으로 쓴다.
  (String, String) _splitForDisplay(String text) {
    final m = RegExp(r'^\[(.+?)\]\s*(.*)$').firstMatch(text.trim());
    if (m != null) {
      final title = m.group(1)!.trim();
      final body = m.group(2)!.trim();
      if (body.isNotEmpty) return (title, body);
    }
    return ('금융 알림', text.trim());
  }

  // --- 확정/수정/삭제 ------------------------------------------------------
  Future<void> _mutate(Future<void> Function() action, String okMsg) async {
    if (_submitting) return;
    setState(() => _submitting = true);
    try {
      await action();
      _snack(okMsg);
      await _reloadAfterMutation();
    } on ApiException catch (e) {
      _snack(e.isNetworkError ? '서버에 연결할 수 없어요' : '요청 실패: ${e.message}');
    } catch (_) {
      _snack('처리 중 오류가 발생했어요.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _confirmPending(PendingTx p) async {
    if (_submitting) return;
    if (_usingFallback) {
      setState(() => _localPending.removeWhere((x) => x.id == p.id));
      _snack('거래를 확정했어요');
      return;
    }
    if (!p.hasTransactionId) {
      _snack('거래 ID가 없어 처리할 수 없어요');
      return;
    }
    await _mutate(
      () => ledgerApi.confirmTransaction(
        transactionId: p.transactionId!,
        userId: _userId,
      ),
      '거래를 확정했어요',
    );
  }

  Future<void> _removePending(PendingTx p) async {
    if (_submitting) return;
    final ok = await _confirmDialog('거래 삭제', '이 거래를 삭제할까요?');
    if (ok != true) return;
    if (_usingFallback) {
      setState(() => _localPending.removeWhere((x) => x.id == p.id));
      _snack('거래를 삭제했어요');
      return;
    }
    if (!p.hasTransactionId) {
      _snack('거래 ID가 없어 처리할 수 없어요');
      return;
    }
    await _mutate(
      () => ledgerApi.deleteTransaction(
        transactionId: p.transactionId!,
        userId: _userId,
      ),
      '거래를 삭제했어요',
    );
  }

  Future<void> _editPending(PendingTx p) async {
    if (_submitting) return;
    final result = await _showEditDialog(p);
    if (result == null) return;

    if (_usingFallback) {
      setState(() {
        final i = _localPending.indexWhere((x) => x.id == p.id);
        if (i >= 0) {
          _localPending[i] = _localPending[i].copyWith(
            method: '직접 수정',
            review: false,
            confidence: 100,
          );
        }
      });
      _snack('거래를 수정했어요');
      return;
    }
    if (!p.hasTransactionId) {
      _snack('거래 ID가 없어 처리할 수 없어요');
      return;
    }

    // 시각만 입력하고 날짜를 비운 경우, 선택 날짜로 보정한다(백엔드는 occurred_at 필요).
    var date = result.date;
    final time = result.time;
    if ((date == null || date.isEmpty) && (time != null && time.isNotEmpty)) {
      date = yyyyMmDd(_selectedDate);
    }

    await _mutate(
      () => ledgerApi.updateTransaction(
        transactionId: p.transactionId!,
        userId: _userId,
        merchant: result.merchant,
        amount: result.amount,
        category: result.category,
        date: (date == null || date.isEmpty) ? null : date,
        time: (time == null || time.isEmpty) ? null : time,
        memo: result.memo,
      ),
      '거래를 수정했어요',
    );
  }

  Future<bool?> _confirmDialog(String title, String message) {
    return showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('취소'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('삭제'),
          ),
        ],
      ),
    );
  }

  Future<_EditResult?> _showEditDialog(PendingTx p) async {
    final merchantCtl = TextEditingController(text: p.merchant);
    final amountCtl = TextEditingController(text: p.amount.abs().toString());
    final categoryCtl = TextEditingController(text: p.category);
    final dateCtl = TextEditingController(text: p.date ?? '');
    final timeCtl = TextEditingController(text: p.time ?? '');
    final memoCtl = TextEditingController(text: p.memo ?? '');
    try {
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('거래 수정'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: merchantCtl,
                  decoration: const InputDecoration(labelText: '상호명'),
                ),
                TextField(
                  controller: amountCtl,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: '금액(원)'),
                ),
                TextField(
                  controller: categoryCtl,
                  decoration: const InputDecoration(labelText: '카테고리'),
                ),
                TextField(
                  controller: dateCtl,
                  decoration: const InputDecoration(
                    labelText: '날짜',
                    hintText: 'YYYY-MM-DD',
                  ),
                ),
                TextField(
                  controller: timeCtl,
                  decoration: const InputDecoration(
                    labelText: '시각',
                    hintText: 'HH:MM',
                  ),
                ),
                TextField(
                  controller: memoCtl,
                  maxLines: 2,
                  decoration: const InputDecoration(
                    labelText: '메모',
                    hintText: '예: 친구랑 저녁, 경비 처리',
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('취소'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('저장'),
            ),
          ],
        ),
      );
      if (ok != true) return null;
      final merchant = merchantCtl.text.trim();
      final amount = int.tryParse(amountCtl.text.replaceAll(',', '').trim());
      final category = categoryCtl.text.trim();
      final date = dateCtl.text.trim();
      final time = timeCtl.text.trim();
      // memo: 원본과 다를 때만 전송(빈 문자열이면 삭제 의도로 전송, 동일하면 미전송).
      final memoText = memoCtl.text.trim();
      final memoChanged = memoText != (p.memo ?? '');
      return _EditResult(
        merchant: merchant.isEmpty ? null : merchant,
        amount: amount,
        category: category.isEmpty ? null : category,
        date: date.isEmpty ? null : date,
        time: time.isEmpty ? null : time,
        memo: memoChanged ? memoText : null,
      );
    } finally {
      merchantCtl.dispose();
      amountCtl.dispose();
      categoryCtl.dispose();
      dateCtl.dispose();
      timeCtl.dispose();
      memoCtl.dispose();
    }
  }

  void _openReport() => _onTabTap(2);

  void _snack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  // --- Build ---------------------------------------------------------------
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
              child: _buildHeader(),
            ),
            if (_usingFallback) _buildFallbackBadge(),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 0),
              child: BudgetSegmentedControl(
                selectedIndex: _topTab,
                labels: const ['달력', '거래내역', '소비 리포트'],
                onChanged: _onTabTap,
              ),
            ),
            const SizedBox(height: 10),
            Expanded(child: _buildBody()),
          ],
        ),
      ),
    );
  }

  Widget _buildBody() {
    // 아직 보여줄 게 아무것도 없을 때(첫 데이터 도착 전)만 전체 스피너.
    // 빠른 거래내역이 오면 곧바로 화면을 띄우고, 느린 대시보드는 달력 요약
    // 영역에서 개별적으로 로딩 표시한다.
    final hasAnyData = _dashboard != null || _monthTx != null || _usingFallback;
    if (_loading && !hasAnyData) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_errorMessage != null && !hasAnyData) {
      return _buildErrorView();
    }
    return PageView(
      controller: _pageController,
      onPageChanged: (index) => setState(() => _topTab = index),
      children: [
        _LedgerPage(
          onRefresh: () => _loadDashboard(silent: true),
          children: _buildCalendarView(),
        ),
        _LedgerPage(
          onRefresh: () => _loadDashboard(silent: true),
          children: _buildListView(),
        ),
        LedgerReportContent(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
          focusedMonth: _focusedMonth,
          refreshToken: _refreshToken,
          isActive: _topTab == 2,
          onMonthChanged: _onReportMonthChanged,
        ),
      ],
    );
  }

  Widget _buildErrorView() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.cloud_off_rounded,
              size: 40,
              color: AppTheme.textSecondary,
            ),
            const SizedBox(height: 12),
            Text(
              _errorMessage ?? '데이터를 불러오지 못했어요.',
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 14,
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () => _loadDashboard(),
              child: const Text('다시 시도'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFallbackBadge() {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 10, 16, 0),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(
        color: TossColors.orangeWeak,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: const [
          Icon(Icons.wifi_off_rounded, size: 14, color: AppTheme.orange),
          SizedBox(width: 6),
          Expanded(
            child: Text(
              '오프라인 데모 데이터 표시 중 · 서버 연결 시 실제 거래로 전환돼요',
              style: TextStyle(
                fontSize: 11.5,
                fontWeight: FontWeight.w600,
                color: AppTheme.orange,
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _onTabTap(int index) {
    if (_topTab == index) return;
    setState(() => _topTab = index);
    // 로딩 중에는 PageView 가 아직 트리에 없어 컨트롤러가 붙어있지 않다.
    // 이때 animateToPage 를 호출하면 'PageController is not attached to a
    // PageView' assertion 으로 크래시가 나므로, 붙어있을 때만 애니메이션하고
    // 아니면 다음 프레임(=PageView 가 그려진 뒤)에 해당 탭으로 점프한다.
    if (_pageController.hasClients) {
      _pageController.animateToPage(
        index,
        duration: const Duration(milliseconds: 240),
        curve: Curves.easeOutCubic,
      );
    } else {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _pageController.hasClients) {
          _pageController.jumpToPage(index);
        }
      });
    }
  }

  Widget _buildHeader() {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '가계부',
                style: AppTextStyles.screenTitle.copyWith(
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 2),
              Row(
                children: [
                  _MonthArrow(
                    icon: Icons.chevron_left,
                    onTap: () => _onChangeMonth(-1),
                  ),
                  Flexible(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 6),
                      child: Text(
                        '${monthLabel(_focusedMonth)} · AI 자동 기록',
                        overflow: TextOverflow.ellipsis,
                        style: AppTextStyles.meta.copyWith(
                          color: AppTheme.textSecondary,
                        ),
                      ),
                    ),
                  ),
                  _MonthArrow(
                    icon: Icons.chevron_right,
                    onTap: () => _onChangeMonth(1),
                  ),
                ],
              ),
            ],
          ),
        ),
        const AppTopActions(),
      ],
    );
  }

  Widget _buildMonthSummary(int monthExpense, int monthIncome) {
    return GlassCard(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
      onTap: _openReport,
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('$_month월에 쓴 돈', style: TossTypography.caption),
                const SizedBox(height: 4),
                TossCountUpText(
                  value: monthExpense,
                  formatter: (v) => '${LedgerStyles.formatWon(v)}원',
                  style: TossTypography.display.copyWith(fontSize: 26),
                ),
                const SizedBox(height: 6),
                Text.rich(
                  TextSpan(
                    style: TossTypography.caption,
                    children: [
                      const TextSpan(text: '수입 '),
                      TextSpan(
                        text: '${LedgerStyles.formatWon(monthIncome)}원',
                        style: const TextStyle(
                          fontWeight: FontWeight.w600,
                          color: TossColors.blue600,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const Icon(Icons.chevron_right, color: TossColors.grey400),
        ],
      ),
    );
  }

  String _briefingText(DayInfo info) {
    if (_usingApi) {
      final b = _dashboard?.selectedDate?['briefing'];
      if (b is Map) {
        final msg = b['message'] ?? b['title'];
        if (msg != null && msg.toString().trim().isNotEmpty) {
          return msg.toString();
        }
      }
      if (info.spend > 0) {
        return '$_month월 $_selectedDay일에는 총 ${LedgerStyles.formatWon(info.spend)}원을 사용했어요.';
      }
      return '$_month월 $_selectedDay일에는 기록된 소비가 없어요.';
    }
    if (info.spend > 0) {
      return '$_month월 $_selectedDay일에는 총 ${LedgerStyles.formatWon(info.spend)}원을 사용했어요. (오프라인 데모)';
    }
    return '$_month월 $_selectedDay일 · 오프라인 데모 데이터예요.';
  }

  List<Widget> _buildCalendarView() {
    // 대시보드(달력 요약·브리핑)가 아직 오지 않았고 오프라인 fallback 도 아니면,
    // mock 데이터를 잠깐 보여주는 대신 이 영역에만 가벼운 로더를 표시한다.
    // (거래내역 탭은 이미 실데이터로 즉시 사용 가능하다.)
    if (_dashboard == null && !_usingFallback) {
      // 대시보드 조회가 실패한 경우: 무한 로더 대신 오류 + 다시 시도.
      if (_errorMessage != null) {
        return [
          Padding(
            padding: const EdgeInsets.only(top: 60),
            child: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.cloud_off_rounded,
                      size: 36, color: AppTheme.textSecondary),
                  const SizedBox(height: 12),
                  Text(
                    _errorMessage ?? '이번 달 요약을 불러오지 못했어요.',
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                        fontSize: 13, color: AppTheme.textSecondary),
                  ),
                  const SizedBox(height: 14),
                  ElevatedButton(
                    onPressed: () => _loadDashboard(),
                    child: const Text('다시 시도'),
                  ),
                ],
              ),
            ),
          ),
        ];
      }
      return const [
        Padding(
          padding: EdgeInsets.only(top: 80),
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                CircularProgressIndicator(),
                SizedBox(height: 14),
                Text(
                  '이번 달 요약을 불러오는 중…',
                  style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                ),
              ],
            ),
          ),
        ),
      ];
    }

    final Map<int, DayInfo> dayData = _usingApi
        ? _dashboard!.dayInfos()
        : MockLedgerData.dayData;
    final info = dayData[_selectedDay] ?? const DayInfo();
    final txs = _usingApi
        ? _dashboard!.selectedDayTransactions()
        : (MockLedgerData.txByDay[_selectedDay] ?? const <LedgerTx>[]);
    final monthExpense = _usingApi
        ? _dashboard!.monthExpense
        : MockLedgerData.monthSpend;
    final monthIncome = _usingApi
        ? _dashboard!.monthIncome
        : MockLedgerData.monthIncome;

    final weekday = DateTime(_year, _month, _selectedDay).weekday % 7;
    final selectedLabel = '$_month월 $_selectedDay일 · ${_dow[weekday]}요일';
    final briefing = _briefingText(info);

    return [
      LedgerAiBriefingCard(
        title: 'AI 소비 브리핑',
        trailing: '$_month월 $_selectedDay일',
        body: briefing,
      ),
      const SizedBox(height: 14),
      GlassCard(
        padding: const EdgeInsets.fromLTRB(14, 16, 14, 12),
        child: LedgerCalendarGrid(
          selectedDay: _selectedDay,
          onSelect: (day) => _onSelectDate(DateTime(_year, _month, day)),
          year: _year,
          month: _month,
          dayData: dayData,
        ),
      ),
      const SizedBox(height: 14),
      _buildMonthSummary(monthExpense, monthIncome),
      const SizedBox(height: 14),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4),
        child: Row(
          children: [
            Text(
              selectedLabel,
              style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary,
              ),
            ),
            const Spacer(),
            Text(
              _dayTotalLabel(info),
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: _dayTotalColor(info),
              ),
            ),
          ],
        ),
      ),
      const SizedBox(height: 10),
      if (txs.isEmpty)
        const GlassCard(
          padding: EdgeInsets.symmetric(vertical: 24, horizontal: 16),
          child: Center(
            child: Text(
              '이 날은 기록된 소비가 없어요',
              style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
            ),
          ),
        )
      else
        GlassCard(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Column(
            children: [
              for (int i = 0; i < txs.length; i++)
                LedgerTransactionRow(
                  tx: txs[i],
                  showDivider: i != txs.length - 1,
                ),
            ],
          ),
        ),
      const SizedBox(height: 14),
      LedgerAutoDetectCard(
        pending: _pendingList,
        submitting: _submitting,
        onSimulate: _openNotificationComposer,
        onConfirm: _confirmPending,
        onEdit: _editPending,
        onRemove: _removePending,
      ),
      if (_budgetAlertMessage() case final msg?) ...[
        const SizedBox(height: 12),
        _BudgetAlertBanner(message: msg, onTap: _openReport),
      ],
    ];
  }

  /// 예산 경고 배너 문구. budget_alerts 데이터가 있을 때만 생성, 없으면 null(배너 숨김).
  /// API 모드는 dashboard budget_alerts, fallback 은 mock 예산 중 초과 항목을 사용한다.
  /// 하드코딩 고정 문구는 쓰지 않는다.
  String? _budgetAlertMessage() {
    if (_usingApi) {
      return _dashboard!.topBudgetAlertMessage();
    }
    // 오프라인 데모: mock 예산 중 초과(경고) 항목이 있을 때만.
    for (final b in MockLedgerData.reportBudgets) {
      if (b.over) return '${b.name} 예산의 ${b.pct}%를 사용했어요';
    }
    return null;
  }

  List<Widget> _buildListView() {
    if (_hasMonthTx) {
      // 선택 날짜에 한정하지 않고 '월 전체' 거래를 일자별 그룹으로 보여준다.
      // (결제 알림 자동 감지 카드는 목록 맨 아래로 배치한다.)
      final groups = _monthTx?.dayGroups() ?? const <LedgerDayGroup>[];
      final widgets = <Widget>[
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 2, 4, 8),
          child: Text(
            '$_month월 거래내역',
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
            ),
          ),
        ),
      ];

      if (groups.isEmpty) {
        widgets.add(
          const GlassCard(
            padding: EdgeInsets.symmetric(vertical: 24, horizontal: 16),
            child: Center(
              child: Text(
                '이 달은 기록된 거래가 없어요.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
              ),
            ),
          ),
        );
      } else {
        for (final g in groups) {
          widgets.add(_buildDayGroupHeader(g));
          widgets.add(
            GlassCard(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Column(
                children: [
                  for (int i = 0; i < g.transactions.length; i++)
                    LedgerTransactionRow(
                      tx: g.transactions[i],
                      showDivider: i != g.transactions.length - 1,
                    ),
                ],
              ),
            ),
          );
          widgets.add(const SizedBox(height: 12));
        }
      }

      // 결제 알림 자동 감지 카드: 맨 아래.
      widgets.add(const SizedBox(height: 6));
      widgets.add(_autoDetectCard());
      return widgets;
    }

    // 오프라인 fallback: mock 전체 월 거래를 일자별로 묶어 보여준다.
    final days = MockLedgerData.txByDay.keys.toList()
      ..sort((a, b) => b.compareTo(a));

    return [
      for (final day in days) ...[
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 6, 4, 8),
          child: Text(
            '$_month월 $day일',
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
            ),
          ),
        ),
        GlassCard(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Column(
            children: [
              for (int i = 0; i < MockLedgerData.txByDay[day]!.length; i++)
                LedgerTransactionRow(
                  tx: MockLedgerData.txByDay[day]![i],
                  showDivider: i != MockLedgerData.txByDay[day]!.length - 1,
                ),
            ],
          ),
        ),
        const SizedBox(height: 12),
      ],
      // 결제 알림 자동 감지 카드: 맨 아래.
      const SizedBox(height: 6),
      _autoDetectCard(),
    ];
  }

  /// 결제 알림 자동 감지 카드(거래내역 탭 하단 공용).
  Widget _autoDetectCard() {
    return LedgerAutoDetectCard(
      pending: _pendingList,
      submitting: _submitting,
      onSimulate: _openNotificationComposer,
      onConfirm: _confirmPending,
      onEdit: _editPending,
      onRemove: _removePending,
    );
  }

  /// 거래내역 탭의 일자별 그룹 헤더(날짜 + 우측 지출/수입 합계).
  Widget _buildDayGroupHeader(LedgerDayGroup g) {
    final String rightLabel;
    final Color rightColor;
    if (g.expenseTotal > 0) {
      rightLabel = '지출 ${LedgerStyles.formatWon(g.expenseTotal)}원';
      rightColor = AppTheme.textPrimary;
    } else if (g.incomeTotal > 0) {
      rightLabel = '수입 ${LedgerStyles.formatWon(g.incomeTotal)}원';
      rightColor = AppTheme.blue;
    } else {
      rightLabel = '';
      rightColor = AppTheme.textSecondary;
    }
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 6, 4, 8),
      child: Row(
        children: [
          Text(
            '${g.month}월 ${g.day}일',
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
            ),
          ),
          const Spacer(),
          if (rightLabel.isNotEmpty)
            Text(
              rightLabel,
              style: TextStyle(
                fontSize: 12.5,
                fontWeight: FontWeight.w600,
                color: rightColor,
              ),
            ),
        ],
      ),
    );
  }

  String _dayTotalLabel(DayInfo info) {
    if (info.spend > 0) return '지출 ${LedgerStyles.formatWon(info.spend)}원';
    if (info.income > 0) return '수입 ${LedgerStyles.formatWon(info.income)}원';
    return '소비 없음';
  }

  Color _dayTotalColor(DayInfo info) {
    if (info.spend > 0) return AppTheme.textPrimary;
    if (info.income > 0) return AppTheme.blue;
    return AppTheme.textSecondary;
  }
}

/// 거래 수정 다이얼로그 결과.
class _EditResult {
  final String? merchant;
  final int? amount;
  final String? category;
  final String? date;
  final String? time;
  final String? memo;

  const _EditResult({
    this.merchant,
    this.amount,
    this.category,
    this.date,
    this.time,
    this.memo,
  });
}

class _MonthArrow extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;

  const _MonthArrow({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Padding(
        padding: const EdgeInsets.all(2),
        child: Icon(icon, size: 18, color: AppTheme.textSecondary),
      ),
    );
  }
}

class _LedgerPage extends StatelessWidget {
  final List<Widget> children;
  final Future<void> Function()? onRefresh;

  const _LedgerPage({required this.children, this.onRefresh});

  @override
  Widget build(BuildContext context) {
    final list = ListView(
      physics: const AlwaysScrollableScrollPhysics(
        parent: BouncingScrollPhysics(),
      ),
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
      children: children,
    );
    if (onRefresh == null) return list;
    return RefreshIndicator(onRefresh: onRefresh!, child: list);
  }
}

class _BudgetAlertBanner extends StatelessWidget {
  final String message;
  final VoidCallback onTap;

  const _BudgetAlertBanner({required this.message, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        decoration: BoxDecoration(
          color: TossColors.orangeWeak,
          borderRadius: BorderRadius.circular(TossRadius.lg),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          children: [
            Container(
              width: 32,
              height: 32,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: AppTheme.orange.withValues(alpha: 0.16),
                borderRadius: BorderRadius.circular(9),
              ),
              child: const Icon(
                Icons.warning_amber_rounded,
                size: 18,
                color: AppTheme.orange,
              ),
            ),
            const SizedBox(width: 11),
            Expanded(
              child: Text(
                message,
                style: const TextStyle(
                  fontSize: 12.5,
                  height: 1.35,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary,
                ),
              ),
            ),
            Icon(
              Icons.chevron_right,
              size: 18,
              color: AppTheme.orange.withValues(alpha: 0.7),
            ),
          ],
        ),
      ),
    );
  }
}
