# AI-Reinvest

LangGraph 기반 AI 주식 리포트 자동 생성 시스템입니다.

AI-Reinvest는 FastAPI 백엔드, React 프론트엔드, OpenAI structured output, Chroma/langchain_chroma 기반 로컬 RAG, 그리고 `backend/flows/*/tool.py`의 직접 분석 노드를 조합해 종목별 투자 리포트를 생성하고 대시보드에서 확인하는 프로젝트입니다.

> 투자 리포트는 참고용입니다. 최종 투자 판단과 그 결과에 대한 책임은 사용자 본인에게 있습니다.

---

## Core Architecture

현재 런타임 흐름은 다음과 같습니다.

```text
FastAPI
-> pipelines/report_pipeline.py
-> LangGraph graphs/report_graph.py
-> ReportState
-> flows/*/tool.py direct nodes
-> OpenAI structured-output analysis
-> markdown report files
-> summary.md
-> React dashboard
```

LangGraph node 순서:

```text
validate_input
-> macro
-> accounting
-> research
-> youtube_rag
-> price
-> analysis
-> save_summary
-> finalize
```

주요 특징:

- `ReportState`가 종목별 실행 상태를 관리합니다.
- 여러 종목 생성 중 한 종목이 실패해도 다른 종목 처리를 계속합니다.
- macro 분석은 batch 단위로 1회만 실행되고 각 종목 state에 주입됩니다.
- 리포트 파일 생성과 summary 저장을 분리해 관리합니다.
- `summary_saved=True`까지 완료되어야 최종 `completed`로 판단합니다.
- `/api/report-status/{job_id}`는 `targets_status`로 종목별 진행 상태를 제공합니다.

---

## Direct Node Implementations

### Macro

- 파일: `backend/flows/macro/tool.py`
- deterministic macro data collection and interpretation
- 주요 출력:
  - `macro_json`
  - `macro_score`
  - `macro_score_reasons`
  - `macro_briefing`
- 해석 대상:
  - 원/달러 환율
  - 미국 10년물 금리
  - VIX, 미국시장 공포지수
  - Nasdaq
  - WTI 원유 가격
- 여러 종목 리포트 생성 시 batch에서 한 번만 실행됩니다.

### Accounting

- 파일: `backend/flows/accounting/tool.py`
- yfinance 기반 재무 데이터 수집
- `YFINANCE_CACHE_DIR`가 있으면 해당 경로를 사용하고, 없으면 OS temp 하위의 안전한 cache 경로를 사용합니다.
- 주요 출력:
  - `acc_data`
  - `revenue`
  - `net_income`
  - `fcf`
  - `fundamental_score`
  - `fundamental_score_reasons`
  - `financial_summary`
- 가격 계산과 markdown 가격 단위 호환성은 Python 로직이 통제합니다.

### Research

- 파일: `backend/flows/research/tool.py`
- 직접 Serper/news HTTP 경로를 사용합니다.
- 검색 결과를 단순 나열하지 않고 deterministic synthesis를 수행합니다.
- 주요 출력:
  - `research_json`
  - `sentiment`
  - `sentiment_score`
  - `momentum_strength`
  - `sentiment_reason`
  - `news_summary`
- 긍정/부정/중립 이슈를 검색 결과 기반으로 분류합니다.
- 검색 실패 또는 유효 뉴스 부족 시 fabricated news 없이 fallback을 반환합니다.

### Youtube RAG

- 파일: `backend/flows/youtube/tool.py`
- 로컬 YouTube transcript RAG를 검색합니다.
- Chroma read path는 `langchain_chroma.Chroma`를 사용합니다.
- report generation 중에는 기존 `chroma_db`를 읽기 전용으로 사용하며 DB rebuild/write를 수행하지 않습니다.
- content type을 구분합니다.
  - `SPECIFIC`
  - `MARKET`
  - `MINDSET`
  - `RISK`
  - `PSYCHOLOGY`
  - `GENERAL`
- `SPECIFIC` 근거가 있을 때만 종목 직접 인사이트로 다루고, 그 외에는 일반 시장 원칙이나 리스크 관리 원칙으로만 해석합니다.

### Analysis

- 파일: `backend/flows/analysis/tool.py`
- 직접 OpenAI structured-output 호출을 사용합니다.
- schema:
  - `DirectAnalysisOutput`
  - `DirectChartData`
