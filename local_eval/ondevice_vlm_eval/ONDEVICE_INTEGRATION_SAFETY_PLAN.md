# SmolVLM 온디바이스 테스트 ↔ Feature_CM(음성비서/브리핑) 통합 안전 계획

목적: 팀장이 Feature_CM 에 반영한 음성 비서(Vosk)/오늘의 브리핑 기능과, SmolVLM-500M 온디바이스
이미지 인증 실험이 **서로 충돌하지 않도록** 격리·검증하는 계획. 현 단계 SmolVLM 은 real-only 평가에서
FP=9(모델 hallucination)로 **온디바이스 진입 보류(NO-GO)** 상태 → 프로덕션 연결 금지, **debug-only 실험만** 허용.

원칙: 기존 verification API / Rule Engine core / 음성 다운로드 로직을 건드리지 않는다. VLM 은 evidence 만,
판정은 Rule Engine. SmolVLM 은 개발자 전용 경로에서 evidence JSON 로그만 출력한다.

---

## 1. Feature_CM 변경사항 요약
- 오늘의 브리핑 화면 통합 (실제 API + "듣기" 버튼)
- 음성 호출 추가: 메뉴 > AI 음성 비서 > 음성 비서(포비), "포비 오늘 브리핑" 호출
- 화면 꺼져도 동작(백그라운드 음성 서비스)
- **음성 모델 ~48MB 앱 첫 실행 시 자동 다운로드**
- **minSdk 30 상향**
- Vosk 플러그인 `frontend/plugins/` 포함
- 권한: 마이크 / 알림 / 배터리 최적화 제외
- `baseUrl` 은 `frontend/lib/services/api_client.dart` 에서 환경별 설정

## 2. SmolVLM 온디바이스와 충돌 가능 지점
| 영역 | Feature_CM | SmolVLM 실험 | 충돌 위험 | 격리 방침 |
| --- | --- | --- | --- | --- |
| **모델 다운로드 경로** | Vosk ~48MB 자동 다운로드(첫 실행) | SmolVLM ONNX ~360MB(조합 A) | 동시 다운로드 시 대역폭/디스크/첫실행 지연, 로직 혼선 | **다운로드 로직 분리**. SmolVLM 은 자동 다운로드 금지(수동/디버그 트리거). 음성 다운로더에 절대 섞지 않음 |
| **로컬 저장소** | `files/vosk/` (음성 모델) | `files/smolvlm/` (별도) | 경로 겹치면 삭제/캐시 충돌 | 5절대로 경로 분리 |
| **권한** | 마이크/알림/배터리 | 카메라(기존 인증) | SmolVLM 은 추가 권한 불필요(카메라는 기존 인증이 이미 보유) | 신규 권한 추가 금지 |
| **백그라운드 서비스** | 음성 상시 백그라운드(화면 꺼져도) | SmolVLM 추론은 foreground 단발 | 백그라운드 음성 + 대형 추론 동시 → 메모리 경합/ANR | SmolVLM 은 **foreground, 단발, 음성 서비스와 동시 실행 지양**. 테스트 시 음성 OFF 우선 |
| **메모리/발열** | Vosk(경량) 상시 | SmolVLM 3세션 ~2GB peak | Z Flip3(8GB)에서 동시 로드 시 OOM/발열 | 세션 순차 로드/해제, 음성과 동시 미로드, 추론 후 세션 해제 |
| **카메라/이미지 인증 플로우** | (기존) | SmolVLM evidence 추출 | 기존 플로우에 잘못 끼면 오판/FP | **기존 인증 플로우 불변**. SmolVLM 은 별도 debug 화면에서만, Rule Engine/서버 판정과 분리 |
| **baseUrl/API** | api_client.dart 환경별 | SmolVLM 은 온디바이스(네트워크 불요) | baseUrl 변경/서버 판정 경로 오염 | SmolVLM debug 는 API 호출 안 함(로컬 evidence 로그만). baseUrl 로직 미변경 |

## 3. 안전한 브랜치 전략
```bash
# 1) Feature_CM 최신 반영 + 정상 동작 확인 (SmolVLM 손대기 전)
git fetch origin
git checkout Feature_CM
git pull --ff-only origin Feature_CM
#  → 앱 빌드/실행, 음성 비서·브리핑 정상 동작 확인(회귀 없음) 후에만 다음 단계

# 2) Feature_CM 에서 실험 브랜치 분기 (음성 기능 위에 얹되 격리)
git checkout -b feature/smolvlm-ondevice-from-feature-cm

# 3) SmolVLM 관련 변경은 이 브랜치에서만. 커밋은 debug 경로/asset 로더/문서에 한정.
#    Feature_CM 로 병합은 debug-only 검증 + 사용자 승인 후 별도 결정(현재는 병합 금지).
```
- **원칙**: 항상 Feature_CM 기준으로 분기. main/production 직접 수정 금지. 실험 브랜치는 언제든 폐기 가능.

## 4. debug-only 테스트 경로
- 기존 이미지 인증 플로우(camera_capture_service / verification_api / image_verification_screen)는 **그대로 유지**.
- SmolVLM 실행은 **개발자용 히든 화면/버튼**(예: 설정 > (디버그) On-device VLM Test, `kDebugMode` 또는 원격끄기 플래그로 게이트)에서만.
- 동작: 이미지 1장 선택/촬영 → 온디바이스 SmolVLM → **evidence JSON 만 화면/logcat 출력**. PASS/FAIL 판정·서버 전송·인증 상태 변경 **없음**.
- 프로덕션 인증 결과에 SmolVLM 출력이 절대 반영되지 않음(관찰 전용). Rule Engine/서버 판정 경로와 분리.

