package com.example.frontend

import android.app.Notification
import android.os.Handler
import android.os.Looper
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import io.flutter.plugin.common.EventChannel

/**
 * 서비스(백그라운드)와 MainActivity(Flutter EventChannel) 사이의 브리지.
 *
 * NotificationListenerService 는 Activity 와 독립적으로 살아있으므로, 수신한 알림을
 * 여기(process-내 싱글턴)에 모아 EventSink 로 흘려보낸다. Flutter 스트림이 아직
 * 리스닝 전이면 임시 큐잉한다(앱 실행 중 한정 — 프로세스 종료 시 유실).
 */
object LedgerNotificationBridge {
    private val mainHandler = Handler(Looper.getMainLooper())
    private val pending = ArrayDeque<Map<String, Any?>>()
    private const val MAX_QUEUE = 50
    private var sink: EventChannel.EventSink? = null

    fun setSink(s: EventChannel.EventSink?) {
        mainHandler.post {
            sink = s
            if (s != null) {
                while (pending.isNotEmpty()) {
                    s.success(pending.removeFirst())
                }
            }
        }
    }

    fun emit(event: Map<String, Any?>) {
        mainHandler.post {
            val s = sink
            if (s != null) {
                s.success(event)
            } else {
                if (pending.size >= MAX_QUEUE) pending.removeFirst()
                pending.addLast(event)
            }
        }
    }
}

/**
 * 결제/입금 알림 수신 서비스.
 *
 * 개인정보 보호: 알림 원문은 백엔드 전송(EventChannel→Flutter→simulate) 외에
 * 로컬 로그로 남기지 않는다. 파싱/분류는 하지 않고 원문만 전달한다(백엔드가 source of truth).
 */
class LedgerNotificationListenerService : NotificationListenerService() {

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        val n = sbn ?: return
        val notification = n.notification ?: return

        // 진행중(ongoing)·그룹 요약 알림은 거래가 아니므로 무시.
        val flags = notification.flags
        if (flags and Notification.FLAG_ONGOING_EVENT != 0) return
        if (flags and Notification.FLAG_GROUP_SUMMARY != 0) return

        val extras = notification.extras ?: return
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString().orEmpty()
        val bigText = extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString().orEmpty()
        val subText = extras.getCharSequence(Notification.EXTRA_SUB_TEXT)?.toString().orEmpty()

        val body = listOf(text, bigText).firstOrNull { it.isNotBlank() }.orEmpty()
        val combined = listOf(title, body).filter { it.isNotBlank() }.joinToString(" ").trim()
        if (combined.isBlank()) return

        val pkg = n.packageName ?: ""
        // 앱이 띄운 시연용 로컬 알림은 이미 직접 등록되므로 재수집하지 않는다(중복 방지).
        if (pkg == packageName) return
        if (!isFinancial(pkg, "$combined $subText")) return

        LedgerNotificationBridge.emit(
            mapOf(
                "text" to combined,
                "packageName" to pkg,
                "postedAt" to n.postTime,
            )
        )
    }

    /**
     * whitelist 패키지이거나 금융 키워드를 포함할 때만 처리한다.
     * (실제 금융 앱 packageName 은 기기에서 확인 후 [WHITELIST_PACKAGES] 에 채운다.)
     */
    private fun isFinancial(pkg: String, haystack: String): Boolean {
        if (WHITELIST_PACKAGES.contains(pkg)) return true
        return FINANCIAL_KEYWORDS.any { haystack.contains(it) }
    }

    companion object {
        // 초기에는 비워두고 키워드 필터로 병행. 실제 packageName 확인 후 추가:
        //   "com.kakaopay.app"(카카오페이), "viva.republica.toss"(토스), 카드사 앱 등
        private val WHITELIST_PACKAGES: Set<String> = emptySet()

        private val FINANCIAL_KEYWORDS = listOf(
            "카드", "승인", "결제", "입금", "출금", "송금", "승인취소",
        )
    }
}
