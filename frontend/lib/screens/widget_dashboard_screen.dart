import 'package:flutter/material.dart';
import '../data/dashboard_navigation.dart';
import '../data/widget_catalog.dart';
import '../data/widget_layout_store.dart';
import '../models/dashboard_model.dart';
import '../models/dashboard_widget_model.dart';
import '../models/schedule_model.dart';
import '../models/todo_model.dart';
import '../services/api_client.dart';
import '../services/dashboard_api.dart';
import '../services/schedule_api.dart';
import '../services/todo_api.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../widgets/dashboard_widgets/add_widget_sheet.dart';
import '../widgets/dashboard_widgets/ai_recommendation_widget.dart';
import '../widgets/dashboard_widgets/briefing_widget.dart';
import '../widgets/dashboard_widgets/budget_widget.dart';
import '../widgets/dashboard_widgets/dashboard_widget_card.dart';
import '../widgets/dashboard_widgets/monthly_calendar_widget.dart';
import '../widgets/dashboard_widgets/ocr_verification_widget.dart';
import '../widgets/dashboard_widgets/preparation_widget.dart';
import '../widgets/dashboard_widgets/reservation_candidate_widget.dart';
import '../widgets/dashboard_widgets/spending_analysis_widget.dart';
import '../widgets/dashboard_widgets/todo_dashboard_widget.dart';
import '../widgets/dashboard_widgets/weather_widget.dart';
import '../widgets/dashboard_widgets/weekly_calendar_widget.dart';
import 'ai_chat_screen.dart';
import 'booking_recommend_screen.dart';
import 'briefing_screen.dart';
import 'dashboard_stub_screens.dart';
import 'ledger_report_screen.dart';
import 'weather_detail_screen.dart';

/// 위젯 탭 — 사용자가 직접 구성하는 AI 대시보드.
/// 편집 모드에서 위젯을 드래그로 재배치 / 크기 변경 / 삭제 / 추가할 수 있다.
/// 레이아웃은 shared_preferences 에 저장되어 앱 재시작 후에도 유지된다.
class WidgetDashboardScreen extends StatefulWidget {
  const WidgetDashboardScreen({super.key});

  @override
  State<WidgetDashboardScreen> createState() => _WidgetDashboardScreenState();
}

class _WidgetDashboardScreenState extends State<WidgetDashboardScreen> {
  static const double _gap = 12;

  List<DashboardWidgetItem> _items = [];
  bool _editing = false;
  bool _layoutLoaded = false;

  // 실데이터 (기존 service + dashboardRefresh 패턴 재사용).
  List<TodoModel> _todos = [];
  List<ScheduleModel> _schedules = [];
  DashboardData? _dashboard;
  bool _dataLoading = false;

  @override
  void initState() {
    super.initState();
    _loadLayout();
    dashboardRefresh.addListener(_loadData);
  }

  @override
  void dispose() {
    dashboardRefresh.removeListener(_loadData);
    super.dispose();
  }

  Future<void> _loadLayout() async {
    final items = await widgetLayoutStore.load();
    if (!mounted) return;
    setState(() {
      _items = items;
      _layoutLoaded = true;
    });
    _loadData();
  }

  /// 대시보드에 존재하는 위젯 종류에 맞춰 필요한 실데이터만 불러온다.
  Future<void> _loadData() async {
    final types = _items.map((e) => e.type).toSet();
    final needTodos = types.contains(DashboardWidgetType.todo);
    final needSchedules = types.contains(DashboardWidgetType.monthlyCalendar) ||
        types.contains(DashboardWidgetType.weeklyCalendar);
    final needDashboard = types.contains(DashboardWidgetType.briefing);
    if (!needTodos && !needSchedules && !needDashboard) return;

    if (mounted) setState(() => _dataLoading = true);

    if (needTodos) {
      try {
        final todos = await todoApi.list();
        if (mounted) _todos = todos;
      } on ApiException catch (_) {
        // 백엔드 미연결 시 빈 목록으로 graceful degrade.
      } catch (_) {}
    }
    if (needSchedules) {
      try {
        final schedules = await scheduleApi.list();
        if (mounted) _schedules = schedules;
      } on ApiException catch (_) {
      } catch (_) {}
    }
    if (needDashboard) {
      try {
        final dash = await dashboardApi.getTodayDashboard();
        if (mounted) _dashboard = dash;
      } on ApiException catch (_) {
      } catch (_) {}
    }

    if (mounted) setState(() => _dataLoading = false);
  }

  void _persist() => widgetLayoutStore.save(_items);

  // ── 편집 동작 ──────────────────────────────────────────────
  void _enterEdit() {
    if (!_editing) setState(() => _editing = true);
  }

  void _finishEdit() {
    setState(() => _editing = false);
    _persist();
  }

  void _reorder(int from, int to) {
    if (from == to) return;
    setState(() {
      final item = _items.removeAt(from);
      var insert = to;
      if (from < to) insert -= 1;
      _items.insert(insert.clamp(0, _items.length), item);
    });
    _persist();
  }

