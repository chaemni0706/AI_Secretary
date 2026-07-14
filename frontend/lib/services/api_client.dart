import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

/// ---------------------------------------------------------------------------
/// 실행 환경별 Base URL
/// ---------------------------------------------------------------------------
/// - PC 로컬(Flutter Web, 같은 PC):   http://127.0.0.1:8000
/// - Android Emulator:                http://10.0.2.2:8000
/// - 실제 기기(같은 Wi-Fi):            http://{PC_IP}:8000  (예: http://192.168.0.10:8000)
///
/// 필요하면 실행 시 `--dart-define=API_BASE_URL=http://...:8000` 로 덮어쓴다.
/// 미지정 시 아래 기본값 사용(실기기 테스트는 PC IP 기준).
const String _configuredBaseUrl = String.fromEnvironment('API_BASE_URL');
final String baseUrl = _resolveBaseUrl();

String _resolveBaseUrl() {
  if (_configuredBaseUrl.isNotEmpty) return _configuredBaseUrl;
  if (kIsWeb) {
    final host = Uri.base.host.isNotEmpty ? Uri.base.host : 'localhost';
    return 'http://$host:8000';
  }
  // 실기기(같은 Wi-Fi) 테스트 기준 PC IP. IP 가 바뀌거나 USB(adb reverse) 로
  // 붙일 땐 --dart-define=API_BASE_URL=http://...:8000 (예: http://127.0.0.1:8000) 로 덮어쓸 것.
  return 'http://192.168.0.73:8000';
}

/// API 공통 prefix (`/health` 제외).
const String apiPrefix = '/api/v1';

