import os
import json
import logging
import subprocess
import sys
from dotenv import load_dotenv
from types import SimpleNamespace
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pydantic import BaseModel, Field
from typing import List

from flows.research.tool import search_tool
from flows.accounting.tool import collect_financial_data
from flows.macro.tool import collect_macro_data
from flows.youtube.tool import get_guru_youtube_tool

# ?좏뒠釉??먮룞???뚯씠?꾨씪???꾪룷??
from vector_db.fetch_latest_youtube_ids import fetch_all_latest_youtube_ids
from vector_db.fetch_latest_youtube_ids import fetch_all_latest_youtube_ids
from vector_db.youtube_update_guard import filter_processable_video_ids
from services.report_file_service import save_report_files
from services.summary_service import extract_report_summary
from schemas.report_state import ReportState, create_initial_report_state

# ?쒖뒪??濡쒓퉭 諛??붾쾭源??덉씠??

# 0. ?섍꼍 蹂??濡쒕뱶
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
        raise RuntimeError(f"?섍꼍蹂???꾨씫: {name}")
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

    # 1) ?ъ옄 ?щ━: VIX
    if vix_index >= cfg["vix_high_risk"]:
        score -= 1
        reasons.append(f"VIX {vix_index} high risk")
    elif 0 < vix_index <= cfg["vix_low_risk"]:
        score += 1
        reasons.append(f"VIX {vix_index} stable")

    # 2) ?좎씤?? 誘멸뎅 10?꾨Ъ 湲덈━
    if us_10y_yield >= cfg["us_10y_high_risk"]:
        score -= 1
        reasons.append(f"US 10Y {us_10y_yield} high yield pressure")
    elif 0 < us_10y_yield <= cfg["us_10y_low_risk"]:
        score += 1
        reasons.append(f"US 10Y {us_10y_yield} low yield relief")

    # 3) ?섏쑉
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

    # ?쒖씠??
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

    # 留ㅼ텧
    if revenue[-1] > revenue[-2]:
        score += 1
        reasons.append("recent revenue declined")
    elif revenue[-1] < revenue[-2]:
        score -= 1
        reasons.append("recent revenue growth")

    # 遺梨꾨퉬??
    debt_warning_cutoff = SCORING_CONFIG["financial"]["debt_warning_cutoff"]
    if isinstance(debt_to_equity, (int, float)) and debt_to_equity > debt_warning_cutoff:
        score -= 1
        reasons.append(f"debt-to-equity {debt_to_equity}% exceeds 100%")

    # 怨쇰룄???곹뼢 諛⑹?: -3 ~ +3?쇰줈 ?쒗븳
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
    理쒖쥌 遺꾩꽍 structured-output ?몄텧???꾨떖???낅젰???뺤텞?쒕떎.
    ?덈Т 湲??먮낯 JSON??洹몃?濡??ｌ쑝硫??좏겙 珥덇낵 ?먮뒗 Pydantic ?뚯떛 ?ㅽ뙣 ?꾪뿕??而ㅼ쭊??
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



def normalize_stock_pool(stock_pool):
    """
    ?몃? ?낅젰 醫낅ぉ ?곗씠?곕? main.py ?대? ?쒖? ?뺤떇?쇰줈 蹂?섑븳??
    ?쒖? ?뺤떇: [("TSLA", "Tesla"), ("005930.KS", "Samsung Electronics")]
    """

    default_stock_pool = [
        ("TSLA", "Tesla"),
        ("005930.KS", "Samsung Electronics"),
        ("000660.KS", "SK Hynix"),
    ]

    if stock_pool is None:
        return default_stock_pool

    if not isinstance(stock_pool, list) or not stock_pool:
        raise ValueError("stock_pool? 鍮꾩뼱 ?덉? ?딆? list?ъ빞 ?⑸땲??")

    normalized = []

    for item in stock_pool:
        if isinstance(item, dict):
            ticker = item.get("ticker")
            company = item.get("company")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            ticker, company = item
        else:
            raise ValueError(f"?섎せ??醫낅ぉ ?낅젰 ?뺤떇?낅땲?? {item}")

        ticker = normalize_kr_ticker(ticker)
        company = str(company).strip() if company else ""

        if not ticker or not company:
            raise ValueError(f"ticker/company 媛믪씠 鍮꾩뼱 ?덉뒿?덈떎: {item}")

        normalized.append((ticker, company))

    return normalized


