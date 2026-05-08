# 📈 AI-Reinvest: LangGraph 기반 AI 주식 리포트 자동화 시스템

OpenAI LLM, CrewAI Agent/Task, LangGraph, RAG(Retrieval-Augmented Generation), FastAPI, React를 활용하여  
**거시경제 분석 → 재무제표 검증 → 뉴스 리서치 → 유튜브 RAG 검색 → 최종 투자 의견 생성 → React 대시보드 시각화**까지 자동화하는 AI 주식 리포트 시스템입니다.

현재 구조는 **LangGraph가 전체 리포트 생성 흐름을 제어하고, 일부 분석 단계 내부에서는 CrewAI Agent/Task를 사용하는 하이브리드 구조**입니다.  
향후 CrewAI 의존성을 단계적으로 제거하고, LangGraph node + 직접 함수 호출 + OpenAI structured output 중심 구조로 전환할 예정입니다.

---

## ✨ 핵심 기능 (Core Features)

### 🧭 LangGraph 기반 리포트 생성 파이프라인

리포트 생성 흐름은 LangGraph `StateGraph(ReportState)` 기반으로 관리됩니다.

```text
validate_input
→ macro
→ accounting
→ research
→ youtube_rag
→ price
→ analysis
→ save_summary
→ finalize
```

주요 특징:

- 종목별 `ReportState` 기반 상태 관리
- 여러 종목 생성 시 한 종목 실패가 전체 실패로 이어지지 않도록 격리
- `summary_saved=True`까지 완료되어야 최종 `completed` 처리
- `report_generated`, `partial_failed`, `failed` 등 중간 상태 구분
- `/api/report-status/{job_id}`를 통해 종목별 진행 상태 실시간 조회
- 다중 종목 생성 시 공통 macro 분석은 batch당 1회만 실행

---

### 🤖 CrewAI Agent/Task 기반 분석 모듈

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

> 향후 계획: CrewAI Agent/Task를 Macro → Accounting → Research → Youtube RAG → Analysis 순서로 직접 함수화하고, 마지막에 `crewai` / `crewai-tools` 의존성을 제거할 예정입니다.

---

### 🛡️ LLM 환각 방어 로직

- LLM이 숫자와 방향성을 임의로 판단하지 않도록 Python 기반 사전 채점 로직 적용
- 재무 데이터 검증 실패 시 분석 중단 처리
- 3개년 연속 적자, FCF 마이너스, 부채비율 과다 등 기계적 FAIL 룰 적용
- 시스템 점수와 구루 점수를 분리하여 최종 투자 의견 산출
- 최종 리포트 작성 단계에서는 시스템이 산출한 투자 의견과 가격 가이드를 그대로 사용하도록 제한

---

### 🧠 YouTube RAG 기반 투자 인사이트

- 유튜브 영상 텍스트를 로컬 `transcripts/`에 저장
- `text-embedding-3-small`로 ChromaDB에 임베딩
- 신규 영상만 감지하여 증분 업데이트
- 이미 임베딩된 영상은 `source(video_id)` 기준으로 스킵
- 라이브/예약 영상은 즉시 처리하지 않고 pending 목록으로 분리
- 유튜브 발언의 성격을 구분
  - 종목 직접 발언
  - 시장 원칙
  - 리스크 관리
  - 투자 심리
  - 일반 시황

---

### 🖥️ React + FastAPI 대시보드

- FastAPI API 서버 기반 리포트 조회
- React에서 마크다운 리포트 렌더링
- 종목별 최신 리포트 카드 자동 분리
- 상세 리포트 페이지 제공
- 재무 차트 데이터 시각화
- 한국 주식과 미국 주식 단위 구분
  - 한국 주식: 조 원
  - 미국 주식: Billion USD
- 미국 주식 가격에는 원화 환산 표시
  - 예: `$411.79 (약 599,400원)`
  - 환산 기준: `1달러 = 1,455.62원`
