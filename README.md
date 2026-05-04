# 📈 AI-Reinvest: Multi-Agent Stock Analysis System

CrewAI, OpenAI LLM, RAG(Retrieval-Augmented Generation), FastAPI, React를 활용하여 주식 시장 조사, 재무 분석, 유튜브 기반 투자 인사이트, 최종 리포트 생성을 자동화하는 AI 멀티 에이전트 시스템입니다.

본 프로젝트는 단순한 리포트 생성기를 넘어, **거시경제 분석 → 재무제표 검증 → 뉴스 리서치 → 유튜브 RAG 검색 → 최종 투자 의견 생성 → React 대시보드 시각화**까지 하나의 파이프라인으로 연결하는 것을 목표로 합니다.

---

## ✨ 핵심 기능 (Core Features)

### 🤖 Multi-Agent 협업 아키텍처

- `MacroAgent`
  - 환율, 미국 10년물 금리, 나스닥, WTI, VIX 등 글로벌 거시경제 지표 분석
- `AccountingAgent`
  - 재무제표, 수익성, 부채비율, 현금흐름, 이동평균선 기반 정량 분석
- `ResearchAgent`
  - 타겟 종목의 최신 뉴스 및 시장 센티먼트 수집
- `YoutubeAgent`
  - 로컬 ChromaDB 기반 RAG 검색으로 유튜브 투자 인사이트 추출
- `AnalysisAgent`
  - 거시경제, 재무, 뉴스, 유튜브 인사이트를 종합하여 최종 투자 리포트 작성

### 🛡️ LLM 환각 방어 로직

- LLM이 숫자와 방향성을 임의로 판단하지 않도록 Python 기반 사전 채점 로직 적용
- 재무 데이터 검증 실패 시 분석 중단
- 3개년 연속 적자, FCF 마이너스, 부채비율 과다 등 기계적 FAIL 룰 적용
- 시스템 점수와 구루 점수를 분리하여 최종 투자 의견 산출

### 🧠 YouTube RAG 기반 투자 인사이트

- 유튜브 자막 텍스트를 로컬 ChromaDB에 저장
- 신규 영상만 감지하여 증분 업데이트
- 기존 임베딩 데이터는 유지하여 중복 임베딩 비용 최소화
- 유튜브 발언의 성격을 구분
  - 종목 직접 발언
  - 시장 원칙
  - 리스크 관리
  - 투자 심리
  - 일반 시황

### 🖥️ React + FastAPI 대시보드

- FastAPI API 서버 기반 리포트 조회
- React에서 마크다운 리포트 렌더링
- 종목별 리포트 카드 자동 분리
- 상세 리포트 페이지 제공
- 재무 차트 데이터 시각화
- 한국 주식과 미국 주식 단위 구분
  - 한국 주식: 조 원
  - 미국 주식: Billion USD
- 리포트 생성 요청 후 job 상태 polling
- 완료 시 메인 화면 자동 새로고침

### 🔐 로그인 및 세션 보호

- FastAPI 기반 로그인 API
- HttpOnly 쿠키 기반 세션 관리
- 리포트 조회, 리포트 생성, job 상태 조회 API 보호
- 로그인하지 않은 사용자는 리포트 생성 및 조회 불가
- `/api/me`를 통한 로그인 상태 확인

### 🧾 종목 검색 및 리포트 생성

- React에서 종목 검색 후 선택
- FastAPI에서 기본 종목 목록 제공
- 내부 JSON 기반 종목 검색
- 내부 DB에 없는 영문 티커/영문 종목명은 Yahoo Finance fallback 검색
- 사용자가 선택한 종목은 cache JSON에 저장 가능
- 선택한 종목을 기반으로 백그라운드 리포트 생성 job 실행

---

## 🏗️ 시스템 아키텍처 (Folder Structure)

