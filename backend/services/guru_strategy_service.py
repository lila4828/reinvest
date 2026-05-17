"""Guru strategy context helpers.

The default path is deterministic/fallback. The optional OpenAI path is guarded
by REPORT_GURU_STRATEGY_LLM_ENABLED and does not perform retrieval.
"""

import json
import logging

from pydantic import BaseModel, Field

from services.runtime_config_service import (
    get_openai_guru_strategy_model,
    is_guru_strategy_llm_enabled,
)


logger = logging.getLogger(__name__)

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


class GuruStrategyEvidenceItem(BaseModel):
    title: str = Field(default="")
    date: str = Field(default="")
    reason: str = Field(default="")


class GuruStrategySourceWindow(BaseModel):
    broadcast_count: int = 0
    start_date: str = "N/A"
    end_date: str = "N/A"
    source_policy: str = DEFAULT_SOURCE_POLICY


class GuruStrategyContextOutput(BaseModel):
    recent_market_view: str = ""
    preferred_stock_style: str = ""
    avoid_stock_style: str = ""
    portfolio_principle: str = ""
    risk_control_rule: str = ""
    mindset_summary: str = ""
    action_guide: str = ""
    source_window: GuruStrategySourceWindow = Field(default_factory=GuruStrategySourceWindow)
    evidence_items: list[GuruStrategyEvidenceItem] = Field(default_factory=list)


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    return value if isinstance(value, list) else []


def _trim_text(value, max_chars):
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


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


def _build_llm_docs(docs, limit=3):
    compact_docs = []
    for doc in _dedupe_and_rank_docs(docs, limit=limit):
        compact_docs.append(
            {
                "title": _trim_text(doc.get("title"), 180),
                "date": _trim_text(doc.get("date"), 80),
                "source": _trim_text(doc.get("source"), 80),
                "search_type": _trim_text(doc.get("search_type"), 80),
                "theme_hint": _trim_text(doc.get("theme_hint"), 80),
                "query": _trim_text(doc.get("query"), 160),
                "content_excerpt": _trim_text(doc.get("content"), 500),
            }
        )
    return compact_docs


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
        "llm_docs": _build_llm_docs(docs),
        "doc_count": len(_as_list(docs)),
        "source_window": _build_source_window(selected_docs),
        "evidence_items": _build_evidence_items(selected_docs),
    }


def _sanitize_string(value, max_chars):
    return _trim_text(value, max_chars)


def _sanitize_source_window(value, fallback):
    data = value.model_dump() if hasattr(value, "model_dump") else _as_dict(value)
    fallback_data = _as_dict(fallback)
    try:
        broadcast_count = int(data.get("broadcast_count", fallback_data.get("broadcast_count", 0)))
    except (TypeError, ValueError):
        broadcast_count = int(fallback_data.get("broadcast_count", 0) or 0)
    return {
        "broadcast_count": max(0, min(broadcast_count, 3)),
        "start_date": _sanitize_string(data.get("start_date") or fallback_data.get("start_date") or "N/A", 80),
        "end_date": _sanitize_string(data.get("end_date") or fallback_data.get("end_date") or "N/A", 80),
        "source_policy": _sanitize_string(
            data.get("source_policy") or fallback_data.get("source_policy") or DEFAULT_SOURCE_POLICY,
            160,
        ),
    }


def _sanitize_evidence_items(items, max_items=3):
    output = []
    seen = set()
    for item in _as_list(items):
        data = item.model_dump() if hasattr(item, "model_dump") else _as_dict(item)
        title = _sanitize_string(data.get("title"), 180)
        date = _sanitize_string(data.get("date"), 80)
        reason = _sanitize_string(data.get("reason"), 180)
        key = (title.lower(), date.lower())
        if key in seen:
            continue
        seen.add(key)
        output.append({"title": title, "date": date, "reason": reason})
        if len(output) >= max_items:
            break
    return output


