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
1. 
- **이슈:** 검색 에이전트가 주식 시장의 극단적인 부정적 단어(예: '나락', '피바람' 등)를 필터링하거나 제외하고 가져오는 세부 제약을 설정하려 함.
- **원인:** 현재 CrewAI와 Gemini API 간의 호환성 혹은 `safety_settings` 설정 방식의 차이로 인해 해당 제약 조건이 정상 동작하지 않거나 에러를 발생시키는 현상 발견.
- **해결(임시):** 원활한 전체 시스템 구동을 위해 해당 필터링 로직은 주석 처리 후 진행.
- **향후 계획:** CrewAI 및 Pydantic 라이브러리 버전을 재검토하고 최신 문서에 맞춰 정교한 Prompt Engineering 또는 Safety 설정을 재도전할 예정.

---

## 📅 2일차 개발 로그 (2026-04-17)

✅ 오늘 완료한 작업
1. **LLM 인프라 고도화 및 안정화:**
문제: Gemini 무료 버전 사용 시 503 에러(과부하) 및 일일 할당량 초과 시 CrewAI의 Fallback 로직이 작동하지 않고 프로세스가 강제 종료되는 현상 발생.
해결: 의도대로 흐르지 않는 Fallback 옵션에 의존하는 대신, Gemini 한도 초과 시 즉시 OpenAI API(유료 결제분)로 모델을 전환하도록 로직 변경. 안정적인 에이전트 구동 환경 확보.

2. **회계 에이전트(Accounting Team) 기능 강화:**
Agent & Task 고도화: 재무제표 분석 프롬프트를 정교화하여 데이터 추출의 정확도 향상.
Tool 추가: 특정 주식의 재무 데이터를 실시간으로 가져올 수 있는 파이낸스 API 도구 통합.

3. **검색 에이전트(Research Team) 구조 개선:**
Agent 수정: 기사 검색 및 요약 성능 향상을 위한 프롬프트 최적화.
확장성 확보: 추후 검색 엔진 변경이나 필터링 로직 추가가 용이하도록 커스텀 Tool 구조 설계.

4. **데이터 소스(Data Source) 전략 수정:**
이슈: FMP(Financial Modeling Prep) API 도입을 시도했으나, 무료 플랜의 제한(일일 데이터 접근 불가, 장 마감 후 제한적 접근 등)으로 테스트 단계에서 부적합 판단.
대안: 상대적으로 속도는 느리지만 안정적인 데이터 호출이 가능한 **yfinance**를 사용하여 정보 수집 로직 구현 완료.
향후 계획: 서비스 배포 및 전수 조사(KOSPI, KOSDAQ) 단계에서는 처리 속도를 위해 FMP 유료 API로 전환 검토.

🚩 트러블 슈팅 (Troubleshooting)
1. 
- **이슈:** Gemini 무료 버전 Quota(할당량) 초과 및 Fallback 미작동
- **원인:** API 제공업체의 Hard Block(한도 소진)은 프레임워크 수준에서 예외로 처리되어 자동 Fallback이 어려움.
- **해결:** main.py에 수동 엔진 스위치 로직을 도입. Gemini 한도 초과 시 주석 처리만으로 즉시 OpenAI 엔진으로 전환하여 개발 흐름이 끊기지 않도록 조치.

2. 
- **이슈:** FMP(Financial Modeling Prep) API 권한 및 데이터 갱신 이슈
- **원인:** FMP API 정책 변경으로 무료 사용자는 미국 주요 87개 종목으로 데이터 접근이 제한됨을 확인. 또한 무료 티어는 실시간성 데이터 반영이 느림.
- **해결:** 테스트 단계의 유연성과 한국 시장 데이터 확보를 위해 yfinance 기반 커스텀 툴로 전환.

---

## 📅 3일차 개발 로그 (2026-04-20)

✅ 오늘 완료한 작업
**퀀트 스크리닝 파이프라인(Funnel 구조) 완성:**
- 다중 종목(Multi-stock) 스캔을 위한 for 루프 도입.
- 1단계 재무/상장 검증에서 부적격(FAIL) 판정 시, 이후 에이전트(리서치/분석) 구동을 즉시 중단(continue)하여 API 비용 및 LLM 토큰 낭비 완벽 차단.

**거시경제(Macro) 에이전트 신규 도입:**
- 개별 종목(나무)뿐만 아니라 글로벌 경제(숲)를 분석하기 위해 MacroAgent 추가.
- 원/달러 환율, 나스닥 지수, 미국 10년물 국채 금리 데이터를 수집하여 한국 시장에 미치는 영향을 분석.
- 효율성 최적화: 전체 프로세스 시작 전 단 1회만 호출하여 전체 종목의 컨텍스트(Context)로 공유하도록 설계.

**회계 도구(accounting/tool.py) 데이터 고도화:**
- 실시간 가치평가(Valuation): 현재 주가, 예상 PER, PBR 지표 추가.
- 신규 상장 필터링: yfinance의 1년(200거래일) 주가 이력을 확인하여 상장 1년 미만 신규 기업 즉시 컷오프(FAIL) 기능 추가.
- 장기 투자 지표 추가: 산업군(Sector) 분류, 배당 수익률(가산점 용도), 초장기 이동평균선(MA60~999) 데이터 수집 로직 추가.

**최종 투자 리포트 프롬프트 고도화 (analysis/task.py):**
- 수집된 재무, 매크로, 차트, 뉴스 데이터를 융합하여 4단 마크다운 구조(펀더멘털 -> 모멘텀/매크로 -> 방향성 예측 -> 최종 의견)로 일관되게 출력하도록 프롬프트 강력 통제.

🚩 트러블 슈팅 (Troubleshooting)
1. 
- **이슈:**LLM의 숫자/부호 인식 환각(Hallucination) 현상 및 논리 오류.
잉여현금흐름(FCF)의 마이너스(-)를 순이익 적자로 오인하여 우량주(삼성전자)를 FAIL 처리.
리스트 내 숫자가 작아짐에도(실적 악화) '성장/개선'으로 거짓 포장하여 리포트 작성.
- **원인:**텍스트 기반 LLM의 고질적인 수치 연산 및 데이터 배열(Array) 방향 리딩 한계.
- **해결:**수학적 판단을 LLM에게 맡기지 않고, Python 코드(tool.py) 단에서 1차 사전 채점 수행. 3개년 순이익 패턴(예: +++, ++-, ---)을 기호로 추출하고, Python이 판정한 합격/경고/탈락 결과 텍스트만 LLM에 전달. 분석 프롬프트에 '배열의 왼쪽이 최신'임을 명시하여 환각 완벽 방어.
2. 
- **이슈:**한국 주식(.KS, .KQ) 호출 시 특정 종목의 PBR(priceToBook) 데이터 누락.
- **원인:**yfinance API가 미국 외 국가 주식의 특정 지표를 빈칸(N/A)으로 반환하는 고질적 버그.
- **해결:**API가 PBR을 제공하지 않을 경우, currentPrice(현재 주가)와 bookValue(주당순자산)를 가져와 **파이썬 단에서 직접 PBR을 연산(주가 ÷ 주당순자산)**하여 빈 값을 채우는 우회(Bypass) 로직 구현.

---

##  📅 4일차 개발 로그 (2026-04-21)

✅ 오늘 완료한 작업
**회계 에이전트(Accounting Team) 고도화:**
- 데이터 추출 범위 확장: ROE(자기자본이익률), YoY(전년 대비 성장률) 계산 로직 추가.
- 현금흐름 패턴 분석: 영업 활동, 투자 활동, 재무 활동 현금흐름의 부호를 조합하여 기업의 자금 운용 상태를 기계적으로 판별하는 기능 구현.

**거시경제(Macro Team) 에이전트 설계 및 업데이트:**
- 시장 모멘텀 파악: 단순 현재가가 아닌 '1개월 추세 변화율' 계산 로직 반영.
- 공포 지수 및 원유 추가: 글로벌 투자 심리 파악을 위한 VIX 지수와 인플레이션 지표인 WTI 원유 가격 정보 수집 기능 추가.

**검색 에이전트(Research Team) 정밀화:**
- 출처 필터링 강제: SerperDevTool의 검색 타입을 news로 고정하고 메이저 경제 매체(hankyung, mk 등)로 도메인 제한.
- 시공간 통제: 파이썬 datetime을 활용해 오늘 날짜 기준 검색 프롬프트 자동 생성.

