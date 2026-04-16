# 📈 AI-Reinvest: Multi-Agent Stock Analysis System

CrewAI와 Google Gemini LLM을 활용하여 주식 시장 조사, 재무 분석, 그리고 최종 투자 전략 수립을 자동화하는 지능형 에이전트 시스템입니다.

## 🛠️ 개발 배경: *** 별도 개인 개발 프로젝트 ***
- **동기:** "갑자기 혼자 개발해보고 싶다"는 생각에서 시작.
- **목표:** 단순 정보를 넘어 시장 기사와 재무제표를 융합 분석하여 실질적인 주식 구매 추천 서비스 구현.

## 📅 1일차 개발 로그 (2026-04-16)

### ✅ 오늘 완료한 작업
1. **모듈화 아키텍처 완성:** - `main.py`가 중앙 컨트롤러가 되어 팀원들을 지휘하는 구조 설계.
   - 확장성을 고려해 `flows/` 폴더 내 도메인별로 파일(Agents, Tasks) 분할 완료.
2. **에이전트 팀 구성:**
   - **Research Team:** 실시간 시장 뉴스 및 기사 데이터 수집.
   - **Accounting Team:** 최근 재무제표 분석 및 수익성/건전성 데이터 추출.
   - **Analysis Team:** 리서치와 재무 데이터를 통합하여 사용자에게 최종 리포트 전달.
3. **LLM 최적화:** - Gemini 2.5 Flash(속도)와 Pro(추론) 모델을 분산 배치하여 부하 관리 및 품질 향상.

### 🚩 트러블 슈팅 (Troubleshooting)
- **이슈:** 검색 에이전트가 주식 시장의 극단적인 부정적 단어(예: '나락', '피바람' 등)를 필터링하거나 제외하고 가져오는 세부 제약을 설정하려 함.
- **원인:** 현재 CrewAI와 Gemini API 간의 호환성 혹은 `safety_settings` 설정 방식의 차이로 인해 해당 제약 조건이 정상 동작하지 않거나 에러를 발생시키는 현상 발견.
- **해결(임시):** 원활한 전체 시스템 구동을 위해 해당 필터링 로직은 주석 처리 후 진행.
- **향후 계획:** CrewAI 및 Pydantic 라이브러리 버전을 재검토하고 최신 문서에 맞춰 정교한 Prompt Engineering 또는 Safety 설정을 재도전할 예정.

---

## 🏗️ 폴더 구조
```text
reinvest/
├── main.py                 # 전체 실행 및 LLM 설정 (Controller)
├── flows/                  # 에이전트 및 태스크 모듈화
│   ├── research/           # [검색] 최신 기사 수집 및 전달
│   │   ├── agents.py
│   │   └── tasks.py
│   ├── accounting/         # [재무] 재무제표 분석 및 데이터 추출
│   │   ├── agents.py
│   │   └── tasks.py
│   └── analysis/           # [분석] 데이터를 융합하여 최종 리포트 작성
│       ├── agents.py
│       └── tasks.py
└── requirements.txt        # 필요 라이브러리 목록