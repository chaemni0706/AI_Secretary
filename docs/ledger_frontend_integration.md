# AI 가계부 — 프론트엔드 API 연동 & 수동 검증 가이드

> **범위 / 성격**
> 이 기능은 **실제 금융사 API 연동이 아니다.** 카드/은행 "알림 원문 텍스트"를 백엔드가
> 룰 기반으로 파싱·분류·중복판정해 거래로 저장하는 **MVP**다. LLM/OCR/실금융 API 없이
> 결정론적으로 동작한다. 프론트는 금액/상호/카테고리를 **파싱하지 않고** 원문만 전달하며,
> 저장의 source of truth 는 백엔드다.
>
> 실제 Android `NotificationListenerService`(진짜 알림 자동 수신)는 **선택/확장 단계**다.
> 아래 "확장: 실시간 알림" 절 참고. 기본 시연은 "시연용 금융 알림 보내기" 버튼만으로 충분하다.

## 아키텍처 개요

```
[알림 원문]
  ├─ 시연 버튼(로컬 알림 표시 + 원문)                     ← 기본 시연 경로
  └─ (확장) Android NotificationListenerService → EventChannel
        │
        ▼
LedgerNotificationIngestService.ingestRawNotification()   ← 단일 진입점
        │  POST /api/v1/ledger/notifications/simulate
        ▼
백엔드 파싱/분류/중복판정 → SQLite 저장
        │
        ▼
ledgerApi.dashboard / report 재조회 → 화면 반영
```

주요 파일: `services/ledger_api.dart`, `models/ledger_api_models.dart`(DTO),
`models/ledger_mappers.dart`(DTO→UI 모델), `services/ledger_notification_ingest_service.dart`,
`services/local_demo_notification_service.dart`, `screens/ledger_screen.dart`,
`screens/ledger_report_screen.dart`.

Mock(`models/mock_ledger_data.dart`)은 **서버 미도달 시 오프라인 데모 fallback**으로만 쓰인다(삭제하지 않음).
모든 화면은 `DateTime.now()` 기준 현재 월로 시작한다(하드코딩 날짜 없음).

## 정적 분석 / 테스트

```bash
# 프론트
cd frontend
flutter analyze
flutter test        # (테스트가 있는 경우)

# 백엔드
pytest backend/tests/test_ledger_seed.py
```

## 백엔드 실행

```bash
python scripts/init_local_db.py
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
# (선택) 현재 월 기준 데모 거래 시드
curl -X POST "http://127.0.0.1:8000/api/v1/ledger/mock/seed?user_id=local-user"
```

## 앱 실행 (Base URL)

- Android Emulator: `http://10.0.2.2:8000`
- 실기기(같은 Wi-Fi): `http://<PC_IP>:8000`
- 필요 시: `flutter run --dart-define=API_BASE_URL=http://<host>:8000`

## 수동 검증 시나리오

1. **가계부 홈 진입**
   - 상단에 **현재 월**(예: 2026년 7월)이 표시되는지.
   - 백엔드 ON → 실제 dashboard(요약/달력/대기거래) 표시.
   - 백엔드 OFF → 상단 "오프라인 데모 데이터 표시 중" 배지 + Mock fallback 표시.

2. **시연용 금융 알림 보내기**
   - 자동 감지 카드의 **"알림 보내기"** → 템플릿(스타벅스/배민/카카오페이 등) 선택 또는 직접 입력 → **등록**.
   - 상단에 금융 알림이 뜨고(로컬 알림), 같은 원문이 백엔드에 전송됨.
   - 거래가 **대기(pending)** 또는 확정으로 목록에 나타나는지.
   - SnackBar: 성공 "금융 알림을 감지해 가계부에 등록했어요" / 중복 "이미 등록된 알림이에요" / 서버실패 "서버 연결 후 다시 시도해 주세요".

3. **거래 확인(확정)**
   - 대기 거래의 **확정** 클릭 → 대기 목록에서 사라지고, 선택 날짜 거래/월 요약에 반영(대시보드 재조회).

4. **거래 수정**
   - **수정** → 상호/금액/카테고리(및 날짜/시각/메모) 변경 → 저장 → 재조회 후 반영 확인.

5. **거래 삭제**
   - **삭제** → 확인 다이얼로그 → soft delete → 화면에서 사라짐.

6. **월 이동**
   - 헤더 `‹ ›`로 이전/다음 월 이동 → 해당 월 데이터 재조회. 31일 선택 후 2월 이동 시 말일로 안전 보정.

7. **소비 리포트 탭**
   - 방금 확정/등록한 거래가 카테고리별 소비·예산 사용률·월 요약에 반영되는지.
   - (이미 열려 있던 리포트는 **당겨서 새로고침**으로 최신화.)

8. **중복 방지**
   - 같은 알림을 여러 번 보내도 백엔드 dedup으로 "이미 등록된 알림이에요" 처리되어 중복 저장되지 않음.

## 확장: 실시간 알림(Android, 선택)

실제 카드/은행 알림 자동 수신은 `LedgerNotificationListenerService`(Kotlin) + EventChannel로 준비돼 있다.

1. 앱 실행 → 알림 작성 다이얼로그의 **"실시간 자동 감지 설정 열기(Android)"** → 시스템 "알림 접근" 권한 허용.
2. 실제 결제/입금 알림 도착 시 네이티브 필터(금융 키워드/whitelist) 통과분만 `ingestRawNotification(source:'android_listener')`로 자동 등록 → 대시보드 재조회.
3. 정밀도 향상: 실제 금융 앱 `packageName` 확인 후 `LedgerNotificationListenerService.WHITELIST_PACKAGES`에 추가.

한계(현재 MVP): 오프라인 수신분은 앱 실행 중 in-memory 큐로만 임시 보관(프로세스 종료 시 유실). 영구 큐는 후속 과제.

## 응답 규약(참고)

- prefix: `/api/v1`, envelope: `{success, message, data}` (프론트 `ApiClient`가 해제).
- enum(소문자): `transaction_type`= expense|income|cancel|ignore, `source_type`= notification|receipt_scan|manual|seed, `status`= pending|confirmed|duplicate|deleted|needs_review.
- amount: 원화 정수, date: `YYYY-MM-DD`, time: `HH:MM`, occurred_at: ISO datetime.