**리포트 자동 저장 시스템 구축 (main.py):**
- 파일 관리 최적화: 분석 결과가 터미널에서 휘발되지 않도록 result YYYY-MM-DD.md 경로에 자동 저장 로직 구현.
- 일별 동기화: 당일 중복 실행 시 '덮어쓰기'를 통해 최신 리포트 한 개만 유지하고, 날짜가 바뀌면 새 파일이 생성되도록 설계.

🚩 트러블 슈팅 (Troubleshooting)
1. 
- **이슈:**특정 종목의 '당일' 기사가 없을 경우 검색 결과가 비어 있거나, AI가 존재하지 않는 가짜 뉴스 링크를 생성하는 현상 우려.
- **해결:**검색 태스크에 "당일 기사가 없으면 최근 2~3일 전 기사라도 활용하라"는 예외 처리 지침 추가 및 실제 도구가 반환한 URL만 사용하도록 강력한 제약 설정.

2. 
- **이슈:** PER(5.378128), 매출액(333605938000000) 등 가공되지 않은 원시 데이터가 리포트에 그대로 노출되어 가독성이 심각하게 떨어짐.
- **해결:** 분석 에이전트(Analysis Task) 지침 수정. 모든 소수점 지표는 둘째 자리까지 반올림 표기.화폐 단위는 0의 나열 대신 '조', '억' 단위를 사용하여 직관적으로 변환하여 작성하도록 로직 및 프롬프트 고도화.

---

## 📅 5일차 개발 로그 (2026-04-22)

✅ **오늘 완료한 작업**
**시스템 아키텍처 및 모델 최적화:**
- **추론 모델(Reasoning Model) 전면 도입**: 리서치 에이전트의 모델을 `gpt-4o-mini`에서 `o3-mini`로 변경. 요약 과정에서의 데이터 손실을 방지하고, 50조와 57조의 차이를 논리적으로 판별하는 심층 추론 프로세스 구축.
- **LLM 라우팅 전략 수립**: `fast_llm`(4o-mini), `fact_llm`(o3-mini), `smart_llm`(gpt-5.4)으로 역할을 분담하여 비용 효율성과 분석 정확도를 동시에 확보.

**매크로 데이터 해석 로직 고도화:**
- **통계적 유의성 확보**: 환율, VIX, 원가(WTI)의 3개월 평균 및 표준편차를 기반으로 현재 수치의 변동성을 평가하는 로직 설계.
- **외국인 수급 예측**: 고환율과 공포 지수 상승이 한국 시장 내 외국인 매수세 감소에 미치는 영향을 수치적으로 반영.

**리서치 태스크(Research Task) 정밀 타격:**
- **정보원 확장**: 단순 뉴스 검색을 넘어 국내외 주요 증권사의 리포트 및 목표가 변경 자료를 수집하도록 검색 쿼리 다변화.
- **팩트 우선순위 알고리즘**: '전망'보다 '확정/발표' 키워드가 포함된 데이터를 최우선적으로 채택하도록 강제.

**리포트 UI/UX 개선 (Final Report):**
- **Decision-First 레이아웃**: 리포트 최상단에 [한 줄 평 + 가격 테이블]을 배치하여 즉각적인 의사결정 지원.
- **입체적 분석(Duality)**: 환율 상승이 수출주 실적에는 호재이나 외국인 자금 이탈에는 악재인 점 등 시장의 양면성을 저울질하는 분석 로직 반영.
- **데이터 부록(Appendix) 신설**: 하단에 원천 재무 데이터를 표 형식으로 보존하여 향후 그래프 시각화(Matplotlib/Plotly)를 위한 파이프라인 준비.

🚩 **트러블 슈팅 (Troubleshooting)**

1. 
**이슈:** 추론 모델의 API 파라미터 충돌
- **현상:** `o3-mini` 모델 사용 시 `temperature` 파라미터를 전송하면 API 에러(400) 발생.
- **해결:** 추론 모델은 자체 논리 구조를 사용하므로 설정값에서 `temperature`를 제거하여 안정적으로 구동 성공.

---

## 📅 5일차 개발 로그 (2026-04-23)

✅ **오늘 완료한 작업**
**비동기 RAG(Asynchronous RAG) 기반 유튜브 파이프라인 구축:**
- 아키텍처 설계: 매번 유튜브 API를 호출하여 발생하는 토큰 폭발(Token Overflow)과 처리 지연 문제를 해결하기 위해, 수집 봇(update_youtube_db.py)과 검색 도구(LocalYoutubeSearchTool)를 분리.
- 로컬 벡터 DB(ChromaDB) 도입: 주알홍쌤 채널의 400여 개 영상 자막 데이터를 1,000자 단위로 청킹(Chunking)하여 로컬에 임베딩(text-embedding-3-small). 이를 통해 API 비용을 90% 이상 절감하고 검색 속도를 1초 이내로 단축.

**인간 구루(Guru)의 뷰(View) 및 철학 통합:**
- YoutubeAgent: 숫자로 된 재무 데이터와 건조한 뉴스 기사를 넘어, 시장을 대하는 전문가의 통찰력과 마인드셋을 추출하는 전담 에이전트(o3-mini 기반) 투입.
- AnalysisTask 프롬프트 고도화: 리포트 레이아웃에 4. 📺 구루의 시선 섹션을 신설. 퀀트 분석과 뉴스 모멘텀에 인간 전문가의 심리적/철학적 뷰를 입체적으로 융합.

**개발 환경 최적화 및 DX(Developer Experience) 개선:**
- 대규모 데이터 처리 시각화: 400개가 넘는 영상 자막 추출 과정의 지루함을 없애고 진행 상황을 모니터링하기 위해 tqdm 프로그레스 바 적용.
- Git 형상 관리 세팅: 용량이 크고 재현 가능한 로컬 벡터 DB(chroma_db/)가 GitHub에 푸시되지 않도록 .gitignore 설정 완료.

**README.md 문서화:**
- 새롭게 추가된 RAG 아키텍처와 YoutubeAgent의 역할을 명시하여 프로젝트의 시스템 구조도를 최신화.

🚩 **트러블 슈팅 (Troubleshooting)**
1. 
**이슈:** ChromaDB 빈 데이터(Empty List) Upsert 크래시
**현상:** 수집기 봇 실행 시, 일부 유튜브 영상의 자막 추출이 실패하여 청크(Chunk)가 0개인 상태로 DB에 저장을 시도하다가 ValueError: Expected Embeddings to be non-empty list... 발생.

---

## 📅 6일차 개발 로그 (2026-04-24)

✅ **오늘 완료한 작업**
**유튜브 RAG 파이프라인 아키텍처 전면 개편 (2-Step 구조 도입):**
- 기존 `youtube-transcript-api`를 활용한 텍스트 크롤링 방식에서, 오디오 추출 후 AI로 전사하는 **오디오-텍스트 변환(STT) 방식**으로 파이프라인을 완전히 변경.
- **Step 1 (`update_youtube_db.py`)**: `yt-dlp`를 활용해 오디오를 다운로드한 후, **OpenAI Whisper API(테스트용 1개) 및 로컬 GPU(나머지 전체)**를 활용해 텍스트로 변환(STT)하고 `transcripts/` 폴더에 개별 저장.
- **Step 2 (`build_vector_db.py`)**: 안전하게 수집 완료된 텍스트 파일들만 별도로 읽어와서 로컬 벡터 DB(ChromaDB)를 생성하도록 구조를 분리.

**비용 및 안정성 최적화 (이어하기 방어 로직):**
- 대규모 변환 시 발생하는 API 요금과 처리 시간을 최적화하기 위해, 이미 변환된 텍스트 파일이나 오디오 파일이 존재하면 즉시 다운로드를 스킵(Skip)하는 완벽한 체크포인트/이어하기 기능 구현.
- 쇼츠(Shorts) 및 라이브 스트리밍 풀버전 영상과 일반 10분 내외 VOD 영상을 구분하여 RAG 데이터의 순도를 높임.

**README.md 및 문서화 최신화:**
- 새롭게 도입된 2단계(2-Step) DB 구축 방법에 맞춰 시작 가이드(Getting Started) 전면 수정 완료.

