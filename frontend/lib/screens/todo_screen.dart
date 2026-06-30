import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';

class TodoScreen extends StatefulWidget {
  const TodoScreen({super.key});

  @override
  State<TodoScreen> createState() => _TodoScreenState();
}

class _TodoScreenState extends State<TodoScreen> {
  int _tabIndex = 0;

  static const _todayTodos = [
    _TodoItem(
      time: '09:30',
      title: '발표 자료 최종 확인',
      priority: '높음',
      priorityColor: AppTheme.red,
      deadline: '13:00 마감 · 30분 전',
      isDone: false,
      supplies: ['노트북', '충전기', '발표 자료', '레이저 포인터'],
      doneSupplies: ['노트북', '충전기'],
    ),
    _TodoItem(
      time: '11:00',
      title: '병원 예약 확인 전화',
      priority: '보통',
      priorityColor: AppTheme.orange,
      deadline: null,
      isDone: false,
      supplies: [],
      doneSupplies: [],
    ),
    _TodoItem(
      time: '14:00',
      title: 'AI 스터디 노트 정리',
      priority: '보통',
      priorityColor: AppTheme.orange,
      deadline: null,
      isDone: false,
      supplies: [],
      doneSupplies: [],
    ),
    _TodoItem(
      time: '19:00',
      title: '저녁 약속 준비',
      priority: '낮음',
      priorityColor: AppTheme.textSecondary,
      deadline: null,
      isDone: false,
      supplies: [],
      doneSupplies: [],
    ),
  ];

  static const _doneTodos = [
    _TodoItem(
      time: '08:00',
      title: '아침 운동',
      priority: '보통',
      priorityColor: AppTheme.orange,
      deadline: null,
      isDone: true,
      supplies: [],
      doneSupplies: [],
    ),
    _TodoItem(
      time: '09:00',
      title: '이메일 확인 및 답장',
      priority: '높음',
      priorityColor: AppTheme.red,
      deadline: null,
      isDone: true,
      supplies: [],
      doneSupplies: [],
    ),
    _TodoItem(
      time: '09:15',
      title: '프로젝트 회의 준비',
      priority: '높음',
      priorityColor: AppTheme.red,
      deadline: null,
      isDone: true,
      supplies: [],
      doneSupplies: [],
    ),
  ];

