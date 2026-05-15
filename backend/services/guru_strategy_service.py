"""Deterministic guru strategy context helpers.

This module prepares a compact batch-level strategy context from provided
Youtube/RAG documents. It does not query Chroma, call OpenAI, or mutate runtime
state by itself.
"""

DEFAULT_SOURCE_POLICY = "recent_retrieved_docs_not_db_global_latest"

FALLBACK_CONTEXT = {
    "recent_market_view": "최근 구루 전략 맥락을 확인할 수 있는 충분한 자료가 없어 중립적으로 해석합니다.",
    "preferred_stock_style": "확인된 자료가 부족해 특정 선호 스타일을 단정하지 않습니다.",
    "avoid_stock_style": "확인된 자료가 부족해 특정 회피 대상을 단정하지 않습니다.",
    "portfolio_principle": "분산과 가격 규율을 우선 적용합니다.",
    "risk_control_rule": "신용/과도한 집중 투자는 피하고 손실 제한 기준을 유지합니다.",
    "mindset_summary": "자료 부족 시 구루 신호보다 시스템 가격/재무 판단을 우선합니다.",
    "action_guide": "무리한 추격매수보다 분할 접근과 확인 매매를 우선합니다.",
}

CATEGORY_RULES = {
    "avoid_stock_style": {
        "keywords": ["잡주", "동전주", "부실", "우하향", "penny", "junk", "weak"],
        "text": "제공 자료에서는 부실하거나 우하향하는 약한 종목을 경계하는 맥락이 확인됩니다.",
    },
    "preferred_stock_style": {
        "keywords": ["주도주", "대형주", "신고가", "강한 종목", "leader", "large cap", "breakout"],
        "text": "제공 자료에서는 시장 주도주, 대형주, 강한 추세 종목을 선호하는 맥락이 확인됩니다.",
    },
    "portfolio_principle": {
        "keywords": ["분산", "몰빵", "etf", "포트폴리오", "allocation", "diversification"],
        "text": "제공 자료에서는 과도한 집중보다 분산과 포트폴리오 관리를 중시하는 맥락이 확인됩니다.",
    },
    "risk_control_rule": {
        "keywords": ["신용", "파생", "리스크", "손절", "위험", "margin", "derivative", "stop loss"],
        "text": "제공 자료에서는 신용, 파생, 손실 확대를 경계하고 리스크 통제를 우선하는 맥락이 확인됩니다.",
    },
    "mindset_summary": {
        "keywords": ["fomo", "멘탈", "기다림", "원칙", "심리", "patience", "mindset", "discipline"],
        "text": "제공 자료에서는 조급한 추격보다 원칙, 기다림, 심리 관리가 중요하다는 맥락이 확인됩니다.",
    },
    "recent_market_view": {
        "keywords": ["코스피", "시장", "강한 장", "위험선호", "nasdaq", "market", "risk-on"],
        "text": "제공 자료에서는 시장 흐름과 위험선호 여부를 함께 확인해야 한다는 맥락이 확인됩니다.",
    },
}


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    return value if isinstance(value, list) else []


def _doc_text(doc):
    parts = [
        doc.get("title"),
        doc.get("theme_hint"),
        doc.get("search_type"),
        doc.get("query"),
        doc.get("content"),
        doc.get("transcript"),
        doc.get("snippet"),
    ]
    return " ".join(str(part or "") for part in parts).lower()


def _safe_int(value, default=10**9):
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


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


def _matched_text(category, docs):
    keywords = CATEGORY_RULES[category]["keywords"]
    for doc in docs:
        text = _doc_text(doc)
        if any(keyword.lower() in text for keyword in keywords):
            return CATEGORY_RULES[category]["text"]
    return FALLBACK_CONTEXT[category]


def _build_evidence_items(docs):
    evidence_items = []
    for doc in docs[:3]:
        reason_parts = []
        if doc.get("theme_hint"):
            reason_parts.append(str(doc["theme_hint"]))
        if doc.get("search_type"):
            reason_parts.append(str(doc["search_type"]))
        reason = ", ".join(reason_parts) or "제공된 검색 문서 기준 전략 맥락"
        evidence_items.append(
            {
                "title": doc.get("title") or "제목 없음",
                "date": doc.get("date") or "날짜 없음",
                "reason": reason[:160],
            }
        )
    return evidence_items


def _build_source_window(docs, source_policy=DEFAULT_SOURCE_POLICY):
    dates = [
        str(doc.get("date") or "").strip()
        for doc in docs
        if str(doc.get("date") or "").strip() not in {"", "날짜 없음", "N/A"}
    ]
    return {
        "broadcast_count": min(len(docs), 3),
        "start_date": min(dates) if dates else "N/A",
        "end_date": max(dates) if dates else "N/A",
        "source_policy": source_policy,
    }


def build_guru_strategy_context_input(docs: list[dict] | None = None) -> dict:
    selected_docs = _dedupe_and_rank_docs(docs)
    return {
        "selected_docs": selected_docs,
        "source_window": _build_source_window(selected_docs),
        "evidence_items": _build_evidence_items(selected_docs),
    }


def build_guru_strategy_context_fallback(reason: str | None = None) -> dict:
    context = dict(FALLBACK_CONTEXT)
    context["source_window"] = {
        "broadcast_count": 0,
        "start_date": "N/A",
        "end_date": "N/A",
        "source_policy": reason or DEFAULT_SOURCE_POLICY,
    }
    context["evidence_items"] = []
    return context


def build_guru_strategy_context_deterministic(docs: list[dict] | None = None) -> dict:
    context_input = build_guru_strategy_context_input(docs)
    selected_docs = context_input["selected_docs"]
    if not selected_docs:
        return build_guru_strategy_context_fallback("mock_or_provided_docs_empty")

    context = {
        "recent_market_view": _matched_text("recent_market_view", selected_docs),
        "preferred_stock_style": _matched_text("preferred_stock_style", selected_docs),
        "avoid_stock_style": _matched_text("avoid_stock_style", selected_docs),
        "portfolio_principle": _matched_text("portfolio_principle", selected_docs),
        "risk_control_rule": _matched_text("risk_control_rule", selected_docs),
        "mindset_summary": _matched_text("mindset_summary", selected_docs),
        "action_guide": "제공된 전략 맥락은 종목별 가격, 재무, 뉴스 판단과 함께 보수적으로 적용해야 합니다.",
        "source_window": context_input["source_window"],
        "evidence_items": context_input["evidence_items"],
    }
    return context


def attach_guru_strategy_context(payload: dict, context: dict | None = None) -> dict:
    output = dict(_as_dict(payload))
    output["guru_strategy_context"] = (
        context if isinstance(context, dict)
        else build_guru_strategy_context_fallback("context_not_provided")
    )
    return output
