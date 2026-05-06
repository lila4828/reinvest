import os
import json
import logging
import re
from dotenv import load_dotenv
from crewai import Crew, Process, LLM
from datetime import datetime

from flows.research.agent import ResearchAgent
from flows.research.task import ResearchTask
from flows.analysis.agent import AnalysisAgent
from flows.analysis.task import AnalysisTask
from flows.accounting.agent import AccountingAgent
from flows.accounting.task import AccountingTask
from flows.macro.agent import MacroAgent
from flows.macro.task import MacroTask
from flows.youtube.agent import YoutubeAgent
from flows.youtube.task import YoutubeTask

# 유튜브 자동화 파이프라인 임포트
from vector_db.fetch_latest_youtube_ids import fetch_all_latest_youtube_ids
from vector_db.update_youtube_db import build_local_youtube_db
from vector_db.build_vector_db import build_db_from_transcripts

# 시스템 로깅 및 디버깅 레이어
from logging.handlers import RotatingFileHandler

# 0. 환경 변수 로드
load_dotenv()

log_file_handler = RotatingFileHandler(
    "system.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        log_file_handler,
    ],
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

SCORING_CONFIG = {
    "macro": {
        "vix_high_risk": 20,
        "vix_low_risk": 15,
        "us_10y_high_risk": 4.3,
        "us_10y_low_risk": 4.0,
        "exchange_rate_high_risk": 1400,
        "exchange_rate_low_risk": 1300,
    },
    "financial": {
        "debt_fail_cutoff": 200,
        "debt_warning_cutoff": 100,
    },
    "research": {
        "positive_cutoff": 65,
        "negative_cutoff": 35,
    },
    "final": {
        "system_weight": 0.30,
        "guru_weight": 0.70,
        "strong_buy_cutoff": 70,
        "buy_cutoff": 60,
        "hold_cutoff": 40,
    },
}

def require_env(name: str):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"환경변수 누락: {name}")
    return value


def is_valid_numeric_series(values, min_len=3):
    if not isinstance(values, list):
        return False
    if len(values) < min_len:
        return False
    return all(isinstance(x, (int, float)) for x in values)


def calculate_macro_score(exchange_rate, us_10y_yield, vix_index):
    if exchange_rate is None or us_10y_yield is None or vix_index is None:
        return 0, ["매크로 핵심 지표 일부 누락으로 중립 처리"]

    cfg = SCORING_CONFIG["macro"]
    score = 0
    reasons = []

    # 1) 투심: VIX
    if vix_index >= cfg["vix_high_risk"]:
        score -= 1
        reasons.append(f"VIX {vix_index} 고위험")
    elif 0 < vix_index <= cfg["vix_low_risk"]:
        score += 1
        reasons.append(f"VIX {vix_index} 안정")

    # 2) 할인율: 미국 10년물 금리
    if us_10y_yield >= cfg["us_10y_high_risk"]:
        score -= 1
        reasons.append(f"미 10년물 {us_10y_yield} 고금리 부담")
    elif 0 < us_10y_yield <= cfg["us_10y_low_risk"]:
        score += 1
        reasons.append(f"미 10년물 {us_10y_yield} 금리 부담 완화")

    # 3) 환율
    if exchange_rate >= cfg["exchange_rate_high_risk"]:
        score -= 1
        reasons.append(f"환율 {exchange_rate}원 고환율 부담")
    elif 0 < exchange_rate <= cfg["exchange_rate_low_risk"]:
        score += 1
        reasons.append(f"환율 {exchange_rate}원 안정")

    if not reasons:
        reasons.append("매크로 지표가 중립 구간")

    return score, reasons