def sanitize_guru_strategy_context_output(value, docs: list[dict] | None = None) -> dict:
    data = value.model_dump() if hasattr(value, "model_dump") else _as_dict(value)
    fallback = build_guru_strategy_context_deterministic(docs)
    return {
        "recent_market_view": _sanitize_string(data.get("recent_market_view") or fallback["recent_market_view"], 500),
        "preferred_stock_style": _sanitize_string(data.get("preferred_stock_style") or fallback["preferred_stock_style"], 500),
        "avoid_stock_style": _sanitize_string(data.get("avoid_stock_style") or fallback["avoid_stock_style"], 500),
        "portfolio_principle": _sanitize_string(data.get("portfolio_principle") or fallback["portfolio_principle"], 500),
        "risk_control_rule": _sanitize_string(data.get("risk_control_rule") or fallback["risk_control_rule"], 500),
        "mindset_summary": _sanitize_string(data.get("mindset_summary") or fallback["mindset_summary"], 500),
        "action_guide": _sanitize_string(data.get("action_guide") or fallback["action_guide"], 500),
        "source_window": _sanitize_source_window(data.get("source_window"), fallback["source_window"]),
        "evidence_items": _sanitize_evidence_items(data.get("evidence_items")),
    }


def build_guru_strategy_context_messages(context_input: dict) -> list[dict]:
    llm_payload = {
        "doc_count": context_input.get("doc_count", 0),
        "source_window": context_input.get("source_window"),
        "source_policy": _as_dict(context_input.get("source_window")).get("source_policy", DEFAULT_SOURCE_POLICY),
        "selected_docs": context_input.get("llm_docs", []),
    }
    return [
        {
            "role": "system",
            "content": (
                "You generate a compact guru_strategy_context for a stock report batch. "
                "Use only the provided YouTube/RAG docs/context. Do not invent YouTube "
                "quotes, dates, prices, target prices, or claims. Do not claim exact "
                "latest 3 broadcasts unless source_window proves it. Use cautious source "
                "wording such as '최근 검색된 구루 전략 맥락' or '최근 확인된 방송 맥락'. "
                "Extract broad principles: recent_market_view, preferred_stock_style, "
                "avoid_stock_style, portfolio_principle, risk_control_rule, "
                "mindset_summary, and action_guide. Do not generate a direct Buy/Sell "
                "opinion for any individual stock. Do not let strategy context alone "
                "imply immediate Buy. If evidence is weak, noisy, or empty, produce a "
                "conservative neutral context. Write natural Korean text fields. Keep "
                "evidence_items compact."
            ),
        },
        {
            "role": "user",
            "content": (
                "Build guru_strategy_context from this compact context:\n"
                + json.dumps(llm_payload, ensure_ascii=False, indent=2)
            ),
        },
    ]


def call_guru_strategy_context_structured_output(
    docs: list[dict] | None = None,
) -> dict:
    context_input = build_guru_strategy_context_input(docs)

    from openai import OpenAI

    client = OpenAI()
    completion = client.beta.chat.completions.parse(
        model=get_openai_guru_strategy_model(),
        messages=build_guru_strategy_context_messages(context_input),
        response_format=GuruStrategyContextOutput,
    )
    parsed = completion.choices[0].message.parsed
    return sanitize_guru_strategy_context_output(parsed, docs)


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


def build_guru_strategy_context_with_llm_or_fallback(
    docs: list[dict] | None = None,
) -> dict:
    if is_guru_strategy_llm_enabled():
        try:
            return call_guru_strategy_context_structured_output(docs)
        except Exception as exc:
            logger.warning(
                "guru_strategy_context LLM failed; using deterministic fallback: %s",
                exc,
            )

    return build_guru_strategy_context_deterministic(docs)


def attach_guru_strategy_context(payload: dict, context: dict | None = None) -> dict:
    output = dict(_as_dict(payload))
    output["guru_strategy_context"] = (
        context if isinstance(context, dict)
        else build_guru_strategy_context_fallback("context_not_provided")
    )
    return output
