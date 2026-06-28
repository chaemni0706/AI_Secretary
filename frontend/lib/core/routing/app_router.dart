import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../features/home/home_shell.dart';
import '../../features/today/today_screen.dart';
import '../../features/ai_chat/ai_chat_screen.dart';
import '../../features/calendar/calendar_screen.dart';
import '../../features/todo/todo_screen.dart';
import '../../features/more/more_screen.dart';
import '../../features/reservation_candidate/reservation_candidate_screen.dart';
import '../../features/reservation_message/reservation_message_screen.dart';
import 'app_routes.dart';

/// go_router 정의.
/// - StatefulShellRoute.indexedStack: 하단 탭 5개 관리
/// - 상세 화면 2개는 shell 밖에 둬서 BottomBar가 보이지 않게 처리
class AppRouter {
  AppRouter._();

  static final GoRouter router = GoRouter(
    initialLocation: AppRoutes.today,
    routes: [
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) {
          return HomeShell(navigationShell: navigationShell);
        },
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.today,
                builder: (context, state) => const TodayScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.aiChat,
                builder: (context, state) => const AiChatScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.calendar,
                builder: (context, state) => const CalendarScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.todo,
                builder: (context, state) => const TodoScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.more,
                builder: (context, state) => const MoreScreen(),
              ),
            ],
          ),
        ],
      ),

      GoRoute(
        path: AppRoutes.reservationCandidate,
        builder: (context, state) => const ReservationCandidateScreen(),
      ),
      GoRoute(
        path: AppRoutes.reservationMessage,
        builder: (context, state) => const ReservationMessageScreen(),
      ),
    ],
    errorBuilder: (context, state) => Scaffold(
      body: Center(
        child: Text('경로를 찾을 수 없습니다: ${state.uri}'),
      ),
    ),
  );
}