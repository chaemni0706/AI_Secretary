import '../models/briefing_model.dart';
import '../models/dashboard_model.dart';
import 'api_client.dart';
import 'dashboard_api.dart';

/// 하루 브리핑 API.
///
/// 백엔드 `POST /api/v1/briefings/daily` 는 request body 로 그 날의
/// schedules/todos 를 직접 받는다(방식 B). 그래서 먼저 dashboard/today 로
/// 오늘 데이터를 가져와 브리핑 요청 body 를 구성한다.
class BriefingApi {
  /// [date] : "YYYY-MM-DD" (미지정 시 서버 오늘)
  Future<BriefingModel> getDailyBriefing({String? date, String? userId}) async {
    // 1) 오늘 일정/할 일 확보.
    final DashboardData dash =
        await dashboardApi.getTodayDashboard(date: date, userId: userId);
    final targetDate = date ?? dash.date;

    // 2) 브리핑 request body 구성 (백엔드 스키마 필드명 그대로).
    final schedules = dash.schedules
        .map((s) => {
              'title': s.title,
              'category': s.category ?? 'etc',
              'start_time': s.startTime,
              'end_time': s.endTime,
              'priority': s.priority,
            })
        .toList();
    final todos = dash.todos
        .map((t) => {
              'title': t.title,
              'priority': t.priority,
              'is_done': t.completed,
            })
        .toList();

    // 3) 브리핑 생성 요청.
    final data = await apiClient.postData(
      '$apiPrefix/briefings/daily',
      body: {
        'date': targetDate,
        'schedules': schedules,
        'todos': todos,
      },
    );
    return BriefingModel.fromJson(data as Map<String, dynamic>);
  }
}

final briefingApi = BriefingApi();
