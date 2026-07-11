package com.example.frontend

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        // 온디바이스 SmolVLM 브릿지 등록(fallback-safe; 모델 미존재 시 서버 fallback).
        SmolVlmBridge(applicationContext).register(flutterEngine)
    }
}