- 리포트 생성 요청 후 job 상태 polling
- floating toast 1개에서 종목별 진행 상태 표시
- 완료 시 메인 화면 자동 새로고침
- 모든 주요 화면에 footer 표시
- 읽지 않은 오늘 날짜 리포트에 `NEW` badge 표시
- 상세 리포트 제목 아래 기준 날짜/시간 표시
  - 예: `기준: 2026-05-08 10:38`

---

### 🧾 종목 검색 및 리포트 생성

- React에서 종목 검색 후 선택
- 여러 종목을 한 번에 선택하여 리포트 생성 요청
- FastAPI에서 기본 종목 목록 제공
- 내부 JSON 기반 종목 검색
- KRX 공공데이터포털 API 기반 한국 주식 종목 목록 자동 갱신
- NASDAQ Trader Symbol Directory 기반 미국 주식 종목 목록 자동 갱신
- 한국 주식과 미국 주식 통합 검색 지원
- 한글 별칭 기반 미국 주식 검색 지원
  - 예: `테슬라` → `TSLA`
  - 예: `엔비디아` → `NVDA`
  - 예: `팔란티어` → `PLTR`
- 검색 결과 점수 기반 정렬
  - 티커 정확 일치 우선
  - 회사명 정확 일치 우선
  - 별칭/키워드 일치 우선
- 선택한 종목은 `stock_search_cache.json`에 저장되어 이후 검색 후보로 활용

---

## 🏗️ 시스템 아키텍처 (Folder Structure)

```text
ai-reinvest/
├── backend/
│   ├── api.py
│   ├── main.py
│   ├── graphs/
│   │   ├── __init__.py
│   │   └── report_graph.py
│   ├── pipelines/
│   │   ├── __init__.py
│   │   └── report_pipeline.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── report_state.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── report_file_service.py
│   │   ├── report_metadata_service.py
│   │   └── summary_service.py
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
│   │   ├── process_pending_live_videos.py
│   │   ├── youtube_update_guard.py
│   │   ├── pending_live_videos.json
│   │   └── ...
│   ├── stock_search/
│   │   ├── __init__.py
│   │   ├── search_store.py
│   │   ├── update_krx_stock_master.py
│   │   ├── update_us_stock_master.py
│   │   ├── rebuild_stock_master.py
│   │   ├── suggest_alias_from_cache.py
│   │   └── data/
│   │       ├── stock_master_kr.json
│   │       ├── stock_master_us.json
│   │       ├── stock_master.json
│   │       ├── stock_alias_ko.json
│   │       └── stock_search_cache.json
│   ├── transcripts/
│   ├── result/
│   │   └── YYYY-MM-DD/
│   │       ├── summary.md
│   │       └── 종목별_리포트.md
│   ├── chroma_db/
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
├── DEV_LOG.md
└── README.md
```

---

## 🚀 시작하기 (Getting Started)

### 0. 저장소 클론

```bash
git clone <repository-url>
cd ai-reinvest
```

---

### 1. 백엔드 환경 설정

`backend` 폴더 경로에 `.env` 파일을 생성하고 API 키를 등록합니다.

```env
# LLM / Search API
OPENAI_API_KEY=your_openai_api_key
SERPER_API_KEY=your_serper_api_key

# KRX 공공데이터포털 API
DATA_GO_KR_API_KEY=your_data_go_kr_api_key

# Login / Session
ADMIN_USERNAME=your_login_username
ADMIN_PASSWORD=your_login_password
SESSION_SECRET=your_random_secret_key

# Local / Deploy Cookie Option
COOKIE_SECURE=false

# YouTube update timeout
YOUTUBE_UPDATE_TIMEOUT_SECONDS=60
PENDING_YOUTUBE_PROCESS_TIMEOUT_SECONDS=180
```

`DATA_GO_KR_API_KEY`는 공공데이터포털의 금융위원회_KRX상장종목정보 API 활용 신청 후 발급받은 인증키를 사용합니다.

---

