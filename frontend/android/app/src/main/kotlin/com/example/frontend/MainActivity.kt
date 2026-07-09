package com.example.frontend

import android.content.Intent
import android.provider.Settings
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val eventsChannel = "ai_secretary/ledger_notifications"
    private val controlChannel = "ai_secretary/ledger_notifications/control"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        // 네이티브 리스너 → Flutter 알림 원문 스트림.
        EventChannel(flutterEngine.dartExecutor.binaryMessenger, eventsChannel)
            .setStreamHandler(object : EventChannel.StreamHandler {
                override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
                    LedgerNotificationBridge.setSink(events)
                }

                override fun onCancel(arguments: Any?) {
                    LedgerNotificationBridge.setSink(null)
                }
            })

        // 권한 확인 / 설정 화면 열기.
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, controlChannel)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "isPermissionGranted" -> result.success(isNotificationAccessGranted())
                    "openSettings" -> {
                        startActivity(
                            Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)
                                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        )
                        result.success(null)
                    }
                    else -> result.notImplemented()
                }
            }
    }

    private fun isNotificationAccessGranted(): Boolean {
        val flat = Settings.Secure.getString(
            contentResolver, "enabled_notification_listeners"
        )
        return flat?.contains(packageName) == true
    }
}