  int _expandedIndex = 0;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            _buildTabBar(),
            _buildProgressCard(),
            Expanded(
              child: Stack(
                children: [
                  IndexedStack(
                    index: _tabIndex,
                    children: [
                      _buildTodoList(_todayTodos, showExpand: true),
                      _buildUpcomingList(),
                      _buildTodoList(_doneTodos, isDoneTab: true),
                    ],
                  ),
                  // 고정 하단 버튼
                  Positioned(
                    left: 16, right: 16, bottom: 16,
                    child: GestureDetector(
                      onTap: () {},
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 15),
                        decoration: BoxDecoration(
                          color: AppTheme.blue,
                          borderRadius: BorderRadius.circular(16),
                          boxShadow: [
                            BoxShadow(
                              color: AppTheme.blue.withOpacity(0.35),
                              blurRadius: 14,
                              offset: const Offset(0, 5),
                            ),
                          ],
                        ),
                        child: const Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.add, color: Colors.white, size: 18),
                            SizedBox(width: 6),
                            Text(
                              '할 일 추가',
                              style: TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w700,
                                color: Colors.white,
                                letterSpacing: -0.2,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '할 일',
                style: TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                  letterSpacing: -0.5,
                ),
              ),
              Text(
                '6월 29일 일요일',
                style: const TextStyle(
                    fontSize: 13, color: AppTheme.textSecondary),
              ),
            ],
          ),
          GestureDetector(
            onTap: () {},
            child: Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.7),
                shape: BoxShape.circle,
                border: Border.all(color: AppTheme.separator),
              ),
              child:
                  const Icon(Icons.tune, color: AppTheme.textPrimary, size: 20),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTabBar() {
    final labels = ['오늘 4', '예정 7', '완료 12'];
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.55),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.separator.withOpacity(0.6)),
        ),
        padding: const EdgeInsets.all(3),
        child: Row(
          children: List.generate(labels.length, (i) {
            final isActive = i == _tabIndex;
            return Expanded(
              child: GestureDetector(
                onTap: () => setState(() => _tabIndex = i),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  padding: const EdgeInsets.symmetric(vertical: 9),
                  decoration: BoxDecoration(
                    color: isActive ? Colors.white : Colors.transparent,
                    borderRadius: BorderRadius.circular(10),
                    boxShadow: isActive
                        ? [BoxShadow(color: Colors.black.withOpacity(0.07), blurRadius: 6, offset: const Offset(0, 2))]
                        : null,
                  ),
                  child: Text(
                    labels[i],
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: isActive ? FontWeight.w600 : FontWeight.w400,
                      color: isActive ? AppTheme.textPrimary : AppTheme.textSecondary,
                    ),
                  ),
                ),
              ),
            );
          }),
        ),
      ),
    );
  }

  Widget _buildProgressCard() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
      child: GlassCard(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  '오늘 진행률',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const Text(
                  '68%',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.blue,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: 0.68,
                backgroundColor: AppTheme.separator,
                valueColor: const AlwaysStoppedAnimation(AppTheme.blue),
                minHeight: 6,
              ),
            ),
            const SizedBox(height: 6),
            const Text(
              '완료 3개 · 남은 할 일 4개',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTodoList(List<_TodoItem> todos,
      {bool isDoneTab = false, bool showExpand = false}) {
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 80),
      physics: const BouncingScrollPhysics(),
      itemCount: todos.length,
      itemBuilder: (context, i) {
        final todo = todos[i];
        final isExpanded = showExpand && i == _expandedIndex;
        return Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: GestureDetector(
            onTap: () {
              if (showExpand) setState(() => _expandedIndex = i);
            },
            child: GlassCard(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(
                        isDoneTab
                            ? Icons.check_circle
                            : Icons.radio_button_unchecked,
                        color: isDoneTab
                            ? AppTheme.green
                            : AppTheme.textSecondary,
                        size: 22,
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              todo.title,
                              style: TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.w600,
                                color: isDoneTab
                                    ? AppTheme.textSecondary
                                    : AppTheme.textPrimary,
                                decoration: isDoneTab
                                    ? TextDecoration.lineThrough
                                    : null,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Row(
                              children: [
                                Text(
                                  todo.time,
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: AppTheme.textSecondary,
                                  ),
                                ),
                                if (todo.deadline != null) ...[
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      '· ${todo.deadline}',
                                      style: const TextStyle(
                                        fontSize: 12,
                                        color: AppTheme.red,
                                      ),
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ],
                              ],
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 8),
                      PillBadge(
                        label: todo.priority,
                        color: todo.priorityColor,
                      ),
                    ],
                  ),
                  if (isExpanded && todo.supplies.isNotEmpty) ...[
                    const SizedBox(height: 10),
                    const Divider(color: AppTheme.separator, height: 1),
                    const SizedBox(height: 10),
                    const Row(
                      children: [
                        Icon(Icons.backpack_outlined,
                            size: 14, color: AppTheme.textSecondary),
                        SizedBox(width: 4),
                        Text(
                          '준비물',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    ...todo.supplies.map((s) => Padding(
                          padding: const EdgeInsets.only(bottom: 5),
                          child: Row(
                            children: [
                              Icon(
                                todo.doneSupplies.contains(s)
                                    ? Icons.check_circle
                                    : Icons.radio_button_unchecked,
                                size: 16,
                                color: todo.doneSupplies.contains(s)
                                    ? AppTheme.green
                                    : AppTheme.textSecondary,
                              ),
                              const SizedBox(width: 8),
                              Text(
                                s,
                                style: TextStyle(
                                  fontSize: 13,
                                  color: todo.doneSupplies.contains(s)
                                      ? AppTheme.textSecondary
                                      : AppTheme.textPrimary,
                                  decoration:
                                      todo.doneSupplies.contains(s)
                                          ? TextDecoration.lineThrough
                                          : null,
                                ),
                              ),
                            ],
                          ),
                        )),
                    const SizedBox(height: 4),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        TextButton.icon(
                          onPressed: () {},
                          icon: const Icon(Icons.flag_outlined, size: 14),
                          label: const Text('우선순위',
                              style: TextStyle(fontSize: 12)),
                          style: TextButton.styleFrom(
                              foregroundColor: AppTheme.textSecondary,
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 8)),
                        ),
                        TextButton.icon(
                          onPressed: () {},
                          icon: const Icon(Icons.notifications_outlined,
                              size: 14),
                          label: const Text('알림',
                              style: TextStyle(fontSize: 12)),
                          style: TextButton.styleFrom(
                              foregroundColor: AppTheme.textSecondary,
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 8)),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildUpcomingList() {
    final items = [
      ('7월 1일', '치과 정기 검진', '10:00', AppTheme.teal),
      ('7월 2일', '프로젝트 발표 준비', '14:00', AppTheme.blue),
      ('7월 3일', '미용실 예약', '19:00', AppTheme.purple),
      ('7월 4일', '가족 모임', '12:00', AppTheme.orange),
      ('7월 5일', '독서 클럽', '15:00', AppTheme.green),
      ('7월 7일', '월간 회고', '20:00', AppTheme.red),
      ('7월 10일', '생일 파티', '18:00', AppTheme.orange),
    ];
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 80),
      physics: const BouncingScrollPhysics(),
      itemCount: items.length,
      itemBuilder: (context, i) {
        final (date, title, time, color) = items[i];
        return Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: GlassCard(
            padding: const EdgeInsets.all(14),
            child: Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(Icons.event_outlined, color: color, size: 22),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title,
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.textPrimary,
                          )),
                      const SizedBox(height: 3),
                      Text('$date · $time',
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppTheme.textSecondary,
                          )),
                    ],
                  ),
                ),
                Icon(Icons.radio_button_unchecked,
                    color: AppTheme.textSecondary, size: 20),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _TodoItem {
  final String time;
  final String title;
  final String priority;
  final Color priorityColor;
  final String? deadline;
  final bool isDone;
  final List<String> supplies;
  final List<String> doneSupplies;

  const _TodoItem({
    required this.time,
    required this.title,
    required this.priority,
    required this.priorityColor,
    required this.deadline,
    required this.isDone,
    required this.supplies,
    required this.doneSupplies,
  });
}
