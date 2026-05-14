import json
import logging
import math
import os
import tempfile

import yfinance as yf


logger = logging.getLogger(__name__)


def configure_yfinance_cache():
    cache_dir = os.getenv(
        "YFINANCE_CACHE_DIR",
        os.path.join(tempfile.gettempdir(), "ai_reinvest_yfinance_cache"),
    )

    try:
        os.makedirs(cache_dir, exist_ok=True)
        if hasattr(yf, "set_tz_cache_location"):
            yf.set_tz_cache_location(cache_dir)
    except Exception as e:
        logger.warning("yfinance cache 설정 실패. 기본 cache 설정으로 진행합니다. %s", e)


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
    yfinance financials/cashflow는 보통 최신 -> 과거 순서다.
    리포트와 차트는 과거 -> 최근 순서를 기대하므로 reverse해서 반환한다.
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


def _is_valid_numeric_series(values, min_len=3):
    if not isinstance(values, list):
        return False
    if len(values) < min_len:
        return False
    return all(isinstance(x, (int, float)) for x in values)


def _pct_change(old, new):
    if not isinstance(old, (int, float)) or not isinstance(new, (int, float)) or old == 0:
        return None
    return round(((new - old) / abs(old)) * 100, 2)


def _trend_text(values, label):
    if not _is_valid_numeric_series(values):
        return f"{label} 데이터 부족"

    first, middle, last = values[0], values[1], values[2]
    change = _pct_change(first, last)
    change_text = f"({change:+.2f}%)" if change is not None else ""

    if last > middle > first:
        return f"{label}은 3개년 연속 개선 {change_text}".strip()
    if last < middle < first:
        return f"{label}은 3개년 연속 둔화 {change_text}".strip()
    if last > first:
        return f"{label}은 변동성은 있으나 3년 전 대비 개선 {change_text}".strip()
    if last < first:
        return f"{label}은 변동성 속 3년 전 대비 둔화 {change_text}".strip()
    return f"{label}은 3년 전과 유사한 수준"


def _valuation_text(per, pbr):
    parts = []
    if isinstance(per, (int, float)) and per > 0:
        if per < 8:
            parts.append(f"PER {per:.2f}배는 낮은 밸류에이션 구간")
        elif per > 25:
            parts.append(f"PER {per:.2f}배는 이익 대비 부담이 큰 구간")
        else:
            parts.append(f"PER {per:.2f}배는 중립 구간")
    else:
        parts.append("PER 확인 제한")

    if isinstance(pbr, (int, float)) and pbr > 0:
        if pbr < 1:
            parts.append(f"PBR {pbr:.2f}배는 장부가 대비 할인 구간")
        elif pbr > 3:
            parts.append(f"PBR {pbr:.2f}배는 자산가치 대비 프리미엄 구간")
        else:
            parts.append(f"PBR {pbr:.2f}배는 중립 구간")
    else:
        parts.append("PBR 확인 제한")

    return ", ".join(parts)


def _moving_average_text(current_price, ma_60, ma_200, ma_350):
    if not isinstance(current_price, (int, float)) or current_price <= 0:
        return "현재가 데이터 부족으로 이동평균선 해석 제한"

    available = [
        ("60일선", ma_60),
        ("200일선", ma_200),
        ("350일선", ma_350),
    ]
    valid = [(name, value) for name, value in available if isinstance(value, (int, float)) and value > 0]
    if not valid:
        return "주요 이동평균선 데이터 부족"

    above = [name for name, value in valid if current_price >= value]
    below = [name for name, value in valid if current_price < value]

    parts = []
    if above:
        parts.append(f"현재가는 {', '.join(above)} 위")
    if below:
        parts.append(f"현재가는 {', '.join(below)} 아래")
    return ", ".join(parts)


