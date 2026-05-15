"""Deterministic macro context helpers.

This module builds a compact interpretation layer from an existing macro
payload. It does not collect macro data, call an LLM, or change macro_score.
"""

SECTOR_KEYS = [
    "semiconductor",
    "financial",
    "growth",
    "energy",
    "shipbuilding",
    "defense",
    "consumer",
]

CONFIDENCE_LEVELS = {"HIGH", "MEDIUM", "LOW"}

DEFAULT_SECTOR_NOTE = "직접 영향은 제한적이며 종목별 실적 요인 확인이 필요합니다."


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    return value if isinstance(value, list) else []


def _safe_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_positive(value):
    numeric = _safe_float(value)
    return numeric is not None and numeric > 0


def _is_negative(value):
    numeric = _safe_float(value)
    return numeric is not None and numeric < 0


def _indicator_count(macro_data):
    keys = [
        "exchange_rate",
        "us_10y_yield",
        "nasdaq_index",
        "wti_price",
        "vix_index",
    ]
    return sum(1 for key in keys if _safe_float(macro_data.get(key)) is not None)


def _build_positive_factors(macro_data):
    factors = []
    reasons = [str(reason) for reason in _as_list(macro_data.get("macro_score_reasons")) if reason]
    for reason in reasons:
        if any(marker in reason for marker in ["완화", "긍정", "지지", "support", "우호"]):
            factors.append(reason[:180])

    if _is_positive(macro_data.get("nasdaq_index_change_1mo")):
        factors.append("나스닥 1개월 변화율이 플러스로 위험자산 선호를 일부 지지합니다.")
    if _is_negative(macro_data.get("vix_index_change_1mo")):
        factors.append("VIX 1개월 변화율이 하락해 변동성 부담 완화 신호가 있습니다.")
    if _is_positive(macro_data.get("exchange_rate_change_1mo")):
        factors.append("원/달러 환율 상승은 일부 수출주에는 매출 환산 효과를 줄 수 있습니다.")

    return _dedupe(factors)[:3]


def _build_risk_factors(macro_data):
    factors = [str(warning)[:180] for warning in _as_list(macro_data.get("risk_warnings")) if warning]
    reasons = [str(reason) for reason in _as_list(macro_data.get("macro_score_reasons")) if reason]
    for reason in reasons:
        if any(marker in reason for marker in ["부담", "위험", "압력", "risk", "고금리"]):
            factors.append(reason[:180])

    us_10y = _safe_float(macro_data.get("us_10y_yield"))
    vix = _safe_float(macro_data.get("vix_index"))
    if us_10y is not None and us_10y >= 4.3:
        factors.append("미국 10년물 금리가 높은 구간이면 성장주 할인율 부담이 커질 수 있습니다.")
    if _is_positive(macro_data.get("us_10y_yield_change_1mo")):
        factors.append("미국 10년물 금리 상승은 밸류에이션 압력으로 작용할 수 있습니다.")
    if vix is not None and vix >= 20:
        factors.append("VIX가 높은 구간이면 위험회피 심리가 커질 수 있습니다.")
    if _is_positive(macro_data.get("vix_index_change_1mo")):
        factors.append("VIX 상승은 단기 변동성 확대 신호입니다.")
    if _is_positive(macro_data.get("wti_price_change_1mo")):
        factors.append("WTI 상승은 인플레이션과 원가 부담 요인으로 해석할 수 있습니다.")

    return _dedupe(factors)[:3]


def _dedupe(items):
    output = []
    seen = set()
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(text)
    return output


def _infer_market_regime(macro_data, risk_factors):
    if not macro_data.get("is_data_valid"):
        return "중립/데이터 제한"

    nasdaq_up = _is_positive(macro_data.get("nasdaq_index_change_1mo"))
    nasdaq_down = _is_negative(macro_data.get("nasdaq_index_change_1mo"))
    vix = _safe_float(macro_data.get("vix_index"))
    vix_up = _is_positive(macro_data.get("vix_index_change_1mo"))
    vix_calm = (vix is not None and vix < 18) or _is_negative(macro_data.get("vix_index_change_1mo"))
    us_10y = _safe_float(macro_data.get("us_10y_yield"))
    us_10y_up = _is_positive(macro_data.get("us_10y_yield_change_1mo"))
    has_rate_pressure = (us_10y is not None and us_10y >= 4.3) or us_10y_up
    has_risk_off = (vix is not None and vix >= 20) or vix_up or nasdaq_down or len(risk_factors) >= 2

    if nasdaq_up and vix_calm and not has_rate_pressure and len(risk_factors) <= 1:
        return "위험선호 우위"
    if has_rate_pressure and nasdaq_up:
        return "고금리 부담과 기술주 강세가 공존"
    if has_risk_off:
        return "위험회피 압력"
    if nasdaq_up or vix_calm:
        return "완만한 위험선호"
    return "혼조"


def _infer_confidence(macro_data, market_regime):
    if not macro_data.get("is_data_valid"):
        return "LOW"
    count = _indicator_count(macro_data)
    if count >= 4 and market_regime not in {"혼조", "중립/데이터 제한"}:
        return "HIGH"
    if count >= 3:
        return "MEDIUM"
    return "LOW"