/// 백엔드 공통 응답(`{success, message, data}`)에서 success=false 이거나
/// 네트워크 오류가 발생했을 때 던지는 예외.
class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final String? requestUri;
  final dynamic responseBody;
  // 서버가 아직 처리 중(예: 무거운 VLM 추론)이라 응답이 늦어 클라이언트 타임아웃에
  // 걸린 경우인지 여부. 연결 거부/오프라인 등 다른 네트워크 오류와 구분해, UI가
  // "이미지가 거절됐다"가 아니라 "서버가 아직 분석 중일 수 있다"고 정직하게 안내하게 한다.
  final bool isTimeout;

  ApiException(
    this.message, {
    this.statusCode,
    this.requestUri,
    this.responseBody,
    this.isTimeout = false,
  });

  /// 서버에 도달하지 못한 오류(연결 거부/타임아웃/오프라인 등)인지 여부.
  /// statusCode 가 없으면 요청이 기기를 벗어나지 못했거나 응답이 없는 경우로 본다.
  /// 이 값이 true 일 때만 온디바이스 fallback(로컬 파서/브리핑/공감)으로 전환한다.
  /// (4xx/5xx 는 서버가 응답한 것이므로 fallback 하지 않고 그대로 전달한다.)
  bool get isNetworkError => statusCode == null;

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
        // 서버 미도달(연결 거부/잘못된 IP/오프라인)은 빠르게 판정해 온디바이스
        // 폴백으로 전환한다. 서버 처리 시간은 receiveTimeout 으로 별도 확보.
        connectTimeout: const Duration(seconds: 4),
        receiveTimeout: const Duration(seconds: 10),
        // 공통 헤더: JSON 요청/응답 + 클라이언트 타임존(서버가 상대날짜 해석에 참고 가능).
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-Client-Timezone': 'Asia/Seoul',
        },
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
          // 요청 시작 시각을 기록해 응답에서 소요 시간을 계산한다.
          options.extra['_startedAt'] = DateTime.now();
          debugPrint('[API REQUEST] ${options.method} ${options.uri}');
          handler.next(options);
        },
        onResponse: (response, handler) {
          debugPrint(
            '[API RESPONSE] ${response.statusCode} '
            '${_elapsedMs(response.requestOptions)}ms '
            '${response.requestOptions.uri} '
            'body=${_short(response.data)}',
          );
          handler.next(response);
        },
        onError: (e, handler) {
          debugPrint(
            '[API ERROR] status=${e.response?.statusCode} '
            '${_elapsedMs(e.requestOptions)}ms '
            'uri=${e.requestOptions.uri} type=${e.type} '
            'message=${e.message} body=${_short(e.response?.data)}',
          );
          handler.next(e);
        },
      ),
    );
  }

  /// 요청 시작 이후 경과 시간(ms). 서버 응답이 느린지 즉시 판단하는 용도.
  static int _elapsedMs(RequestOptions options) {
    final started = options.extra['_startedAt'];
    if (started is DateTime) {
      return DateTime.now().difference(started).inMilliseconds;
    }
    return -1;
  }

  /// 로그용으로 응답 본문을 최대 300자로 자른다.
  /// 큰 payload 를 통째로 debugPrint 하면 Flutter 로그 throttling 에 걸려
  /// 로그가 밀리고 초기 로딩이 버벅이는 원인이 되므로 짧게만 남긴다.
  static String _short(dynamic data) {
    final s = data?.toString() ?? 'null';
    return s.length > 300 ? '${s.substring(0, 300)}…(${s.length}자)' : s;
  }

  static final ApiClient instance = ApiClient._internal();

  late final Dio _dio;

  Dio get dio => _dio;

  // NOTE: `path` 는 호출부(각 *_api.dart)에서 이미 `$apiPrefix/...` 형태로 넘긴다.
  // 여기서 다시 apiPrefix 를 붙이면 기존 서비스들(notification/dashboard/todo/
  // schedule/booking_message 등)이 전부 `/api/v1/api/v1/...` 이중 prefix 로
  // 깨지므로 절대 여기서 접두사를 추가하지 않는다.

  /// GET 후 envelope 를 풀어 `data` 를 반환.
  Future<dynamic> getData(String path, {Map<String, dynamic>? query}) async {
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
      final res = await _dio.post(
        path,
        data: body,
        queryParameters: query,
        options: Options(contentType: Headers.jsonContentType),
      );
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

  /// multipart/form-data(파일 업로드) POST 후 envelope 를 풀어 `data` 를 반환.
  /// 이미지 인증(`/verification/image/{type}`)처럼 파일을 올릴 때 사용한다.
  Future<dynamic> postMultipart(String path, FormData formData) async {
    try {
      final res = await _dio.post(
        path,
        data: formData,
        options: Options(
          contentType: 'multipart/form-data',
          // 이미지 전송 + 판정 시간을 고려해 여유 있게.
          // 주의(Phase 12): 이 60초는 "가짜 300초짜리 fp32 reference 엔진을 가리기 위해"
          // 늘린 값이 아니다 -- 그 반대로, 이 값을 300초+ 로 늘려서 느린 백엔드를 숨기지
          // 않기로 한 명시적 결정이다. reference_fp32 Qwen7B 엔진(~300-320초/call)은 이
          // 타임아웃보다 근본적으로 느리므로, 그 경로를 타는 요청은 여기서 정직하게
          // 타임아웃 처리된다 -- 원인은 이미지가 아니라 서버 쪽 모델 지연이라는 것을
          // isTimeout 플래그로 UI에 전달한다. 실제 해법은 이 값을 늘리는 게 아니라
          // (qwen_recovery/qwen7b_quantized_engine_report.md) 더 빠른 엔진/다른 GPU다.
          sendTimeout: const Duration(seconds: 60),
          receiveTimeout: const Duration(seconds: 60),
        ),
      );
      return _unwrap(res);
    } on DioException catch (e) {
      final isTimeout = e.type == DioExceptionType.sendTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.connectionTimeout;
      throw ApiException(
        isTimeout
            ? '서버 응답이 지연되고 있어요. 모델이 아직 이미지를 분석 중일 수 있습니다.'
            : '네트워크 오류: ${e.message ?? e.type.name}',
        statusCode: e.response?.statusCode,
        requestUri: e.requestOptions.uri.toString(),
        responseBody: e.response?.data,
        isTimeout: isTimeout,
      );
    }
  }

  /// PATCH 후 envelope 를 풀어 `data` 를 반환.
  Future<dynamic> patchData(String path, {Object? body}) async {
    try {
      final res = await _dio.patch(
        path,
        data: body,
        options: Options(contentType: Headers.jsonContentType),
      );
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
  Future<dynamic> putData(String path, {Object? body}) async {
    try {
      final res = await _dio.put(
        path,
        data: body,
        options: Options(contentType: Headers.jsonContentType),
      );
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

  /// DELETE 후 envelope 를 풀어 `data` 를 반환.
  Future<dynamic> deleteData(String path, {Object? body}) async {
    try {
      final res = await _dio.delete(path, data: body);
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