def calculate_fundamental_score(net_income, fcf, revenue, debt_to_equity=None):
    if (
        not is_valid_numeric_series(net_income)
        or not is_valid_numeric_series(fcf)
        or not is_valid_numeric_series(revenue)
    ):
        return 0, ["재무 배열 데이터 불완전"]

    score = 0
    reasons = []

    # 순이익
    if net_income[-1] > 0 and net_income[-1] >= net_income[-2]:
        score += 1
        reasons.append("최근 순이익 흑자 및 전년 대비 개선")
    elif net_income[-1] < 0:
        score -= 1
        reasons.append("최근 순이익 적자")

    # FCF
    if fcf[-1] > 0:
        score += 1
        reasons.append("최근 FCF 플러스")
    elif fcf[-1] < 0:
        score -= 1
        reasons.append("최근 FCF 마이너스")

    # 매출
    if revenue[-1] > revenue[-2]:
        score += 1
        reasons.append("최근 매출 성장")
    elif revenue[-1] < revenue[-2]:
        score -= 1
        reasons.append("최근 매출 감소")

    # 부채비율
    debt_warning_cutoff = SCORING_CONFIG["financial"]["debt_warning_cutoff"]
    if isinstance(debt_to_equity, (int, float)) and debt_to_equity > debt_warning_cutoff:
        score -= 1
        reasons.append(f"부채비율 {debt_to_equity}%로 100% 초과")

    # 과도한 영향 방지: -3 ~ +3으로 제한
    score = max(-3, min(3, score))

    return score, reasons


def get_price_unit(ticker: str):
    if ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return "원"
    return "USD"


def format_price(value, unit):
    if value is None:
        return "N/A"

    if not isinstance(value, (int, float)):
        return "N/A"

    if unit == "원":
        return f"{value:,.0f}원"

    return f"${value:,.2f}"

def sanitize_filename(value: str):
    """
    Windows/macOS/Linux에서 문제 될 수 있는 파일명 문자를 제거한다.
    """
    invalid_chars = '<>:"/\\|?*'
    text = str(value)

    for ch in invalid_chars:
        text = text.replace(ch, "_")

    return text.strip()

def truncate_text(value, max_chars=3000):
    if value is None:
        return ""

    text = str(value)

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n...[TRUNCATED]"

def extract_report_summary(md_report: str):
    if not md_report or not isinstance(md_report, str):
        return ""

    # 상세 본문 시작 전까지만 남김
    return md_report.split("\n---")[0].strip()


def compact_analysis_inputs(acc_data, macro_json, research_json, youtube_json):
    """
    최종 AnalysisAgent에 넘길 입력을 압축한다.
    너무 긴 원본 JSON을 그대로 넣으면 토큰 초과 / Pydantic 파싱 실패 위험이 커진다.
    """
    compact_accounting = {
        "ticker": acc_data.get("ticker"),
        "current_price": acc_data.get("current_price"),
        "per": acc_data.get("per"),
        "pbr": acc_data.get("pbr"),
        "dividend_yield": acc_data.get("dividend_yield"),
        "roe_raw": acc_data.get("roe_raw"),
        "roe_label": acc_data.get("roe_label"),
        "debt_to_equity": acc_data.get("debt_to_equity"),
        "operating_margin": acc_data.get("operating_margin"),
        "ma_60": acc_data.get("ma_60"),
        "ma_200": acc_data.get("ma_200"),
        "ma_350": acc_data.get("ma_350"),
        "ma_500": acc_data.get("ma_500"),
        "ma_999": acc_data.get("ma_999"),
        "revenue": acc_data.get("revenue"),
        "net_income": acc_data.get("net_income"),
        "fcf": acc_data.get("fcf"),
        "fundamental_score": acc_data.get("fundamental_score"),
        "fundamental_score_reasons": acc_data.get("fundamental_score_reasons"),
        "status": acc_data.get("status"),
        "financial_summary": truncate_text(acc_data.get("financial_summary"), 1200),
    }

    return {
        "accounting": json.dumps(compact_accounting, ensure_ascii=False, indent=2),
        "macro": truncate_text(macro_json, 2000),
        "research": truncate_text(research_json, 2500),
        "youtube": truncate_text(youtube_json, 5000),
    }


class DummyResult:
    pydantic = None
    raw = "Timeout or Error"

def safe_kickoff(crew, label: str):
    try:
        return crew.kickoff()
    except Exception as e:
        logger.exception(f"❌ {label} kickoff 실패: {e}")
        return DummyResult()

