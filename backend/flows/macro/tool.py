import json
import math

import yfinance as yf


MACRO_SCORE_CONFIG = {
    "vix_high_risk": 20,
    "vix_low_risk": 15,
    "us_10y_high_risk": 4.3,
    "us_10y_low_risk": 4.0,
    "exchange_rate_high_risk": 1400,
    "exchange_rate_low_risk": 1300,
}


def _to_float(value, default=None):
    try:
        if value is None:
            return default
        val_f = float(value)
        if math.isnan(val_f):
            return default
        return val_f
    except Exception:
        return default


def _format_value(value, suffix=""):
    if value is None:
        return "확인 불가"
    return f"{value:,.2f}{suffix}"


def _format_change(value):
    if value is None:
        return "1개월 변동률 확인 불가"

    direction = "상승" if value > 0 else "하락" if value < 0 else "보합"
    return f"1개월 {abs(value):.2f}% {direction}"


def _fetch_macro_point(ticker: str, name: str, reverse_risk: bool = False):
    hist = yf.Ticker(ticker).history(period="6mo")

    if hist is None or len(hist) < 60:
        return {
            "name": name,
            "ticker": ticker,
            "current": None,
            "change_1mo_pct": None,
            "is_danger": False,
            "warning": f"{name} 데이터 부족",
        }

    current = _to_float(hist["Close"].iloc[-1])
    past_1mo = _to_float(hist["Close"].iloc[-21])

    if current is None or past_1mo is None or past_1mo == 0:
        return {
            "name": name,
            "ticker": ticker,
            "current": None,
            "change_1mo_pct": None,
            "is_danger": False,
            "warning": f"{name} 수치 계산 실패",
        }

    change_1mo_pct = round(((current - past_1mo) / past_1mo) * 100, 2)

    recent_60d = hist["Close"].tail(60)
    mean = _to_float(recent_60d.mean())
    std = _to_float(recent_60d.std())

    is_danger = False
    warning = ""

    if mean is not None and std is not None:
        if not reverse_risk:
            if current > mean + (2 * std):
                is_danger = True
                warning = f"{name} 급등 경고"
        else:
            if current < mean - (2 * std):
                is_danger = True
                warning = f"{name} 급락 경고"

    return {
        "name": name,
        "ticker": ticker,
        "current": round(current, 2),
        "change_1mo_pct": change_1mo_pct,
        "is_danger": is_danger,
        "warning": warning,
    }


def _score_exchange_rate(exchange_rate):
    cfg = MACRO_SCORE_CONFIG
    if exchange_rate is None:
        return 0, "원/달러 환율 데이터가 없어 환율 영향은 중립으로 처리"
    if exchange_rate >= cfg["exchange_rate_high_risk"]:
        return -1, f"원/달러 환율 {exchange_rate:,.2f}원은 수입 물가 상승 압력과 외국인 수급 부담 요인"
    if 0 < exchange_rate <= cfg["exchange_rate_low_risk"]:
        return 1, f"원/달러 환율 {exchange_rate:,.2f}원은 환율 부담 완화 요인"
    return 0, f"원/달러 환율 {exchange_rate:,.2f}원은 중립권"


def _score_us_10y(us_10y_yield):
    cfg = MACRO_SCORE_CONFIG
    if us_10y_yield is None:
        return 0, "미국 10년물 금리 데이터가 없어 할인율 영향은 중립으로 처리"
    if us_10y_yield >= cfg["us_10y_high_risk"]:
        return -1, f"미국 10년물 금리 {us_10y_yield:,.2f}%는 성장주 밸류에이션에 부담"
    if 0 < us_10y_yield <= cfg["us_10y_low_risk"]:
        return 1, f"미국 10년물 금리 {us_10y_yield:,.2f}%는 할인율 부담 완화 요인"
    return 0, f"미국 10년물 금리 {us_10y_yield:,.2f}%는 중립권"


def _score_vix(vix_index):
    cfg = MACRO_SCORE_CONFIG
    if vix_index is None:
        return 0, "미국시장 공포지수 데이터가 없어 위험선호 영향은 중립으로 처리"
    if vix_index >= cfg["vix_high_risk"]:
        return -1, f"미국시장 공포지수 {vix_index:,.2f}는 위험회피 심리 강화 신호"
    if 0 < vix_index <= cfg["vix_low_risk"]:
        return 1, f"미국시장 공포지수 {vix_index:,.2f}는 안정적인 위험선호 환경"
    return 0, f"미국시장 공포지수 {vix_index:,.2f}는 중립권"


def _describe_nasdaq(nasdaq_index, nasdaq_change_1mo):
    if nasdaq_index is None:
        return "나스닥 지수 데이터가 없어 글로벌 성장주 심리 확인이 제한적"
    if nasdaq_change_1mo is None:
        return f"나스닥 지수는 {_format_value(nasdaq_index)}로 확인되나 1개월 흐름은 제한적"
    if nasdaq_change_1mo > 3:
        return f"나스닥은 {_format_change(nasdaq_change_1mo)}으로 위험자산 선호에 우호적"
    if nasdaq_change_1mo < -3:
        return f"나스닥은 {_format_change(nasdaq_change_1mo)}으로 성장주 심리에 부담"
    return f"나스닥은 {_format_change(nasdaq_change_1mo)}으로 뚜렷한 방향성은 제한적"


