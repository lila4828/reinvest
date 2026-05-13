import json
import math
import yfinance as yf
from crewai.tools import tool


def _to_float(value, default=None):
    try:
        if value is None:
            return default
        if isinstance(value, str):
            if value.strip().upper() in ["N/A", "NONE", "NULL", ""]:
                return default
            value = value.replace(",", "").replace("%", "")
        val_f = float(value)
        if math.isnan(val_f):
            return default
        return val_f
    except Exception:
        return default


def _safe_round(value, digits=2, default=None):
    value = _to_float(value, default=default)
    if value is None:
        return default
    return round(value, digits)


def _get_last_3_chronological(df, row_name):
    """
    yfinance financials/cashflow는 보통 최신 -> 과거 순서.
    main.py는 과거 -> 최근 순서를 기대하므로 reverse해서 반환.
    """
    try:
        if df is None or row_name not in df.index:
            return []

        values = df.loc[row_name].head(3).tolist()
        clean_values = []

        for value in values:
            parsed = _to_float(value, default=None)
            if parsed is None:
                continue
            clean_values.append(parsed)

        if len(clean_values) < 3:
            return []

        return list(reversed(clean_values))

    except Exception:
        return []


def _get_ma(hist, window):
    try:
        if hist is None or len(hist) < window:
            return None
        return _safe_round(hist["Close"].rolling(window=window).mean().iloc[-1], 2, default=None)
    except Exception:
        return None


def collect_financial_data(ticker: str) -> dict:
    try:
        stock = yf.Ticker(ticker)

        hist = stock.history(period="5y")
        if hist is None or len(hist) < 252:
            return {
                "ticker": ticker,
                "is_data_valid": False,
                "error": "상장 1년 미만 또는 가격 데이터 부족",
                "current_price": None,
                "per": None,
                "pbr": None,
                "dividend_yield": None,
                "ma_60": None,
                "ma_200": None,
                "ma_350": None,
                "ma_500": None,
                "ma_999": None,
                "roe_raw": None,
                "roe_label": "N/A",
                "revenue": [],
                "net_income": [],
                "fcf": [],
                "debt_to_equity": None,
                "operating_margin": None,
                "sector": "N/A",
                "industry": "N/A",
                "financial_summary": "재무 데이터 부족으로 분석 불가",
            }

        info = stock.info or {}
        financials = stock.financials
        cashflow = stock.cashflow

        current_price = _to_float(info.get("currentPrice"), default=None)
        per = _to_float(info.get("forwardPE"), default=None)

        pbr = _to_float(info.get("priceToBook"), default=None)
        if pbr is None or pbr == 0:
            book_value = _to_float(info.get("bookValue"), default=None)
            if current_price and book_value and book_value > 0:
                pbr = round(current_price / book_value, 2)

        dividend_yield = _to_float(info.get("dividendYield"), default=None)
        if dividend_yield is not None:
            dividend_yield = dividend_yield * 100 if dividend_yield < 1 else dividend_yield
            dividend_yield = round(dividend_yield, 2)

        roe_raw = _to_float(info.get("returnOnEquity"), default=None)
        if roe_raw is not None:
            roe_raw = round(roe_raw * 100, 2) if abs(roe_raw) < 1 else round(roe_raw, 2)

        if roe_raw is None:
            roe_label = "N/A"
        elif roe_raw >= 15:
            roe_label = "프리미엄"
        elif roe_raw >= 8:
            roe_label = "보통"
        elif roe_raw > 0:
            roe_label = "저조"
        else:
            roe_label = "적자/부진"

        revenue = _get_last_3_chronological(financials, "Total Revenue")
        net_income = _get_last_3_chronological(financials, "Net Income")
        fcf = _get_last_3_chronological(cashflow, "Free Cash Flow")

        is_data_valid = (
            len(revenue) == 3
            and len(net_income) == 3
            and len(fcf) == 3
            and current_price is not None
        )

        sector = info.get("sector", "N/A")
        industry = info.get("industry", "N/A")

        debt_to_equity = _to_float(info.get("debtToEquity"), default=None)
        operating_margin = _to_float(info.get("operatingMargins"), default=None)
        if operating_margin is not None and abs(operating_margin) < 1:
            operating_margin = round(operating_margin * 100, 2)

        result = {
            "ticker": ticker,
            "is_data_valid": is_data_valid,
            "error": None if is_data_valid else "3개년 재무 데이터 또는 현재가 부족",
            "sector": sector,
            "industry": industry,
            "current_price": current_price,
            "per": per,
            "pbr": pbr,
            "dividend_yield": dividend_yield,
            "ma_60": _get_ma(hist, 60),
            "ma_200": _get_ma(hist, 200),
            "ma_350": _get_ma(hist, 350),
            "ma_500": _get_ma(hist, 500),
            "ma_999": _get_ma(hist, 999),
            "roe_raw": roe_raw,
            "roe_label": roe_label,
            "revenue": revenue,
            "net_income": net_income,
            "fcf": fcf,
            "debt_to_equity": debt_to_equity,
            "operating_margin": operating_margin,
            "financial_summary": (
                f"{sector}/{industry} 기업. "
                f"최근 3개년 매출, 순이익, FCF 데이터를 과거→최근 순서로 수집. "
                f"ROE 평가는 {roe_label}, 부채비율은 {debt_to_equity}."
            ),
        }

        return result

    except Exception as e:
        return {
            "ticker": ticker,
            "is_data_valid": False,
            "error": str(e),
            "current_price": None,
            "per": None,
            "pbr": None,
            "dividend_yield": None,
            "ma_60": None,
            "ma_200": None,
            "ma_350": None,
            "ma_500": None,
            "ma_999": None,
            "roe_raw": None,
            "roe_label": "N/A",
            "revenue": [],
            "net_income": [],
            "fcf": [],
            "debt_to_equity": None,
            "operating_margin": None,
            "sector": "N/A",
            "industry": "N/A",
            "financial_summary": "재무 데이터 수집 중 오류 발생",
        }


@tool("Fetch Financial Data API")
def fetch_financial_data(ticker: str) -> str:
    """
    yfinance에서 재무 데이터를 가져와 JSON 문자열로 반환합니다.
    모든 배열은 과거 -> 최근 순서로 반환합니다.
    """
    return json.dumps(collect_financial_data(ticker), ensure_ascii=False)