```text
ai-reinvest/
├── backend/
│   ├── api.py
│   ├── main.py
│   ├── flows/
│   │   ├── accounting/
│   │   ├── analysis/
│   │   ├── macro/
│   │   ├── research/
│   │   └── youtube/
│   ├── vector_db/
│   │   ├── fetch_latest_youtube_ids.py
│   │   ├── update_youtube_db.py
│   │   ├── build_vector_db.py
│   │   └── ...
│   ├── stock_search/
│   │   ├── __init__.py
│   │   ├── stock_master.json
│   │   ├── stock_search_cache.json
│   │   └── search_store.py
│   ├── result/
│   │   └── YYYY-MM-DD/
│   │       ├── summary.md
│   │       └── 종목별_리포트.md
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── index.jsx
│   │   └── features/
│   │       ├── app/
│   │       ├── layout/
│   │       ├── login/
│   │       ├── main/
│   │       ├── report/
│   │       ├── report-generator/
│   │       └── root.css
│   ├── public/
│   ├── package.json
│   └── package-lock.json
│
├── DEV_LOG.md
├── .gitignore
└── README.md
```

## 🚀 시작하기 (Getting Started)

**0. 저장소 클론**
> git clone <repository-url>
> cd ai-reinvest

**1. 환경 설정:** `backend` 폴더 경로에 `.env` 파일을 생성하고 API 키를 등록합니다.

# LLM / Search API
> OPENAI_API_KEY=your_openai_api_key
> SERPER_API_KEY=your_serper_api_key

# Login / Session
> ADMIN_USERNAME=your_login_username
> ADMIN_PASSWORD=your_login_password
> SESSION_SECRET=your_random_secret_key

# Local / Deploy Cookie Option
> COOKIE_SECURE=false

**2. 백엔드 가상환경 생성 및 활성화:**

- **Windows:**
  > cd backend
  > python -m venv venv(처음 한번만 실행)
  > .\venv\Scripts\activate

- **Mac/Linux:**
  > cd backend
  > python3 -m venv venv(처음 한번만 실행)
  > source venv/bin/activate

**3. 백엔드 패키지 설치:**
> python -m pip install -r requirements.txt

**4. 유튜브 지식 베이스(DB) 구축 (2단계 시스템):**
`backend` 폴더 위치에서 스크립트를 실행하여 유튜브 오디오를 텍스트로 변환한 뒤 DB를 구축합니다.

- **Step 4-1. 오디오 추출 및 텍스트 변환:**
  ※ 💡 **이미 텍스트 변환 작업이 완료되어 제공되므로, 이 단계는 건너뛰고 바로 Step 4-2로 진행하시길 바랍니다.**

  ```bash
  python .\vector_db\update_youtube_db.py
  ```
  ※ `transcripts/` 폴더에 영상별 텍스트 파일이 개별 저장됩니다. (OpenAI Whisper API 요금 발생 주의)
  
  ```bash
  python .\vector_db\update_youtube_db_local.py
  ```
  ※ 무료 변환을 원할 경우 로컬 PC(GPU)에서 `faster-whisper` 모델 등을 사용하도록 코드를 커스텀할 수 있습니다.
  ※ ⚠️ **소요 시간 참고:** 1시간 분량 영상 400개, 10분 분량 영상 415개 기준, RTX 3070 GPU 환경에서 전체 변환에 약 3일이 소요되었습니다. 데이터 양과 PC 스펙에 따라 시간이 오래 걸릴 수 있습니다.

- **Step 4-2. 로컬 벡터 DB 생성:**
  > python .\vector_db\build_vector_db.py
  ※ 추출된 텍스트들을 쪼개어(Chunking) `chroma_db/` 폴더에 RAG 검색용 벡터 DB를 최종 완성합니다.

**5. 시스템 실행 (AI 분석 및 API 서버):**
> python api.py

**6. 프론트엔드 (React) 실행:**
새로운 터미널을 열고 `frontend` 폴더로 이동하여 패키지를 설치한 후 개발 서버를 엽니다.
> cd frontend
> npm install
> npm start

## 📚 개발 일지 및 트러블슈팅

이 프로젝트를 구축하며 겪은 LLM 쿼터 이슈, API 결측치 문제, 환각 제어 로직 등 상세한 엔지니어링 기록은 DEV_LOG.md에서 확인하실 수 있습니다.