def _describe_wti(wti_price, wti_change_1mo):
    if wti_price is None:
        return "원유 가격 데이터가 없어 비용과 물가 압력 판단은 제한적"
    if wti_change_1mo is None:
        return f"원유 가격은 {_format_value(wti_price, '달러')}로 확인되나 1개월 흐름은 제한적"
    if wti_change_1mo > 5:
        return f"원유 가격은 {_format_change(wti_change_1mo)}으로 물가와 비용 부담 요인"
    if wti_change_1mo < -5:
        return f"원유 가격은 {_format_change(wti_change_1mo)}으로 비용과 인플레이션 부담 완화 요인"
    return f"원유 가격은 {_format_change(wti_change_1mo)}으로 중립권"


def build_macro_interpretation(macro_data: dict):
    exchange_score, exchange_reason = _score_exchange_rate(macro_data.get("exchange_rate"))
    us_10y_score, us_10y_reason = _score_us_10y(macro_data.get("us_10y_yield"))
    vix_score, vix_reason = _score_vix(macro_data.get("vix_index"))

    macro_score = max(-3, min(3, exchange_score + us_10y_score + vix_score))

    nasdaq_reason = _describe_nasdaq(
        macro_data.get("nasdaq_index"),
        macro_data.get("nasdaq_index_change_1mo"),
    )
    wti_reason = _describe_wti(
        macro_data.get("wti_price"),
        macro_data.get("wti_price_change_1mo"),
    )

    macro_score_reasons = [
        exchange_reason,
        us_10y_reason,
        vix_reason,
        nasdaq_reason,
        wti_reason,
    ]

    risk_warnings = [
        warning
        for warning in macro_data.get("risk_warnings", [])
        if warning
    ]

    briefing_parts = [
        f"환율: {_format_value(macro_data.get('exchange_rate'), '원')} ({_format_change(macro_data.get('exchange_rate_change_1mo'))})",
        f"미국 10년물: {_format_value(macro_data.get('us_10y_yield'), '%')} ({_format_change(macro_data.get('us_10y_yield_change_1mo'))})",
        f"나스닥: {_format_value(macro_data.get('nasdaq_index'))} ({_format_change(macro_data.get('nasdaq_index_change_1mo'))})",
        f"원유 가격: {_format_value(macro_data.get('wti_price'), '달러')} ({_format_change(macro_data.get('wti_price_change_1mo'))})",
        f"미국시장 공포지수: {_format_value(macro_data.get('vix_index'))} ({_format_change(macro_data.get('vix_index_change_1mo'))})",
    ]

    macro_briefing = (
        " / ".join(briefing_parts)
        + f". 종합 매크로 점수는 {macro_score}점이며, "
        + " ; ".join(macro_score_reasons)
        + "."
    )

    if risk_warnings:
        macro_briefing += " 추가 경고: " + ", ".join(risk_warnings) + "."

    return macro_score, macro_score_reasons, macro_briefing


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
        "macro_score": 0,
        "macro_score_reasons": ["매크로 데이터 수집 실패로 중립 점수 적용"],
        "macro_briefing": "매크로 데이터 수집 실패로 이번 리포트에서는 매크로 영향을 중립으로 처리합니다.",
        "is_data_valid": False,
        "error": error or "매크로 데이터 수집 실패",
    }


def collect_macro_data() -> dict:
    try:
        krw = _fetch_macro_point("KRW=X", "원/달러 환율")
        nasdaq = _fetch_macro_point("^IXIC", "나스닥 지수", reverse_risk=True)
        us10y = _fetch_macro_point("^TNX", "미국 10년물 국채 금리")
        wti = _fetch_macro_point("CL=F", "원유 가격")
        vix = _fetch_macro_point("^VIX", "미국시장 공포지수")

        points = [krw, nasdaq, us10y, wti, vix]

        is_data_valid = all(point["current"] is not None for point in points)
        warnings = [point["warning"] for point in points if point["warning"]]

        result = {
            "exchange_rate": krw["current"],
            "us_10y_yield": us10y["current"],
            "nasdaq_index": nasdaq["current"],
            "wti_price": wti["current"],
            "vix_index": vix["current"],
            "exchange_rate_change_1mo": krw["change_1mo_pct"],
            "us_10y_yield_change_1mo": us10y["change_1mo_pct"],
            "nasdaq_index_change_1mo": nasdaq["change_1mo_pct"],
            "wti_price_change_1mo": wti["change_1mo_pct"],
            "vix_index_change_1mo": vix["change_1mo_pct"],
            "risk_warnings": warnings,
            "is_data_valid": is_data_valid,
            "error": None if is_data_valid else "일부 매크로 데이터 수집 실패",
        }

        macro_score, macro_score_reasons, macro_briefing = build_macro_interpretation(result)
        result["macro_score"] = macro_score
        result["macro_score_reasons"] = macro_score_reasons
        result["macro_briefing"] = macro_briefing

        return result

    except Exception as e:
        return build_macro_fallback(str(e))


def fetch_macro_data(query: str = "macro") -> str:
    """글로벌 거시경제 지표와 해석을 JSON 문자열로 반환한다."""
    return json.dumps(collect_macro_data(), ensure_ascii=False)
