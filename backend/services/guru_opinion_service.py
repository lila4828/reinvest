"""Deterministic per-stock guru opinion helpers.

This module builds a compact interpretation layer from an existing Youtube
payload. It does not query Chroma, call OpenAI, or change guru score/weight.
"""

import re

MENTION_TYPES = {"DIRECT", "SECTOR", "MARKET", "MINDSET", "NONE"}
SENTIMENTS = {"BULLISH", "NEUTRAL", "BEARISH"}
CONFIDENCE_LEVELS = {"HIGH", "MEDIUM", "LOW"}
FRESH_LEVELS = {"FRESH", "RECENT"}

PRICE_DISCIPLINE_NEUTRAL = (
    "가격 부담 여부는 현재가와 권장 매수가를 함께 확인해 최종분석에서 판단해야 합니다."
)
PRICE_DISCIPLINE_BULLISH = (
    "구루 신호가 긍정적이어도 즉시 전량 매수보다 분할 접근과 가격 규율이 필요합니다."
)

POSITIVE_TERMS = [
    "매수",
    "기회",
    "성장",
    "주도주",
    "대형주",
    "강한 종목",
    "신고가",
    "buy",
    "bullish",
    "growth",
    "leader",
    "opportunity",
    "breakout",
]

NEGATIVE_TERMS = [
    "매도",
    "위험",
    "리스크",
    "손절",
    "부실",
    "우하향",
    "고평가",
    "주의",
    "sell",
    "bearish",
    "risk",
    "overvalued",
    "avoid",
    "weak",
]

MARKET_TERMS = [
    "시장",
    "코스피",
    "코스닥",
    "나스닥",
    "금리",
    "환율",
    "market",
    "nasdaq",
    "macro",
    "risk-on",
]

MINDSET_TERMS = [
    "멘탈",
    "심리",
    "기다림",
    "원칙",
    "분할",
    "mindset",
    "psychology",
    "patience",
    "discipline",
]

SECTOR_TERMS = [
    "반도체",
    "메모리",
    "ai",
    "chip",
    "semiconductor",
    "전기차",
    "ev",
    "battery",
    "auto",
    "자동차",
    "금융",
    "bank",
    "바이오",
    "bio",
    "energy",
    "에너지",
    "방산",
    "defense",
]


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    return value if isinstance(value, list) else []


def _safe_float(value, default=50.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=10**9):
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_content_type(value):
    content_type = str(value or "N/A").upper()
    if content_type in {"SPECIFIC", "MARKET", "MINDSET", "RISK", "PSYCHOLOGY", "GENERAL", "N/A"}:
        return content_type
    return "GENERAL"


def _normalize_freshness(value):
    freshness = str(value or "N/A").upper()
    if freshness in {"FRESH", "RECENT", "OLD", "STALE", "UNKNOWN", "N/A"}:
        return freshness
    return "UNKNOWN"


def _doc_text(doc):
    parts = [
        doc.get("query"),
        doc.get("search_type"),
        doc.get("theme_hint"),
        doc.get("title"),
        doc.get("source"),
        doc.get("content"),
        doc.get("transcript"),
        doc.get("snippet"),
    ]
    return " ".join(str(part or "") for part in parts).lower()


def _payload_text(payload):
    parts = [
        payload.get("key_strategy"),
        payload.get("mindset_summary"),
        payload.get("market_principle"),
        payload.get("risk_control"),
        payload.get("guru_insight_details"),
        payload.get("source_policy"),
    ]
    docs_text = " ".join(_doc_text(doc) for doc in _as_list(payload.get("selected_docs")))
    return f"{' '.join(str(part or '') for part in parts)} {docs_text}".lower()


def _has_any(text, terms):
    for term in terms:
        normalized = term.lower()
        if normalized.isascii() and normalized.isalnum() and len(normalized) <= 3:
            if re.search(rf"\b{re.escape(normalized)}\b", text):
                return True
            continue
        if normalized in text:
            return True
    return False


def _normalize_doc(doc):
    doc = _as_dict(doc)
    return {
        "query": str(doc.get("query") or "")[:160],
        "search_type": str(doc.get("search_type") or "")[:80],
        "theme_hint": str(doc.get("theme_hint") or "")[:80],
        "date": str(doc.get("date") or "날짜 없음")[:80],
        "days_old": doc.get("days_old"),
        "title": str(doc.get("title") or "제목 없음")[:180],
        "source": str(doc.get("source") or "Youtube RAG")[:80],
        "content": str(doc.get("content") or doc.get("transcript") or doc.get("snippet") or "")[:1200],
    }


