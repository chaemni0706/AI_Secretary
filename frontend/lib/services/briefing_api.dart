import '../models/briefing_model.dart';
import '../models/dashboard_model.dart';
import '../models/weather_model.dart';
import 'api_client.dart';
import 'dashboard_api.dart';
import 'preference_store.dart';
import 'weather_api.dart';

/// 하루 브리핑 API.
///
/// 백엔드 `POST /api/v1/briefings/daily` 는 request body 로 그 날의
/// schedules/todos 를 직접 받는다(방식 B). 그래서 먼저 dashboard/today 로
/// 오늘 데이터를 가져와 브리핑 요청 body 를 구성한다.
class BriefingApi {
  /// [date] : "YYYY-MM-DD" (미지정 시 서버 오늘)
  Future<BriefingModel> getDailyBriefing({String? date, String? userId}) async {
    // 1) 오늘 일정/할 일 + 날씨를 동시에 요청(대기 시간 단축). 날씨는 best-effort로
    //    실패해도 브리핑 흐름에 영향 없음(null → 날씨 없이 생성).
    final dashFuture = dashboardApi.getTodayDashboard(date: date, userId: userId);
    final weatherFuture = _tryWeather();
    final DashboardData dash = await dashFuture;
    final WeatherModel? weather = await weatherFuture;
    final targetDate = date ?? dash.date;

    // 2) 브리핑 request body 구성 (백엔드 스키마 필드명 그대로).
    final schedules = dash.schedules
        .map(
          (s) => {
            'title': s.title,
            'category': s.category ?? 'etc',
            'start_time': s.startTime,
            'end_time': s.endTime,
            'priority': s.priority,
          },
        )
        .toList();
    final todos = dash.todos
        .map(
          (t) => {
            'title': t.title,
            'priority': t.priority,
            'is_done': t.completed,
          },
        )
        .toList();

    // 3) 브리핑 생성 요청.
    //    user_context/voice 는 말투/길이/음성 옵션 계약 필드. 서버가 아직
    //    미소비해도 무해(미지 필드 무시)하며, 반영 시 그 말투로 브리핑을 만든다.
    try {
      final data = await apiClient.postData(
        '$apiPrefix/briefings/daily',
        body: {
          'date': targetDate,
          'schedules': schedules,
          'todos': todos,
          if (weather != null) 'weather': _weatherBody(weather),
          'user_context': preferenceStore.userContext,
          'voice': preferenceStore.voice,
        },
      );
      return BriefingModel.fromJson(data as Map<String, dynamic>);
    } on ApiException catch (e) {
      // 서버 미도달(오프라인/타임아웃)일 때만 로컬 일정 기반 간단 브리핑으로 대체.
      // 이미 확보한 dash(오늘 일정/할 일)로 요약을 만든다.
      if (e.isNetworkError) {
        return _localBriefing(dash);
      }
      rethrow;
    }
  }

  /// 날씨 best-effort 조회. 실패(오프라인/권한/타임아웃)하면 null 을 반환해
  /// 브리핑이 날씨 없이 진행되도록 한다.
  Future<WeatherModel?> _tryWeather() async {
    try {
      return await weatherApi.fetchAuto();
    } catch (_) {
      return null;
    }
  }

  /// WeatherModel → 브리핑 요청의 `weather` 필드(백엔드 BriefingWeather 스키마).
  /// 당일 최대 강수확률은 오늘 시간별 예보(pop)에서 뽑고, 최저/최고는 모델의
  /// 값이 없으면 주간 예보 첫날에서 보완한다.
  Map<String, dynamic> _weatherBody(WeatherModel w) {
    final firstDay = w.daily.isNotEmpty ? w.daily.first : null;
    int? maxPop;
    for (final h in w.today) {
      final p = h.pop;
      if (p != null && (maxPop == null || p > maxPop)) maxPop = p;
    }
    return {
      'sky': w.now.sky,
      'precipitation': w.now.precipitation,
      'temp_c': w.now.tempC,
      'temp_min': w.tempMin ?? firstDay?.tempMin,
      'temp_max': w.tempMax ?? firstDay?.tempMax,
      'max_pop': maxPop,
    };
  }

  /// 서버 실패 시: 로컬 일정/할 일로 만드는 간단 브리핑(rule-based, 오프라인).
  BriefingModel _localBriefing(DashboardData dash) {
    final sCount = dash.schedules.length;
    final tCount = dash.todos.where((t) => !t.completed).length;

    final summary = (sCount == 0 && tCount == 0)
        ? '오늘은 등록된 일정이 없어요. (오프라인 상태예요.)'
        : '오늘 일정 $sCount개, 남은 할 일 $tCount개가 있어요. (오프라인 임시 브리핑)';

    final keyPoints = <String>[
      for (final s in dash.schedules)
        [
          if (s.startTime != null && s.startTime!.isNotEmpty) s.startTime,
          s.title,
        ].whereType<String>().join(' '),
      for (final t in dash.todos.where((t) => !t.completed)) '할 일: ${t.title}',
    ];

    final priorityOrder = <PriorityOrderItem>[
      for (final s in dash.schedules.where((s) => s.priority == 'high'))
        PriorityOrderItem(
          title: s.title,
          priority: 'high',
          reason: '우선순위 높은 일정',
        ),
      for (final t in dash.todos.where(
        (t) => !t.completed && t.priority == 'high',
      ))
        PriorityOrderItem(
          title: t.title,
          priority: 'high',
          reason: '우선순위 높은 할 일',
        ),
    ];

    return BriefingModel(
      summary: preferenceStore.applyLength(summary),
      keyPoints: keyPoints,
      priorityOrder: priorityOrder,
    );
  }
}

final briefingApi = BriefingApi();
