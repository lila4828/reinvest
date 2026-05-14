# AI-Reinvest

LangGraph 기반 AI 주식 리포트 자동 생성 시스템입니다.

FastAPI 백엔드, React 프론트엔드, OpenAI structured output, Chroma/langchain_chroma 기반 로컬 RAG, 그리고 직접 함수형 분석 노드를 조합해 종목별 투자 리포트를 생성하고 대시보드에서 확인합니다.

CrewAI는 이전 구현에서 사용하던 방식입니다. 현재 active runtime에서는 CrewAI를 사용하지 않으며, `backend/flows/*/agent.py`, `backend/flows/*/task.py` 파일은 참고용 legacy 파일로만 남아 있을 수 있습니다.

> 투자 리포트는 참고용입니다. 최종 투자 판단과 책임은 사용자 본인에게 있습니다.

---

## Core Architecture

현재 런타임 흐름은 다음과 같습니다.

```text
FastAPI
-> pipelines/report_pipeline.py
-> LangGraph graphs/report_graph.py
-> ReportState
-> direct analysis nodes
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

- `ReportState`로 종목별 실행 상태를 관리합니다.
- 여러 종목 생성 시 한 종목 실패가 전체 실패로 번지지 않도록 격리합니다.
- macro 분석은 batch 단위로 1회 실행한 뒤 각 종목 state에 주입합니다.
- `summary_saved=True`까지 완료되어야 최종 `completed`로 처리합니다.
- `/api/report-status/{job_id}`는 `targets_status`로 종목별 진행 상태를 제공합니다.

---

## Analysis Steps

### Macro

- `collect_macro_data()` 직접 함수 경로를 사용합니다.
- batch-level one-time execution 구조입니다.
- 주요 출력:
  - `macro_json`
  - `macro_score`
  - `macro_score_reasons`

### Accounting

- `collect_financial_data()` 직접 함수 경로를 사용합니다.
- yfinance cache는 `YFINANCE_CACHE_DIR`이 있으면 그 값을 사용하고, 없으면 temp 경로의 `ai_reinvest_yfinance_cache`를 사용합니다.
- 주요 출력:
  - `acc_data`
  - `fundamental_score`
  - `fundamental_score_reasons`
  - chart source fields: `revenue`, `net_income`, `fcf`

### Research

- CrewAI 없이 Serper/news HTTP 검색 경로를 직접 사용합니다.
- 주요 출력:
  - `research_json`
  - `sentiment`

### Youtube RAG

- 로컬 YouTube 검색 도구와 `langchain_chroma.Chroma` read path를 직접 사용합니다.
- 기존 `chroma_db/`를 재사용합니다.
- 리포트 생성 중에는 기본적으로 수동 YouTube update나 Chroma rebuild를 실행하지 않습니다.

### Analysis

- OpenAI structured-output 직접 호출을 사용합니다.
- 시스템이 계산한 `investment_opinion`을 유지하고, LLM이 임의로 투자 의견을 덮어쓰지 않도록 합니다.
- 기존 markdown heading, 가격 라벨, `chart_data` 구조와 호환되도록 렌더링합니다.

---

## CrewAI Removal Status

- CrewAI는 active runtime에서 제거되었습니다.
- `crewai`, `crewai-tools`는 `backend/requirements.txt`에서 제거되었습니다.
- active execution path는 CrewAI를 import하지 않습니다.
- legacy `agent.py` / `task.py` 파일은 참고용으로만 남아 있을 수 있습니다.
- legacy 파일은 현재 report generation 경로에서 import되지 않습니다.

---

## Chroma Status

- Chroma integration은 `langchain_chroma.Chroma`를 사용합니다.
- 기존 `backend/chroma_db/` 경로를 유지합니다.
- `persist_directory`와 `embedding_function` 사용 방식은 유지합니다.
- `backend/vector_db/build_vector_db.py`는 사용자가 직접 실행할 때만 incremental embedding을 수행합니다.
- report generation은 기존 DB를 읽는 경로를 사용합니다.
- manual YouTube update / vector DB build scripts는 별도 운영 작업으로 남아 있습니다.

---

## YouTube Live / Pending Behavior

- live/upcoming 영상은 즉시 처리하지 않고 `backend/vector_db/pending_live_videos.json`에 저장합니다.
- pending item은 `eligible_at` 이후 처리 대상이 됩니다.
- 아직 live/upcoming 상태이면 `eligible_at`을 연장하고, 무한 재시도를 막기 위해 attempts/status를 기록합니다.
- 리포트 생성은 live/upcoming 영상 때문에 대기하지 않습니다.
- 기본값:

```env
REPORT_GENERATION_YOUTUBE_UPDATE_ENABLED=false
```

pending 영상 수동 확인:

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
- `chart_data` 기반 실적 차트 시각화
- 리포트 생성 중 floating progress toast
- `targets_status` 기반 종목별 진행 상태 표시
- footer
- 오늘 날짜 unread 리포트에만 `NEW` badge 표시
- 국내 주식 / 미국 주식 label 표시
- 미국 주식 가격의 원화 환산 표시
- 상세 리포트 기준 날짜/시간 표시

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

리포트 생성 흐름:

```text
React에서 종목 선택
-> POST /api/run-report
-> job_id 발급
-> FastAPI background task
-> LangGraph pipeline 실행
-> GET /api/report-status/{job_id} polling
-> targets_status로 종목별 진행 상태 확인
-> 완료 후 report list / main dashboard refresh
```

---

## Project Structure

```text
backend/
  api.py
  main.py
  graphs/
    report_graph.py
  pipelines/
    report_pipeline.py
  schemas/
    report_state.py
  services/
    report_file_service.py
    report_metadata_service.py
    summary_service.py
  flows/
    macro/
      tool.py
      agent.py        # legacy reference
      task.py         # legacy reference
    accounting/
      tool.py
      agent.py        # legacy reference
      task.py         # legacy reference
    research/
      tool.py
      agent.py        # legacy reference
      task.py         # legacy reference
    youtube/
      tool.py
      agent.py        # legacy reference
      task.py         # legacy reference
    analysis/
      agent.py        # legacy reference
      task.py         # legacy reference
  vector_db/
    fetch_latest_youtube_ids.py
    update_youtube_db.py
    build_vector_db.py
    process_pending_live_videos.py
    youtube_update_guard.py
    pending_live_videos.json
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

