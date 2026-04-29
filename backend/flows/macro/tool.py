import json
import math
import yfinance as yf
from crewai.tools import tool


def _to_float(value, default=None):
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    except Exception:
        return default


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


@tool("Fetch Macro Economy API")
def fetch_macro_data(query: str = "macro") -> str:
    """
    글로벌 거시경제 지표를 JSON 문자열로 반환합니다.
    """
    try:
        krw = _fetch_macro_point("KRW=X", "원/달러 환율")
        nasdaq = _fetch_macro_point("^IXIC", "나스닥 지수", reverse_risk=True)
        us10y = _fetch_macro_point("^TNX", "미국 10년물 국채 금리")
        wti = _fetch_macro_point("CL=F", "WTI 원유")
        vix = _fetch_macro_point("^VIX", "VIX 지수")

        points = [krw, nasdaq, us10y, wti, vix]

        is_data_valid = all(point["current"] is not None for point in points)
        warnings = [point["warning"] for point in points if point["warning"]]

        macro_briefing = (
            f"원/달러 환율 {krw['current']}, "
            f"미국 10년물 금리 {us10y['current']}, "
            f"나스닥 {nasdaq['current']}, "
            f"WTI {wti['current']}, "
            f"VIX {vix['current']}. "
            f"위험 신호: {', '.join(warnings) if warnings else '없음'}"
        )

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
            "macro_briefing": macro_briefing,
            "is_data_valid": is_data_valid,
            "error": None if is_data_valid else "일부 매크로 데이터 수집 실패",
        }

        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        return json.dumps(
            {
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
                "macro_briefing": "매크로 데이터 수집 실패",
                "is_data_valid": False,
                "error": str(e),
            },
            ensure_ascii=False,
        )