  void _delete(String id) {
    setState(() => _items.removeWhere((e) => e.id == id));
    _persist();
  }

  void _resize(String id, WidgetSize size) {
    setState(() {
      final i = _items.indexWhere((e) => e.id == id);
      if (i >= 0) _items[i] = _items[i].copyWith(size: size);
    });
    _persist();
  }

  Future<void> _addWidget() async {
    final result = await showAddWidgetSheet(context);
    if (result == null || !mounted) return;
    setState(() {
      _items.add(DashboardWidgetItem(
        id: widgetLayoutStore.newId(result.type),
        type: result.type,
        size: result.size,
      ));
      _editing = true;
    });
    _persist();
    _loadData();
  }

  // ── 위젯 클릭 → 해당 기능 화면으로 이동 ─────────────────────
  void _onWidgetTap(DashboardWidgetType type) {
    switch (type) {
      case DashboardWidgetType.briefing:
        _push(const BriefingScreen());
      case DashboardWidgetType.monthlyCalendar:
      case DashboardWidgetType.weeklyCalendar:
        requestTab(DashboardTabIndex.calendar);
      case DashboardWidgetType.weather:
        _push(const WeatherDetailScreen());
      case DashboardWidgetType.budget:
        requestTab(DashboardTabIndex.ledger);
      case DashboardWidgetType.spendingAnalysis:
        _push(const LedgerReportScreen());
      case DashboardWidgetType.preparation:
        _push(const PreparationDetailScreen());
      case DashboardWidgetType.todo:
        requestTab(DashboardTabIndex.todo);
      case DashboardWidgetType.ocr:
        _push(const OcrVerificationDetailScreen());
      case DashboardWidgetType.aiRecommendation:
        _push(const AiChatScreen());
      case DashboardWidgetType.reservation:
        _push(const BookingRecommendScreen());
    }
  }

  void _push(Widget screen) {
    Navigator.of(context, rootNavigator: true)
        .push(MaterialPageRoute(builder: (_) => screen));
  }