### 2. 백엔드 가상환경 생성 및 활성화

Windows:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
```

Mac/Linux:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

---

### 3. 백엔드 패키지 설치

```powershell
python -m pip install -r requirements.txt
```

> 주의: 현재는 CrewAI가 아직 실행 경로에 남아 있으므로 `chromadb~=1.1.0` 계열을 유지합니다.  
> `langchain-chroma` 전환은 CrewAI 제거 이후 진행할 예정입니다.

---

### 4. 종목 검색 DB 구축 및 갱신

한국 주식과 미국 주식 종목 데이터를 각각 수집한 뒤, 최종적으로 하나의 `stock_master.json`으로 통합합니다.

#### Step 4-1. 한국 주식(KRX) 종목 갱신

```powershell
python .\stock_search\update_krx_stock_master.py
```

생성 파일:

```text
backend/stock_search/data/stock_master_kr.json
```

#### Step 4-2. 미국 주식(US) 종목 갱신

```powershell
python .\stock_search\update_us_stock_master.py
```

생성 파일:

```text
backend/stock_search/data/stock_master_us.json
```

#### Step 4-3. KR + US + 한글 별칭 통합

```powershell
python .\stock_search\rebuild_stock_master.py
```

생성 파일:

```text
backend/stock_search/data/stock_master.json
```

#### Step 4-4. 한글 별칭 관리

미국 주식은 기본적으로 티커와 영문 회사명으로 검색됩니다.  
한글 검색을 지원하려면 아래 파일에 별칭을 추가합니다.

```text
backend/stock_search/data/stock_alias_ko.json
```

예시:

```json
{
  "TSLA": ["테슬라", "tesla"],
  "NVDA": ["엔비디아", "엔비", "nvidia"],
  "AAPL": ["애플", "apple"],
  "MSFT": ["마이크로소프트", "마소", "microsoft"],
  "PLTR": ["팔란티어", "palantir"],
  "SOFI": ["소파이", "sofi"]
}
```

별칭을 수정한 뒤에는 최종 DB를 다시 생성합니다.

```powershell
python .\stock_search\rebuild_stock_master.py
```

#### Step 4-5. 캐시 기반 별칭 후보 확인

```powershell
python .\stock_search\suggest_alias_from_cache.py
```

`stock_search_cache.json`에 쌓인 한글 키워드를 기반으로 `stock_alias_ko.json`에 추가할 후보를 출력합니다.

---

### 5. 유튜브 지식 베이스 구축

`backend` 폴더 위치에서 스크립트를 실행합니다.

#### Step 5-1. 최신 유튜브 영상 ID 갱신

```powershell
python .\vector_db\fetch_latest_youtube_ids.py
```

#### Step 5-2. 오디오 추출 및 텍스트 변환

```powershell
python -B -m vector_db.update_youtube_db
```

`transcripts/` 폴더에 영상별 텍스트 파일이 저장됩니다.

> 오디오 다운로드 및 Whisper/STT 작업은 시간이 오래 걸릴 수 있습니다.  
> 이미 텍스트 변환이 완료되어 제공되는 경우 이 단계는 건너뛸 수 있습니다.

#### Step 5-3. pending live 영상 확인

```powershell
python -B -m vector_db.process_pending_live_videos --dry-run
python -B -m vector_db.process_pending_live_videos --dry-run --max-items 1
```

#### Step 5-4. pending live 영상 수동 처리

```powershell
python -B -m vector_db.process_pending_live_videos --max-items 1
```

#### Step 5-5. 로컬 벡터 DB 생성 / 증분 업데이트

```powershell
python .\vector_db\build_vector_db.py
```

추출된 텍스트를 chunking하여 `chroma_db/` 폴더에 RAG 검색용 벡터 DB를 생성합니다.  
이미 임베딩된 영상은 metadata의 `source(video_id)` 기준으로 스킵합니다.

---

### 6. 백엔드 API 서버 실행

```powershell
python api.py
```

또는 개발 중에는:

```powershell
python -m uvicorn api:app --host 127.0.0.1 --port 8001 --reload
```

---

### 7. 프론트엔드 환경 설정

`frontend` 폴더 경로에 `.env` 파일을 생성하고 백엔드 API 주소를 등록합니다.

```env
VITE_API_BASE_URL=http://localhost:8001
```

Vite 환경변수는 반드시 `VITE_`로 시작해야 합니다.

---

### 8. 프론트엔드 실행

```powershell
cd frontend
npm install
npm run dev
```

package.json 설정에 따라 `npm run start`를 사용하는 경우도 있습니다.

```powershell
npm run start
```

---

## 🧪 검증 명령

### 백엔드 정적 검증

```powershell
cd C:\test\backend
.\venv\Scripts\activate