def set_report_step(state: ReportState | None, step: str):
    if state is not None:
        state["current_step"] = step


def append_report_error(state: ReportState | None, message: str):
    if state is None:
        return

    state.setdefault("errors", []).append(message)


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
            "%s timeout(%s珥?. 湲곗〈 YouTube Vector DB瑜??ъ슜??怨꾩냽 吏꾪뻾?⑸땲??",
            step_name,
            timeout_seconds,
        )
        return False
    except Exception as e:
        logger.warning(
            "%s ?ㅽ뻾 ?ㅽ뙣. 湲곗〈 YouTube Vector DB瑜??ъ슜??怨꾩냽 吏꾪뻾?⑸땲?? %s",
            step_name,
            e,
        )
        return False

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        detail = stderr or stdout or f"returncode={result.returncode}"
        logger.warning(
            "%s ?ㅽ뙣. 湲곗〈 YouTube Vector DB瑜??ъ슜??怨꾩냽 吏꾪뻾?⑸땲?? %s",
            step_name,
            detail[-1000:],
        )
        return False

    logger.info("%s ?꾨즺", step_name)
    return True


def update_youtube_vector_db():
    logger.debug("[0?④퀎] ?좏뒠釉?理쒖떊 ?곸긽 ?뺤씤...")

    try:
        new_vids = fetch_all_latest_youtube_ids(fetch_limit=5)

        if not new_vids:
            logger.info("?좏뒠釉??좉퇋 ?곸긽 ?놁쓬. 湲곗〈 DB瑜??ъ슜?⑸땲??")
            return

        processable_vids, skipped_vids = filter_processable_video_ids(new_vids)

        if skipped_vids:
            logger.warning(
                "?좏뒠釉?理쒖떊 ?곸긽 %s媛쒕뒗 live/upcoming/泥섎━ 遺덇? ?곹깭??pending ??????ㅽ궢?덉뒿?덈떎.",
                len(skipped_vids),
            )

        if not processable_vids:
            logger.info(
                "?대쾲 由ы룷???앹꽦 以?泥섎━ 媛?ν븳 ?좏뒠釉??좉퇋 ?곸긽???놁뼱 湲곗〈 DB瑜??ъ슜?⑸땲??"
            )
            return

        logger.info(
            "?좏뒠釉?理쒖떊 ?곸긽 %s媛?媛먯?. YouTube Vector DB瑜??쒗븳 ?쒓컙 ?덉뿉???낅뜲?댄듃?⑸땲??",
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
        logger.exception(f"?좏뒠釉?DB ?낅뜲?댄듃 ?ㅽ뙣. 湲곗〈 DB濡?吏꾪뻾?⑸땲?? {e}")


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

    logger.info(f"留ㅽ겕濡?遺꾩꽍 ?꾨즺 (Macro Score: {macro_score}, ?댁쑀: {macro_score_reasons})")

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
        msg = f"[遺꾩꽍 以묐떒] {company}: ?щТ ?곗씠???섏쭛 ?ㅽ뙣 ?먮뒗 ?뚯떛 ?ㅻ쪟"
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
        msg = f"[遺꾩꽍 以묐떒] {company} FAIL ?ъ쑀: 3媛쒕뀈 ?щТ ?곗씠??遺議??먮뒗 ?レ옄???곗씠???ㅻ쪟"
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
        fail_reason = "3媛쒕뀈 ?곗냽 ?쒖씠???곸옄"
    elif all(f < 0 for f in fcf):
        is_fail = True
        fail_reason = "3媛쒕뀈 ?곗냽 ?됱뿬?꾧툑?먮쫫(FCF) 留덉씠?덉뒪"
    elif revenue[-1] <= 0:
        is_fail = True
        fail_reason = "理쒓렐 留ㅼ텧 ?곗씠???ㅻ쪟(0 ?댄븯)"
    elif isinstance(debt_to_equity, (int, float)) and debt_to_equity > 200:
        is_fail = True
        fail_reason = "遺梨꾨퉬??200% 珥덇낵"

    if is_fail:
        msg = f"[遺꾩꽍 以묐떒] {company} FAIL ?ъ쑀: {fail_reason}"
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

    logger.info(f"?щТ 寃利??듦낵 (Fund Score: {fund_score})")

    return acc_data, None


def build_research_fallback(error: str | None = None):
    data = {
        "sentiment_score": 50,
        "momentum_strength": "LOW",
        "news_summary": "由ъ꽌移??곗씠???섏쭛 ?ㅽ뙣濡?fallback 泥섎━?덉뒿?덈떎.",
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
                "title": title[:300] or "?쒕ぉ ?놁쓬",
                "source": str(item.get("source") or "異쒖쿂 遺덈챸")[:100],
                "date": str(item.get("date") or "?좎쭨 ?놁쓬")[:100],
                "link": link[:500] or "URL ?놁쓬",
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
        return "?좏슚??理쒖떊 ?댁뒪 寃곌낵媛 ?놁뼱 以묐┰ fallback?쇰줈 泥섎━?덉뒿?덈떎."

    summary_lines = []
    for item in results[:3]:
        title = item.get("title") or "?쒕ぉ ?놁쓬"
        source = item.get("source") or "異쒖쿂 遺덈챸"
        date = item.get("date") or "?좎쭨 ?놁쓬"
        snippet = item.get("snippet") or ""
        summary_lines.append(
            f"{company} 愿???댁뒪: {title} ({source}, {date}) - {snippet[:180]}"
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
        logger.exception(f"[{company}] 由ъ꽌移??곗씠???섏쭛 ?ㅽ뙣. fallback 泥섎━: {e}")
        append_report_error(state, f"由ъ꽌移??곗씠???섏쭛 ?ㅽ뙣: {e}")
        return DirectResult(build_research_fallback(str(e)))


def parse_research_result(research_result, company: str, state: ReportState | None = None):
    if not research_result.pydantic or not getattr(research_result.pydantic, "is_data_valid", False):
        logger.warning(f"[{company}] research data invalid; fallback applied")
        research_data = {
                "sentiment_score": 50,
                "momentum_strength": "LOW",
                "news_summary": "由ъ꽌移??곗씠???섏쭛 ?ㅽ뙣濡?fallback 泥섎━?섏뿀?듬땲??",
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
        "guru_insight_details": "?좏뒠釉??곗씠???섏쭛 ?ㅽ뙣濡?fallback 泥섎━?덉뒿?덈떎.",
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
        return "?좏슚???좏뒠釉??몄궗?댄듃媛 ?놁뼱 以묐┰ fallback?쇰줈 泥섎━?덉뒿?덈떎."

    lines = []
    for doc in selected_docs[:max_docs]:
        date = doc.get("date") or "N/A"
        title = doc.get("title") or "?쒕ぉ ?놁쓬"
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
        key_strategy = "醫낅ぉ 吏곸젒 ?멸툒 ?먮즺瑜?李멸퀬?섎릺, ?ㅽ겕由쏀듃???녿뒗 媛寃??먮떒? 留뚮뱾吏 ?딆뒿?덈떎."
    elif content_type in ["MARKET", "MINDSET", "RISK", "PSYCHOLOGY"]:
        key_strategy = "援щ（???쒖옣 ?먯튃怨?由ъ뒪??愿由?愿?먯쓣 ?꾩옱 醫낅ぉ ?먮떒??李멸퀬?⑸땲??"
    else:
        key_strategy = "?좎쓽誘명븳 ?좏뒠釉??몄궗?댄듃媛 ?쒗븳?곸씠誘濡?以묐┰?쇰줈 諛섏쁺?⑸땲??"

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
        logger.exception(f"[{company}] ?좏뒠釉??곗씠???섏쭛 ?ㅽ뙣. fallback 泥섎━: {e}")
        append_report_error(state, f"?좏뒠釉??곗씠???섏쭛 ?ㅽ뙣: {e}")
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
                "guru_insight_details": "?좏뒠釉??곗씠???섏쭛 ?ㅽ뙣濡?fallback 泥섎━?섏뿀?듬땲??",
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

    # 援щ（ ?먯닔 70%???뺤꽦???몄궗?댄듃瑜?諛섏쁺?섍린 ?꾪븳 媛以묒튂??
    # MARKET/MINDSET/RISK/PSYCHOLOGY 湲곕컲 ?몄궗?댄듃媛 ?놁쑝硫??쒖뒪???먯닔留??ъ슜?쒕떎.
    if (
        content_type == "SPECIFIC"
        and freshness_level in ["FRESH", "RECENT"]
        and guru_score != 50.0
    ):
        guru_weight = SCORING_CONFIG["final"]["guru_weight"]
    else:
        guru_weight = 0.0

    logger.debug(
        f"[{company}] ?좏뒠釉??몄궗?댄듃 ?곸슜: {content_type} "
        f"| ?좎꽑?? {freshness_level} | 湲곗??? {insight_date} "
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

    # total_score 踰붿쐞
    # fundamental_score: -3 ~ +3
    # macro_score: -3 ~ +3
    # sentiment: -1 ~ +1
    # 珥앺빀: -7 ~ +7
    # 50?먯쓣 以묐┰?쇰줈 ?먭퀬, 1?먮떦 ??7?먯뵫 ?대룞
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
        f"[?쒖뒪??梨꾩젏] {company} | ?쒖뒪???먯닔: {system_score}??"
        f"(?щТ {fundamental_score} + 留ㅽ겕濡?{macro_score} + ?댁뒪 {sentiment})"
    )
    logger.info(
        f"[理쒖쥌 ?먯젙] {company} | 醫낇빀 {final_weighted_score:.1f}??"
        f"(?쒖뒪??{system_weight:.0%} + 援щ（ {guru_weight:.0%}[{guru_sentiment_label}]) ??{final_opinion}"
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
        "one_line_conclusion": f"{company} 遺꾩꽍 寃곌낵??{final_opinion} ?섍껄?낅땲??",
        "executive_summary": [
            "?쒖뒪???곗텧 ?ъ옄 ?섍껄??湲곗??쇰줈 由ы룷?몃? 援ъ꽦?덉뒿?덈떎.",
            "?쇰? 遺꾩꽍 臾몄옣 ?앹꽦???ㅽ뙣???낅젰 ?곗씠??以묒떖??fallback???곸슜?덉뒿?덈떎.",
            "媛寃⑷낵 李⑦듃 ?곗씠?곕뒗 湲곗〈 怨꾩궛 寃곌낵瑜??좎??덉뒿?덈떎.",
        ],
        "macro_analysis": truncate_text(macro_json, 900) or "留ㅽ겕濡??곗씠?곌? ?쒗븳?곸엯?덈떎.",
        "fundamental_analysis": truncate_text(json.dumps(acc_data or {}, ensure_ascii=False), 900),
        "momentum_analysis": truncate_text(research_json, 700) or "?댁뒪 ?곗씠?곌? ?쒗븳?곸엯?덈떎.",
        "guru_analysis": truncate_text(youtube_json, 800) or "?좏뒠釉??몄궗?댄듃媛 ?쒗븳?곸엯?덈떎.",
        "final_conclusion": error or "吏곸젒 遺꾩꽍 ?앹꽦 ?ㅽ뙣濡?fallback 由ы룷?몃? ?묒꽦?덉뒿?덈떎.",
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
        normalized["executive_summary"].append("?낅젰 ?곗씠?곕? 湲곗??쇰줈 蹂댁닔?곸쑝濡??먮떒?덉뒿?덈떎.")

    for key in [
        "one_line_conclusion",
        "macro_analysis",
        "fundamental_analysis",
        "momentum_analysis",
        "guru_analysis",
        "final_conclusion",
    ]:
        if not normalized.get(key):
            normalized[key] = "?곗씠?곌? ?쒗븳?곸씠誘濡?蹂댁닔?곸쑝濡??댁꽍?덉뒿?덈떎."

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

    logger.debug(f"[{company}] 理쒖쥌 由ы룷???앹꽦 以?..")
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
        buy_comment = "신규 매수 비권고"

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

    summary_output = f"> **理쒓렐 ?낅뜲?댄듃 ?쇱떆:** {now_text}\n\n"
    summary_output += "<!-- MACRO_DATA\n"
    summary_output += macro_json
    summary_output += "\n-->\n\n"

    summary_cards = []

    for item in all_reports:
        if item.get("status") == "SUCCESS":
            summary_cards.append(extract_report_summary(item.get("report", "")))
        else:
            summary_cards.append(
                f"# ?뱢 {item.get('company', 'N/A')} ?ъ링 ?ъ옄 ?꾨왂 由ы룷??n\n"
                f"> {item.get('report', '遺꾩꽍 ?ㅽ뙣')}"
            )

    summary_output += "\n\n---\n\n".join(summary_cards)

    return summary_output

def build_output_report_item(state: ReportState):
    final_report = state.get("final_report") or {}
    report = final_report.get("markdown") or final_report.get("raw")

    if report is None:
        report = "\n".join(state.get("errors", [])) or "遺꾩꽍 ?ㅽ뙣"

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
        "raw": f"[醫낅ぉ 遺꾩꽍 ?ㅽ뙣] {company_name} ({ticker}) ?덉쇅 諛쒖깮: {error}",
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
        logger.info(f"遺꾩꽍 ?쒖옉: {company_name} ({ticker})")

        acc_data, failed_item = run_accounting_step(
            ticker=ticker,
            company=company_name,
            state=state,
        )

        if failed_item:
            state["output_report"] = failed_item
            return finalize_state(state)

        logger.debug(f"[{company_name}] 由ъ꽌移??곗씠???섏쭛 以?..")
        research_result = run_research_step(
            company=company_name,
            state=state,
        )

        logger.debug(f"[{company_name}] ?좏뒠釉??곗씠???섏쭛 以?..")
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
            logger.info(f"[{company_name}] 由ы룷???앹꽦 ?꾨즺")
        else:
            fallback_report = f"[{company_name}]\n{final_result.raw}"
            append_report_error(state, "Analysis ?먯씠?꾪듃 援ъ“???뚯떛 ?ㅽ뙣")
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
            logger.error(f"[{company_name}] Analysis ?먯씠?꾪듃 援ъ“???뚯떛 ?ㅽ뙣")

    except Exception as e:
        msg = f"[醫낅ぉ 遺꾩꽍 ?ㅽ뙣] {company_name} ({ticker}) ?덉쇅 諛쒖깮: {e}"
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
            logger.exception(f"醫낅ぉ蹂?由ы룷???앹꽦 以??덉쇅 諛쒖깮: {company_name} ({ticker})")
            state = build_failed_state((ticker, company_name), e)

            if status_callback:
                status_callback(state)

        results.append(state)

    return results, macro_context


def run_financial_crew(stock_pool=None, status_callback=None):
    stock_pool = normalize_stock_pool(stock_pool)
    require_env("OPENAI_API_KEY")

    # ?댁뒪 由ъ꽌移섏뿉???ъ슜
    require_env("SERPER_API_KEY")

    agents = {}
    tasks = {}

    # ---------------------------------------------------------
    # 0. ?좏뒠釉?DB ?낅뜲?댄듃
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
