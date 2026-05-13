import os
import json
import logging
import subprocess
import sys
from dotenv import load_dotenv
from types import SimpleNamespace
from crewai import Crew, Process, LLM
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pydantic import BaseModel, Field
from typing import List

from flows.research.tool import search_tool
from flows.accounting.tool import collect_financial_data
from flows.macro.tool import collect_macro_data
from flows.youtube.tool import get_guru_youtube_tool

# 유튜브 자동화 파이프라인 임포트
from vector_db.fetch_latest_youtube_ids import fetch_all_latest_youtube_ids
from vector_db.fetch_latest_youtube_ids import fetch_all_latest_youtube_ids
from vector_db.youtube_update_guard import filter_processable_video_ids
from services.report_file_service import save_report_files
from services.summary_service import extract_report_summary
from schemas.report_state import ReportState, create_initial_report_state

# 시스템 로깅 및 디버깅 레이어

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

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
YOUTUBE_UPDATE_TIMEOUT_SECONDS = int(
    os.getenv("YOUTUBE_UPDATE_TIMEOUT_SECONDS", "60")
)


class DirectChartData(BaseModel):
    period: str = Field(description="T-2, T-1, T")
    revenue: float = Field(description="revenue")
    net_profit: float = Field(description="net profit")
    fcf: float = Field(description="free cash flow")


class DirectAnalysisOutput(BaseModel):
    investment_opinion: str
    one_line_conclusion: str
    executive_summary: List[str]
    macro_analysis: str
    fundamental_analysis: str
    momentum_analysis: str
    guru_analysis: str
    final_conclusion: str
    chart_data: List[DirectChartData]

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
        return 0, ["macro data missing"]

    cfg = SCORING_CONFIG["macro"]
    score = 0
    reasons = []

    # 1) 투자 심리: VIX
    if vix_index >= cfg["vix_high_risk"]:
        score -= 1
        reasons.append(f"VIX {vix_index} high risk")
    elif 0 < vix_index <= cfg["vix_low_risk"]:
        score += 1
        reasons.append(f"VIX {vix_index} stable")

    # 2) 할인율: 미국 10년물 금리
    if us_10y_yield >= cfg["us_10y_high_risk"]:
        score -= 1
        reasons.append(f"US 10Y {us_10y_yield} high yield pressure")
    elif 0 < us_10y_yield <= cfg["us_10y_low_risk"]:
        score += 1
        reasons.append(f"US 10Y {us_10y_yield} low yield relief")

    # 3) 환율
    if exchange_rate >= cfg["exchange_rate_high_risk"]:
        score -= 1
        reasons.append(f"exchange rate {exchange_rate} high FX pressure")
    elif 0 < exchange_rate <= cfg["exchange_rate_low_risk"]:
        score += 1
        reasons.append(f"exchange rate {exchange_rate} stable")

    if not reasons:
        reasons.append("macro indicators are neutral")

    return score, reasons


def calculate_fundamental_score(net_income, fcf, revenue, debt_to_equity=None):
    if (
        not is_valid_numeric_series(net_income)
        or not is_valid_numeric_series(fcf)
        or not is_valid_numeric_series(revenue)
    ):
        return 0, ["financial series data invalid"]

    score = 0
    reasons = []

    # 순이익
    if net_income[-1] > 0 and net_income[-1] >= net_income[-2]:
        score += 1
        reasons.append("recent net income positive or improved")
    elif net_income[-1] < 0:
        score -= 1
        reasons.append("recent net income is negative")

    # FCF
    if fcf[-1] > 0:
        score += 1
        reasons.append("recent FCF positive")
    elif fcf[-1] < 0:
        score -= 1
        reasons.append("recent FCF negative")

    # 매출
    if revenue[-1] > revenue[-2]:
        score += 1
        reasons.append("recent revenue declined")
    elif revenue[-1] < revenue[-2]:
        score -= 1
        reasons.append("recent revenue growth")

    # 부채비율
    debt_warning_cutoff = SCORING_CONFIG["financial"]["debt_warning_cutoff"]
    if isinstance(debt_to_equity, (int, float)) and debt_to_equity > debt_warning_cutoff:
        score -= 1
        reasons.append(f"debt-to-equity {debt_to_equity}% exceeds 100%")

    # 과도한 영향 방지: -3 ~ +3으로 제한
    score = max(-3, min(3, score))

    return score, reasons


def get_price_unit(ticker: str):
    if ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return "KRW"
    return "USD"


def format_price(value, unit):
    if value is None:
        return "N/A"

    if not isinstance(value, (int, float)):
        return "N/A"

    if unit == "KRW":
        return f"{value:,.0f}원"

    return f"${value:,.2f}"

def truncate_text(value, max_chars=3000):
    if value is None:
        return ""

    text = str(value)

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n...[TRUNCATED]"

def normalize_kr_ticker(ticker: str):
    ticker = str(ticker or "").strip().upper()

    if (
        len(ticker) == 10
        and ticker.startswith("A")
        and ticker[1:7].isalnum()
        and ticker[7:] in [".KS", ".KQ"]
    ):
        return ticker[1:]

    return ticker