def _build_sector_impact(macro_data, market_regime):
    us_10y = _safe_float(macro_data.get("us_10y_yield"))
    exchange_up = _is_positive(macro_data.get("exchange_rate_change_1mo"))
    nasdaq_up = _is_positive(macro_data.get("nasdaq_index_change_1mo"))
    wti_up = _is_positive(macro_data.get("wti_price_change_1mo"))
    risk_off = "위험회피" in market_regime

    impact = {key: DEFAULT_SECTOR_NOTE for key in SECTOR_KEYS}

    if nasdaq_up:
        impact["semiconductor"] = "나스닥 강세는 반도체와 AI 관련 수요 기대를 지지할 수 있습니다."
        impact["growth"] = "성장주는 위험선호 회복의 수혜를 받을 수 있으나 금리 부담 확인이 필요합니다."
    if us_10y is not None and us_10y >= 4.3:
        impact["growth"] = "높은 금리는 성장주 밸류에이션 부담으로 작용할 수 있습니다."
        impact["financial"] = "고금리 환경은 금융주 순이자마진에는 우호적일 수 있으나 경기 둔화 위험도 함께 봐야 합니다."
    if exchange_up:
        impact["semiconductor"] = "환율 상승은 수출 반도체 기업의 원화 환산 매출에 우호적일 수 있습니다."
        impact["shipbuilding"] = "환율 상승은 수출 비중이 큰 조선 업종에 환산 효과를 줄 수 있습니다."
    if wti_up:
        impact["energy"] = "WTI 상승은 에너지 업종에는 가격 모멘텀이 될 수 있으나 비용 부담 업종에는 부담입니다."
        impact["consumer"] = "유가 상승은 소비재와 내수 업종의 비용 부담으로 이어질 수 있습니다."
    if risk_off:
        impact["defense"] = "위험회피 환경에서는 방산처럼 방어적 성격이 있는 업종을 상대적으로 점검할 수 있습니다."
        impact["consumer"] = "위험회피 환경에서는 소비 둔화와 비용 부담을 함께 확인해야 합니다."

    return impact


def _build_summary(macro_data, market_regime):
    briefing = str(macro_data.get("macro_briefing") or "").strip()
    if briefing:
        return briefing[:700]
    score = _safe_int(macro_data.get("macro_score"), 0)
    return f"현재 매크로 환경은 {market_regime}로 해석되며, 시스템 매크로 점수는 {score}점입니다."


def _build_final_impact(market_regime, score):
    if "위험선호" in market_regime and score > 0:
        return "Buy 판단을 지지할 수 있으나 가격 규율 확인이 필요합니다."
    if "위험회피" in market_regime or score < 0:
        return "위험회피 환경으로 보수적 접근이 필요합니다."
    if "고금리" in market_regime:
        return "기술주 강세가 있더라도 금리 부담을 함께 반영해 진입 가격을 보수적으로 봐야 합니다."
    return "혼조 환경으로 종목별 실적과 가격 매력 확인이 중요합니다."


def _data_as_of(macro_data):
    for key in ["data_as_of", "as_of", "date", "updated_at", "timestamp"]:
        value = macro_data.get(key)
        if value:
            return str(value)
    return "N/A"


def build_macro_context_input(macro_data: dict | None = None) -> dict:
    data = _as_dict(macro_data)
    return {
        "macro_data": data,
        "indicator_count": _indicator_count(data),
        "macro_score": _safe_int(data.get("macro_score"), 0),
        "macro_score_reasons": list(_as_list(data.get("macro_score_reasons"))),
        "risk_warnings": list(_as_list(data.get("risk_warnings"))),
        "macro_briefing": data.get("macro_briefing") or "",
    }


def build_macro_context_fallback(
    macro_data: dict | None = None,
    reason: str | None = None,
) -> dict:
    summary = reason or "매크로 데이터가 부족해 중립적으로 해석합니다."
    return {
        "market_regime": "중립/데이터 제한",
        "positive_factors": [],
        "risk_factors": [],
        "sector_impact": {key: DEFAULT_SECTOR_NOTE for key in SECTOR_KEYS},
        "summary": summary,
        "final_impact": "혼조 환경으로 종목별 실적과 가격 매력 확인이 중요합니다.",
        "data_as_of": _data_as_of(_as_dict(macro_data)),
        "confidence": "LOW",
    }


def build_macro_context_deterministic(macro_data: dict | None = None) -> dict:
    data = _as_dict(macro_data)
    if not data or not data.get("is_data_valid"):
        reason = data.get("error") or data.get("macro_briefing") or None
        return build_macro_context_fallback(data, reason)

    positive_factors = _build_positive_factors(data)
    risk_factors = _build_risk_factors(data)
    market_regime = _infer_market_regime(data, risk_factors)
    score = _safe_int(data.get("macro_score"), 0)

    return {
        "market_regime": market_regime,
        "positive_factors": positive_factors,
        "risk_factors": risk_factors,
        "sector_impact": _build_sector_impact(data, market_regime),
        "summary": _build_summary(data, market_regime),
        "final_impact": _build_final_impact(market_regime, score),
        "data_as_of": _data_as_of(data),
        "confidence": _infer_confidence(data, market_regime),
    }


def attach_macro_context(macro_data: dict | None = None) -> dict:
    output = dict(_as_dict(macro_data))
    output["macro_context"] = build_macro_context_deterministic(output)
    return output