def _dedupe_and_rank_docs(docs, limit=3):
    normalized = [_normalize_doc(doc) for doc in _as_list(docs) if isinstance(doc, dict)]
    normalized.sort(key=lambda item: (_safe_int(item.get("days_old")), item.get("date") or ""))

    deduped = []
    seen = set()
    for doc in normalized:
        key = (doc["title"].strip().lower(), doc["date"].strip().lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(doc)
        if len(deduped) >= limit:
            break

    return deduped


def _company_terms(company, ticker):
    terms = []
    company_text = str(company or "").strip()
    ticker_text = str(ticker or "").strip()
    if company_text:
        terms.append(company_text.lower())
    if ticker_text:
        terms.extend({ticker_text.lower(), ticker_text.replace(".KS", "").lower()})
    return [term for term in terms if term]


def _infer_mention_type(company, ticker, payload, docs, content_type):
    if not docs:
        return "NONE"

    text = _payload_text({**payload, "selected_docs": docs})
    company_terms = _company_terms(company, ticker)
    direct_match = any(term and term in text for term in company_terms)

    if content_type == "SPECIFIC" and (direct_match or docs):
        return "DIRECT"
    if direct_match:
        return "DIRECT"
    if _has_any(text, SECTOR_TERMS):
        return "SECTOR"
    if content_type in {"MINDSET", "PSYCHOLOGY", "RISK"} or _has_any(text, MINDSET_TERMS):
        return "MINDSET"
    if content_type == "MARKET" or _has_any(text, MARKET_TERMS):
        return "MARKET"
    return "NONE"


def _infer_sentiment(payload, text):
    score = _safe_float(payload.get("guru_sentiment_score"))
    positive = _has_any(text, POSITIVE_TERMS)
    negative = _has_any(text, NEGATIVE_TERMS)

    if score > 55 or (positive and not negative):
        return "BULLISH"
    if score < 45 or (negative and not positive):
        return "BEARISH"
    return "NEUTRAL"


def _infer_confidence(mention_type, freshness_level, docs, text):
    has_clear_evidence = bool(docs) and (
        _has_any(text, POSITIVE_TERMS)
        or _has_any(text, NEGATIVE_TERMS)
        or mention_type in {"DIRECT", "SECTOR", "MARKET"}
    )

    if mention_type == "DIRECT" and freshness_level == "FRESH" and has_clear_evidence:
        return "HIGH"
    if (
        (mention_type == "DIRECT" and freshness_level == "RECENT")
        or (mention_type in {"SECTOR", "MARKET"} and has_clear_evidence and freshness_level in FRESH_LEVELS)
    ):
        return "MEDIUM"
    return "LOW"


def _build_evidence_items(docs, mention_type):
    evidence_items = []
    for doc in docs[:3]:
        reason_parts = []
        if doc.get("theme_hint"):
            reason_parts.append(str(doc["theme_hint"]))
        if doc.get("search_type"):
            reason_parts.append(str(doc["search_type"]))
        if mention_type != "NONE":
            reason_parts.append(f"{mention_type} relevance")
        reason = ", ".join(reason_parts) or "제공된 검색 문서 기준 구루 의견 근거"
        evidence_items.append(
            {
                "title": doc.get("title") or "제목 없음",
                "date": doc.get("date") or "날짜 없음",
                "reason": reason[:160],
            }
        )
    return evidence_items


def _build_summary(mention_type, sentiment, confidence):
    if mention_type == "DIRECT":
        return f"수집된 구루 자료는 해당 종목 직접 맥락으로 분류되며, 방향성은 {sentiment}, 신뢰도는 {confidence}입니다."
    if mention_type == "SECTOR":
        return f"수집된 구루 자료는 종목 직접 추천이 아니라 업종/테마 연결 근거이며, 방향성은 {sentiment}입니다."
    if mention_type == "MARKET":
        return f"수집된 구루 자료는 시장관을 통한 간접 영향으로 해석되며, 방향성은 {sentiment}입니다."
    if mention_type == "MINDSET":
        return "수집된 구루 자료는 종목 의견보다 투자 태도와 리스크 관리 원칙에 가깝습니다."
    return "해당 종목에 적용할 수 있는 충분한 구루 의견 근거가 확인되지 않았습니다."


def _build_stock_relevance(mention_type):
    return {
        "DIRECT": "종목명, 티커 또는 SPECIFIC 분류 근거가 있어 종목 직접 맥락으로 봅니다.",
        "SECTOR": "종목 직접 언급은 제한적이지만 업종/테마 연결성이 있습니다.",
        "MARKET": "개별 종목보다 시장 환경을 통해 간접적으로 연결됩니다.",
        "MINDSET": "종목 방향성보다 매매 태도와 리스크 관리에 대한 참고 신호입니다.",
        "NONE": "적용 가능한 직접/간접 근거가 부족합니다.",
    }.get(mention_type, "적용 가능한 근거가 제한적입니다.")


def _build_opinion_impact(sentiment, mention_type, confidence):
    if sentiment == "BULLISH" and mention_type in {"DIRECT", "SECTOR", "MARKET"} and confidence in {"HIGH", "MEDIUM"}:
        return "구루 신호는 긍정적 해석을 보강할 수 있지만 시스템 점수와 가격 규율을 함께 확인해야 합니다."
    if sentiment == "BEARISH":
        return "구루 신호는 리스크 점검과 보수적 판단을 강화하는 요인입니다."
    return "구루 신호만으로 투자 의견을 바꾸기에는 근거가 제한적입니다."


def _build_risk_warning(content_type, sentiment):
    if content_type == "RISK" or sentiment == "BEARISH":
        return "구루 자료가 리스크 또는 부정 신호를 포함하므로 포지션 크기와 손실 제한 기준을 보수적으로 확인해야 합니다."
    return ""


def _build_buy_upgrade_signal(sentiment, mention_type, confidence, freshness_level):
    return (
        sentiment == "BULLISH"
        and mention_type in {"DIRECT", "SECTOR", "MARKET"}
        and confidence in {"HIGH", "MEDIUM"}
        and freshness_level in FRESH_LEVELS
    )


def build_guru_opinion_input(company: str, ticker: str | None, youtube_payload: dict | None = None) -> dict:
    payload = _as_dict(youtube_payload)
    docs = _dedupe_and_rank_docs(payload.get("selected_docs"))
    content_type = _normalize_content_type(payload.get("content_type"))
    freshness_level = _normalize_freshness(payload.get("freshness_level"))
    text = _payload_text({**payload, "selected_docs": docs})

    return {
        "company": company,
        "ticker": ticker,
        "youtube_payload": payload,
        "selected_docs": docs,
        "content_type": content_type,
        "freshness_level": freshness_level,
        "text": text,
    }


def build_guru_opinion_fallback(reason: str | None = None) -> dict:
    summary = reason or "해당 종목에 적용할 수 있는 충분한 구루 의견 근거가 확인되지 않았습니다."
    return {
        "mention_type": "NONE",
        "sentiment": "NEUTRAL",
        "confidence": "LOW",
        "stock_relevance": "적용 가능한 직접/간접 근거가 부족합니다.",
        "opinion_impact": "구루 신호만으로 투자 의견을 바꾸기에는 근거가 제한적입니다.",
        "buy_upgrade_signal": False,
        "price_discipline_note": PRICE_DISCIPLINE_NEUTRAL,
        "risk_warning": "",
        "summary": str(summary)[:400],
        "evidence_items": [],
    }


def build_guru_opinion_deterministic(
    company: str,
    ticker: str | None,
    youtube_payload: dict | None = None,
) -> dict:
    opinion_input = build_guru_opinion_input(company, ticker, youtube_payload)
    payload = opinion_input["youtube_payload"]
    docs = opinion_input["selected_docs"]

    if not payload or not payload.get("is_data_valid") or not docs:
        return build_guru_opinion_fallback("유효한 구루 검색 결과가 부족해 중립으로 처리했습니다.")

    content_type = opinion_input["content_type"]
    freshness_level = opinion_input["freshness_level"]
    text = opinion_input["text"]
    mention_type = _infer_mention_type(company, ticker, payload, docs, content_type)
    sentiment = _infer_sentiment(payload, text)
    confidence = _infer_confidence(mention_type, freshness_level, docs, text)
    buy_upgrade_signal = _build_buy_upgrade_signal(
        sentiment,
        mention_type,
        confidence,
        freshness_level,
    )

    price_note = PRICE_DISCIPLINE_BULLISH if sentiment == "BULLISH" else PRICE_DISCIPLINE_NEUTRAL

    return {
        "mention_type": mention_type,
        "sentiment": sentiment,
        "confidence": confidence,
        "stock_relevance": _build_stock_relevance(mention_type),
        "opinion_impact": _build_opinion_impact(sentiment, mention_type, confidence),
        "buy_upgrade_signal": buy_upgrade_signal,
        "price_discipline_note": price_note,
        "risk_warning": _build_risk_warning(content_type, sentiment),
        "summary": _build_summary(mention_type, sentiment, confidence),
        "evidence_items": _build_evidence_items(docs, mention_type),
    }


def attach_guru_opinion(
    company: str,
    ticker: str | None,
    youtube_payload: dict | None = None,
) -> dict:
    payload = dict(_as_dict(youtube_payload))
    payload["guru_opinion"] = build_guru_opinion_deterministic(company, ticker, payload)
    return payload
