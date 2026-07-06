import '../models/booking_message_model.dart';
import 'api_client.dart';
import 'preference_store.dart';

/// 예약 문의 메시지 생성 API.
///
/// 백엔드 `POST /api/v1/messages/reservation` 실제 스키마:
///   { "input": str?,
///     "reservation_info": {category, target_date, preferred_time, purpose},
///     "style": {tone, length, channel} }
class BookingMessageApi {
  /// [tone]   : polite | casual | formal
  /// [length] : short | medium | long
  /// [channel]: sms | call | kakao | etc
  ///
  /// [length] 를 지정하지 않으면 사용자 설정 response_length(short/normal/detailed)를
  /// 예약 메시지 length(short/medium/long)로 매핑해 사용한다.
  Future<BookingMessageModel> generate({
    required String category,
    String? targetDate,
    String? preferredTime,
    String? purpose,
    String? input,
    String tone = 'polite',
    String? length,
    String channel = 'sms',
  }) async {
    final effLength = length ?? _lengthFromResponseLength(preferenceStore.responseLength);
    final data = await apiClient.postData(
      '$apiPrefix/messages/reservation',
      body: {
        if (input != null) 'input': input,
        'reservation_info': {
          'category': category,
          if (targetDate != null) 'target_date': targetDate,
          if (preferredTime != null) 'preferred_time': preferredTime,
          if (purpose != null) 'purpose': purpose,
        },
        'style': {
          'tone': tone,
          'length': effLength,
          'channel': channel,
        },
        // 말투/길이 계약 필드(서버 미소비여도 무해).
        'user_context': preferenceStore.userContext,
      },
    );
    return BookingMessageModel.fromJson(data as Map<String, dynamic>);
  }

  /// response_length(short|normal|detailed) → 예약 메시지 length(short|medium|long).
  String _lengthFromResponseLength(String responseLength) {
    switch (responseLength) {
      case 'short':
        return 'short';
      case 'detailed':
      case 'long':
        return 'long';
      default:
        return 'medium';
    }
  }
}

final bookingMessageApi = BookingMessageApi();