python -B -m py_compile main.py api.py graphs\report_graph.py pipelines\report_pipeline.py services\summary_service.py services\report_file_service.py schemas\report_state.py

python -B -c "import api; print('api import ok')"
```

### 프론트 빌드 검증

```powershell
cd C:\test\frontend
npm run build
```

### pending live dry-run

```powershell
cd C:\test\backend
.\venv\Scripts\activate

python -B -m vector_db.process_pending_live_videos --dry-run
```

---

## 📊 리포트 저장 구조

리포트는 날짜별 폴더에 저장됩니다.

```text
backend/result/YYYY-MM-DD/
├── summary.md
├── 삼성전자_005930.KS.md
├── 테슬라_TSLA.md
└── ...
```

- `summary.md`: 메인 화면 요약 카드용
- `회사명_티커.md`: 상세 리포트용
- 같은 날짜에 동일 티커를 다시 생성하면 최신 리포트로 갱신
- summary 저장 성공까지 완료되어야 최종 `completed`로 판단

---

## 🧩 API 개요

주요 API:

```text
POST /api/login
POST /api/logout
GET  /api/me

GET  /api/reports
GET  /api/reports/{date}/{filename}

GET  /api/stock-options
GET  /api/stock-search

POST /api/run-report
GET  /api/report-status/{job_id}
```

리포트 생성 흐름:

```text
프론트에서 종목 선택
→ POST /api/run-report
→ job_id 발급
→ 백그라운드에서 LangGraph pipeline 실행
→ GET /api/report-status/{job_id} polling
→ 완료 시 리포트 목록/메인 화면 자동 새로고침
```

---

## 🗺️ 향후 작업 계획

### 1. CrewAI 제거 전환

현재는 LangGraph + CrewAI 하이브리드 구조입니다.

향후 순서:

```text
1. CrewAI Agent/Task별 실제 역할 정리
2. Macro node 직접 함수화
3. Accounting node 직접 함수화
4. Research node 직접 함수화
5. Youtube RAG node 직접 함수화
6. Analysis node를 OpenAI structured output 직접 호출로 변경
7. crewai / crewai-tools 제거
8. chromadb / langchain-chroma 최신화
```

### 2. Chroma 최신화

현재는 CrewAI의 `chromadb~=1.1.0` 요구사항 때문에 `langchain_community.vectorstores.Chroma`를 유지합니다.

CrewAI 제거 이후:

```python
from langchain_chroma import Chroma
```

구조로 전환하고, `chromadb`도 최신 호환 버전으로 정리할 예정입니다.

### 3. 배포용 background job 구조 정리

현재는 로컬 개발 중심 구조입니다.  
배포 시에는 리포트 생성 job, YouTube update, pending live 처리 등을 별도 worker/background scheduler로 분리할 예정입니다.

---

## 📚 개발 일지 및 트러블슈팅

이 프로젝트를 구축하며 겪은 LLM 쿼터 이슈, API 결측치 문제, 환각 제어 로직, LangGraph 전환, YouTube live 처리, 종목별 진행 UI, ChromaDB 버전 충돌 등 상세한 엔지니어링 기록은 `DEV_LOG.md`에서 확인할 수 있습니다.
