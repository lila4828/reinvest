# 📈 AI-Reinvest: Multi-Agent Stock Analysis System

CrewAI와 OpenAI LLM, 그리고 RAG(Retrieval-Augmented Generation) 기술을 활용하여 주식 시장 조사, 재무 분석, 전문가 통찰 융합을 자동화하는 지능형 AI 에이전트 시스템입니다.

## ✨ 핵심 기능 (Core Features)

* **🤖 Multi-Agent 협업 아키텍처:**
    * `MacroAgent`: 환율, 금리, 나스닥 등 글로벌 거시경제 지표 분석
    * `AccountingAgent`: 재무제표 건전성, 신규 상장 여부, 초장기 이평선(MA999) 퀀트 분석
    * `ResearchAgent`: 타겟 종목의 최신 시장 뉴스 및 센티먼트 수집
    * `YoutubeAgent`: 인간 구루의 투자 철학과 시황 뷰를 RAG 기반으로 추출
    * `AnalysisAgent`: 위 데이터를 융합하여 최종 투자 의견(Buy/Hold/Sell) 리포트 발행
* **🛡️ LLM 환각(Hallucination) 원천 방어 시스템:**
    * AI의 숫자/방향성 리딩 오류를 막기 위해 Python 기반의 1차 사전 채점(Pre-scoring) 룰베이스 엔진 탑재 (예: 턴어라운드 로직 `++-` 자동 판별)
* **⚡ 동적 하이브리드 LLM 라우팅:**
    * 가벼운 리서치 업무(Flash/Mini)와 심층 분석(Pro/4o)에 맞는 모델을 분산 배치하여 비용 효율성과 추론 품질 극대화
* **📉 결측치 자동 보정 (Bypass Logic):**
    * 해외 API(`yfinance`)의 한국 주식 데이터(PBR, 배당률 등) 누락 및 오류 발생 시, 파이썬 단에서 직접 연산하여 보정하는 방어 로직 구현

## 🏗️ 시스템 아키텍처 (Folder Structure)
```text
reinvest/
├── main.py                 # 전체 파이프라인 컨트롤러 및 LLM 엔진 설정
├── flows/                  # 도메인별 에이전트/태스크 모듈
│   ├── macro/              # 글로벌 거시경제 지표 수집 및 분석
│   ├── accounting/         # 재무 분석, 퀀트 데이터 추출, 사전 채점
│   ├── research/           # 최신 뉴스 및 기사 수집
│   ├── youtube/            # youtube 인사이트 추출 로직
│   └── analysis/           # 종합 투자 리포트 작성
├── update_youtube_db.py    # 🎥 유튜브 오디오 추출 및 Whisper API 텍스트 변환 스크립트
├── build_vector_db.py      # 🧠 추출된 텍스트를 로컬 벡터 DB(ChromaDB)로 구축하는 스크립트
├── requirements.txt        # 의존성 패키지
└── DEV_LOG.md              # 💡 일자별 개발 일지 및 트러블슈팅 기록
```

## 🚀 시작하기 (Getting Started)

**1. 환경 설정:** 프로젝트 루트 경로에 `.env` 파일을 생성하고 API 키를 등록합니다.
> SERPER_API_KEY="your_serper_api_key"
> OPENAI_API_KEY="your_openai_api_key"

**2. 가상환경 생성 및 활성화:**
- **Windows:**
  > python -m venv venv
  > .\venv\Scripts\activate

- **Mac/Linux:**
  > python3 -m venv venv
  > source venv/bin/activate

**3. 패키지 설치:**
> pip install -r requirements.txt

**4. 유튜브 지식 베이스(DB) 구축 (2단계 시스템):**
유튜브의 강력한 봇 차단(429 에러)을 우회하기 위해, 오디오를 다운로드하여 직접 텍스트로 변환한 뒤 DB를 구축합니다.

- **Step 4-1. 오디오 추출 및 텍스트 변환:**
  > python update_youtube_db.py
  ※ `transcripts/` 폴더에 영상별 텍스트 파일이 개별 저장됩니다. (OpenAI Whisper API 요금 발생 주의)
  > python update_youtube_db_local.py
  ※ 무료 변환을 원할 경우 로컬 PC(GPU)에서 `faster-whisper` 모델 등을 사용하도록 코드를 커스텀할 수 있습니다.

- **Step 4-2. 로컬 벡터 DB 생성:**
  > python build_vector_db.py
  ※ 추출된 텍스트들을 쪼개어(Chunking) `chroma_db/` 폴더에 RAG 검색용 벡터 DB를 최종 완성합니다.

**5. 시스템 실행:**
> python main.py

## 📚 개발 일지 및 트러블슈팅
이 프로젝트를 구축하며 겪은 LLM 쿼터 이슈, API 결측치 문제, 환각 제어 로직 등 상세한 엔지니어링 기록은 DEV_LOG.md에서 확인하실 수 있습니다.