- 시스템이 계산한 `investment_opinion`을 보존합니다.
- LLM은 제공된 데이터의 해석과 문장화를 담당하며, 가격/점수/차트/최종 의견을 임의로 바꾸지 못하도록 제한합니다.
- senior analyst report writing constraints와 hallucination 방어 규칙을 포함합니다.

---

## CrewAI Removal Status

- CrewAI는 active runtime에서 제거되었습니다.
- `crewai` / `crewai-tools`는 `backend/requirements.txt`에서 제거되었습니다.
- legacy `backend/flows/*/agent.py`와 `backend/flows/*/task.py` 파일도 삭제되었습니다.
- active execution은 `backend/flows/*/tool.py` 직접 구현만 사용합니다.
- 현재 리포트 생성 경로는 CrewAI를 import하거나 실행하지 않습니다.

---

## Hallucination Defense

AI-Reinvest는 리포트 품질을 높이되 LLM이 사실을 만들어내지 않도록 다음 원칙을 사용합니다.

- 사실, 숫자, 가격, 점수, 최종 투자 의견은 시스템 로직이 통제합니다.
- LLM은 제공된 `macro_json`, `acc_data`, `research_json`, `youtube_json`, 가격 기준을 설명할 수 있지만 새로운 사실을 만들 수 없습니다.
- `investment_opinion`은 시스템 채점 로직으로 계산되며, LLM 출력 후에도 시스템 값으로 보존됩니다.
- markdown heading, 가격표, `chart_data`, 리포트 구조는 deterministic Python renderer가 통제합니다.
- 뉴스의 숫자나 전망은 참고 신호이며 감사된 재무제표 사실로 취급하지 않습니다.
- YouTube의 일반 투자 원칙은 종목 직접 추천으로 해석하지 않습니다.
- 데이터가 없거나 약하면 단정하지 않고 보수적으로 표현합니다.
- 명시 연도 데이터가 없으면 `2023년 기준` 같은 calendar-year 표현 대신 `최근 기간`, `T 기준`, `최근 연도 기준`을 사용합니다.

---

## Chroma / Youtube RAG

- Chroma import는 `langchain_chroma.Chroma`를 사용합니다.
- 기존 `backend/chroma_db/` 경로는 유지합니다.
- 리포트 생성 중에는 기존 DB를 읽습니다.
- manual vector DB update/build scripts는 별도 운영 작업으로 남아 있습니다.
- live/upcoming YouTube 영상은 즉시 처리하지 않고 pending 로직으로 관리합니다.
- report generation 기본값은 다음과 같습니다.

```env
REPORT_GENERATION_YOUTUBE_UPDATE_ENABLED=false
```

pending 영상 dry-run:

```powershell
cd backend
python -B -m vector_db.process_pending_live_videos --dry-run
python -B -m vector_db.process_pending_live_videos --dry-run --max-items 1
```

pending 영상 수동 처리:

```powershell
cd backend
python -B -m vector_db.process_pending_live_videos --max-items 1
```

---

## Frontend Features

- 메인 대시보드 리포트 카드
- 상세 리포트 보기
- `chart_data` 기반 차트 시각화
- 리포트 생성 중 floating progress toast
- `targets_status` 기반 종목별 진행 상태 표시
- footer
- 오늘 날짜 unread 리포트의 `NEW` badge
- 국내 주식 / 미국 주식 label
- 미국 주식 가격의 원화 환산 표시
- 원화 환산은 frontend rendering 전용이며 markdown source에 강제로 넣지 않습니다.

---

## API Overview

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

`GET /api/report-status/{job_id}`는 기존 job 필드와 함께 optional `targets_status`를 제공합니다.

리포트 생성 흐름:

```text
React에서 종목 선택
-> POST /api/run-report
-> job_id 발급
-> FastAPI background task
-> LangGraph pipeline 실행
-> GET /api/report-status/{job_id} polling
-> targets_status로 종목별 진행 상태 확인
-> 완료 후 report list / dashboard refresh
```

---

## Project Structure

```text
backend/
  api.py
  main.py
  graphs/
  pipelines/
  schemas/
  services/
  flows/
    macro/
    accounting/
    research/
    youtube/
    analysis/
  vector_db/
  stock_search/
  transcripts/
  chroma_db/
  result/
    YYYY-MM-DD/
      summary.md
      종목별_리포트.md
  requirements.txt

frontend/
  src/
    features/
      app/
      layout/
      login/
      main/
      report/
      report-generator/
  package.json

README.md
DEV_LOG.md
```