🚩 **트러블 슈팅 (Troubleshooting)**
1. 
**이슈:** 어제(5일차) 발생한 '자막 부재로 인한 ChromaDB 크래시' 문제 해결 시도 중, 지속적인 `429 Too Many Requests` (IP 차단) 발생.
- **배경 및 원인:** 어제 발견된 빈 자막 에러를 해결하기 위해 쿠키(`cook.txt`) 주입, 랜덤 대기 시간(4~9초), 스마트폰 핫스팟 우회 등을 적용하여 텍스트를 크롤링하려 시도함. 그러나 유튜브의 강력한 매크로 방어 시스템으로 인해 대량 요청 시 즉각적인 차단이 발생함. 또한 유튜버가 자막을 아예 막아둔 영상(라이브, 쇼츠 등)에 대한 근본적인 대처도 필요한 상황이었음.
- **해결:** 텍스트 API 요청(Scraping)을 과감히 포기하고, 미디어 스트림(`yt-dlp`)으로 오디오 파일만 로컬에 다운로드한 뒤 AI로 전사(STT)하는 방식을 채택함. 파이프라인 검증을 위해 **최초 1개 영상은 OpenAI Whisper API로 테스트**하여 차단 우회 및 완벽한 추출을 확인함. 이후 전체 변환 시 예상되는 대규모 API 요금(약 3~4만 원)을 방어하기 위해, **나머지 400여 개의 영상은 개인 로컬 PC의 그래픽카드(RTX 3070)와 오픈소스 Whisper 모델을 활용하여 전면 무료로 변환**함. 결과적으로 비용 부담 없이 IP 차단을 완벽히 회피하고 모든 영상의 인사이트를 100% 추출해내는 데이터 무결성을 확보.

---

## 📅 주말 개발 로그 (2026-04-25 ~ 2026-04-26)

### ✅ 주말 동안 완료한 작업
**1. 대규모 로컬 STT 파이프라인 가동 (전수 변환):**
- 6일차에 구축한 우회 파이프라인을 바탕으로, **나머지 400여 개의 영상은 개인 로컬 PC의 그래픽카드(RTX 3070)와 오픈소스 Whisper 모델을 활용하여 전면 무료로 변환**함.
- 결과적으로 막대한 API 비용 부담 없이 유튜브의 IP 차단을 완벽히 회피하고, 모든 영상의 투자 인사이트를 100% 추출해내는 데이터 무결성을 확보 완료.

---

## 📅 7일차 개발 로그 (2026-04-27)

### ✅ 오늘 완료한 작업
**1. 유튜브 RAG 검색 로직 최적화 (과거 데이터 타격 문제 해결):**
- **이슈:** 순수 유사도 검색(`k=6`)만 사용할 경우, 2022년 등 과거의 영상이 유사도가 높다는 이유로 2026년 최신 영상보다 우선적으로 검색되는 문제 발생.
- **해결:** `flows/youtube/tool.py`의 검색 로직을 수정하여 넉넉하게 30개(`k=30`)의 청크를 먼저 뽑아온 뒤, 파이썬 로직에서 메타데이터의 `date` 기준으로 최신순 정렬을 수행. 이후 상위 6개(`latest_docs[:6]`)만 잘라서 에이전트에게 전달하도록 변경하여 무조건 가장 최근의 유의미한 발언을 타격하도록 고도화 완료.

**2. 프롬프트 엔지니어링 (환각 통제 및 문맥 보존):**
- **날것의 뷰 유지:** o3-mini 모델이 유튜버의 발언을 점잖게 뭉뚱그리는 현상을 막기 위해, "독특한 비유(예: 에베레스트 고산병), 구체적인 수치를 날것 그대로 살리라"고 프롬프트 강화.
- **서술형(줄글) 전달:** 분석 에이전트(AI)가 유튜버의 감정선과 뉘앙스를 완벽히 이해할 수 있도록 개조식 요약을 폐지하고, 분량 제한 없는 상세한 서술형으로 전달하도록 Task 수정.

### 🚩 트러블 슈팅 (Troubleshooting)
1. 
- **이슈:** `o3-mini`의 '과잉 충성'으로 인한 수치 환각(Hallucination) 발생 (예: 영상에 없는 "65,000원대에서 72,500원대로 상승", "8% 상승" 등을 지어냄).
- **원인:** 프롬프트에서 "구체적인 수치를 생생하게 살리라"고 강하게 지시하자, 추론 능력이 강한 모델이 텍스트에 수치가 부족하다고 판단하고 자신의 학습 데이터를 바탕으로 그럴듯한 숫자를 창조해냄.
- **해결:** 프롬프트에 🚨 `[환각 방지 엄수]` 항목을 신설하여 "검색된 영상 텍스트에 존재하지 않는 가짜 수치를 절대 임의로 지어내지 말 것"을 명시함. 결과적으로 팩트 수치만 보존하여 원천 데이터의 신뢰도 복구 성공.

---

## 📅 8일차 개발 로그 (2026-04-28)

### ✅ 오늘 완료한 작업
**1. 프론트엔드 동적 렌더링 및 UI/UX 고도화:**
- **Markdown 파싱 & 렌더링:** FastAPI 백엔드(`/api/reports`)와 통신하여 최신 마크다운 리포트를 가져오고, 정규식과 분리 로직(`split`)을 통해 거시경제 지표와 종목별 리포트를 동적으로 렌더링(`react-markdown` 활용).
- **메인 페이지 미리보기:** 메인 화면(`MainBody.jsx`)에서는 전체 내용 대신 '3줄 요약'까지만 잘라내어 가독성 확보.
- **상세 리포트 커스텀 UI:** 종목 개수 증가에 대비해 상세 화면(`ReportDetail.jsx`)에 검색 기능이 포함된 커스텀 드롭다운 컴포넌트 구현.
- **SPA 라우팅 최적화 (깜빡임 방지):** `App.jsx`에서 `<MainHeader />`를 `<Routes>` 바깥으로 빼내어, 페이지 전환 시 실시간 티커 위젯(TradingView)이 재로딩되는 현상을 완벽하게 해결.
- **디자인 디테일:** 헤더 로고 호버 애니메이션 추가 및 현재 페이지 상태에 맞춘 조건부 네비게이션 버튼 구현.

**2. 백엔드 안정화 및 프롬프트 교정:**
- **API 서버 구축:** `FastAPI`를 도입하고 CORS를 허용하여 프론트엔드 연동.
- **매크로 누락 방지 프롬프트:** 분석 에이전트(`AnalysisTask`)가 'WTI 원유'와 'VIX 공포지수'를 결과물에서 누락하지 않도록 템플릿에 명시적 강제 규칙(`[필수 지표 포함]`) 추가.

### 🚩 트러블 슈팅 (Troubleshooting)
1. **이슈:** 페이지(Main <-> Report) 이동 시마다 트레이딩뷰 위젯이 파괴되었다가 재생성되면서 화면이 심하게 깜빡이고 리소스를 낭비하는 현상 발견.
   - **해결:** 개별 페이지 컴포넌트에 종속되어 있던 헤더 레이아웃을 React Router 최상단(`App.jsx`) 바깥쪽으로 분리. 이를 통해 페이지 콘텐츠가 바뀌어도 위젯은 백그라운드에 그대로 유지되도록 SPA 아키텍처 최적화 완료.

---

## 📅 9일차 개발 로그 (2026-04-29)
### ChatGPT Puls 와 Gemini Puls를 동시에 사용 -> 문제점 더 잘잡아줌

### ✅ 오늘 완료한 작업

**1. CrewAI 구조화 출력 안정화**
- `output_pydantic` 사용 구간에서 발생하던 OpenAI structured output 스키마 오류를 점검.
- `MacroOutput`의 자유 Dict 구조(`change_1mo`)를 제거하고, 각 지표의 1개월 변화율을 명시적 필드로 분리.
  - `exchange_rate_change_1mo`
  - `us_10y_yield_change_1mo`
  - `nasdaq_index_change_1mo`
  - `wti_price_change_1mo`
  - `vix_index_change_1mo`
- `stream=True`와 Pydantic 파싱 조합에서 빈 응답/파싱 실패가 발생하여, 구조화 출력을 사용하는 LLM 설정에서 스트리밍을 제거.

**2. 에이전트 역할 재정의**
- AccountingAgent, MacroAgent, YoutubeAgent, AnalysisAgent의 역할을 자유 분석가가 아니라 “데이터 구조화 요원” 중심으로 재정리.
- 회계/매크로 에이전트는 도구가 반환한 JSON을 그대로 Pydantic 스키마에 매핑하도록 역할을 제한.
- 최종 분석 에이전트는 투자 의견을 새로 판단하지 않고, `main.py`가 산출한 `investment_opinion`과 가격 가이드를 그대로 리포트 문장으로 구조화하도록 수정.

**3. 최종 점수 엔진 정리**
- 점수 기준을 `SCORING_CONFIG`로 통합하여 매크로, 재무, 뉴스, 구루 점수 임계값을 한곳에서 관리하도록 변경.
- 재무 점수는 순이익, FCF, 매출 성장, 부채비율을 반영해 산출.
- 매크로 점수는 환율, 미국 10년물 금리, VIX를 기준으로 산출하고, 점수 산출 사유를 로그에 함께 남기도록 개선.
- 구루 점수는 `SPECIFIC` 영상일 때만 최종 점수에 반영하고, `MARKET/MINDSET/N/A` 영상은 리포트 참고 자료로만 사용하도록 조정.

