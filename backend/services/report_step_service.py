import json
import logging
from types import SimpleNamespace

from flows.accounting.tool import collect_financial_data
from flows.accounting.tool import calculate_fundamental_score as calculate_accounting_fundamental_score
from flows.analysis.tool import call_analysis_structured_output
from flows.macro.tool import build_macro_fallback as build_macro_tool_fallback
from flows.macro.tool import collect_macro_data
from flows.research.tool import build_research_fallback
from flows.research.tool import collect_research_data
from flows.youtube.tool import build_youtube_data_from_search
from flows.youtube.tool import build_youtube_fallback
from flows.youtube.tool import run_local_youtube_search
from schemas.report_state import ReportState
from services.investment_opinion_service import calculate_investment_opinion
from services.investment_opinion_service import apply_guru_positive_policy
from services.guru_strategy_service import attach_guru_strategy_context
from services.price_service import calculate_price_targets


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
    return calculate_accounting_fundamental_score(
        net_income=net_income,
        fcf=fcf,
        revenue=revenue,
        debt_to_equity=debt_to_equity,
    )


def truncate_text(value, max_chars=3000):
    if value is None:
        return ""

    text = str(value)

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n...[TRUNCATED]"


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


def set_report_step(state: ReportState | None, step: str):
    if state is not None:
        state["current_step"] = step


def append_report_error(state: ReportState | None, message: str):
    if state is None:
        return

    state.setdefault("errors", []).append(message)


def build_macro_fallback(error: str | None = None):
    return build_macro_tool_fallback(error)


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
        macro_score = macro_data.get("macro_score")
        macro_score_reasons = macro_data.get("macro_score_reasons")

        if macro_score is None or not macro_score_reasons:
            macro_score, macro_score_reasons = calculate_macro_score(
                exchange_rate=macro_data.get("exchange_rate"),
                us_10y_yield=macro_data.get("us_10y_yield"),
                vix_index=macro_data.get("vix_index"),
            )
            macro_data["macro_score"] = macro_score
            macro_data["macro_score_reasons"] = macro_score_reasons

        macro_json = json.dumps(macro_data, ensure_ascii=False, indent=2)

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

    fund_score = acc_data.get("fundamental_score")
    fund_score_reasons = acc_data.get("fundamental_score_reasons")

    if fund_score is None or not fund_score_reasons:
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
                "news_summary": "리서치 데이터 수집 실패로 fallback 처리했습니다.",
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
        youtube_data = build_youtube_fallback()
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

    # 구루 점수 70% 가중은 특정 종목 인사이트를 반영하기 위한 가중치다.
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


def extract_guru_opinion(youtube_json: str = ""):
    if not youtube_json:
        return None

    try:
        youtube_data = json.loads(youtube_json)
    except Exception:
        return None

    guru_opinion = youtube_data.get("guru_opinion")
    if isinstance(guru_opinion, dict):
        return guru_opinion

    return None


def attach_guru_strategy_context_to_youtube_json(
    youtube_json: str = "",
    guru_strategy_context: dict | None = None,
    state: ReportState | None = None,
):
    if not isinstance(guru_strategy_context, dict):
        return youtube_json

    try:
        youtube_data = json.loads(youtube_json) if youtube_json else {}
    except Exception:
        youtube_data = {}

    youtube_data = attach_guru_strategy_context(youtube_data, guru_strategy_context)
    merged_json = json.dumps(youtube_data, ensure_ascii=False, indent=2)

    if state is not None:
        state["youtube_context"] = merged_json

    return merged_json


def decide_final_opinion(
    acc_data,
    macro_score,
    sentiment,
    guru_score,
    guru_weight,
    company: str,
    youtube_json: str = "",
    state: ReportState | None = None,
):
    set_report_step(state, "opinion")
    fundamental_score = acc_data.get("fundamental_score", 0)
    opinion_result = calculate_investment_opinion(
        fundamental_score=fundamental_score,
        macro_score=macro_score,
        sentiment=sentiment,
        guru_score=guru_score,
        guru_weight=guru_weight,
        final_config=SCORING_CONFIG["final"],
    )
    guru_opinion = extract_guru_opinion(youtube_json)
    opinion_result = apply_guru_positive_policy(
        opinion_result,
        guru_opinion=guru_opinion,
        accounting_data=acc_data,
    )
    final_opinion = opinion_result["final_opinion"]
    system_score = opinion_result["system_score"]
    system_weight = opinion_result["system_weight"]
    final_weighted_score = opinion_result["final_weighted_score"]
    guru_sentiment_label = opinion_result["guru_sentiment_label"]

    logger.debug(
        f"[시스템 채점] {company} | 시스템 점수: {system_score}점 "
        f"(재무 {fundamental_score} + 매크로 {macro_score} + 뉴스 {sentiment})"
    )
    logger.info(
        f"[최종 판정] {company} | 종합 {final_weighted_score:.1f}점 "
        f"(시스템 {system_weight:.0%} + 구루 {guru_weight:.0%}[{guru_sentiment_label}]) -> {final_opinion}"
    )

    return final_opinion


def run_price_step(acc_data, company: str, state: ReportState | None = None):
    set_report_step(state, "price")
    current_price, target_buy_price, defense_price = calculate_price_targets(acc_data)

    if not isinstance(current_price, (int, float)) or current_price <= 0:
        logger.warning(f"[{company}] price data missing; skip price target")

    if state is not None:
        state["price_data"] = {
            "current_price": current_price,
            "target_buy_price": target_buy_price,
            "defense_price": defense_price,
        }

    return current_price, target_buy_price, defense_price


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
            "시스템이 산출한 투자 의견을 기준으로 리포트를 구성했습니다.",
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