---

## Environment Variables

`backend/.env` 예시:

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_ANALYSIS_MODEL=gpt-4o-mini
SERPER_API_KEY=your_serper_api_key
DATA_GO_KR_API_KEY=your_data_go_kr_api_key

ADMIN_USERNAME=your_login_username
ADMIN_PASSWORD=your_login_password
SESSION_SECRET=your_random_secret_key
COOKIE_SECURE=false

YOUTUBE_UPDATE_TIMEOUT_SECONDS=60
PENDING_YOUTUBE_PROCESS_TIMEOUT_SECONDS=180
REPORT_GENERATION_YOUTUBE_UPDATE_ENABLED=false

# Optional
YFINANCE_CACHE_DIR=C:\tmp\ai_reinvest_yfinance_cache
```

`frontend/.env` 예시:

```env
VITE_API_BASE_URL=http://localhost:8001
```

---

## Setup

### Backend

Windows:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
python -m pip install -r requirements.txt
```

Mac/Linux:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

Import check:

```powershell
python -B -c "import api; print('api import ok')"
python -B -c "import main; print('main import ok')"
python -B -c "from langchain_chroma import Chroma; print('langchain_chroma import ok')"
```

Run backend:

```powershell
python -m uvicorn api:app --host 127.0.0.1 --port 8001 --reload
```

### Frontend

```powershell
cd frontend
npm install
npm run start
```

`package.json`의 `start`는 Vite dev server를 실행합니다.

---

## Stock Search Data

국내/미국 종목 검색 데이터는 수동 갱신할 수 있습니다.

```powershell
cd backend
python .\stock_search\update_krx_stock_master.py
python .\stock_search\update_us_stock_master.py
python .\stock_search\rebuild_stock_master.py
```

별칭은 다음 파일에서 관리합니다.

```text
backend/stock_search/data/stock_alias_ko.json
```

---

## Manual YouTube / Vector DB Operations

리포트 생성 중에는 기본적으로 YouTube update / Chroma rebuild를 수행하지 않습니다. 필요할 때만 아래 명령을 수동 실행합니다.

최신 영상 ID 갱신:

```powershell
cd backend
python .\vector_db\fetch_latest_youtube_ids.py
```

transcript 추출:

```powershell
cd backend
python -B -m vector_db.update_youtube_db
```

Chroma DB incremental build:

```powershell
cd backend
python .\vector_db\build_vector_db.py
```

---

## Validation Commands

Backend:

```powershell
cd backend
python -B -m py_compile main.py api.py graphs\report_graph.py pipelines\report_pipeline.py schemas\report_state.py services\summary_service.py services\report_file_service.py services\report_metadata_service.py flows\macro\tool.py flows\accounting\tool.py flows\research\tool.py flows\youtube\tool.py flows\analysis\tool.py vector_db\build_vector_db.py

python -B -c "import api; print('api import ok')"
python -B -c "import main; print('main import ok')"
python -B -c "from langchain_chroma import Chroma; print('langchain_chroma import ok')"
```

Frontend:

```powershell
cd frontend
npm.cmd run build
```

---

## Report Output

리포트는 날짜별 폴더에 저장됩니다.

```text
backend/result/YYYY-MM-DD/
  summary.md
  삼성전자_005930.KS.md
  테슬라_TSLA.md
  ...
```

- `summary.md`: 메인 화면 카드 데이터
- 종목별 `.md`: 상세 리포트 데이터
- 같은 날짜의 같은 종목은 기존 의도대로 upsert/갱신됩니다.
- summary 저장 성공까지 완료되어야 최종 `completed`로 판단합니다.

---

## Future Work

- production deployment와 background worker 분리
- `main.py` 추가 slimming
- pending YouTube processing scheduler 구성
- requirements slimming과 dependency audit
- frontend bundle size optimization
- 더 많은 종목과 시장 상황에 대한 리포트 품질 평가 케이스 추가

---

## Disclaimer

이 프로젝트가 생성하는 리포트는 투자 참고용입니다. 데이터 수집, 검색, LLM 분석, RAG 결과에는 오류나 누락이 있을 수 있습니다. 최종 투자 판단과 그 결과에 대한 책임은 사용자 본인에게 있습니다.
