import 'package:flutter/foundation.dart';

import '../models/dashboard_model.dart';
import 'api_client.dart';

/// 대시보드 관련 API.
class DashboardApi {
  /// `GET /api/v1/dashboard/today`
  ///
  /// [date]  : "YYYY-MM-DD" (선택, 미지정 시 서버 오늘)
  /// [userId]: 선택
  Future<DashboardData> getTodayDashboard({
    String? date,
    String? userId,
  }) async {
    final query = <String, dynamic>{};
    if (date != null) query['date'] = date;
    if (userId != null) query['user_id'] = userId;

    final data = await apiClient.getData(
      '$apiPrefix/dashboard/today',
      query: query.isEmpty ? null : query,
    );
    return DashboardData.fromJson(data as Map<String, dynamic>);
  }
}

final dashboardApi = DashboardApi();

/// 저장(생성) 후 홈 대시보드를 다시 불러오게 하는 전역 트리거.
///
/// 다른 화면(AI 챗 등)에서 일정/할 일을 저장한 뒤 [bump] 를 호출하면,
/// 이 값을 listen 하는 홈 화면이 대시보드를 새로고침한다.
final ValueNotifier<int> dashboardRefresh = ValueNotifier<int>(0);

void triggerDashboardRefresh() {
  dashboardRefresh.value++;
}
