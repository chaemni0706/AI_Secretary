Vosk 한국어 모델 폴더
=====================

여기에 Vosk 한국어 "소형" 모델 zip 파일을 넣으세요 (오픈소스, 무료, 계정 불필요).

1) https://alphacephei.com/vosk/models 접속
2) Korean 항목의 소형 모델(예: vosk-model-small-ko-0.22) zip 다운로드
3) 다운로드한 zip 을 이 폴더에 그대로 저장
   - 파일명이 다르면 lib/services/hotword_service.dart 의 _modelAsset 경로를 맞춰주세요.

참고:
- 소형 모델은 대략 50MB 안팎이라 APK 용량이 그만큼 늘어납니다(전용 기기면 무방).
- 릴리즈 빌드 시 android/app/proguard-rules.pro 에 아래를 추가하세요(JNA 보호):
    -keep class com.sun.jna.* { *; }
    -keepclassmembers class * extends com.sun.jna.* { public *; }