def calculate_fundamental_score(net_income, fcf, revenue, debt_to_equity=None):
    if (
        not _is_valid_numeric_series(net_income)
        or not _is_valid_numeric_series(fcf)
        or not _is_valid_numeric_series(revenue)
    ):
        return 0, ["3개년 재무 시계열 데이터 부족"]

    score = 0
    reasons = []

    if net_income[-1] > 0 and net_income[-1] >= net_income[-2]:
        score += 1
        reasons.append("최근 순이익이 흑자이며 전년 대비 개선")
    elif net_income[-1] < 0:
        score -= 1
        reasons.append("최근 순이익이 적자")
    else:
        reasons.append("최근 순이익 개선 강도는 제한적")

    if fcf[-1] > 0:
        score += 1
        reasons.append("최근 잉여현금흐름(FCF)이 플러스")
    elif fcf[-1] < 0:
        score -= 1
        reasons.append("최근 잉여현금흐름(FCF)이 마이너스")
    else:
        reasons.append("최근 잉여현금흐름(FCF)은 중립")

    if revenue[-1] > revenue[-2]:
        score += 1
        reasons.append("최근 매출이 전년 대비 증가")
    elif revenue[-1] < revenue[-2]:
        score -= 1
        reasons.append("최근 매출이 전년 대비 감소")
    else:
        reasons.append("최근 매출은 전년과 유사")

    if isinstance(debt_to_equity, (int, float)):
        if debt_to_equity > 100:
            score -= 1
            reasons.append(f"부채비율 {debt_to_equity:.2f}%로 재무 레버리지 부담")
        else:
            reasons.append(f"부채비율 {debt_to_equity:.2f}%로 과도한 레버리지 부담은 제한적")
    else:
        reasons.append("부채비율 데이터 확인 제한")

    score = max(-3, min(3, score))
    return score, reasons


def build_financial_summary(data: dict):
    revenue = data.get("revenue", [])
    net_income = data.get("net_income", [])
    fcf = data.get("fcf", [])
    debt_to_equity = data.get("debt_to_equity")
    operating_margin = data.get("operating_margin")
    roe_raw = data.get("roe_raw")
    roe_label = data.get("roe_label", "N/A")

    summary_parts = [
        f"{data.get('sector', 'N/A')}/{data.get('industry', 'N/A')} 기업",
        _trend_text(revenue, "매출"),
        _trend_text(net_income, "순이익"),
        _trend_text(fcf, "FCF"),
        _valuation_text(data.get("per"), data.get("pbr")),
        _moving_average_text(
            data.get("current_price"),
            data.get("ma_60"),
            data.get("ma_200"),
            data.get("ma_350"),
        ),
    ]

    if isinstance(roe_raw, (int, float)):
        summary_parts.append(f"ROE {roe_raw:.2f}%({roe_label})")
    else:
        summary_parts.append("ROE 확인 제한")

    if isinstance(operating_margin, (int, float)):
        summary_parts.append(f"영업이익률 {operating_margin:.2f}%")
    else:
        summary_parts.append("영업이익률 확인 제한")

    if isinstance(debt_to_equity, (int, float)):
        if debt_to_equity > 200:
            summary_parts.append(f"부채비율 {debt_to_equity:.2f}%로 고위험")
        elif debt_to_equity > 100:
            summary_parts.append(f"부채비율 {debt_to_equity:.2f}%로 주의 필요")
        else:
            summary_parts.append(f"부채비율 {debt_to_equity:.2f}%로 관리 가능 범위")
    else:
        summary_parts.append("부채비율 확인 제한")

    return " / ".join(summary_parts)


def build_financial_fallback(ticker: str, error: str, summary: str):
    return {
        "ticker": ticker,
        "is_data_valid": False,
        "error": error,
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
        "financial_summary": summary,
        "fundamental_score": 0,
        "fundamental_score_reasons": ["재무 데이터 부족으로 중립 점수 적용"],
    }


def collect_financial_data(ticker: str) -> dict:
    try:
        configure_yfinance_cache()
        stock = yf.Ticker(ticker)

        hist = stock.history(period="5y")
        if hist is None or len(hist) < 252:
            return build_financial_fallback(
                ticker,
                "상장 1년 미만 또는 가격 데이터 부족",
                "재무 데이터 부족으로 분석이 제한됩니다.",
            )

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
            roe_label = "우수"
        elif roe_raw >= 8:
            roe_label = "보통"
        elif roe_raw > 0:
            roe_label = "낮음"
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
        }

        fund_score, fund_score_reasons = calculate_fundamental_score(
            net_income=net_income,
            fcf=fcf,
            revenue=revenue,
            debt_to_equity=debt_to_equity,
        )
        result["fundamental_score"] = fund_score
        result["fundamental_score_reasons"] = fund_score_reasons
        result["financial_summary"] = build_financial_summary(result)

        return result

    except Exception as e:
        return build_financial_fallback(
            ticker,
            str(e),
            "재무 데이터 수집 중 오류가 발생했습니다.",
        )


def fetch_financial_data(ticker: str) -> str:
    """
    yfinance에서 재무 데이터를 가져와 JSON 문자열로 반환합니다.
    모든 재무 배열은 과거 -> 최근 순서로 반환합니다.
    """
    return json.dumps(collect_financial_data(ticker), ensure_ascii=False)
