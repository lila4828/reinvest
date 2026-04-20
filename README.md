# 📈 AI-Reinvest: Multi-Agent Stock Analysis System

CrewAI와 Google Gemini/OpenAI LLM을 활용하여 주식 시장 조사, 재무 분석, 그리고 최종 투자 전략 수립을 자동화하는 지능형 AI 에이전트 시스템입니다. 

## ✨ 핵심 기능 (Core Features)

* **🤖 Multi-Agent 협업 아키텍처:**
    * `MacroAgent`: 환율, 금리, 나스닥 등 글로벌 거시경제 지표 분석
    * `AccountingAgent`: 재무제표 건전성, 신규 상장 여부, 초장기 이평선(MA999) 퀀트 분석
    * `ResearchAgent`: 타겟 종목의 최신 시장 뉴스 및 센티먼트 수집
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
│   └── analysis/           # 종합 투자 리포트 작성
├── requirements.txt        # 의존성 패키지
└── DEV_LOG.md              # 💡 일자별 개발 일지 및 트러블슈팅 기록
```

## 🚀 시작하기 (Getting Started)
**환경 설정:** .env 파일에 SERPER_API_KEY 및 OPENAI_API_KEY 등록

**패키지 설치:** pip install -r requirements.txt

**실행:** python main.py

## 📚 개발 일지 및 트러블슈팅
이 프로젝트를 구축하며 겪은 LLM 쿼터 이슈, API 결측치 문제, 환각 제어 로직 등 상세한 엔지니어링 기록은 DEV_LOG.md에서 확인하실 수 있습니다.