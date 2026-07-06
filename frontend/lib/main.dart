import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'screens/add_item_choice_screen.dart';
import 'screens/ai_chat_screen.dart';
import 'screens/todo_screen.dart';
import 'screens/calendar_screen.dart';
import 'screens/widget_dashboard_screen.dart';
import 'screens/ledger_screen.dart';
import 'screens/my_page_screen.dart';
import 'data/dashboard_navigation.dart';
import 'services/briefing_scheduler_service.dart';
import 'services/preference_store.dart';
import 'theme/app_theme.dart';
import 'widgets/draggable_assistant_fab.dart';

/// 알림 탭 시 화면 이동에 쓰는 루트 네비게이터 키(전화형 알림 화면으로 이동).
final GlobalKey<NavigatorState> rootNavigatorKey = GlobalKey<NavigatorState>();

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.dark,
    ),
  );
  // AI 음성 스타일 설정을 미리 불러와 캐시(비차단; 실패해도 기본값으로 동작).
  // 로드가 끝나면 자동 브리핑 시각이 설정돼 있는 경우 로컬 알림을 예약한다.
  preferenceStore.ensureLoaded().then((_) async {
    await briefingSchedulerService.init(rootNavigatorKey);
    if (preferenceStore.briefingTime.isNotEmpty) {
      await briefingSchedulerService.scheduleDailyBriefing(preferenceStore.briefingTime);
    }
  });
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      navigatorKey: rootNavigatorKey,
      title: '나의 AI 비서',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      home: const MainNavigator(),
    );
  }
}

class MainNavigator extends StatefulWidget {
  final int initialIndex;

  const MainNavigator({super.key, this.initialIndex = 0});

  @override
  State<MainNavigator> createState() => _MainNavigatorState();
}

class _MainNavigatorState extends State<MainNavigator> {
  late int _currentIndex;
  late Set<int> _visitedIndexes;

  final List<Widget> _screens = const [
    CalendarScreen(),
    TodoScreen(),
    WidgetDashboardScreen(),
    LedgerScreen(),
    MyPageScreen(),
  ];

  @override
  void initState() {
    super.initState();
    final lastIndex = _screens.length - 1;
    _currentIndex = widget.initialIndex.clamp(0, lastIndex);
    _visitedIndexes = {_currentIndex};
    // 위젯 대시보드에서 위젯을 누르면 해당 하단 탭으로 전환.
    requestedTabIndex.addListener(_handleTabRequest);
  }

  @override
  void dispose() {
    requestedTabIndex.removeListener(_handleTabRequest);
    super.dispose();
  }

  void _handleTabRequest() {
    final index = requestedTabIndex.value;
    if (index < 0) return;
    final clamped = index.clamp(0, _screens.length - 1);
    setState(() {
      _currentIndex = clamped;
      _visitedIndexes.add(clamped);
    });
    clearTabRequest();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      body: Stack(
        children: [
          IndexedStack(
            index: _currentIndex,
            children: List.generate(
              _screens.length,
              (i) => _visitedIndexes.contains(i)
                  ? _screens[i]
                  : const SizedBox.shrink(),
            ),
          ),
          DraggableAssistantFab(
            actions: [
              AssistantMenuAction(
                icon: Icons.photo_camera_outlined,
                tooltip: '카메라',
                color: AppTheme.teal,
                onTap: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('이미지 인식 기능은 준비 중입니다.')),
                  );
                },
              ),
              AssistantMenuAction(
                icon: Icons.auto_awesome,
                tooltip: 'AI',
                color: AppTheme.purple,
                onTap: () {
                  Navigator.of(context, rootNavigator: true).push(
                    MaterialPageRoute(builder: (_) => const AiChatScreen()),
                  );
                },
              ),
              AssistantMenuAction(
                icon: Icons.add,
                tooltip: '일정/할 일 추가',
                color: AppTheme.blue,
                onTap: () {
                  Navigator.of(context, rootNavigator: true).push(
                    MaterialPageRoute(
                      builder: (_) => const AddItemChoiceScreen(),
                    ),
                  );
                },
              ),
            ],
          ),
        ],
      ),
      bottomNavigationBar: _BottomNav(
        currentIndex: _currentIndex,
        onTap: (i) => setState(() {
          _currentIndex = i;
          _visitedIndexes.add(i);
        }),
      ),
    );
  }
}

class _BottomNav extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onTap;

  const _BottomNav({required this.currentIndex, required this.onTap});

  static const _items = [
    (Icons.calendar_month_outlined, Icons.calendar_month, '캘린더'),
    (Icons.checklist_outlined, Icons.checklist, '할 일'),
    (Icons.widgets_outlined, Icons.widgets, '위젯'),
    (
      Icons.account_balance_wallet_outlined,
      Icons.account_balance_wallet,
      '가계부',
    ),
    (Icons.person_outline, Icons.person, '마이페이지'),
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.9),
        border: Border(top: BorderSide(color: AppTheme.separator, width: 0.5)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 12,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 56,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: List.generate(_items.length, (i) {
              final (icon, activeIcon, label) = _items[i];
              final isActive = i == currentIndex;
              return GestureDetector(
                onTap: () => onTap(i),
                behavior: HitTestBehavior.opaque,
                child: SizedBox(
                  width: 64,
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        isActive ? activeIcon : icon,
                        size: 24,
                        color: isActive
                            ? AppTheme.blue
                            : AppTheme.textSecondary,
                      ),
                      const SizedBox(height: 3),
                      Text(
                        label,
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: isActive
                              ? FontWeight.w600
                              : FontWeight.w400,
                          color: isActive
                              ? AppTheme.blue
                              : AppTheme.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            }),
          ),
        ),
      ),
    );
  }
}