**4. 파이프라인 안정성 강화**
- `safe_kickoff()`를 도입하여 Crew 실행 실패 시 전체 프로세스가 중단되지 않고 fallback 결과로 이어지도록 방어.
- 종목별 `try/except` 격리를 적용하여 특정 종목 분석 실패가 전체 종목 분석 중단으로 이어지지 않도록 개선.
- ResearchAgent와 YouTubeAgent 병렬 실행을 제거하고 순차 실행으로 변경하여 CrewAI 객체 및 ChromaDB 동시 접근 리스크를 제거.

**5. 최종 리포트 출력 품질 개선**
- 본문 재무 수치는 원본 숫자를 그대로 노출하지 않고, 한국 종목은 조/억 원 단위, 미국 종목은 B/M 달러 단위로 변환해 서술하도록 AnalysisTask 프롬프트 개선.
- `chart_data`는 시각화용 원천 데이터 보존을 위해 원본 float 값을 그대로 유지하도록 분리.
- 투자 의견에 따라 가격 표의 코멘트를 다르게 표시하도록 수정.
  - `Strong Buy / Buy`: 적정 비중 매수 권고
  - `Hold`: 관망 또는 보유 기준
  - `Sell`: 신규 매수 비권장
- 방어선이 현재가보다 위에 잡히지 않도록, 현재가 아래에 있는 이동평균선 중 가장 가까운 값을 방어선으로 선택하도록 가격 로직 수정.

**6. 결과 저장 구조 확장**
- 기존 일별 단일 파일 저장 구조를 `result/YYYY-MM-DD/summary.md + 종목별 리포트` 구조로 변경.
- 종목별 리포트를 `회사명_티커.md` 형태로 저장하도록 수정.
- 하루 단위 최종본 유지 정책은 유지하여 같은 날짜에 재실행하면 summary와 종목별 파일이 최신 결과로 덮어써지도록 설계.
- `sanitize_filename()`을 추가하여 파일명에 사용할 수 없는 문자를 안전하게 치환.

### 🚩 트러블 슈팅 (Troubleshooting)

1. **이슈:** OpenAI structured output에서 `MacroOutput` 스키마 오류 발생
- **현상:** `change_1mo: Dict[str, Optional[float]]` 필드가 response_format schema 검증에서 거부됨.
- **원인:** OpenAI structured output이 자유 Dict 구조와 Optional 조합을 안정적으로 처리하지 못함.
- **해결:** `change_1mo`를 제거하고 각 지표별 1개월 변화율을 명시적 평면 필드로 분리.

2. **이슈:** `output_pydantic` + `stream=True` 조합에서 LLM 응답 파싱 실패
- **현상:** `Failed to get parsed result from stream`, `Received None or empty response from LLM call` 에러 발생.
- **원인:** CrewAI의 Pydantic 출력 파싱과 OpenAI streaming 응답 조합이 불안정하게 동작.
- **해결:** 구조화 출력이 필요한 LLM 설정에서 `stream=True`를 제거.

3. **이슈:** 병렬 처리 안정성 우려
- **현상:** ResearchAgent와 YouTubeAgent를 병렬 실행할 경우 CrewAI 객체 및 ChromaDB 동시 접근 안정성을 보장하기 어려움.
- **원인:** CrewAI/Crew 객체와 로컬 ChromaDB 동시 접근의 thread-safe 여부가 불확실함.
- **해결:** 병렬 처리 대신 순차 수집 방식으로 변경하여 안정성을 우선 확보.

4. **이슈:** 투자 의견과 가격 표 문구 충돌
- **현상:** `Sell` 판정 종목에도 “적정 비중 매수 권고” 문구가 표시됨.
- **원인:** 가격 표 코멘트가 투자 의견과 무관하게 고정 문구로 들어가 있었음.
- **해결:** 투자 의견별로 표 코멘트를 분기 처리.

5. **이슈:** 방어선이 현재가보다 위에 잡히는 문제
- **현상:** 현재가보다 높은 이동평균선이 “하락 시 방어선”으로 표시됨.
- **원인:** 기존 가격 로직이 이동평균선과 현재가의 상대 위치를 비교하지 않음.
- **해결:** 현재가보다 낮은 이동평균선만 방어선 후보로 사용하고, 후보가 없으면 현재가의 90%를 fallback 방어선으로 설정.

---

## 📅 10일차 개발 로그 (2026-05-04)

### ✅ 오늘 완료한 작업

1. **ChromaDB 증분 임베딩 구조 복구 및 안정화**
   - 기존 벡터DB를 유지한 상태에서 신규 유튜브 자막만 추가 임베딩하도록 흐름 확인.
   - ChromaDB 최대 batch size 초과 오류를 해결하기 위해 chunk 추가 로직을 batch 단위로 분할 처리.
   - 최종적으로 기존 962개 영상 기준 신규 임베딩 대상 없음 상태까지 정상 확인.
   - 현재 Chroma chunk 개수 26,407개 유지 확인.

2. **유튜브 업데이트 파이프라인 정리**
   - `main.py`에서 직접 URL을 넘겨 유튜브 업데이트를 수행하던 구조를 정리.
   - `fetch_latest_youtube_ids.py`가 최신 영상 확인을 담당하도록 역할 분리.
   - `fetch_all_latest_youtube_ids()` 기반으로 `videos`, `streams`를 모두 확인하는 구조로 변경.
   - 신규 영상이 없으면 기존 YouTube 벡터DB를 그대로 사용하는 흐름 확인.

3. **리포트 그래프 시각화 개선**
   - 기존 리포트 하단 JSON 형태의 `chart_data`를 React 차트로 렌더링하도록 개선.
   - 한국 주식과 미국 주식의 단위 차이를 반영.
     - 한국 주식: `조 원`
     - 미국 주식: `Billion USD`
   - `T-2`, `T-1`, `T` 표기를 사용자 친화적으로 변경.
     - `2년 전`, `1년 전`, `현재`
   - 차트 값 표시 방식을 개선.
     - 막대 위 값 표시
     - 반올림 처리
     - 음수 값 표시 위치 보정
     - 가독성을 위해 색상 적용

4. **`main.py` 종목 입력 구조 변경**
   - 기존 고정 종목 리스트 구조를 외부 입력 가능 구조로 변경.
   - `run_financial_crew(stock_pool=None)` 형태로 수정.
   - `normalize_stock_pool()`을 추가하여 API에서 전달받은 종목 입력을 내부 표준 형식으로 변환.
   - 기본값은 기존처럼 `TSLA`, `005930.KS`를 유지.
   - 리포트 저장 로직을 `save_report_files(output)` 함수로 분리.
   - 향후 `api.py`에서 `run_financial_crew(stock_pool=...)` 호출 가능하도록 구조 정리.

5. **FastAPI 로그인/세션 구조 추가**
   - `.env`에 로그인/세션 관련 환경변수 추가.
   - `/api/login`, `/api/logout`, `/api/me` 구현.
   - `HttpOnly` 쿠키 기반 세션 구조 적용.
   - 세션 만료 시간 24시간 설정.
   - `/api/reports`, `/api/reports/{date}/{filename}`에 로그인 보호 적용.
   - `/api/me`는 로그인 상태 확인용으로 200 OK를 반환하도록 수정.

6. **FastAPI 백그라운드 Job 구조 추가**
   - `/api/run-report` 추가.
   - `/api/report-status/{job_id}` 추가.
   - 리포트 생성 요청 시 `job_id` 발급.
   - 백그라운드에서 리포트 생성 작업이 실행되는 구조 구성.
   - `pending`, `running`, `success`, `failed` 상태 관리.
   - 세션별 job 접근 검증 추가.
   - 같은 세션에서 중복 실행 방지 로직 추가.
   - 테스트 모드로 실제 OpenAI API 호출 없이 job 흐름 검증 완료.

7. **React 로그인 화면 및 인증 흐름 추가**
   - `features/login/Login.jsx`, `Login.css` 추가.
   - `App.jsx`에서 로그인 상태 확인 후 화면 분기.
   - 로그인 성공 시 메인 화면 표시.
   - 새로고침 시 `/api/me`로 로그인 상태 유지 확인.
   - 로그아웃 버튼 추가.
   - 기존 `components` 구조를 `features/layout` 중심으로 정리.
   - `App.jsx`를 `features/app/App.jsx`로 이동하고 `index.jsx`는 루트에 유지.

