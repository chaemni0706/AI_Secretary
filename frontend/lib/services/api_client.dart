import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

/// ---------------------------------------------------------------------------
/// 실행 환경별 Base URL
/// ---------------------------------------------------------------------------
/// - PC 로컬(Flutter Web, 같은 PC):   http://127.0.0.1:8000
/// - Android Emulator:                http://10.0.2.2:8000
/// - 실제 기기(같은 Wi-Fi):            http://{PC_IP}:8000  (예: http://192.168.0.10:8000)
///
/// 환경에 맞게 아래 값 하나만 바꾸면 됩니다.
// const String baseUrl = 'http://127.0.0.1:8000';
const String baseUrl = 'http://141.223.140.85:8000';

// Android Emulator용:
// const String baseUrl = 'http://10.0.2.2:8000';

// 실제 기기용:
// const String baseUrl = 'http://192.168.0.10:8000';

/// API 공통 prefix (`/health` 제외).
const String apiPrefix = '/api/v1';

/// 백엔드 공통 응답(`{success, message, data}`)에서 success=false 이거나
/// 네트워크 오류가 발생했을 때 던지는 예외.
class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final String? requestUri;
  final dynamic responseBody;

  ApiException(this.message, {this.statusCode, this.requestUri, this.responseBody});

  @override
  String toString() =>
      'ApiException($statusCode): $message @ $requestUri body=$responseBody';
}

/// Dio 기반 API 클라이언트 (싱글턴).
///
/// 모든 응답은 공통 envelope `{ "success": bool, "message": string, "data": any }`
/// 를 따르므로, 여기서 envelope 를 풀어 `data` 만 반환한다. success=false 이면
/// [ApiException] 을 던진다.
class ApiClient {
  ApiClient._internal() {
    _dio = Dio(
      BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 10),
        headers: {'Content-Type': 'application/json'},
        // 4xx/5xx 도 예외 없이 받아서 envelope 를 직접 해석한다.
        validateStatus: (_) => true,
      ),
    );

    // 네트워크 진단용 로그.
    // - onRequest: 실제로 어떤 URL 로 요청이 나가는지(baseUrl + path) 확인.
    // - onResponse: 서버까지 도달했는지 + 상태코드 확인.
    // - onError: 서버 도달 전 실패(연결 거부/타임아웃/cleartext 차단 등) 진단.
    // Flutter 로그에 요청 URL 이 찍혔는데 백엔드 터미널에 로그가 없다면,
    // 요청이 기기를 벗어나지 못한 것(네트워크/HTTP 차단 문제)으로 판단한다.
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          debugPrint('[API REQUEST] ${options.method} ${options.uri}');
          handler.next(options);
        },
        onResponse: (response, handler) {
          debugPrint(
            '[API RESPONSE] ${response.statusCode} ${response.requestOptions.uri} '
            'body=${response.data}',
          );
          handler.next(response);
        },
        onError: (e, handler) {
          debugPrint(
            '[API ERROR] status=${e.response?.statusCode} '
            'uri=${e.requestOptions.uri} type=${e.type} '
            'message=${e.message} body=${e.response?.data}',
          );
          handler.next(e);
        },
      ),
    );
  }

  static final ApiClient instance = ApiClient._internal();

  late final Dio _dio;

  Dio get dio => _dio;

  // NOTE: `path` 는 호출부(각 *_api.dart)에서 이미 `$apiPrefix/...` 형태로 넘긴다.
  // 여기서 다시 apiPrefix 를 붙이면 기존 서비스들(notification/dashboard/todo/
  // schedule/booking_message 등)이 전부 `/api/v1/api/v1/...` 이중 prefix 로
  // 깨지므로 절대 여기서 접두사를 추가하지 않는다.

  /// GET 후 envelope 를 풀어 `data` 를 반환.
  Future<dynamic> getData(
    String path, {
    Map<String, dynamic>? query,
  }) async {
    try {
      final res = await _dio.get(path, queryParameters: query);
      return _unwrap(res);
    } on DioException catch (e) {
      throw ApiException(
        '네트워크 오류: ${e.message ?? e.type.name}',
        statusCode: e.response?.statusCode,
        requestUri: e.requestOptions.uri.toString(),
        responseBody: e.response?.data,
      );
    }
  }

  /// POST 후 envelope 를 풀어 `data` 를 반환.
  Future<dynamic> postData(
    String path, {
    Object? body,
    Map<String, dynamic>? query,
  }) async {
    try {
      final res = await _dio.post(path, data: body, queryParameters: query);
      return _unwrap(res);
    } on DioException catch (e) {
      throw ApiException(
        '네트워크 오류: ${e.message ?? e.type.name}',
        statusCode: e.response?.statusCode,
        requestUri: e.requestOptions.uri.toString(),
        responseBody: e.response?.data,
      );
    }
  }

  /// PATCH 후 envelope 를 풀어 `data` 를 반환.
  Future<dynamic> patchData(
    String path, {
    Object? body,
  }) async {
    try {
      final res = await _dio.patch(path, data: body);
      return _unwrap(res);
    } on DioException catch (e) {
      throw ApiException(
        '네트워크 오류: ${e.message ?? e.type.name}',
        statusCode: e.response?.statusCode,
        requestUri: e.requestOptions.uri.toString(),
        responseBody: e.response?.data,
      );
    }
  }

  /// PUT 후 envelope 를 풀어 `data` 를 반환.
  Future<dynamic> putData(
    String path, {
    Object? body,
  }) async {
    try {
      final res = await _dio.put(path, data: body);
      return _unwrap(res);
    } on DioException catch (e) {
      throw ApiException(
        '네트워크 오류: ${e.message ?? e.type.name}',
        statusCode: e.response?.statusCode,
        requestUri: e.requestOptions.uri.toString(),
        responseBody: e.response?.data,
      );
    }
  }

  /// 공통 envelope 검증 후 `data` 반환. 실패 시 [ApiException].
  dynamic _unwrap(Response res) {
    final uri = res.requestOptions.uri.toString();
    final body = res.data;
    if (body is Map<String, dynamic>) {
      final success = body['success'] == true;
      final message = (body['message'] ?? '').toString();
      if (success) {
        return body['data'];
      }
      throw ApiException(
        message.isNotEmpty ? message : '요청이 실패했습니다.',
        statusCode: res.statusCode,
        requestUri: uri,
        responseBody: body,
      );
    }
    // envelope 가 아니면(예상 밖 응답) 그대로 오류 처리.
    throw ApiException(
      '알 수 없는 응답 형식입니다. (status ${res.statusCode})',
      statusCode: res.statusCode,
      requestUri: uri,
      responseBody: body,
    );
  }
}

/// 간편 접근용 전역 인스턴스.
final apiClient = ApiClient.instance;