def compact_analysis_inputs(acc_data, macro_json, research_json, youtube_json):
    """
    최종 분석 structured-output 호출에 전달할 입력을 압축한다.
    너무 긴 원본 JSON을 그대로 넣으면 토큰 초과 또는 Pydantic 파싱 실패 위험이 커진다.
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


class DirectPayload(SimpleNamespace):
    def model_dump(self, mode=None, include=None, **kwargs):
        data = dict(self.__dict__)

        if include:
            data = {key: data.get(key) for key in include if key in data}

        return data

    def model_dump_json(self, indent=None, include=None, **kwargs):
        return json.dumps(
            self.model_dump(include=include),
            ensure_ascii=False,
            indent=indent,
        )


class DirectResult:
    def __init__(self, data):
        self.raw = json.dumps(data, ensure_ascii=False)
        self.pydantic = DirectPayload(**data)


def safe_kickoff(crew, label: str):
    try:
        return crew.kickoff()
    except Exception as e:
        logger.exception(f"{label} kickoff 실패: {e}")
        return DummyResult()

def normalize_stock_pool(stock_pool):
    """
    외부 입력 종목 데이터를 main.py 내부 표준 형식으로 변환한다.
    표준 형식: [("TSLA", "Tesla"), ("005930.KS", "Samsung Electronics")]
    """

    default_stock_pool = [
        ("TSLA", "Tesla"),
        ("005930.KS", "Samsung Electronics"),
        ("000660.KS", "SK Hynix"),
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

        ticker = normalize_kr_ticker(ticker)
        company = str(company).strip() if company else ""

        if not ticker or not company:
            raise ValueError(f"ticker/company 값이 비어 있습니다: {item}")

        normalized.append((ticker, company))

    return normalized


def set_report_step(state: ReportState | None, step: str):
    if state is not None:
        state["current_step"] = step


def append_report_error(state: ReportState | None, message: str):
    if state is None:
        return

    state.setdefault("errors", []).append(message)


def create_llms(openai_api_key: str):
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

    return fast_llm, fact_llm, smart_llm


def create_crew_components(fast_llm, fact_llm, smart_llm):
    return {
        "agents": {},
        "tasks": {},
    }


def run_python_module_call_with_timeout(step_name: str, code: str, timeout_seconds: int):
    try:
        result = subprocess.run(
            [sys.executable, "-B", "-c", code],
            cwd=BACKEND_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "%s timeout(%s초). 기존 YouTube Vector DB를 사용해 계속 진행합니다.",
            step_name,
            timeout_seconds,
        )
        return False
    except Exception as e:
        logger.warning(
            "%s 실행 실패. 기존 YouTube Vector DB를 사용해 계속 진행합니다: %s",
            step_name,
            e,
        )
        return False

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        detail = stderr or stdout or f"returncode={result.returncode}"
        logger.warning(
            "%s 실패. 기존 YouTube Vector DB를 사용해 계속 진행합니다: %s",
            step_name,
            detail[-1000:],
        )
        return False

    logger.info("%s 완료", step_name)
    return True


def update_youtube_vector_db():
    logger.debug("[0단계] 유튜브 최신 영상 확인...")

    try:
        new_vids = fetch_all_latest_youtube_ids(fetch_limit=5)

        if not new_vids:
            logger.info("유튜브 신규 영상 없음. 기존 DB를 사용합니다.")
            return

        processable_vids, skipped_vids = filter_processable_video_ids(new_vids)

        if skipped_vids:
            logger.warning(
                "유튜브 최신 영상 %s개는 live/upcoming/처리 불가 상태라 pending 저장 후 스킵했습니다.",
                len(skipped_vids),
            )

        if not processable_vids:
            logger.info(
                "이번 리포트 생성 중 처리 가능한 유튜브 신규 영상이 없어 기존 DB를 사용합니다."
            )
            return

        logger.info(
            "유튜브 최신 영상 %s개 감지. YouTube Vector DB를 제한 시간 안에서 업데이트합니다.",
            len(processable_vids),
        )

        if not run_python_module_call_with_timeout(
            "YouTube transcript update",
            "from vector_db.update_youtube_db import build_local_youtube_db; build_local_youtube_db()",
            YOUTUBE_UPDATE_TIMEOUT_SECONDS,
        ):
            return

        run_python_module_call_with_timeout(
            "YouTube vector DB rebuild",
            "from vector_db.build_vector_db import build_db_from_transcripts; build_db_from_transcripts()",
            YOUTUBE_UPDATE_TIMEOUT_SECONDS,
        )

    except Exception as e:
        logger.exception(f"유튜브 DB 업데이트 실패. 기존 DB로 진행합니다: {e}")


def build_macro_fallback(error: str | None = None):
    return {
        "exchange_rate": None,
        "us_10y_yield": None,
        "nasdaq_index": None,
        "wti_price": None,
        "vix_index": None,
        "exchange_rate_change_1mo": None,
        "us_10y_yield_change_1mo": None,
        "nasdaq_index_change_1mo": None,
        "wti_price_change_1mo": None,
        "vix_index_change_1mo": None,
        "risk_warnings": [],
        "macro_briefing": "macro data collection failed; neutral state applied",
        "is_data_valid": False,
        "error": error or "macro_result invalid",
    }


def run_macro_step(macro_agent=None, macro_tasks=None, state: ReportState | None = None):
    set_report_step(state, "macro")
    logger.debug("macro analysis started")

    try:
        macro_data = collect_macro_data()
    except Exception as e:
        logger.exception("macro data collection failed; neutral macro_score applied")
        append_report_error(state, f"macro data collection failed: {e}")
        macro_data = build_macro_fallback(str(e))

    if not macro_data or not macro_data.get("is_data_valid"):
        logger.warning("macro data collection failed; neutral macro_score applied")
        macro_score = 0
        macro_score_reasons = ["macro data collection failed; neutral score applied"]
        macro_data = {**build_macro_fallback(), **(macro_data or {})}
        macro_json = json.dumps(
            macro_data,
            ensure_ascii=False,
            indent=2,
        )
    else:
        macro_json = json.dumps(macro_data, ensure_ascii=False, indent=2)

        macro_score, macro_score_reasons = calculate_macro_score(
            exchange_rate=macro_data.get("exchange_rate"),
            us_10y_yield=macro_data.get("us_10y_yield"),
            vix_index=macro_data.get("vix_index"),
        )

    logger.info(f"매크로 분석 완료 (Macro Score: {macro_score}, 이유: {macro_score_reasons})")

    if state is not None:
        state["macro_data"] = {
            "raw": macro_data,
            "json": macro_json,
            "macro_score": macro_score,
            "macro_score_reasons": macro_score_reasons,
        }

    return macro_score, macro_score_reasons, macro_json


def build_failed_report_item(ticker: str, company: str, message: str):
    return {
        "ticker": ticker,
        "company": company,
        "status": "FAILED",
        "report": message,
    }


def run_accounting_step(
    accounting_agent=None,
    acc_tasks=None,
    ticker: str = "",
    company: str = "",
    state: ReportState | None = None,
):
    set_report_step(state, "accounting")
    acc_data = collect_financial_data(ticker)

    if not acc_data or not acc_data.get("is_data_valid"):
        msg = f"[분석 중단] {company}: 재무 데이터 수집 실패 또는 파싱 오류"
        logger.error(msg)
        append_report_error(state, msg)
        if state is not None:
            state["status"] = "failed"
        return None, build_failed_report_item(ticker, company, msg)

    if state is not None:
        state["accounting_data"] = acc_data

    net_income = acc_data.get("net_income", [])
    fcf = acc_data.get("fcf", [])
    revenue = acc_data.get("revenue", [])

    if (
        not is_valid_numeric_series(net_income)
        or not is_valid_numeric_series(fcf)
        or not is_valid_numeric_series(revenue)
    ):
        msg = f"[분석 중단] {company} FAIL 사유: 3개년 재무 데이터 부족 또는 숫자형 데이터 오류"
        logger.warning(msg)
        append_report_error(state, msg)
        if state is not None:
            state["status"] = "failed"
        return None, build_failed_report_item(ticker, company, msg)

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
        msg = f"[분석 중단] {company} FAIL 사유: {fail_reason}"
        logger.warning(msg)
        append_report_error(state, msg)
        if state is not None:
            state["status"] = "failed"
        return None, build_failed_report_item(ticker, company, msg)

    fund_score, fund_score_reasons = calculate_fundamental_score(
        net_income=net_income,
        fcf=fcf,
        revenue=revenue,
        debt_to_equity=debt_to_equity,
    )

    acc_data["status"] = "PASS"
    acc_data["fundamental_score"] = fund_score
    acc_data["fundamental_score_reasons"] = fund_score_reasons
    if state is not None:
        state["accounting_data"] = acc_data

    logger.info(f"재무 검증 통과 (Fund Score: {fund_score})")

    return acc_data, None


def build_research_fallback(error: str | None = None):
    data = {
        "sentiment_score": 50,
        "momentum_strength": "LOW",
        "news_summary": "리서치 데이터 수집 실패로 fallback 처리했습니다.",
        "is_data_valid": False,
    }

    if error:
        data["error"] = error

    return data


def build_research_queries(company: str):
    return [
        f"{company} 최신 뉴스 주가 전망",
        f"{company} 주가 수급 투자심리 기관 외국인",
        f"{company} 실적 전망 목표가 증권사 리포트",
        f"{company} 산업 경쟁사 시장점유율 수요 전망",
        f"{company} stock news earnings analyst rating outlook",
    ]


def parse_research_search_result(raw_result, query: str):
    if isinstance(raw_result, str):
        return json.loads(raw_result)

    if isinstance(raw_result, dict):
        return raw_result

    return {
        "is_data_valid": False,
        "error": f"unexpected research search result type: {type(raw_result).__name__}",
        "query": query,
        "results": [],
    }


def run_research_search(query: str):
    return parse_research_search_result(search_tool._run(query), query)


def dedupe_research_results(results):
    deduped = []
    seen = set()

    for item in results:
        if not isinstance(item, dict):
            continue

        title = str(item.get("title") or "").strip()
        link = str(item.get("link") or "").strip()
        snippet = str(item.get("snippet") or "").strip()

        if not title and not snippet:
            continue

        key = (link or title).lower()
        if key in seen:
            continue

        seen.add(key)
        deduped.append(
            {
                "title": title[:300] or "제목 없음",
                "source": str(item.get("source") or "출처 불명")[:100],
                "date": str(item.get("date") or "날짜 없음")[:100],
                "link": link[:500] or "URL 없음",
                "snippet": snippet[:1000],
            }
        )

    return deduped


def score_research_results(results):
    positive_keywords = [
        "상승",
        "호재",
        "수주",
        "실적 개선",
        "목표가 상향",
        "흑자",
        "성장",
        "earnings beat",
        "upgrade",
        "outperform",
        "buy",
        "record",
    ]
    negative_keywords = [
        "하락",
        "악재",
        "실적 부진",
        "목표가 하향",
        "적자",
        "소송",
        "감소",
        "downgrade",
        "sell",
        "miss",
        "loss",
        "recall",
    ]

    joined = " ".join(
        f"{item.get('title', '')} {item.get('snippet', '')}".lower()
        for item in results
        if isinstance(item, dict)
    )
    positive_hits = sum(1 for keyword in positive_keywords if keyword.lower() in joined)
    negative_hits = sum(1 for keyword in negative_keywords if keyword.lower() in joined)

    score = 50 + min(20, positive_hits * 5) - min(20, negative_hits * 5)
    score = max(15, min(85, score))

    distance = abs(score - 50)
    if len(results) >= 3 and distance >= 15:
        strength = "HIGH"
    elif distance >= 8:
        strength = "MEDIUM"
    else:
        strength = "LOW"

    return score, strength


def summarize_research_results(company: str, results):
    if not results:
        return "유효한 최신 뉴스 결과가 없어 중립 fallback으로 처리했습니다."

    summary_lines = []
    for item in results[:3]:
        title = item.get("title") or "제목 없음"
        source = item.get("source") or "출처 불명"
        date = item.get("date") or "날짜 없음"
        snippet = item.get("snippet") or ""
        summary_lines.append(
            f"{company} 관련 뉴스: {title} ({source}, {date}) - {snippet[:180]}"
        )

    return "\n".join(summary_lines)


def collect_research_data(company: str):
    all_results = []
    errors = []

    for query in build_research_queries(company):
        try:
            search_result = run_research_search(query)
        except Exception as e:
            errors.append(f"{query}: {e}")
            continue

        if not search_result.get("is_data_valid"):
            error = search_result.get("error")
            if error:
                errors.append(f"{query}: {error}")
            continue

        all_results.extend(search_result.get("results") or [])

    results = dedupe_research_results(all_results)

    if not results:
        fallback = build_research_fallback(
            "; ".join(errors) if errors else "no valid news results"
        )
        fallback["queries"] = build_research_queries(company)
        fallback["results"] = []
        return fallback

    sentiment_score, momentum_strength = score_research_results(results)

    return {
        "sentiment_score": sentiment_score,
        "momentum_strength": momentum_strength,
        "news_summary": summarize_research_results(company, results),
        "is_data_valid": True,
        "queries": build_research_queries(company),
        "result_count": len(results),
        "results": results[:10],
        "errors": errors,
    }


def run_research_step(
    researcher_agent=None,
    res_tasks=None,
    company: str = "",
    state: ReportState | None = None,
):
    set_report_step(state, "research")
    try:
        return DirectResult(collect_research_data(company))
    except Exception as e:
        logger.exception(f"[{company}] 리서치 데이터 수집 실패. fallback 처리: {e}")
        append_report_error(state, f"리서치 데이터 수집 실패: {e}")
        return DirectResult(build_research_fallback(str(e)))


def parse_research_result(research_result, company: str, state: ReportState | None = None):
    if not research_result.pydantic or not getattr(research_result.pydantic, "is_data_valid", False):
        logger.warning(f"[{company}] research data invalid; fallback applied")
        research_data = {
                "sentiment_score": 50,
                "momentum_strength": "LOW",
                "news_summary": "리서치 데이터 수집 실패로 fallback 처리되었습니다.",
                "is_data_valid": False,
            }
        research_json = json.dumps(
            research_data,
            ensure_ascii=False,
        )
        if state is not None:
            state["research_data"] = {
                "raw": research_data,
                "json": research_json,
                "sentiment": 0,
            }
        return 0, research_json

    score = research_result.pydantic.sentiment_score

    research_cfg = SCORING_CONFIG["research"]

    if score >= research_cfg["positive_cutoff"]:
        sentiment = 1
    elif score <= research_cfg["negative_cutoff"]:
        sentiment = -1
    else:
        sentiment = 0

    research_data = research_result.pydantic.model_dump(mode="json")
    research_json = research_result.pydantic.model_dump_json(indent=2)
    if state is not None:
        state["research_data"] = {
            "raw": research_data,
            "json": research_json,
            "sentiment": sentiment,
        }

    return sentiment, research_json


def build_youtube_fallback(error: str | None = None):
    data = {
        "guru_sentiment_score": 50.0,
        "key_strategy": "N/A",
        "content_type": "N/A",
        "insight_date": "N/A",
        "freshness_level": "N/A",
        "mindset_summary": "youtube fallback applied",
        "market_principle": "youtube fallback applied",
        "risk_control": "youtube fallback applied",
        "guru_insight_details": "유튜브 데이터 수집 실패로 fallback 처리했습니다.",
        "is_data_valid": False,
    }

    if error:
        data["error"] = error

    return data


def parse_youtube_search_result(raw_result):
    if isinstance(raw_result, str):
        return json.loads(raw_result)

    if isinstance(raw_result, dict):
        return raw_result

    return {
        "is_data_valid": False,
        "error": f"unexpected youtube search result type: {type(raw_result).__name__}",
        "selected_docs": [],
        "content_type_hint": "N/A",
        "freshness_level": "N/A",
        "latest_date": "N/A",
    }


def run_local_youtube_search(company: str):
    return parse_youtube_search_result(get_guru_youtube_tool()._run(company))


def score_youtube_docs(content_type: str, freshness_level: str, selected_docs):
    if content_type != "SPECIFIC" or freshness_level not in ["FRESH", "RECENT"]:
        return 50.0

    joined = " ".join(
        f"{doc.get('title', '')} {doc.get('content', '')}".lower()
        for doc in selected_docs
        if isinstance(doc, dict)
    )
    positive_keywords = [
        "매수",
        "좋은 기업",
        "기회",
        "성장",
        "상승",
        "저평가",
        "buy",
        "growth",
        "opportunity",
    ]
    negative_keywords = [
        "매도",
        "위험",
        "리스크",
        "하락",
        "고평가",
        "주의",
        "sell",
        "risk",
        "overvalued",
    ]

    positive_hits = sum(1 for keyword in positive_keywords if keyword.lower() in joined)
    negative_hits = sum(1 for keyword in negative_keywords if keyword.lower() in joined)
    score = 50.0 + min(20, positive_hits * 5) - min(20, negative_hits * 5)

    if freshness_level == "RECENT":
        score = 50.0 + ((score - 50.0) * 0.6)

    return float(max(35.0, min(65.0, score)))


def summarize_youtube_docs(selected_docs, max_docs=3):
    if not selected_docs:
        return "유효한 유튜브 인사이트가 없어 중립 fallback으로 처리했습니다."

    lines = []
    for doc in selected_docs[:max_docs]:
        date = doc.get("date") or "N/A"
        title = doc.get("title") or "제목 없음"
        search_type = doc.get("search_type") or doc.get("theme_hint") or "GENERAL"
        content = str(doc.get("content") or "")[:220]
        lines.append(f"{date} / {title} / {search_type}: {content}")

    return "\n".join(lines)


def build_youtube_data_from_search(company: str, search_result):
    selected_docs = search_result.get("selected_docs") or []
    content_type = search_result.get("content_type_hint") or "N/A"
    freshness_level = search_result.get("freshness_level") or "N/A"
    insight_date = search_result.get("latest_date") or "N/A"

    if not search_result.get("is_data_valid") or not selected_docs:
        return build_youtube_fallback(search_result.get("error") or "no relevant youtube results")

    guru_score = score_youtube_docs(content_type, freshness_level, selected_docs)
    details = summarize_youtube_docs(selected_docs)

    if content_type == "SPECIFIC":
        key_strategy = "종목 직접 언급 자료를 참고하되, 스크립트에 없는 가격 판단은 만들지 않습니다."
    elif content_type in ["MARKET", "MINDSET", "RISK", "PSYCHOLOGY"]:
        key_strategy = "구루의 시장 원칙과 리스크 관리 관점을 현재 종목 판단에 참고합니다."
    else:
        key_strategy = "유의미한 유튜브 인사이트가 제한적이므로 중립으로 반영합니다."

    return {
        "guru_sentiment_score": guru_score,
        "key_strategy": key_strategy,
        "content_type": content_type,
        "insight_date": insight_date,
        "freshness_level": freshness_level,
        "mindset_summary": details,
        "market_principle": details,
        "risk_control": details,
        "guru_insight_details": details[:1200],
        "is_data_valid": True,
    }


def run_youtube_rag_step(
    youtube_agent=None,
    yt_tasks=None,
    company: str = "",
    state: ReportState | None = None,
):
    set_report_step(state, "youtube_rag")
    try:
        search_result = run_local_youtube_search(company)
        return DirectResult(build_youtube_data_from_search(company, search_result))
    except Exception as e:
        logger.exception(f"[{company}] 유튜브 데이터 수집 실패. fallback 처리: {e}")
        append_report_error(state, f"유튜브 데이터 수집 실패: {e}")
        return DirectResult(build_youtube_fallback(str(e)))


def parse_youtube_result(youtube_result, company: str, state: ReportState | None = None):
    if not youtube_result.pydantic or not getattr(youtube_result.pydantic, "is_data_valid", False):
        logger.warning(f"[{company}] youtube data invalid; fallback applied")
        youtube_data = {
                "guru_sentiment_score": 50.0,
                "key_strategy": "N/A",
                "content_type": "N/A",
                "insight_date": "N/A",
                "freshness_level": "N/A",
                "mindset_summary": "youtube fallback applied",
                "market_principle": "youtube fallback applied",
                "risk_control": "youtube fallback applied",
                "guru_insight_details": "유튜브 데이터 수집 실패로 fallback 처리되었습니다.",
                "is_data_valid": False,
            }
        youtube_json = json.dumps(
            youtube_data,
            ensure_ascii=False,
        )
        if state is not None:
            state["youtube_context"] = youtube_json
        return 50.0, 0.0, youtube_json

    guru_score = youtube_result.pydantic.guru_sentiment_score
    content_type = getattr(youtube_result.pydantic, "content_type", "UNKNOWN")
    freshness_level = getattr(youtube_result.pydantic, "freshness_level", "UNKNOWN")
    insight_date = getattr(youtube_result.pydantic, "insight_date", "N/A")

    # 구루 점수 70%는 정성적 인사이트를 반영하기 위한 가중치다.
    # MARKET/MINDSET/RISK/PSYCHOLOGY 기반 인사이트가 없으면 시스템 점수만 사용한다.
    if (
        content_type == "SPECIFIC"
        and freshness_level in ["FRESH", "RECENT"]
        and guru_score != 50.0
    ):
        guru_weight = SCORING_CONFIG["final"]["guru_weight"]
    else:
        guru_weight = 0.0

    logger.debug(
        f"[{company}] 유튜브 인사이트 적용: {content_type} "
        f"| 신선도: {freshness_level} | 기준일: {insight_date} "
        f"| Guru Score: {guru_score} | Guru Weight: {guru_weight:.0%}"
    )

    youtube_json = youtube_result.pydantic.model_dump_json(indent=2)
    if state is not None:
        state["youtube_context"] = youtube_json

    return guru_score, guru_weight, youtube_json


def decide_final_opinion(
    acc_data,
    macro_score,
    sentiment,
    guru_score,
    guru_weight,
    company: str,
    state: ReportState | None = None,
):
    set_report_step(state, "opinion")
    fundamental_score = acc_data.get("fundamental_score", 0)

    total_score = fundamental_score + macro_score + sentiment

    # total_score 범위
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
        f"[시스템 채점] {company} | 시스템 점수: {system_score}점 "
        f"(재무 {fundamental_score} + 매크로 {macro_score} + 뉴스 {sentiment})"
    )
    logger.info(
        f"[최종 판정] {company} | 종합 {final_weighted_score:.1f}점 "
        f"(시스템 {system_weight:.0%} + 구루 {guru_weight:.0%}[{guru_sentiment_label}]) → {final_opinion}"
    )

    return final_opinion


def calculate_price_targets(acc_data, company: str, state: ReportState | None = None):
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
        logger.warning(f"[{company}] price data missing; skip price target")

    if state is not None:
        state["price_data"] = {
            "current_price": current_price,
            "target_buy_price": target_buy_price,
            "defense_price": defense_price,
        }

    return current_price, target_buy_price, defense_price


def run_price_step(acc_data, company: str, state: ReportState | None = None):
    set_report_step(state, "price")
    return calculate_price_targets(acc_data, company, state=state)


def build_analysis_chart_data(acc_data):
    revenue = acc_data.get("revenue") if isinstance(acc_data, dict) else []
    net_income = acc_data.get("net_income") if isinstance(acc_data, dict) else []
    fcf = acc_data.get("fcf") if isinstance(acc_data, dict) else []
    periods = ["T-2", "T-1", "T"]
    chart_data = []

    for index, period in enumerate(periods):
        chart_data.append(
            {
                "period": period,
                "revenue": float(revenue[index]) if index < len(revenue) and isinstance(revenue[index], (int, float)) else 0.0,
                "net_profit": float(net_income[index]) if index < len(net_income) and isinstance(net_income[index], (int, float)) else 0.0,
                "fcf": float(fcf[index]) if index < len(fcf) and isinstance(fcf[index], (int, float)) else 0.0,
            }
        )

    return chart_data


def build_analysis_fallback(
    company: str = "",
    final_opinion: str = "Hold",
    acc_data=None,
    macro_json="",
    research_json="",
    youtube_json="",
    error: str | None = None,
):
    return {
        "investment_opinion": final_opinion,
        "one_line_conclusion": f"{company} 분석 결과는 {final_opinion} 의견입니다.",
        "executive_summary": [
            "시스템 산출 투자 의견을 기준으로 리포트를 구성했습니다.",
            "일부 분석 문장 생성에 실패해 입력 데이터 중심의 fallback을 적용했습니다.",
            "가격과 차트 데이터는 기존 계산 결과를 유지했습니다.",
        ],
        "macro_analysis": truncate_text(macro_json, 900) or "매크로 데이터가 제한적입니다.",
        "fundamental_analysis": truncate_text(json.dumps(acc_data or {}, ensure_ascii=False), 900),
        "momentum_analysis": truncate_text(research_json, 700) or "뉴스 데이터가 제한적입니다.",
        "guru_analysis": truncate_text(youtube_json, 800) or "유튜브 인사이트가 제한적입니다.",
        "final_conclusion": error or "직접 분석 생성 실패로 fallback 리포트를 작성했습니다.",
        "chart_data": build_analysis_chart_data(acc_data or {}),
    }


def normalize_analysis_output(data, final_opinion: str, acc_data):
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    elif not isinstance(data, dict):
        data = {}

    normalized = dict(data)
    normalized["investment_opinion"] = final_opinion

    summary = normalized.get("executive_summary")
    if not isinstance(summary, list):
        summary = [str(summary)] if summary else []
    normalized["executive_summary"] = [str(item) for item in summary[:3]]
    while len(normalized["executive_summary"]) < 3:
        normalized["executive_summary"].append("입력 데이터를 기준으로 보수적으로 판단했습니다.")

    for key in [
        "one_line_conclusion",
        "macro_analysis",
        "fundamental_analysis",
        "momentum_analysis",
        "guru_analysis",
        "final_conclusion",
    ]:
        if not normalized.get(key):
            normalized[key] = "데이터가 제한적이므로 보수적으로 해석했습니다."

    chart_data = normalized.get("chart_data")
    if not isinstance(chart_data, list) or not chart_data:
        chart_data = build_analysis_chart_data(acc_data or {})

    normalized["chart_data"] = [
        {
            "period": str(item.get("period", f"T-{2 - index}") if isinstance(item, dict) else f"T-{2 - index}"),
            "revenue": float(item.get("revenue", 0) if isinstance(item, dict) and isinstance(item.get("revenue", 0), (int, float)) else 0),
            "net_profit": float(item.get("net_profit", 0) if isinstance(item, dict) and isinstance(item.get("net_profit", 0), (int, float)) else 0),
            "fcf": float(item.get("fcf", 0) if isinstance(item, dict) and isinstance(item.get("fcf", 0), (int, float)) else 0),
        }
        for index, item in enumerate(chart_data[:3])
    ]

    return normalized


def call_analysis_structured_output(
    company: str = "",
    analysis_inputs=None,
    final_opinion: str = "Hold",
    target_buy_price=None,
    defense_price=None,
):
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    target_buy_price_text = (
        f"{target_buy_price:,.2f}"
        if isinstance(target_buy_price, (int, float))
        else "N/A"
    )
    defense_price_text = (
        f"{defense_price:,.2f}"
        if isinstance(defense_price, (int, float))
        else "N/A"
    )

    completion = client.beta.chat.completions.parse(
        model=os.getenv("OPENAI_ANALYSIS_MODEL", "gpt-4o-mini"),
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior investment report writer. Return only structured "
                    "data matching the schema. Do not override the provided system "
                    "investment opinion. Do not invent prices, earnings, or YouTube claims."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Company: {company}\n"
                    f"System investment opinion: {final_opinion}\n"
                    f"Target buy price: {target_buy_price_text}\n"
                    f"Defense price: {defense_price_text}\n\n"
                    f"Accounting data:\n{analysis_inputs['accounting']}\n\n"
                    f"Macro data:\n{analysis_inputs['macro']}\n\n"
                    f"Research data:\n{analysis_inputs['research']}\n\n"
                    f"YouTube data:\n{analysis_inputs['youtube']}\n\n"
                    "Write concise Korean report fields. chart_data must contain T-2, "
                    "T-1, T using accounting revenue, net_income as net_profit, and fcf "
                    "raw numeric values."
                ),
            },
        ],
        response_format=DirectAnalysisOutput,
    )

    return completion.choices[0].message.parsed


def run_final_analysis_step(
    analyst_agent=None,
    ana_tasks=None,
    company: str = "",
    acc_data=None,
    macro_json="",
    research_json="",
    youtube_json="",
    final_opinion: str = "Hold",
    target_buy_price=None,
    defense_price=None,
    state: ReportState | None = None,
):
    set_report_step(state, "analysis")
    analysis_inputs = compact_analysis_inputs(
        acc_data=acc_data,
        macro_json=macro_json,
        research_json=research_json,
        youtube_json=youtube_json,
    )

    logger.debug(f"[{company}] 최종 리포트 생성 중...")
    try:
        result_data = call_analysis_structured_output(
            company=company,
            analysis_inputs=analysis_inputs,
            final_opinion=final_opinion,
            target_buy_price=target_buy_price,
            defense_price=defense_price,
        )
        normalized = normalize_analysis_output(result_data, final_opinion, acc_data)
        return DirectResult(normalized)
    except Exception as e:
        logger.exception(f"[{company}] analysis structured output failed; fallback applied: {e}")
        append_report_error(state, f"analysis structured output failed: {e}")
        return DirectResult(
            build_analysis_fallback(
                company=company,
                final_opinion=final_opinion,
                acc_data=acc_data,
                macro_json=macro_json,
                research_json=research_json,
                youtube_json=youtube_json,
                error=str(e),
            )
        )


def render_markdown_report(
    ticker: str,
    company: str,
    final_opinion: str,
    final_result,
    current_price,
    target_buy_price,
    defense_price,
    state: ReportState | None = None,
):
    set_report_step(state, "render_report")
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

    if state is not None:
        state["chart_data"] = final_result.pydantic.model_dump(
            include={"chart_data"},
            mode="json",
        )
        state["final_report"] = {
            "investment_opinion": report_data.investment_opinion,
            "one_line_conclusion": report_data.one_line_conclusion,
            "markdown": md_report,
        }
        state["status"] = "report_generated"

    return md_report

def build_run_summary_output(macro_json, all_reports):
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

    return summary_output

def build_output_report_item(state: ReportState):
    final_report = state.get("final_report") or {}
    report = final_report.get("markdown") or final_report.get("raw")

    if report is None:
        report = "\n".join(state.get("errors", [])) or "분석 실패"

    return {
        "ticker": state.get("ticker"),
        "company": state.get("company_name"),
        "status": "SUCCESS" if state.get("status") in ["report_generated", "completed"] else "FAILED",
        "report": report,
    }


def finalize_state(state: ReportState):
    has_report = bool(state.get("final_report") or state.get("markdown_report"))

    if state.get("status") == "failed":
        return state

    if has_report and state.get("summary_saved") is True:
        state["status"] = "completed"
    elif has_report:
        state["status"] = "report_generated"
    else:
        state["status"] = "failed"

    return state


def build_failed_state(target, error):
    if isinstance(target, dict):
        ticker = target.get("ticker")
        company_name = target.get("company_name") or target.get("company")
    else:
        ticker, company_name = target

    state = create_initial_report_state(ticker, company_name)
    state["status"] = "failed"
    state["current_step"] = "failed"
    state["summary_saved"] = False
    state.setdefault("errors", []).append(str(error))
    state["final_report"] = {
        "raw": f"[종목 분석 실패] {company_name} ({ticker}) 예외 발생: {error}",
    }
    state["output_report"] = build_output_report_item(state)
    return state


def run_single_report_pipeline(
    ticker,
    company_name,
    agents,
    tasks,
    macro_context,
):
    state = create_initial_report_state(ticker, company_name)

    if macro_context.get("macro_data"):
        state["macro_data"] = macro_context["macro_data"]

    try:
        logger.info(f"분석 시작: {company_name} ({ticker})")

        acc_data, failed_item = run_accounting_step(
            ticker=ticker,
            company=company_name,
            state=state,
        )

        if failed_item:
            state["output_report"] = failed_item
            return finalize_state(state)

        logger.debug(f"[{company_name}] 리서치 데이터 수집 중...")
        research_result = run_research_step(
            company=company_name,
            state=state,
        )

        logger.debug(f"[{company_name}] 유튜브 데이터 수집 중...")
        youtube_result = run_youtube_rag_step(
            company=company_name,
            state=state,
        )

        sentiment, research_json = parse_research_result(
            research_result,
            company_name,
            state=state,
        )

        guru_score, guru_weight, youtube_json = parse_youtube_result(
            youtube_result,
            company_name,
            state=state,
        )

        final_opinion = decide_final_opinion(
            acc_data=acc_data,
            macro_score=macro_context["macro_score"],
            sentiment=sentiment,
            guru_score=guru_score,
            guru_weight=guru_weight,
            company=company_name,
            state=state,
        )

        current_price, target_buy_price, defense_price = run_price_step(
            acc_data,
            company_name,
            state=state,
        )

        final_result = run_final_analysis_step(
            company=company_name,
            acc_data=acc_data,
            macro_json=macro_context["macro_json"],
            research_json=research_json,
            youtube_json=youtube_json,
            final_opinion=final_opinion,
            target_buy_price=target_buy_price,
            defense_price=defense_price,
            state=state,
        )

        if final_result.pydantic:
            md_report = render_markdown_report(
                ticker=ticker,
                company=company_name,
                final_opinion=final_opinion,
                final_result=final_result,
                current_price=current_price,
                target_buy_price=target_buy_price,
                defense_price=defense_price,
                state=state,
            )
            state["output_report"] = {
                "ticker": ticker,
                "company": company_name,
                "status": "SUCCESS",
                "report": md_report,
            }
            logger.info(f"[{company_name}] 리포트 생성 완료")
        else:
            fallback_report = f"[{company_name}]\n{final_result.raw}"
            append_report_error(state, "Analysis 에이전트 구조화 파싱 실패")
            state["status"] = "failed"
            state["final_report"] = {
                "raw": final_result.raw,
                "markdown": fallback_report,
            }
            state["output_report"] = {
                "ticker": ticker,
                "company": company_name,
                "status": "FAILED",
                "report": fallback_report,
            }
            logger.error(f"[{company_name}] Analysis 에이전트 구조화 파싱 실패")

    except Exception as e:
        msg = f"[종목 분석 실패] {company_name} ({ticker}) 예외 발생: {e}"
        logger.exception(msg)
        append_report_error(state, msg)
        state["status"] = "failed"
        state["summary_saved"] = False
        state["final_report"] = {
            "raw": msg,
        }
        state["output_report"] = {
            "ticker": ticker,
            "company": company_name,
            "status": "FAILED",
            "report": msg,
        }

    return finalize_state(state)


def build_macro_context(agents=None, tasks=None):
    macro_state: ReportState = {
        "status": "running",
        "current_step": "macro",
        "errors": [],
    }
    macro_score, macro_score_reasons, macro_json = run_macro_step(
        state=macro_state,
    )

    return {
        "macro_data": macro_state.get("macro_data"),
        "macro_score": macro_score,
        "macro_score_reasons": macro_score_reasons,
        "macro_json": macro_json,
    }


def run_multiple_report_pipeline(targets, agents, tasks, macro_context=None, status_callback=None):
    from graphs.report_graph import run_single_report_graph

    if macro_context is None:
        macro_context = build_macro_context(agents, tasks)

    results = []

    for ticker, company_name in targets:
        try:
            state = run_single_report_graph(
                ticker,
                company_name,
                agents,
                tasks,
                macro_context,
                status_callback=status_callback,
            )
        except Exception as e:
            logger.exception(f"종목별 리포트 생성 중 예외 발생: {company_name} ({ticker})")
            state = build_failed_state((ticker, company_name), e)

            if status_callback:
                status_callback(state)

        results.append(state)

    return results, macro_context


def run_financial_crew(stock_pool=None, status_callback=None):
    stock_pool = normalize_stock_pool(stock_pool)
    openai_api_key = require_env("OPENAI_API_KEY")

    # 뉴스 리서치에서 사용
    require_env("SERPER_API_KEY")

    fast_llm, fact_llm, smart_llm = create_llms(openai_api_key)
    crew_components = create_crew_components(fast_llm, fact_llm, smart_llm)
    agents = crew_components["agents"]
    tasks = crew_components["tasks"]

    # ---------------------------------------------------------
    # 0. 유튜브 DB 업데이트
    # ---------------------------------------------------------
    update_youtube_vector_db()

    logger.debug("report pipeline started")
    report_states, macro_context = run_multiple_report_pipeline(
        stock_pool,
        agents,
        tasks,
        status_callback=status_callback,
    )
    all_reports = [
        state.get("output_report") or build_output_report_item(state)
        for state in report_states
    ]
    summary_output = build_run_summary_output(macro_context["macro_json"], all_reports)

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "summary": summary_output,
        "reports": all_reports,
        "_report_states": report_states,
    }

if __name__ == "__main__":
    output = run_financial_crew()

    logger.debug("=" * 60)
    logger.debug("report pipeline started")
    logger.debug("=" * 60)

    print(output["summary"])

    save_report_files(output)