8. **React 리포트 API 호출 인증 적용**
   - `MainTop.jsx`, `MainBody.jsx`, `useReports.js`의 API 요청에 `credentials: 'include'` 또는 `withCredentials` 적용.
   - 로그인 세션 쿠키가 포함된 상태로 리포트 목록/상세 조회 가능하도록 수정.
   - 백엔드에서 인증되지 않은 API 접근은 401로 차단 확인.

9. **React 리포트 생성 UI 추가**
   - `features/report-generator/ReportGenerator.jsx`, `ReportGenerator.css` 추가.
   - 메인 화면에 새 리포트 생성 영역 추가.
   - 종목 선택 후 `/api/run-report` 호출.
   - `job_id` 기반 polling으로 `/api/report-status/{job_id}` 확인.
   - 작업 완료 시 메인 리포트와 매크로 영역이 자동 새로고침되도록 `refreshKey` 구조 추가.
   - 사용자 화면에서는 내부용 `job_id` 표시 제거.

10. **API 로그 구조 추가**
   - `api.log` 별도 생성.
   - `system.log`는 분석 파이프라인 로그 중심으로 유지.
   - `api.log`에는 로그인, 로그아웃, 리포트 생성 요청, job 시작/성공/실패, 종목 검색, cache 저장 로그를 기록.
   - `session_id`, 비밀번호, API Key 등 민감 정보는 로그에 남기지 않도록 정리.

11. **`system.log` 운영용 로그 정리**
   - `httpx`, `httpcore`, `openai`, `chromadb`, `urllib3` 로그 레벨을 `WARNING`으로 조정.
   - `HTTP Request`, OpenAI tool validation 같은 과도한 외부 라이브러리 로그를 줄이도록 설정.
   - 개발 확인용 단계 로그는 `logger.debug()`로 낮춤.
   - 최종 판정, 리포트 생성 완료, 저장 완료, 실패/예외 중심으로 `INFO` 로그 유지.

12. **종목 검색 구조 1차 개선**
   - 기존 프론트 고정 종목 목록 방식에서 백엔드 중심 구조로 전환 준비.
   - `stock_search/stock_master.json` 생성.
   - `stock_search/stock_search_cache.json` 생성.
   - `stock_search/search_store.py` 생성.
   - `stock_master.json`과 `stock_search_cache.json`을 합쳐 기본 종목 목록을 제공하는 구조 추가.
   - `/api/stock-options` 추가.
   - `/api/stock-search`를 내부 JSON 검색 후 Yahoo Finance fallback 순서로 변경.
   - `/api/run-report` 호출 시 선택 종목을 `stock_search_cache.json`에 자동 저장하도록 연결.
   - React `ReportGenerator.jsx`에서 `/api/stock-options`, `/api/stock-search`를 호출하는 구조로 변경.

---

### 🚩 트러블 슈팅 (Troubleshooting)

1. **ChromaDB batch size 초과**
   - **이슈:** 신규 chunk 12,968개를 한 번에 ChromaDB에 추가하면서 `Batch size is greater than max batch size` 오류 발생.
   - **원인:** ChromaDB가 한 번에 처리할 수 있는 최대 batch size 제한을 초과.
   - **해결:** `add_documents()`를 5,000개 단위로 나누어 처리하도록 변경.
   - **결과:** 전체 신규 chunk가 정상 추가되었고, 이후 재실행 시 신규 임베딩 대상 없음 확인.

2. **ChromaDB/Rust 내부 panic 오류**
   - **이슈:** ChromaDB 초기화 중 `range start index out of range for slice` panic 발생.
   - **원인:** 버전 변경 과정에서 기존 ChromaDB 저장 구조와 설치 라이브러리 버전 간 충돌 가능성 발생.
   - **해결:** 무리한 최신 구조 전환 대신 기존 구조로 복구하고, 증분 임베딩 방식만 안정화.
   - **결과:** 기존 DB 경로를 유지한 상태에서 정상 실행 확인.

3. **불필요한 OpenAI 토큰 사용**
   - **이슈:** 벡터DB 재구축/중단 과정에서 이미 임베딩된 데이터가 다시 처리되어 토큰 비용 발생.
   - **원인:** 기존 DB 상태와 신규 대상 판별 흐름이 꼬이면서 중복 임베딩 위험 발생.
   - **해결:** 기존 저장 영상 수와 신규 임베딩 대상 수를 명확히 확인하고, 신규 대상이 없으면 즉시 종료하도록 흐름 확인.
   - **결과:** 이후 실행에서 신규 영상 없음 및 신규 임베딩 대상 없음 정상 확인.

4. **FastAPI 세션 없는 접근 차단 검증**
   - **이슈:** 로그인 없이 `/api/reports`, `/api/report-status/{job_id}` 접근 가능 여부 확인 필요.
   - **원인:** OpenAI API Key를 사용하는 서비스이므로 리포트 생성 및 조회 API 보호 필요.
   - **해결:** `get_current_session()` 기반 인증 dependency 적용.
   - **결과:** 세션 없는 접근 시 `401 로그인이 필요합니다.` 정상 반환 확인.

5. **`/api/me` 새로고침 시 401 로그가 반복 출력**
   - **이슈:** React 새로고침마다 `/api/me`가 401을 반환하여 FastAPI 로그가 지저분해짐.
   - **원인:** `/api/me`를 인증 필수 API처럼 처리하고 있었음.
   - **해결:** `/api/me`는 상태 확인 API로 보고, 로그인 안 된 경우에도 `200 OK`와 `authenticated: false` 반환하도록 변경.
   - **결과:** 새로고침 시 에러 로그처럼 보이지 않고 정상 상태 확인 API로 동작.

6. **`MainBody.jsx` 자동 새로고침 수정 중 `listData` 누락**
   - **이슈:** `listData` 선언 없이 `listData.reports`를 사용해 런타임 오류 가능성 발생.
   - **원인:** 자동 새로고침 구조로 수정하면서 `await listRes.json()` 코드가 빠짐.
   - **해결:** `if (!listRes.ok)` 검증 후 `const listData = await listRes.json();` 추가.
   - **결과:** `refreshKey` 기반 자동 새로고침 구조 정상화.

7. **Yahoo Finance 한글 검색 400 오류**
   - **이슈:** `테슬라`, `폴라리스오피스` 같은 한글 검색어가 Yahoo Finance API에서 `400 Bad Request` 발생.
   - **원인:** Yahoo Finance search endpoint가 한글 query를 안정적으로 처리하지 못함.
   - **해결(보류):** 오늘은 영어 티커/영문 검색이 정상 동작하는 것만 확인하고, 한글 전체 종목 검색은 다음 작업으로 넘김.
   - **향후 계획:** KRX 종목 CSV/JSON 전체 데이터를 추가하여 한글 종목 검색은 내부 DB에서 처리하도록 개선 예정.

---

## 📅 휴일 개발 로그 (2026-05-05)

### ✅ 오늘 완료한 작업

**1. 한국 주식(KRX) 종목 DB 자동 갱신 기능 추가**
- 공공데이터포털 `금융위원회_KRX상장종목정보` API를 활용하여 KOSPI/KOSDAQ 종목 리스트를 자동 수집하도록 구현.
- 최신 기준일 데이터가 없을 경우 최근 영업일을 역순으로 조회하여 데이터가 존재하는 날짜로 fallback되도록 처리.
- KOSPI 종목은 Yahoo Finance 호환 티커 형식인 `.KS`로 변환.
- KOSDAQ 종목은 `.KQ`로 변환.
- 수집 결과를 `stock_master_kr.json`에 저장하도록 구성.
- 실제 실행 결과 KRX 기준 종목 2,658개 수집 확인.

**2. 미국 주식(US) 종목 DB 자동 갱신 기능 추가**
- NASDAQ Trader Symbol Directory 데이터를 기반으로 미국 상장 종목 리스트를 자동 수집하도록 구현.
- `nasdaqlisted.txt`에서 NASDAQ 상장 종목을 수집.
- `otherlisted.txt`에서 NYSE/AMEX/기타 거래소 종목을 수집.
- ETF, 테스트 종목 등은 기본 검색 대상에서 제외하도록 필터링.
- `BRK.A`와 같은 점 표기 티커를 Yahoo Finance 호환 형식인 `BRK-A`로 정규화.
- 수집 결과를 `stock_master_us.json`에 저장하도록 구성.
- 실제 실행 결과 미국 종목 7,391개 수집 확인.