## 5. 모델 저장 경로 분리 (필수)
```
<app files dir>/
├── vosk/        ← Feature_CM 음성 모델(~48MB, 기존 로직이 관리)  ※ 건드리지 않음
└── smolvlm/     ← SmolVLM ONNX 자산(디버그 실험 전용)
     ├── decoder_model_merged_q4.onnx
     ├── vision_encoder_int8.onnx
     ├── embed_tokens_int8.onnx
     └── tokenizer/config...
```
- 두 다운로더/로더는 **완전 분리**. 공통 캐시/삭제 로직 공유 금지.
- SmolVLM 자산은 **자동 다운로드 금지** — 디버그 화면에서 명시적 버튼으로만 준비(또는 개발 단말에 수동 push).
- 음성 모델 다운로드 코드에 SmolVLM 다운로드를 끼워넣지 않는다(7절 금지사항).

## 6. 테스트 순서
1. **음성 비서 OFF 상태**에서 SmolVLM 단발 추론 (디버그 화면) → evidence JSON 로그 확인, 크래시/지연 측정.
2. **음성 비서 ON(백그라운드) 상태**에서 SmolVLM 단발 추론 → 동시 실행 충돌(ANR/오디오 끊김/추론 실패) 확인.
3. **앱 크래시 / 메모리 / 발열** 확인: 연속 3~5회 추론, `adb shell dumpsys meminfo`, 온도/배터리, 음성 인식 정상 여부.
4. 각 단계에서 **기존 인증 플로우 정상**(카메라 촬영→서버/Rule Engine 판정) 회귀 없음 확인.
- 통과 기준(실험 관점): 크래시 0, 음성 기능 회귀 0, peak memory ≤ 2GB, warm inference ≤ 3s(참고), 기존 인증 불변.

## 7. 금지 사항
- 기존 **verification API 교체/수정 금지**(엔드포인트·요청/응답 계약 불변).
- **Rule Engine core policy 수정 금지**.
- **음성 모델 다운로드 로직에 SmolVLM 다운로드 섞기 금지**(경로/트리거/캐시 분리).
- **production flow 연결 금지**(SmolVLM 출력이 실제 인증 판정/사용자 상태에 영향 주면 안 됨). 현재 SmolVLM 은 NO-GO(FP=9) 상태.
- minSdk/권한 등 Feature_CM 설정 임의 변경 금지(카메라 외 신규 권한 추가 금지).

## 8. rollback 방법
- 실험은 `feature/smolvlm-ondevice-from-feature-cm` 에 격리 → 문제 시 **브랜치 삭제/체크아웃 Feature_CM** 로 즉시 원복:
  ```bash
  git checkout Feature_CM
  git branch -D feature/smolvlm-ondevice-from-feature-cm   # 필요 시 폐기
  ```
- 단말: SmolVLM 자산은 `files/smolvlm/` 폴더 삭제로 완전 제거(음성 `vosk/` 무영향).
- 디버그 화면은 플래그로 즉시 비활성(빌드 재배포 없이 원격 플래그 가능하면 그걸로).
- Feature_CM 자체는 실험과 파일이 분리되어 있어 되돌릴 것이 없음(실험 커밋만 폐기).

## 9. Z Flip3 테스트 체크리스트
- [ ] Feature_CM pull 후 앱 빌드 성공(minSdk 30), 음성 비서/브리핑 정상.
- [ ] "포비 오늘 브리핑" 음성 호출 정상, 화면 꺼짐 상태 동작 정상.
- [ ] 마이크/알림/배터리 최적화 권한 정상, Vosk ~48MB 첫 실행 다운로드 정상.
- [ ] 실험 브랜치에서 debug 화면 진입 가능(프로덕션 UI 불변).
- [ ] SmolVLM 자산은 `files/smolvlm/` 에만 존재(음성 `vosk/` 와 분리 확인).
- [ ] 음성 OFF + SmolVLM 단발 추론: evidence JSON 로그 출력, 크래시 없음.
- [ ] 음성 ON + SmolVLM 추론: 음성 끊김/ANR/추론 실패 없음(경합 확인).
- [ ] peak memory ≤ ~2GB, 발열/배터리 급증 없음, 연속 추론 안정.
- [ ] 기존 카메라 이미지 인증 플로우(서버/Rule Engine 판정) 회귀 없음.
- [ ] SmolVLM 출력이 실제 인증 결과에 영향 없음(관찰 전용) 확인.
- [ ] baseUrl/API 설정 변경 없음, 서버 판정 경로 정상.

## 현 상태 메모 (중요)
- SmolVLM-500M real-only 평가 FP=9(모델 hallucination) → **온디바이스 단독 verify 보류**. 따라서 이번 통합은
  "프로덕션 연결"이 아니라 **debug-only 실험/계측**만을 목표로 한다. FP=0 달성(예: 서버 Qwen 확인 하이브리드) 전까지
  production flow 연결은 금지. 이 문서는 그 격리 상태에서 Feature_CM 음성 기능과의 무충돌을 보장하기 위한 계획이다.
