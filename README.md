# AI Secretary

> AI 기반 개인 맞춤형 일정 관리 및 생활 비서 서비스

## 📌 프로젝트 소개

AI Secretary는 사용자의 일정, 위치, 날씨, 인간관계, 감정 기록 등을 종합적으로 분석하여 개인 맞춤형 일정을 관리해주는 AI 비서 서비스입니다.

단순한 일정 관리 기능을 넘어 예약 추천, 일정 브리핑, 준비물 추천, 인간관계 관리, 감정 기반 생활 코칭 등을 제공하여 사용자의 일상을 더욱 효율적으로 관리하는 것을 목표로 합니다.

---

## ✨ 주요 기능

* 일정 생성 AI
* 예약 후보 추천 및 캘린더 등록
* 예약 문의 메시지 자동 생성
* 준비물 및 출발 알림
* AI 일정 요약(브리핑)
* 생일 및 기념일 선물 추천
* 인간관계 관리
* 상황 인식형 하루 브리핑
* 감정 기록 기반 생활 코칭

---

## 🏗 프로젝트 구조

```text
AI_Secretary/
├── backend/
├── frontend/
├── docs/
├── on_device/
├── prompts/
├── tests/
├── docker-compose.yml
└── README.md
```

---

## 🛠 Tech Stack

### Frontend

* Flutter
* Dart

### Backend

* FastAPI
* SQLAlchemy
* OpenAI API
* LangChain
* ChromaDB

### AI

* LLM
* RAG
* Sentence Transformers
* Transformers
* Recommendation System

### External API

* Google Calendar API
* Google Maps API
* Firebase Cloud Messaging
* Weather API

---

## ⚙ Development Environment

### Backend

* Python 3.11
* FastAPI

패키지 설치

```bash
cd backend

python -m venv AI_project

# Windows
.\AI_project\Scripts\Activate.ps1

pip install -r requirements.txt
```

Backend 실행

```bash
uvicorn main:app --reload
```

API Docs

```
http://127.0.0.1:8000/docs
```

---

### Frontend

Flutter 패키지 설치

```bash
cd frontend

flutter pub get
```

Flutter 실행

```bash
flutter run
```

---

## 👥 Team

| 역할       | 담당 |
| -------- | -- |
| Frontend |    |
| Backend  |    |
| AI       |    |
| UI/UX    |    |