**3. 종목 검색 데이터 저장 구조 정리**
- 기존 `stock_search` 폴더 바로 아래에 있던 JSON 파일들을 `stock_search/data/` 폴더로 분리.
- 종목 검색 관련 원천/통합/캐시 데이터를 역할별로 분리.
  - `stock_master_kr.json`: 한국 주식 원천 종목 DB
  - `stock_master_us.json`: 미국 주식 원천 종목 DB
  - `stock_master.json`: KR + US + 별칭 통합 최종 검색 DB
  - `stock_alias_ko.json`: 한글 별칭 관리 파일
  - `stock_search_cache.json`: 검색 fallback 및 사용자 선택 기반 캐시

**4. KR + US 통합 종목 DB 생성 로직 분리**
- `rebuild_stock_master.py`를 추가하여 한국/미국 종목 DB와 한글 별칭을 하나의 최종 `stock_master.json`으로 통합하도록 구성.
- 한국 주식은 `005930`, `005930.KS`, `005930.KQ` 같은 형식 차이를 같은 종목으로 판단하도록 중복 제거 로직 개선.
- 미국 주식은 거래소와 티커 기준으로 중복 제거.
- 국장/미장 갱신 스크립트에서 중복된 통합 로직을 제거하고, 공통 `rebuild_stock_master()` 함수를 호출하도록 정리.
- 실제 실행 결과 최종 `stock_master.json`에 총 10,049개 종목 통합 확인.

**5. 종목 검색 중복 제거 및 우선순위 정렬 개선**
- `search_store.py`의 중복 제거 기준을 단순 ticker 비교에서 `make_dedupe_key()` 기반으로 변경.
- 캐시에 기존 종목이 남아 있을 때 삼성전자 등 동일 종목이 중복 표시되는 문제를 방지.
- 검색 결과에 점수 기반 정렬 로직을 추가.
  - 티커 정확 일치 우선
  - 회사명 정확 일치 우선
  - 별칭/키워드 정확 일치 우선
  - 티커/회사명 prefix 일치 우선
  - 포함 검색 결과는 후순위 배치
- `Apple` 검색 시 `AAPL / Apple Inc.`가 다른 Apple 포함 종목보다 우선 노출되도록 개선.
- 검색 요청은 기존 debounce 구조를 유지하여 과도한 API 호출을 방지.

**6. 한글 별칭 검색 구조 추가**
- 미국 주식의 한글 검색을 지원하기 위해 `stock_alias_ko.json` 구조를 도입.
- 예시 별칭 구조를 정의.
  - `TSLA`: 테슬라
  - `NVDA`: 엔비디아, 엔비
  - `AAPL`: 애플
  - `MSFT`: 마이크로소프트, 마소
  - `PLTR`: 팔란티어
  - `SOFI`: 소파이
- 별칭 파일을 수정한 뒤 `rebuild_stock_master.py`를 실행하면 최종 `stock_master.json`의 keywords에 반영되도록 구성.


### 🚩 트러블 슈팅 (Troubleshooting)

1. **이슈:** `Apple` 검색 시 관련 없는 종목이 함께 상단 노출됨
- **현상:** `Apple` 검색 시 `Apple Inc.` 외에도 Apple 단어가 포함된 다른 종목이 함께 검색됨.
- **원인:** 기존 검색 로직이 `clean_keyword in value or value in clean_keyword` 기반 단순 포함 검색이었음.
- **해결:** 검색 결과에 점수 기반 정렬을 적용하여 티커 정확 일치, 회사명 정확 일치, 키워드 정확 일치 결과가 먼저 노출되도록 개선.

2. **이슈:** 별칭을 전 종목에 모두 넣어야 하는지 판단 어려움
- **현상:** 미국 종목 수가 7,000개 이상이라 모든 종목에 한글 별칭을 수동으로 넣기 어려움.
- **원인:** 전체 종목 별칭을 관리하는 것은 비효율적이며 실제 사용 빈도가 낮은 종목이 많음.
- **해결:** `stock_search_cache.json`에 쌓인 사용자 검색 이력을 기반으로 `suggest_alias_from_cache.py`를 통해 별칭 후보를 점진적으로 추가하는 방식으로 결정.

---

## 📅 개발 로그 (2026-05-06)

### ✅ 오늘 완료한 작업

**1. 한국 주식 티커 정규화**
- KRX 데이터의 `A009150.KS` 같은 티커를 Yahoo Finance 호환 형식인 `009150.KS`로 정규화.
- API 요청, Crew 실행 입력, KRX 종목 마스터 생성 로직에 정규화 처리를 추가.
- 기존 `A` prefix 티커도 검색 키워드에는 유지하여 검색 편의성은 보존.

**2. 종목 검색 예외 처리 개선**
- Yahoo Finance fallback 검색이 한글/비정상 query에서 400 오류를 반환해도 서버 500으로 터지지 않도록 처리.
- 검색 결과가 없을 때 빈 결과와 사용자 안내 메시지를 반환하도록 변경.

**3. 리포트 생성 진행 UI 개선**
- React에서 리포트 생성 job 상태를 polling하고 진행률 토스트를 표시하도록 개선.
- 요청 접수, 데이터 수집, 리포트 작성, 완료 단계가 보이도록 UI 구성.
- 리포트 생성 완료 시 메인/리포트 목록이 자동 새로고침되도록 `refreshKey` 흐름을 상위 App으로 이동.
- 여러 종목을 선택해 한 번에 리포트 생성을 요청할 수 있도록 종목 선택 UI를 확장.

**4. `summary.md` 저장/병합 로직 개선**
- 기존에는 새 리포트 생성 시 `summary.md`가 최신 실행 결과로 덮어써지는 문제가 있었음.
- 개별 종목 리포트 파일을 먼저 저장한 뒤, 같은 날짜 폴더의 개별 리포트를 다시 스캔해 `summary.md`를 재구성하도록 변경.
- 동일 티커는 최신 수정 파일 기준으로 하나만 남기도록 정리.
- 분석 중단 파일은 메인 요약 카드 후보에서 제외하도록 처리.

**5. 메인 화면 UI 개편**
- 기존 최신 `summary.md` 기준 표시에서 전체 날짜 폴더의 개별 리포트를 기준으로 종목별 최신 리포트만 표시하도록 변경.
- 종목명/의견 검색 기능 추가.
- 즐겨찾기 별표 기능 추가.
  - 현재는 브라우저 `localStorage`에 저장.
  - 추후 배포/서비스화 시 사용자 계정별 DB 저장으로 확장 가능.
- `Buy`, `Hold`, `Sell`, `분석 중단` 체크 필터 추가.
- 종목 수가 많아질 것을 고려해 스크롤 가능한 compact 리스트로 변경.

### 🚩 트러블 슈팅 (Troubleshooting)

1. **이슈:** 메인 화면이 최신 날짜 `summary.md` 기준으로만 종목을 표시
- **원인:** `MainBody.jsx`가 `summary.md`를 우선 조회하고 그 안의 카드만 파싱했음.
- **해결:** `/api/reports` 전체 목록에서 개별 리포트를 가져오고, 티커별 최신 리포트 1개만 남겨 표시하도록 변경.

2. **이슈:** 종목이 많아질 경우 메인 화면이 난잡해짐
- **원인:** 카드형 UI가 종목 수에 비례해 세로로 길어짐.
- **해결:** 검색/즐겨찾기/상태 필터가 있는 compact 리스트로 변경하고, 리스트 내부 스크롤을 적용.

---

## 📅 개발 로그 (2026-05-07)

### ✅ 오늘 완료한 작업

**1. CrewAI → LangGraph 전환 작업 계획 확정**
- 기존 CrewAI 중심 실행 흐름을 바로 제거하지 않고, 먼저 LangGraph가 전체 리포트 생성 흐름을 제어하도록 전환하는 방향으로 결정.
- 현재 구조는 `LangGraph = orchestration`, `CrewAI = 각 단계 Agent/Task 실행 일부 담당`으로 정리.
- 향후 CrewAI 제거를 위해 Macro, Accounting, Research, Youtube RAG, Analysis를 단계별로 직접 함수화하는 계획 수립.
- Codex 작업 기준 파일과 실행 프롬프트 파일을 만들어, 한 번에 전부 바꾸지 않고 단계별로 진행하는 기준을 정리.

**2. 리포트 저장과 summary 저장 책임 분리**
- `backend/services/summary_service.py`를 중심으로 summary 저장 로직을 분리.
- 종목별 `.md` 리포트 저장과 `summary.md` 저장을 분리하여, 리포트 파일 생성만으로 완료 처리되지 않도록 상태 기준을 정리.
- 추가/정리한 summary 관련 함수:
  - `save_report_summary(state)`
  - `load_existing_summaries(result_dir, current_summary="")`
  - `upsert_summary_item(summary_item, existing_summaries=None)`
  - `build_summary_item_from_state(state)`
  - `render_summary_content(header, summary_items)`