def normalize_stock_pool(stock_pool):
    """
    외부 입력 종목 데이터를 main.py 내부 표준 형식으로 변환한다.
    표준 형식: [("TSLA", "테슬라"), ("005930.KS", "삼성전자")]
    """

    default_stock_pool = [
        ("TSLA", "테슬라"),
        ("005930.KS", "삼성전자"),
        ("000660.KS", "SK하이닉스"),
    ]

    if stock_pool is None:
        return default_stock_pool

    if not isinstance(stock_pool, list) or not stock_pool:
        raise ValueError("stock_pool은 비어 있지 않은 list여야 합니다.")

    normalized = []

    for item in stock_pool:
        if isinstance(item, dict):
            ticker = item.get("ticker")
            company = item.get("company")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            ticker, company = item
        else:
            raise ValueError(f"잘못된 종목 입력 형식입니다: {item}")

        ticker = str(ticker).strip() if ticker else ""
        company = str(company).strip() if company else ""

        if not ticker or not company:
            raise ValueError(f"ticker/company 값이 비어 있습니다: {item}")

        normalized.append((ticker, company))

    return normalized

def run_financial_crew(stock_pool=None):
    stock_pool = normalize_stock_pool(stock_pool)
    openai_api_key = require_env("OPENAI_API_KEY")

    # 뉴스 리서치에서 사용
    require_env("SERPER_API_KEY")

    # 1. 모델 정의
    fast_llm = LLM(
        model="gpt-4o-mini",
        api_key=openai_api_key,
        timeout=60,
    )

    fact_llm = LLM(
        model="o3-mini",
        api_key=openai_api_key,
        timeout=60,
    )

    smart_llm = LLM(
        model="gpt-5.4",
        api_key=openai_api_key,
        temperature=0.4,
        timeout=120,
    )

    # ---------------------------------------------------------
    # 0. 에이전트 및 태스크 사전 초기화
    # ---------------------------------------------------------
    macro_admin = MacroAgent(fast_llm)
    acc_admin = AccountingAgent(fast_llm)
    res_admin = ResearchAgent(fact_llm)
    yt_admin = YoutubeAgent(fact_llm)
    ana_admin = AnalysisAgent(smart_llm)

    macro_agent = macro_admin.macro_economist()
    accounting_agent = acc_admin.financial_analyst()
    researcher_agent = res_admin.news_researcher()
    youtube_agent = yt_admin.guru_analyst()
    analyst_agent = ana_admin.investment_analyst()

    macro_tasks = MacroTask()
    acc_tasks = AccountingTask()
    res_tasks = ResearchTask()
    yt_tasks = YoutubeTask()
    ana_tasks = AnalysisTask()

    # ---------------------------------------------------------
    # 0. 유튜브 DB 업데이트
    # ---------------------------------------------------------
    logger.debug("🔄 [0단계] 유튜브 최신 영상 확인...")

    try:
        new_vids = fetch_all_latest_youtube_ids(fetch_limit=5)

        if new_vids:
            logger.info(
                f"🚨 신규 영상 {len(new_vids)}개 감지 "
                f"→ 자막 생성 및 증분 임베딩 진행"
            )
            build_local_youtube_db()
            build_db_from_transcripts()
        else:
            logger.info("✅ 신규 영상 없음 → 기존 YouTube 벡터DB 사용")

    except Exception as e:
        logger.exception(f"⚠️ 유튜브 DB 업데이트 실패 → 기존 DB로 진행: {e}")

    # ---------------------------------------------------------
    # 1. 매크로 분석
    # ---------------------------------------------------------
    logger.debug("🌍 [1단계] 매크로 분석 시작")

    task_macro = macro_tasks.analyze_macro_economy(macro_agent)

    macro_crew = Crew(
        agents=[macro_agent],
        tasks=[task_macro],
        verbose=False,
        cache=False,
    )

    macro_result = safe_kickoff(macro_crew, "Macro Crew")

    if not macro_result.pydantic or not getattr(macro_result.pydantic, "is_data_valid", False):
        logger.warning("매크로 데이터 수집 실패 → 중립 macro_score 적용")
        macro_score = 0
        macro_score_reasons = ["매크로 데이터 수집 실패로 중립 처리"]
        macro_json = json.dumps(
            {
                "exchange_rate": None,
                "us_10y_yield": None,
                "nasdaq_index": None,
                "wti_price": None,
                "vix_index": None,
                "macro_briefing": "매크로 데이터 수집 실패로 중립 상태 적용",
                "is_data_valid": False,
                "error": "macro_result invalid",
            },
            ensure_ascii=False,
            indent=2,
        )
    else:
        macro_data = macro_result.pydantic.model_dump(mode="json")
        macro_json = macro_result.pydantic.model_dump_json(indent=2)

        macro_score, macro_score_reasons = calculate_macro_score(
            exchange_rate=macro_data.get("exchange_rate"),
            us_10y_yield=macro_data.get("us_10y_yield"),
            vix_index=macro_data.get("vix_index"),
        )

    logger.info(f"✅ 매크로 분석 완료 (Macro Score: {macro_score}, 이유: {macro_score_reasons})")

    # ---------------------------------------------------------
    # 2. 종목 루프
    # ---------------------------------------------------------
    all_reports = []

    logger.debug("🏭 [시스템] 종목 분석 파이프라인 가동")

    for ticker, company in stock_pool:
        try:
            logger.info(f"🎯 분석 시작: {company} ({ticker})")

            # ---------------------------------------------------------
            # 1. 재무 분석
            # ---------------------------------------------------------
            task_accounting = acc_tasks.analyze_financial_statements(
                accounting_agent,
                company,
                ticker,
            )

            financial_crew = Crew(
                agents=[accounting_agent],
                tasks=[task_accounting],
                verbose=False,
                cache=False,
            )

            acc_result = safe_kickoff(financial_crew, f"{company} Accounting Crew")

            if not acc_result.pydantic or not getattr(acc_result.pydantic, "is_data_valid", False):
                msg = f"🚫 [분석 중단] {company}: 재무 데이터 수집 실패 또는 파싱 오류"
                logger.error(msg)
                all_reports.append({
                    "ticker": ticker,
                    "company": company,
                    "status": "FAILED",
                    "report": msg,
                })
                continue

            acc_data = acc_result.pydantic.model_dump(mode="json")

            net_income = acc_data.get("net_income", [])
            fcf = acc_data.get("fcf", [])
            revenue = acc_data.get("revenue", [])

            if (
                not is_valid_numeric_series(net_income)
                or not is_valid_numeric_series(fcf)
                or not is_valid_numeric_series(revenue)
            ):
                msg = f"🚫 [분석 중단] {company} FAIL 사유: 3개년 재무 데이터 부족 또는 숫자형 데이터 오류"
                logger.warning(msg)
                all_reports.append({
                    "ticker": ticker,
                    "company": company,
                    "status": "FAILED",
                    "report": msg,
                })
                continue

            # ---------------------------------------------------------
            # 2. 기계적 FAIL 판정 룰베이스
            # ---------------------------------------------------------
            is_fail = False
            fail_reason = ""

            debt_to_equity = acc_data.get("debt_to_equity")

            if all(ni < 0 for ni in net_income):
                is_fail = True
                fail_reason = "3개년 연속 순이익 적자"
            elif all(f < 0 for f in fcf):
                is_fail = True
                fail_reason = "3개년 연속 잉여현금흐름(FCF) 마이너스"
            elif revenue[-1] <= 0:
                is_fail = True
                fail_reason = "최근 매출 데이터 오류(0 이하)"
            elif isinstance(debt_to_equity, (int, float)) and debt_to_equity > 200:
                is_fail = True
                fail_reason = "부채비율 200% 초과"

            if is_fail:
                msg = f"🚫 [분석 중단] {company} FAIL 사유: {fail_reason}"
                logger.warning(msg)
                all_reports.append({
                    "ticker": ticker,
                    "company": company,
                    "status": "FAILED",
                    "report": msg,
                })
                continue

            fund_score, fund_score_reasons = calculate_fundamental_score(
                net_income=net_income,
                fcf=fcf,
                revenue=revenue,
                debt_to_equity=debt_to_equity,
            )

            acc_data["status"] = "PASS"
            acc_data["fundamental_score"] = fund_score
            acc_data["fundamental_score_reasons"] = fund_score_reasons

            acc_json = json.dumps(
                acc_data,
                indent=2,
                ensure_ascii=False,
                default=str,
            )

            logger.info(f"✅ 재무 검증 통과 (Fund Score: {fund_score})")

            # ---------------------------------------------------------
            # 3. 뉴스 & 유튜브 순차 수집
            # ---------------------------------------------------------
            logger.debug(f"🔄 [{company}] 리서치 데이터 수집 중...")

            def run_research():
                task_res = res_tasks.collect_news_task(researcher_agent, company)
                crew = Crew(
                    agents=[researcher_agent],
                    tasks=[task_res],
                    verbose=False,
                    cache=False,
                )
                return safe_kickoff(crew, f"{company} Research Crew")

            def run_youtube():
                task_yt = yt_tasks.extract_guru_view(youtube_agent, company)
                crew = Crew(
                    agents=[youtube_agent],
                    tasks=[task_yt],
                    verbose=False,
                    cache=False,
                )
                return safe_kickoff(crew, f"{company} YouTube Crew")

            research_result = DummyResult()
            youtube_result = DummyResult()

            try:
                research_result = run_research()
            except Exception as e:
                logger.exception(f"⚠️ [{company}] 리서치 수집 예외 발생 → fallback 적용: {e}")
                research_result = DummyResult()

            logger.debug(f"🔄 [{company}] 유튜브 데이터 수집 중...")

            try:
                youtube_result = run_youtube()
            except Exception as e:
                logger.exception(f"⚠️ [{company}] 유튜브 수집 예외 발생 → fallback 적용: {e}")
                youtube_result = DummyResult()

            # ---------------------------------------------------------
            # 4. Research 결과 검증
            # ---------------------------------------------------------
            if not research_result.pydantic or not getattr(research_result.pydantic, "is_data_valid", False):
                logger.warning(f"[{company}] 리서치 데이터 수집 실패 → Fallback 적용")
                sentiment = 0
                research_json = json.dumps(
                    {
                        "sentiment_score": 50,
                        "momentum_strength": "LOW",
                        "news_summary": "최신 유의미한 뉴스 데이터 수집 실패",
                        "is_data_valid": False,
                    },
                    ensure_ascii=False,
                )
            else:
                score = research_result.pydantic.sentiment_score

                research_cfg = SCORING_CONFIG["research"]

                if score >= research_cfg["positive_cutoff"]:
                    sentiment = 1
                elif score <= research_cfg["negative_cutoff"]:
                    sentiment = -1
                else:
                    sentiment = 0

                research_json = research_result.pydantic.model_dump_json(indent=2)

            # ---------------------------------------------------------
            # 5. YouTube 결과 검증
            # ---------------------------------------------------------
            if not youtube_result.pydantic or not getattr(youtube_result.pydantic, "is_data_valid", False):
                logger.warning(f"[{company}] 유튜브 데이터 수집 실패 → Fallback 적용")
                guru_score = 50.0
                guru_weight = 0.0
                youtube_json = json.dumps(
                    {
                        "guru_sentiment_score": 50.0,
                        "key_strategy": "N/A",
                        "content_type": "N/A",
                        "insight_date": "N/A",
                        "freshness_level": "N/A",
                        "mindset_summary": "유의미한 직접 투자 마인드 발언 없음",
                        "market_principle": "유의미한 시장 대응 원칙 없음",
                        "risk_control": "유의미한 리스크 관리 발언 없음",
                        "guru_insight_details": "최신 유의미한 영상 데이터 수집 실패",
                        "is_data_valid": False,
                    },
                    ensure_ascii=False,
                )
            else:
                guru_score = youtube_result.pydantic.guru_sentiment_score
                content_type = getattr(youtube_result.pydantic, "content_type", "UNKNOWN")
                freshness_level = getattr(youtube_result.pydantic, "freshness_level", "UNKNOWN")
                insight_date = getattr(youtube_result.pydantic, "insight_date", "N/A")

                # 구루 70%는 "최신 종목 직접 발언"일 때만 반영
                # MARKET/MINDSET/RISK/PSYCHOLOGY는 리포트 해석에는 사용하지만 점수에는 반영하지 않음
                if (
                    content_type == "SPECIFIC"
                    and freshness_level in ["FRESH", "RECENT"]
                    and guru_score != 50.0
                ):
                    guru_weight = SCORING_CONFIG["final"]["guru_weight"]
                else:
                    guru_weight = 0.0

                logger.debug(
                    f"📺 [{company}] 유튜브 영상 성격 판별: {content_type} "
                    f"| 신선도: {freshness_level} | 기준일: {insight_date} "
                    f"| Guru Score: {guru_score} | Guru Weight: {guru_weight:.0%}"
                )

                youtube_json = youtube_result.pydantic.model_dump_json(indent=2)

            # ---------------------------------------------------------
            # 6. 최종 투자 의견 결정
            # ---------------------------------------------------------
            fundamental_score = acc_data.get("fundamental_score", 0)

            total_score = fundamental_score + macro_score + sentiment

            # total_score 범위:
            # fundamental_score: -3 ~ +3
            # macro_score: -3 ~ +3
            # sentiment: -1 ~ +1
            # 총합: -7 ~ +7
            # 50점을 중립으로 두고, 1점당 약 7점씩 이동
            system_score = max(0, min(100, 50 + (total_score * 7)))

            if guru_weight > 0:
                system_weight = SCORING_CONFIG["final"]["system_weight"]
            else:
                system_weight = 1.0

            final_weighted_score = (system_score * system_weight) + (guru_score * guru_weight)

            final_cfg = SCORING_CONFIG["final"]

            if final_weighted_score >= final_cfg["strong_buy_cutoff"]:
                final_opinion = "Strong Buy"
            elif final_weighted_score >= final_cfg["buy_cutoff"]:
                final_opinion = "Buy"
            elif final_weighted_score >= final_cfg["hold_cutoff"]:
                final_opinion = "Hold"
            else:
                final_opinion = "Sell"

            if guru_score >= 65:
                guru_sentiment_label = "Bullish"
            elif guru_score <= 35:
                guru_sentiment_label = "Bearish"
            else:
                guru_sentiment_label = "Neutral"

            logger.debug(
                f"📊 [시스템 채점] {company} | 시스템 점수: {system_score}점 "
                f"(재무 {fundamental_score} + 매크로 {macro_score} + 뉴스 {sentiment})"
            )
            logger.info(
                f"🤖 [최종 판정] {company} | 종합 {final_weighted_score:.1f}점 "
                f"(시스템 {system_weight:.0%} + 구루 {guru_weight:.0%}[{guru_sentiment_label}]) → {final_opinion}"
            )
            # ---------------------------------------------------------
            # 7. 목표가 / 방어선 산출
            # ---------------------------------------------------------
            current_price = acc_data.get("current_price")
            ma_60 = acc_data.get("ma_60")
            ma_200 = acc_data.get("ma_200")
            ma_350 = acc_data.get("ma_350")

            if isinstance(current_price, (int, float)) and current_price > 0:
                if (
                    isinstance(ma_60, (int, float))
                    and isinstance(ma_200, (int, float))
                    and ma_60 > ma_200
                    and ma_200 > 0
                ):
                    target_buy_price = ma_60
                    defense_price = ma_200
                else:
                    target_buy_price = current_price * 0.96

                    candidates = [
                        x for x in [ma_60, ma_200, ma_350]
                        if isinstance(x, (int, float)) and 0 < x < target_buy_price
                    ]

                    defense_price = max(candidates) if candidates else target_buy_price * 0.92
            else:
                target_buy_price = None
                defense_price = None
                logger.warning(f"⚠️ [{company}] 가격 데이터 부재로 산출 제외")

            # ---------------------------------------------------------
            # 8. 최종 분석 리포트 생성
            # ---------------------------------------------------------
            analysis_inputs = compact_analysis_inputs(
                acc_data=acc_data,
                macro_json=macro_json,
                research_json=research_json,
                youtube_json=youtube_json,
            )

            task_analysis = ana_tasks.report_writing_task(
                agent=analyst_agent,
                company_name=company,
                accounting_data=analysis_inputs["accounting"],
                macro_data=analysis_inputs["macro"],
                news_data=analysis_inputs["research"],
                youtube_data=analysis_inputs["youtube"],
                final_opinion=final_opinion,
                target_buy_price=target_buy_price,
                defense_price=defense_price,
            )

            analysis_crew = Crew(
                agents=[analyst_agent],
                tasks=[task_analysis],
                process=Process.sequential,
                verbose=False,
                cache=False,
            )

            logger.debug(f"🧠 [{company}] 최종 리포트 생성 중...")
            final_result = safe_kickoff(analysis_crew, f"{company} Analysis Crew")

            # ---------------------------------------------------------
            # 9. Markdown 렌더링
            # ---------------------------------------------------------
            if final_result.pydantic:
                report_data = final_result.pydantic
                chart_json = final_result.pydantic.model_dump_json(
                    include={"chart_data"},
                    indent=2,
                )

                price_unit = get_price_unit(ticker)
                current_price_text = format_price(current_price, price_unit)
                target_buy_price_text = format_price(target_buy_price, price_unit)
                defense_price_text = format_price(defense_price, price_unit)
                
                if final_opinion in ["Strong Buy", "Buy"]:
                    buy_comment = "적정 비중 매수 권고"
                elif final_opinion == "Hold":
                    buy_comment = "관망 또는 보유 기준"
                else:
                    buy_comment = "신규 매수 비권장"

                md_report = f"""# 📈 {company} 심층 투자 전략 리포트

| 구분 | 가격 정보 | 투자 의견 |
| :--- | :--- | :--- |
| **현재가** | **{current_price_text}** | **{report_data.investment_opinion}** |
| **권장 매수가** | **{target_buy_price_text}** | {buy_comment} |
| **하락 시 방어선/저항선** | **{defense_price_text}** | 분할 매수/대응 |

### 💡 수석 애널리스트 한 줄 결론
> **{report_data.one_line_conclusion}**

### 🎯 3줄 요약 (Executive Summary)
"""

                for line in report_data.executive_summary:
                    md_report += f"- {line}\n"

                md_report += f"""
---

## 1. 🌍 매크로 및 시장 환경
{report_data.macro_analysis}

## 2. 📊 펀더멘털 및 퀀트 분석
{report_data.fundamental_analysis}

## 3. 📰 비즈니스 모멘텀 (최신 뉴스)
{report_data.momentum_analysis}

## 4. 📺 구루의 시선 (주알홍쌤 인사이트)
{report_data.guru_analysis}

## 5. 💡 수석 애널리스트 종합 결론
{report_data.final_conclusion}

---

## 📎 실적 차트 데이터
"""

                md_report += "```json\n"
                md_report += chart_json
                md_report += "\n```\n"

                all_reports.append({
                    "ticker": ticker,
                    "company": company,
                    "status": "SUCCESS",
                    "report": md_report,
                })
                logger.info(f"✅ [{company}] 리포트 생성 및 렌더링 완료")

            else:
                fallback_report = f"📈 [{company}]\n{final_result.raw}"

                all_reports.append({
                    "ticker": ticker,
                    "company": company,
                    "status": "FAILED",
                    "report": fallback_report,
                })
                logger.error(f"❌ [{company}] Analysis 에이전트 구조화 파싱 실패")
        except Exception as e:
            msg = f"❌ [종목 분석 실패] {company} ({ticker}) 예외 발생: {e}"
            logger.exception(msg)
            all_reports.append({
                "ticker": ticker,
                "company": company,
                "status": "FAILED",
                "report": msg,
            })
            continue
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    summary_output = f"> **최근 업데이트 일시:** {now_text}\n\n"
    summary_output += "<!-- MACRO_DATA\n"
    summary_output += macro_json
    summary_output += "\n-->\n\n"

    summary_cards = []

    for item in all_reports:
        if item.get("status") == "SUCCESS":
            summary_cards.append(extract_report_summary(item.get("report", "")))
        else:
            summary_cards.append(
                f"# 📈 {item.get('company', 'N/A')} 심층 투자 전략 리포트\n\n"
                f"> {item.get('report', '분석 실패')}"
            )

    summary_output += "\n\n---\n\n".join(summary_cards)

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "summary": summary_output,
        "reports": all_reports,
    }

def save_report_files(output):
    try:
        result_date = output["date"]
        result_dir = os.path.join("result", result_date)
        os.makedirs(result_dir, exist_ok=True)

        # 1. 전체 summary 저장
        summary_file = os.path.join(result_dir, "summary.md")

        with open(summary_file, "w", encoding="utf-8") as f:
            f.write(output["summary"])

        logger.info(f"💾 전체 요약 리포트 저장 완료 → {summary_file}")

        # 2. 종목별 개별 파일 저장
        for item in output["reports"]:
            ticker = sanitize_filename(item["ticker"])
            company = sanitize_filename(item["company"])

            file_name = f"{company}_{ticker}.md"
            file_path = os.path.join(result_dir, file_name)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(item["report"])

            logger.info(f"💾 종목별 리포트 저장 완료 → {file_path}")

        return result_dir

    except Exception as e:
        logger.exception(f"❌ 리포트 파일 저장 실패: {e}")
        raise


if __name__ == "__main__":
    output = run_financial_crew()

    logger.debug("=" * 60)
    logger.debug("🏆 시스템 실행 완료")
    logger.debug("=" * 60)

    print(output["summary"])

    save_report_files(output)