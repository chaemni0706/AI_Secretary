import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'screens/add_item_choice_screen.dart';
import 'screens/ai_chat_screen.dart';
import 'screens/todo_screen.dart';
import 'screens/calendar_screen.dart';
import 'screens/widget_screen.dart';
import 'screens/ledger_screen.dart';
import 'screens/my_page_screen.dart';
import 'theme/app_theme.dart';
import 'widgets/draggable_assistant_fab.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.dark,
    ),
  );
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
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
    WidgetScreen(),
    LedgerScreen(),
    MyPageScreen(),
  ];

  @override
  void initState() {
    super.initState();
    final lastIndex = _screens.length - 1;
    _currentIndex = widget.initialIndex.clamp(0, lastIndex);
    _visitedIndexes = {_currentIndex};
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