- 기존 `build_merged_summary()`는 새 함수들을 사용하도록 호환 유지.
- summary 저장 성공 시 `summary_saved=True`, `status="completed"`로 처리.
- summary 저장 실패 시 `summary_saved=False`, `errors`에 에러를 추가하고 `partial_failed`로 처리.

**3. 종목 단위 pipeline 분리**
- `run_single_report_pipeline(...)`을 추가하여 종목 1개마다 독립 state를 생성하고, accounting/research/youtube/analysis/render 흐름을 진행하도록 분리.
- `run_multiple_report_pipeline(...)`을 추가하여 여러 종목을 순회 처리하도록 구성.
- 한 종목 실패 시에도 다음 종목 분석이 계속 진행되도록 실패 격리 구조 적용.
- `finalize_state(state)`를 추가하여 `summary_saved=True`까지 완료되어야 `completed`, 리포트만 생성된 상태는 `report_generated`로 판단.
- `build_failed_state(target, error)`를 추가하여 예외가 바깥까지 올라와도 실패 state와 실패 report item을 생성하도록 방어.

**4. ReportState 확장**
- `backend/schemas/report_state.py`에 graph 내부 runtime state 필드를 추가.
- 리포트 생성 결과 보존을 위해 `markdown_report`, `output_report` 필드를 추가.
- 이후 LangGraph node별 상태 추적과 summary 저장 상태 추적의 기반을 마련.

**5. LangGraph StateGraph 1차 도입**
- `backend/graphs/report_graph.py`를 추가하여 `StateGraph(ReportState)` 기반 리포트 생성 graph를 구성.
- `backend/graphs/__init__.py`를 추가하여 graph 패키지 진입점을 구성.
- 구성한 node:
  - `validate_input`
  - `macro`
  - `accounting`
  - `research`
  - `youtube_rag`
  - `price`
  - `analysis`
  - `save_summary`
  - `finalize`
- 기존 CrewAI Agent/Task 프롬프트는 유지하고, LangGraph는 orchestration wrapper 역할만 담당하도록 구성.
- 기존 API 응답 구조와 markdown 포맷은 유지.

### 🚩 트러블 슈팅 (Troubleshooting)

1. **이슈:** 리포트 markdown 한글 깨짐
- **현상:** JYP Ent. 리포트에서 제목/표/섹션 라벨이 깨진 한글과 특수 문자로 표시됨.
- **원인:** 리팩토링 중 일부 markdown 템플릿 문자열이 인코딩 손상된 상태로 남음.
- **해결:** 정상 main branch 문구를 기준으로 markdown 템플릿 라벨을 복구. AST 기준 문자열 확인 및 py_compile/import 검증 수행.

---

## 📅 개발 로그 (2026-05-08)

### ✅ 오늘 완료한 작업

**1. macro batch 1회 실행 구조 확정**
- 여러 종목 생성 시 macro 분석이 종목별로 반복되지 않도록 책임 위치를 정리.
- `build_macro_context()`를 추가하여 batch 시작 시 macro 분석을 1회만 실행.
- `run_multiple_report_pipeline()`이 macro 실행 책임을 소유하도록 변경.
- 각 종목 graph state에는 같은 `macro_context`, `macro_json`, `macro_score`, `macro_score_reasons`를 주입.
- `report_graph.py`의 macro node는 이미 macro 값이 주입된 경우 재실행하지 않고 통과하도록 처리.
- stub 검증으로 2종목 입력 시 `macro_calls=1`, `graph_calls=2` 구조 확인.

**2. YouTube 최신 영상 업데이트가 리포트 생성을 막지 않도록 수정**
- 실제 API 검증 중 YouTube 최신 영상 1개가 live/stream 상태로 감지되어 `update_youtube_vector_db()`에서 장시간 멈추는 문제 확인.
- 리포트 생성 중 YouTube 업데이트는 보조 작업으로 보고, 실패/timeout/live skip이어도 기존 Vector DB로 리포트 생성이 계속 진행되도록 변경.
- YouTube transcript update와 vector DB rebuild를 별도 Python subprocess로 실행하고 timeout을 적용.
- live/upcoming 영상은 즉시 처리하지 않고 pending으로 저장하도록 구조 변경.

**3. 프론트 진행 토스트를 종목별 상태 중심으로 개편**
- 기존 전체 단계 UI인 `요청 접수 / 데이터 수집 / 리포트 작성 / 완료`를 제거.
- Job ID 화면 표시 제거.
- floating toast는 1개만 유지하고, polling 때마다 같은 toast id로 업데이트.
- toast 안에 종목별 row를 표시.
- 완료/실패 후 5초 뒤 자동 dismiss 정책 유지.
- 긴 에러는 짧게 잘라 표시.
- 타겟 종목 스캔 현황 아래의 인라인 진행 패널은 제거하고, 진행 상태는 floating toast 안에서만 표시하도록 정리.

**4. 진행률 UX 개선**
- 기존 진행률이 88%에서 오래 멈춰 사용자가 실제 시간 진행률로 오해하는 문제 확인.
- 진행률 계산을 poll count 기반 고정 방식에서 `공통 20% + 종목별 평균 80%` 방식으로 변경.
- 정책:
  - 요청 직후/준비 중: 5%
  - 공통 매크로 분석 중: 10%
  - 공통 매크로 완료 후: 20%
  - 이후 남은 80%는 종목별 평균 진행률로 계산
- `summary_save` 라벨은 `요약 저장 중`에서 `최종 반영 중`으로 변경.
- `report_save`, `report_generated`, `summary_save` 단계에서는 제목이 `AI 리포트 마무리 중`으로 보이도록 정리.

**5. 모든 주요 화면 footer 추가**
- `frontend/src/features/layout/SiteFooter.jsx` 추가.
- `frontend/src/features/layout/SiteFooter.css` 추가.
- 모든 주요 페이지 하단에 일반 홈페이지 형태의 footer 추가.
- 짧은 페이지에서도 footer가 자연스럽게 하단에 오도록 `app-shell`, `main-content` 레이아웃 정리.
- footer 내용:
  - `AI-Reinvest`
  - `AI 기반 투자 리포트 자동 생성 시스템`
  - `데이터는 투자 참고용이며, 최종 투자 판단은 사용자 본인에게 있습니다.`
  - `© 2026 AI-Reinvest. All rights reserved.`
  - `About / Reports / Disclaimer / Contact` 링크 자리

**6. 상세 리포트 목록 UI 정리**
- 리포트 목록의 시장 라벨을 정리.
- 기존 `코스피 / 코스닥 / 나스닥` 표현을 화면에 직접 노출하지 않고, 사용자 친화적인 badge로 변경.
- 표시 형태:
  - `[국내 주식] 삼성전자`
  - `[미국 주식] 테슬라`
- 시장 badge가 먼저 나오고 종목명이 뒤에 오도록 줄 맞춤 정리.

**7. NEW badge 추가 및 조건 개선**
- 사용자가 아직 클릭하지 않은 리포트에 `NEW` badge 표시.
- localStorage key:
  - `ai-reinvest-read-reports`
- 저장 key 예시:
  - `2026-05-08/삼성전자_005930.KS.md`
- 최종 NEW 표시 조건:
  - `report.date === 오늘 날짜`
  - 그리고 해당 report key가 localStorage에 없음
- 이전 날짜 리포트는 읽지 않았어도 NEW 표시하지 않도록 수정.
- 리포트를 클릭하면 localStorage에 읽음 상태를 저장하고 NEW 제거.

**8. 상세 리포트 기준 날짜/시간 표시**
- 상세 리포트 제목 아래 기준 표시 추가.
- 기존 날짜만 표시되던 것을 `YYYY-MM-DD HH:mm`까지 표시하도록 개선.
- 표시 예:
  - `기준: 2026-05-08 10:38`
- 우선순위:
  - `modified_at`
  - `updated_at`
  - `generated_at`
  - `date fallback`
- API가 이미 `modified_at`을 내려주고 있어 새 optional field는 추가하지 않음.
- markdown 원본은 수정하지 않고 프론트 렌더링 단계에서 표시.

**9. 메인 화면 필터 초기화 버튼 추가**
- 메인 화면 `타겟 종목 스캔 현황`의 필터 영역에 `필터 초기화` 버튼 추가.
- 초기화 대상:
  - 검색어
  - 즐겨찾기 필터
  - 의견 필터
