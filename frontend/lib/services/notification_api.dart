import '../models/notification_model.dart';
import 'api_client.dart';

class NotificationApi {
  /// 알림 계획 생성: `POST /api/v1/notifications/plan`
  Future<NotificationPlan> createPlan({
    required String scheduleId,
    String? userId,
    String notificationPreference = 'normal', // normal|strong|forgetful|late_prone
    bool includeChecklist = true,
    bool persist = true,
  }) async {
    final data = await apiClient.postData(
      '$apiPrefix/notifications/plan',
      body: {
        'schedule_id': scheduleId,
        if (userId != null) 'user_id': userId,
        'notification_preference': notificationPreference,
        'include_checklist': includeChecklist,
        'persist': persist,
      },
    );
    return NotificationPlan.fromJson(data as Map<String, dynamic>);
  }

  /// 알림 계획 조회: `GET /api/v1/notifications/plan/{schedule_id}`
  ///
  /// ⚠️ query parameter 방식이 아니다.
  ///   - (X) /api/v1/notifications/plan?schedule_id=abc
  ///   - (O) /api/v1/notifications/plan/abc   ← path parameter
  Future<NotificationPlan> getPlan(String scheduleId) async {
    final data = await apiClient.getData(
      '$apiPrefix/notifications/plan/$scheduleId',
    );
    return NotificationPlan.fromJson(data as Map<String, dynamic>);
  }
}

final notificationApi = NotificationApi();