`package.json`에서 `start`는 Vite dev server를 실행합니다.

---

## Stock Search Data

국내/미국 종목 검색 데이터를 갱신할 수 있습니다.

```powershell
cd backend
python .\stock_search\update_krx_stock_master.py
python .\stock_search\update_us_stock_master.py
python .\stock_search\rebuild_stock_master.py
```

한국어 별칭은 다음 파일에서 관리합니다.

```text
backend/stock_search/data/stock_alias_ko.json
```

---

## Manual YouTube / Vector DB Operations

리포트 생성 중에는 기본적으로 YouTube update / Chroma rebuild를 수행하지 않습니다. 필요한 경우 아래 명령을 수동으로 실행합니다.

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
python -B -m py_compile main.py api.py graphs\report_graph.py pipelines\report_pipeline.py schemas\report_state.py services\summary_service.py services\report_file_service.py services\report_metadata_service.py flows\macro\tool.py flows\accounting\tool.py flows\research\tool.py flows\youtube\tool.py vector_db\build_vector_db.py

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

## Regression Test Summary

CrewAI runtime 제거와 `langchain_chroma` 전환 이후 실제 API 회귀 테스트를 수행했습니다.

- 1-stock generation: 삼성전자
- 2-stock generation: SK하이닉스 + 테슬라
- 결과: completed
- `summary_saved`: true
- 2-stock batch에서 macro batch-once 확인
- markdown heading / price label / chart_data 확인
- 신규 생성 파일에서 mojibake 없음 확인

투자 정확도를 보장한다는 의미는 아니며, 런타임과 출력 호환성 검증 결과입니다.

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

- 배포 환경에서 background worker / scheduler 분리
- legacy CrewAI `agent.py` / `task.py` 파일 정리
- requirements 추가 slimming
- README / DEV_LOG 지속 관리
- pending YouTube video 처리용 production scheduler 구성
- 프론트 bundle size 최적화

CrewAI active runtime removal은 완료되었고, 남은 작업은 legacy reference 정리와 운영 안정화입니다.

---

## Disclaimer

이 프로젝트가 생성하는 리포트는 투자 참고용입니다. 데이터 수집, 검색, LLM 분석, RAG 결과에는 오류나 누락이 있을 수 있습니다. 최종 투자 판단과 그 결과에 대한 책임은 사용자 본인에게 있습니다.
