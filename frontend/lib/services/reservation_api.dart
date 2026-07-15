import '../models/reservation_model.dart';
import 'api_client.dart';

class ReservationApi {
  /// 저장된 일정 기반 예약 후보 추천:
  /// `POST /api/v1/reservations/candidates/from-store`
  ///
  /// 응답의 각 후보는 `reason`(string) + `conflict`(bool) 를 갖는다.
  Future<ReservationResult> candidatesFromStore({
    required String targetDate,
    int durationMinutes = 60,
    String preferredStartTime = '09:00',
    String preferredEndTime = '21:00',
    String? category,
    String? userId,
    bool applyPreferenceBuffer = false,
  }) async {
    final data = await apiClient.postData(
      '$apiPrefix/reservations/candidates/from-store',
      body: {
        'target_date': targetDate,
        'duration_minutes': durationMinutes,
        'preferred_start_time': preferredStartTime,
        'preferred_end_time': preferredEndTime,
        if (category != null) 'category': category,
        if (userId != null) 'user_id': userId,
        'apply_preference_buffer': applyPreferenceBuffer,
      },
    );
    return ReservationResult.fromJson(data as Map<String, dynamic>);
  }

  /// 선택한 후보를 일정 저장용 schedule_draft 로 변환.
  static Map<String, dynamic> candidateToDraft(
    ReservationCandidate c, {
    required String title,
    required String date,
    String? category,
    String priority = 'medium',
    String? location,
  }) {
    return {
      'title': title,
      'date': date,
      'start_time': c.startTime,
      'end_time': c.endTime,
      if (category != null) 'category': category,
      'priority': priority,
      if (location != null) 'location': location,
    };
  }
}

final reservationApi = ReservationApi();
