import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_foreground_task/flutter_foreground_task.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'screens/add_item_choice_screen.dart';
import 'screens/ai_chat_screen.dart';
import 'screens/todo_screen.dart';
import 'screens/calendar_screen.dart';
import 'screens/widget_dashboard_screen.dart';
import 'screens/ledger_screen.dart';
import 'screens/my_page_screen.dart';
import 'screens/image_verification_screen.dart';
import 'data/dashboard_navigation.dart';
import 'services/briefing_scheduler_service.dart';
import 'services/preference_store.dart';
import 'services/schedule_api.dart';
import 'theme/app_theme.dart';
import 'widgets/draggable_assistant_fab.dart';

/// 알림 탭 시 화면 이동에 쓰는 루트 네비게이터 키(전화형 알림 화면으로 이동).
final GlobalKey<NavigatorState> rootNavigatorKey = GlobalKey<NavigatorState>();

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  // 포그라운드 서비스(음성 대기)와 UI 격리자 간 통신 포트 초기화.
  FlutterForegroundTask.initCommunicationPort();
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
      await briefingSchedulerService.scheduleDailyBriefing(
        preferenceStore.briefingTime,
      );
    }
    // 일정 사전(리드타임) 알림: 서버에서 일정을 받아 앞으로의 일정에 미리 예약.
    // 오프라인/실패해도 앱 흐름에 영향 없음.
    try {
      final schedules = await scheduleApi.list();
      await briefingSchedulerService.syncScheduleAlerts(
        schedules,
        leadMinutes: preferenceStore.alertLeadMinutes,
      );
    } catch (e) {
      debugPrint('[main] schedule alert sync failed: $e');
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
      title: 'AI 비서',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      // CupertinoDatePicker(시간 휠 선택) 등 Cupertino 위젯이 필요로 함.
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      supportedLocales: const [Locale('ko', 'KR')],
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
            onLongPress: () {
              Navigator.of(context, rootNavigator: true).push(
                MaterialPageRoute(
                  builder: (_) => const AiChatScreen(autoStartVoice: true),
                ),
              );
            },
            actions: [
              AssistantMenuAction(
                icon: Icons.photo_camera_outlined,
                tooltip: '카메라',
                color: AppTheme.teal,
                onTap: () {
                  Navigator.of(context, rootNavigator: true).push(
                    MaterialPageRoute(
                      builder: (_) => const ImageVerificationScreen(),
                    ),
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
      decoration: const BoxDecoration(
        color: TossColors.bgWhite,
        boxShadow: [
          BoxShadow(
            color: Color(0x0A191F28),
            blurRadius: 16,
            offset: Offset(0, -2),
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