- 필터가 선택되어 있지 않을 때는 덜 강조되거나 비활성화될 수 있도록 UI 톤 정리.

**10. 미국 주식 원화 환산 표시**
- 상세 리포트 가격표에서 미국 주식 달러 가격 옆에 원화 환산 표시 추가.
- 이후 메인 화면 가격 영역에도 같은 환산 표시를 추가.
- 표시 예:
  - `$411.79 (약 599,400원)`
  - `환산 기준: 1달러 = 1,455.62원`
- 환율은 최신 `summary.md`의 `MACRO_DATA.exchange_rate`를 사용.
- 환율이 없으면 기존 달러 가격만 표시.
- 국내 주식은 기존 원화 가격만 유지.

### 🚩 트러블 슈팅 (Troubleshooting)

1. **이슈:** YouTube live 영상 때문에 리포트 생성이 장시간 running 상태에 머묾
- **현상:** 1종목 실제 생성 검증이 30분 넘게 running에 머물다가 timeout.
- **원인:** macro 단계 전 `update_youtube_vector_db()`에서 신규 라이브 영상 1개를 감지하고 오디오/자막 처리 쪽에서 멈춤.
- **해결:** live/upcoming 영상은 즉시 처리하지 않고 pending에 저장. 리포트 생성은 기존 Vector DB로 계속 진행하도록 변경.

4. **이슈:** 진행률이 88%에서 오래 멈춰 사용자에게 대기 시간처럼 보임
- **원인:** poll count 또는 고정 job 단계 기반 progress 계산이 실제 종목별 진행 상태와 맞지 않음.
- **해결:** `공통 20% + 종목별 평균 80%` 방식으로 progress 계산 변경.

5. **이슈:** `langchain-chroma` 설치 후 CrewAI와 `chromadb` 버전 충돌
- **현상:** `langchain-chroma 1.1.0` 설치 과정에서 `chromadb 1.5.9`가 설치됨.
- **원인:** `crewai 1.14.4`는 `chromadb~=1.1.0`을 요구.
- **해결:** CrewAI 제거 전까지 `langchain-chroma` 전환 보류. CrewAI 제거 이후 Chroma 최신화 작업으로 분리.

---

## 개발 로그 (2026-05-13 ~ 2026-05-14)

### 오늘 완료한 작업

**1. CrewAI active runtime 제거 완료**
- 활성 런타임에서 CrewAI 의존성을 제거했다.
- `crewai`, `crewai-tools`는 백엔드 requirements에서 제거된 상태를 유지했다.
- 기존 참조용 `backend/flows/*/agent.py`, `backend/flows/*/task.py` 파일을 삭제했다.
- 임시 마이그레이션 문서도 정리했다.
- 현재 활성 분석 경로는 `backend/flows/*/tool.py` 기반 direct implementation으로 통일됐다.

**2. LangGraph + direct tool.py 구조 확정**
- FastAPI 요청은 pipeline 계층을 통해 LangGraph report workflow로 전달된다.
- LangGraph는 기존 노드 순서를 유지한다.
  - `validate_input → macro → accounting → research → youtube_rag → price → analysis → save_summary → finalize`
- Macro, Accounting, Research, Youtube RAG, Analysis는 각각 direct `tool.py` 모듈을 통해 실행된다.
- `main.py`는 가능한 범위에서 orchestration/wrapper 중심으로 정리했다.
- 다종목 처리, 종목별 실패 격리, `targets_status`, `status_callback`, summary 저장 완료 조건을 유지했다.

**3. 출력 품질 parity 복원**
- CrewAI 제거 후 결과물이 단순 요약처럼 변하는 문제를 확인하고, 기존 Agent/Task가 담당하던 분석 기준을 direct 구조에 맞게 이식했다.
- 단, old Agent/Task 프롬프트를 그대로 복붙하지 않고, 필요한 판단 기준과 작성 제약만 추출했다.
- Analysis structured-output prompt를 보강했다.
  - senior analyst report tone 강화
  - 섹션별 reasoning 강화
  - 정확히 3개 executive summary 유지
  - 한 줄 결론을 짧고 자연스럽게 유지
  - 최종 투자 의견이 시스템 계산값과 일치하도록 제한
- Macro 해석 품질을 복원했다.
  - 환율, 미국 10년물 금리, VIX, Nasdaq, WTI를 압력/지지 요인으로 해석
  - `macro_score`, `macro_score_reasons`, `macro_briefing`을 단순 수치 나열이 아니라 해석 가능한 문장으로 개선
- Accounting 해석 품질을 복원했다.
  - 매출, 순이익, FCF 흐름을 deterministic helper로 해석
  - PER/PBR, ROE, 영업이익률, 부채비율, 이동평균선 맥락을 반영
  - `fundamental_score_reasons`와 `financial_summary` 품질 개선
  - 재무 데이터 수집 실패 fallback 한글 문구 정상 유지
- Research 뉴스 합성 품질을 복원했다.
  - 검색 결과를 단순 나열하지 않고 긍정/부정/중립 이슈로 분류
  - `sentiment_score`, `momentum_strength`, `news_summary`, `sentiment_reason`을 생성
  - 뉴스 숫자나 전망을 감사된 재무제표 사실처럼 다루지 않도록 제한
- Youtube RAG 인사이트 합성 품질을 복원했다.
  - retrieved docs 기반으로 `SPECIFIC`, `MARKET`, `MINDSET`, `RISK`, `PSYCHOLOGY`, `GENERAL` 성격을 구분
  - `SPECIFIC` 근거가 있을 때만 종목 직접 인사이트로 다룸
  - 일반 시장 원칙이나 심리/리스크 관리 원칙을 특정 종목 직접 추천처럼 쓰지 않도록 제한
- 출력 polish를 적용했다.
  - `Target buy price`, `defense price` 같은 영어 잔여 표현 방지
  - `추천하지않음` 같은 어색한 붙여쓰기 방지
  - 명시 연도 데이터가 없을 때 `2023년 기준` 같은 calendar-year 단정 표현 제한
  - 중복 문장부호와 어색한 한국어 표현 방지
  - 매크로 문구를 `수입 물가 상승 압력`, `원가/비용 부담`, `외국인 수급 부담`처럼 자연스럽게 정리

**4. Hallucination 방어 강화**
- 사실, 숫자, 가격, 점수, chart_data, 최종 투자 의견은 시스템 제어 값으로 유지했다.
- LLM은 제공된 데이터의 해석과 설명만 담당하고, 새로운 사실을 만들지 않도록 제약했다.
- `investment_opinion`은 시스템 계산 결과를 보존하도록 후처리했다.
- markdown 제목, 가격표, chart_data 구조는 deterministic rendering으로 유지했다.
- 뉴스의 숫자나 기사 내용을 감사된 재무 데이터처럼 해석하지 않도록 했다.
- Youtube 일반 원칙은 직접 종목 추천으로 오해되지 않도록 구분했다.
- 데이터가 부족한 경우에는 발명하지 않고 보수적으로 표현하도록 했다.

**5. Chroma / langchain_chroma 정리**
- Chroma import를 `langchain_chroma.Chroma`로 이전했다.
- `langchain-chroma` requirement 버전을 현재 구조에 맞게 정리했다.
- 기존 `chroma_db` 경로와 데이터는 유지했다.
- 리포트 생성 중에는 기존 DB를 읽는 경로를 기본으로 사용한다.
- YouTube/vector DB 수동 업데이트 및 build 스크립트는 별도 작업으로 남겨뒀다.
- 기본 리포트 생성 흐름에서는 `REPORT_GENERATION_YOUTUBE_UPDATE_ENABLED=false` 정책을 유지한다.

### 🚩 트러블 슈팅 및 확인 사항

**1. CrewAI 제거 후 결과물 품질 저하**
- **이슈:** CrewAI Agent/Task를 제거하자 리포트 결과물이 이전보다 단순하고 일반적인 요약처럼 변함.
- **원인:** Agent/Task가 담당하던 분석 기준, 문체, 섹션별 작성 제약이 direct 구조로 충분히 이식되지 않았음.
- **해결:** old Agent/Task의 내용을 그대로 복붙하지 않고, 필요한 판단 기준과 anti-hallucination 규칙만 추출하여 `flows/*/tool.py`와 Analysis structured-output prompt에 반영.

**2. main.py 비대화 우려**
- **이슈:** CrewAI 제거 후 direct 구현과 prompt가 `main.py`에 계속 쌓일 가능성이 생김.
- **해결:** Analysis, Research, Youtube RAG 등 단계별 구현을 각 `flows/*/tool.py`로 이동하고, `main.py`는 orchestration/wrapper 중심으로 유지.

---