  void _snack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            Expanded(
              child: !_layoutLoaded
                  ? const Center(child: CircularProgressIndicator())
                  : _buildBody(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 16, 8),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '위젯',
                  style: AppTextStyles.screenTitle.copyWith(
                    color: AppTheme.textPrimary,
                  ),
                ),
                Text(
                  _editing ? '길게 눌러 이동 · 크기/삭제 편집' : '나만의 AI 대시보드',
                  style: AppTextStyles.meta.copyWith(
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          _EditToggleButton(
            editing: _editing,
            onTap: _editing ? _finishEdit : _enterEdit,
          ),
        ],
      ),
    );
  }

  Widget _buildBody() {
    if (_items.isEmpty) return _buildEmpty();

    return LayoutBuilder(
      builder: (context, constraints) {
        final totalW = constraints.maxWidth - 32; // 좌우 패딩 16
        final cellW = (totalW - _gap) / 2;
        final rows = _packRows(_items);

        return ListView(
          physics: const AlwaysScrollableScrollPhysics(
            parent: BouncingScrollPhysics(),
          ),
          padding: const EdgeInsets.fromLTRB(16, 6, 16, 28),
          children: [
            for (final row in rows) ...[
              _buildRow(row, cellW),
              const SizedBox(height: _gap),
            ],
            if (_editing) _buildEditFooter(),
          ],
        );
      },
    );
  }

  /// 순서 리스트를 2열 그리드 행으로 패킹. small 2개는 한 행, medium/large 는 전체폭.
  List<List<DashboardWidgetItem>> _packRows(List<DashboardWidgetItem> items) {
    final rows = <List<DashboardWidgetItem>>[];
    int i = 0;
    while (i < items.length) {
      final item = items[i];
      if (item.size == WidgetSize.small) {
        if (i + 1 < items.length && items[i + 1].size == WidgetSize.small) {
          rows.add([item, items[i + 1]]);
          i += 2;
        } else {
          rows.add([item]);
          i += 1;
        }
      } else {
        rows.add([item]);
        i += 1;
      }
    }
    return rows;
  }

  Widget _buildRow(List<DashboardWidgetItem> row, double cellW) {
    final fullW = cellW * 2 + _gap;
    if (row.length == 2) {
      return Row(
        children: [
          _buildSlot(row[0], cellW, cellW),
          const SizedBox(width: _gap),
          _buildSlot(row[1], cellW, cellW),
        ],
      );
    }
    final item = row.first;
    if (item.size == WidgetSize.small) {
      // 홀로 남은 small 은 왼쪽에 배치.
      return Row(
        children: [
          _buildSlot(item, cellW, cellW),
          const SizedBox(width: _gap),
          SizedBox(width: cellW),
        ],
      );
    }
    final height = item.size == WidgetSize.large ? cellW * 2 + _gap : cellW;
    return _buildSlot(item, fullW, height);
  }

  Widget _buildSlot(DashboardWidgetItem item, double width, double height) {
    final index = _items.indexOf(item);
    final spec = WidgetCatalog.of(item.type);
    final card = DashboardWidgetCard(
      accent: spec.accent,
      editing: _editing,
      currentSize: item.size,
      supportedSizes: spec.supportedSizes,
      onTap: () => _onWidgetTap(item.type),
      onDelete: () => _delete(item.id),
      onResize: (s) => _resize(item.id, s),
      child: _buildContent(item),
    );

    final sized = SizedBox(width: width, height: height, child: card);

    if (!_editing) {
      return GestureDetector(
        onLongPress: _enterEdit,
        child: sized,
      );
    }

    // 편집 모드: 길게 눌러 드래그로 순서 변경.
    return DragTarget<int>(
      onWillAcceptWithDetails: (d) => d.data != index,
      onAcceptWithDetails: (d) => _reorder(d.data, index),
      builder: (context, candidate, rejected) {
        final highlighted = candidate.isNotEmpty;
        return LongPressDraggable<int>(
          data: index,
          feedback: Material(
            color: Colors.transparent,
            child: Opacity(
              opacity: 0.92,
              child: SizedBox(width: width, height: height, child: card),
            ),
          ),
          childWhenDragging: Opacity(
            opacity: 0.3,
            child: sized,
          ),
          child: AnimatedScale(
            scale: highlighted ? 1.03 : 1.0,
            duration: const Duration(milliseconds: 150),
            child: sized,
          ),
        );
      },
    );
  }

  Widget _buildContent(DashboardWidgetItem item) {
    switch (item.type) {
      case DashboardWidgetType.briefing:
        return BriefingWidget(data: _dashboard, loading: _dataLoading);
      case DashboardWidgetType.monthlyCalendar:
        return MonthlyCalendarWidget(schedules: _schedules);
      case DashboardWidgetType.weeklyCalendar:
        return WeeklyCalendarWidget(schedules: _schedules);
      case DashboardWidgetType.weather:
        return WeatherWidget(size: item.size);
      case DashboardWidgetType.budget:
        return const BudgetWidget();
      case DashboardWidgetType.spendingAnalysis:
        return const SpendingAnalysisWidget();
      case DashboardWidgetType.preparation:
        return const PreparationWidget();
      case DashboardWidgetType.todo:
        return TodoDashboardWidget(
          todos: _todos,
          size: item.size,
          loading: _dataLoading,
        );
      case DashboardWidgetType.ocr:
        return const OcrVerificationWidget();
      case DashboardWidgetType.aiRecommendation:
        return const AiRecommendationWidget();
      case DashboardWidgetType.reservation:
        return const ReservationCandidateWidget();
    }
  }

  Widget _buildEditFooter() {
    return Column(
      children: [
        _AddWidgetButton(onTap: _addWidget),
        const SizedBox(height: 12),
        SizedBox(
          width: double.infinity,
          child: FilledButton(
            onPressed: _finishEdit,
            style: FilledButton.styleFrom(
              backgroundColor: AppTheme.blue,
              minimumSize: const Size.fromHeight(48),
            ),
            child: const Text('편집 완료'),
          ),
        ),
      ],
    );
  }

  Widget _buildEmpty() {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 40, 16, 28),
      children: [
        Icon(
          Icons.dashboard_customize_outlined,
          size: 46,
          color: AppTheme.textSecondary.withValues(alpha: 0.5),
        ),
        const SizedBox(height: 12),
        const Text(
          '표시할 위젯이 없어요',
          textAlign: TextAlign.center,
          style: TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w700,
            color: AppTheme.textPrimary,
          ),
        ),
        const SizedBox(height: 4),
        const Text(
          '아래 버튼으로 나만의 대시보드를 구성해보세요.',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
        ),
        const SizedBox(height: 20),
        _AddWidgetButton(onTap: _addWidget),
      ],
    );
  }
}

class _EditToggleButton extends StatelessWidget {
  final bool editing;
  final VoidCallback onTap;

  const _EditToggleButton({required this.editing, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
        decoration: BoxDecoration(
          color: editing ? AppTheme.blue : Colors.white.withValues(alpha: 0.72),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: editing
                ? AppTheme.blue
                : AppTheme.separator.withValues(alpha: 0.8),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.05),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              editing ? Icons.check : Icons.tune,
              size: 16,
              color: editing ? Colors.white : AppTheme.textPrimary,
            ),
            const SizedBox(width: 5),
            Text(
              editing ? '완료' : '편집',
              style: TextStyle(
                fontSize: 13.5,
                fontWeight: FontWeight.w700,
                color: editing ? Colors.white : AppTheme.textPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _AddWidgetButton extends StatelessWidget {
  final VoidCallback onTap;

  const _AddWidgetButton({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 16),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: AppTheme.blue.withValues(alpha: 0.06),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(
            color: AppTheme.blue.withValues(alpha: 0.35),
            width: 1.2,
          ),
        ),
        child: const Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.add, size: 20, color: AppTheme.blue),
            SizedBox(width: 6),
            Text(
              '위젯 추가',
              style: TextStyle(
                fontSize: 14.5,
                fontWeight: FontWeight.w700,
                color: AppTheme.blue,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
