import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:webview_flutter/webview_flutter.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  // 세로 방향 고정
  SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  runApp(const AISecretaryApp());
}

class AISecretaryApp extends StatelessWidget {
  const AISecretaryApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AI 비서',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF6B8CFF),
          brightness: Brightness.light,
        ),
        useMaterial3: true,
      ),
      home: const HtmlViewerScreen(),
    );
  }
}

// HTML 파일 경로 — 나중에 다른 화면으로 교체할 때 이 상수만 수정
const String kHtmlAssetPath = 'assets/html/index.html';

class HtmlViewerScreen extends StatefulWidget {
  const HtmlViewerScreen({super.key});

  @override
  State<HtmlViewerScreen> createState() => _HtmlViewerScreenState();
}

class _HtmlViewerScreenState extends State<HtmlViewerScreen> {
  late final WebViewController _controller;
  bool _isLoading = true;
  bool _hasError = false;

  @override
  void initState() {
    super.initState();
    _initWebView();
  }

  void _initWebView() {
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFFF0F3FF))
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageFinished: (_) {
            setState(() {
              _isLoading = false;
            });
          },
          onWebResourceError: (_) {
            setState(() {
              _isLoading = false;
              _hasError = true;
            });
          },
        ),
      )
      ..loadFlutterAsset(kHtmlAssetPath);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF0F3FF),
      body: SafeArea(
        // HTML 내부에서 safe area를 직접 처리하므로 Flutter SafeArea는 비활성화
        top: false,
        bottom: false,
        child: Stack(
          children: [
            // WebView
            if (!_hasError)
              WebViewWidget(controller: _controller),

            // 로딩 인디케이터
            if (_isLoading && !_hasError)
              const Center(
                child: CircularProgressIndicator(
                  color: Color(0xFF6B8CFF),
                ),
              ),

            // 에러 화면
            if (_hasError)
              _ErrorScreen(onRetry: () {
                setState(() {
                  _isLoading = true;
                  _hasError = false;
                });
                _controller.loadFlutterAsset(kHtmlAssetPath);
              }),
          ],
        ),
      ),
    );
  }
}

class _ErrorScreen extends StatelessWidget {
  final VoidCallback onRetry;

  const _ErrorScreen({required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.error_outline_rounded,
              size: 64,
              color: Color(0xFF6B8CFF),
            ),
            const SizedBox(height: 16),
            const Text(
              '화면을 불러오지 못했어요',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: Color(0xFF2D2D3A),
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'assets/html/index.html 파일을 확인해주세요.',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 13,
                color: Color(0xFF7A7A9A),
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('다시 시도'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF6B8CFF),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 12,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
