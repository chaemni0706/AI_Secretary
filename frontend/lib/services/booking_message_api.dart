import '../models/booking_message_model.dart';
import 'api_client.dart';

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
  Future<BookingMessageModel> generate({
    required String category,
    String? targetDate,
    String? preferredTime,
    String? purpose,
    String? input,
    String tone = 'polite',
    String length = 'short',
    String channel = 'sms',
  }) async {
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
          'length': length,
          'channel': channel,
        },
      },
    );
    return BookingMessageModel.fromJson(data as Map<String, dynamic>);
  }
}

final bookingMessageApi = BookingMessageApi();
