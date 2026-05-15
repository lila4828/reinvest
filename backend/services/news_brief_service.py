"""News brief helpers for research payloads.

The default path is deterministic. The OpenAI path is optional and guarded by
REPORT_NEWS_BRIEF_LLM_ENABLED so local validation cannot call it accidentally.
"""

import logging
import json
from typing import Literal

from pydantic import BaseModel, Field

from services.runtime_config_service import (
    get_openai_news_brief_model,
    is_news_brief_llm_enabled,
)


logger = logging.getLogger(__name__)

NEWS_BRIEF_SENTIMENTS = {"POSITIVE", "NEUTRAL", "NEGATIVE"}
NEWS_BRIEF_MOMENTUM = {"HIGH", "MEDIUM", "LOW"}

PRICE_REFLECTION_NOTE = (
    "뉴스 호재의 주가 반영 여부는 가격 데이터와 함께 최종분석에서 판단해야 합니다."
)
DEFAULT_FRESHNESS_NOTE = (
    "검색 결과의 날짜 정보를 기준으로 최근성을 제한적으로 판단해야 합니다."
)
DEFAULT_SUMMARY = "유효한 뉴스 근거가 제한적이어서 보수적으로 해석해야 합니다."


class NewsBriefEvidenceItem(BaseModel):
    title: str = Field(default="")
    source: str = Field(default="")
    date: str = Field(default="")
    reason: str = Field(default="")


class NewsBriefOutput(BaseModel):
    sentiment: Literal["POSITIVE", "NEUTRAL", "NEGATIVE"]
    momentum_strength: Literal["HIGH", "MEDIUM", "LOW"]
    key_positive_factors: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    price_reflection: str = ""
    summary: str = ""
    final_impact: str = ""
    source_count: int = 0
    freshness_note: str = ""
    evidence_items: list[NewsBriefEvidenceItem] = Field(default_factory=list)


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    return value if isinstance(value, list) else []


def _trim_text(value, max_chars):
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def _normalize_momentum(value):
    momentum = str(value or "LOW").upper()
    if momentum in NEWS_BRIEF_MOMENTUM:
        return momentum
    return "LOW"


def _map_sentiment(score):
    try:
        numeric_score = float(score)
    except (TypeError, ValueError):
        numeric_score = 50

    if numeric_score >= 60:
        return "POSITIVE"
    if numeric_score <= 40:
        return "NEGATIVE"
    return "NEUTRAL"


def _compact_reason(item, fallback):
    reason = str(item.get("reason") or "").strip()
    if reason:
        return reason[:160]
    return fallback


def _compact_factor(item, fallback):
    title = str(item.get("title") or "").strip()
    reason = _compact_reason(item, fallback)
    if title:
        return f"{title[:120]} - {reason}"
    return reason


def _collect_issue_items(issue_breakdown, label):
    return [
        item for item in _as_list(issue_breakdown.get(label))
        if isinstance(item, dict)
    ]


def _build_evidence_items(issue_breakdown, results, max_items=5):
    ordered = []
    for label in ["positive", "negative", "neutral"]:
        ordered.extend(_collect_issue_items(issue_breakdown, label))

    if not ordered:
        ordered = [item for item in _as_list(results) if isinstance(item, dict)]

    evidence_items = []
    seen = set()
    for item in ordered:
        title = str(item.get("title") or "제목 없음").strip()[:160]
        source = str(item.get("source") or "출처 불명").strip()[:80]
        date = str(item.get("date") or "날짜 없음").strip()[:80]
        reason = _compact_reason(item, "수집 뉴스 기준 관찰 항목")
        key = (title.lower(), source.lower(), date.lower())
        if key in seen:
            continue
        seen.add(key)
        evidence_items.append(
            {
                "title": title or "제목 없음",
                "source": source or "출처 불명",
                "date": date or "날짜 없음",
                "reason": reason,
            }
        )
        if len(evidence_items) >= max_items:
            break

    return evidence_items


def _build_llm_result_items(results, max_items=10):
    items = []
    for result in _as_list(results):
        if not isinstance(result, dict):
            continue
        items.append(
            {
                "title": _trim_text(result.get("title"), 160),
                "source": _trim_text(result.get("source"), 80),
                "date": _trim_text(result.get("date"), 80),
                "classification": _trim_text(
                    result.get("classification")
                    or result.get("sentiment")
                    or result.get("label"),
                    40,
                ),
                "reason": _trim_text(result.get("reason"), 180),
                "snippet_excerpt": _trim_text(result.get("snippet"), 240),
            }
        )
        if len(items) >= max_items:
            break
    return items


def _build_freshness_note(evidence_items):
    dates = []
    for item in evidence_items:
        date = str(item.get("date") or "").strip()
        if not date or date in {"날짜 없음", "N/A", "UNKNOWN"}:
            continue
        if date not in dates:
            dates.append(date)

    if dates:
        shown_dates = ", ".join(dates[:3])
        return f"수집 뉴스의 날짜 정보({shown_dates})를 기준으로 최근성을 제한적으로 판단해야 합니다."

    return DEFAULT_FRESHNESS_NOTE


def _build_final_impact(sentiment, momentum_strength):
    if sentiment == "POSITIVE" and momentum_strength in {"HIGH", "MEDIUM"}:
        return "투자 의견을 지지할 수 있으나 가격 규율 확인이 필요합니다."
    if sentiment == "NEGATIVE":
        return "투자 판단에 부담 요인으로 작용할 수 있습니다."
    return "단독으로 투자 의견을 바꾸기에는 근거가 제한적입니다."


def build_news_brief_input(research_payload: dict) -> dict:
    payload = _as_dict(research_payload)
    issue_breakdown = _as_dict(payload.get("issue_breakdown"))
    results = _as_list(payload.get("results"))
    evidence_items = _build_evidence_items(issue_breakdown, results)

    return {
        "sentiment_score": payload.get("sentiment_score"),
        "momentum_strength": _normalize_momentum(payload.get("momentum_strength")),
        "news_summary": payload.get("news_summary"),
        "sentiment_reason": payload.get("sentiment_reason"),
        "issue_breakdown": issue_breakdown,
        "result_count": payload.get("result_count", len(results)),
        "is_data_valid": bool(payload.get("is_data_valid")),
        "top_results": _build_llm_result_items(results),
        "evidence_items": evidence_items,
    }


def _sanitize_string_list(values, max_items, max_chars):
    output = []
    for value in _as_list(values):
        text = _trim_text(value, max_chars)
        if text:
            output.append(text)
        if len(output) >= max_items:
            break
    return output


def _sanitize_evidence_items(items, max_items=5):
    output = []
    seen = set()
    for item in _as_list(items):
        data = item.model_dump() if hasattr(item, "model_dump") else _as_dict(item)
        title = _trim_text(data.get("title"), 160)
        source = _trim_text(data.get("source"), 80)
        date = _trim_text(data.get("date"), 80)
        reason = _trim_text(data.get("reason"), 180)
        key = (title.lower(), source.lower(), date.lower())
        if key in seen:
            continue
        seen.add(key)
        output.append(
            {
                "title": title,
                "source": source,
                "date": date,
                "reason": reason,
            }
        )
        if len(output) >= max_items:
            break
    return output


def sanitize_news_brief_output(value, research_payload: dict | None = None) -> dict:
    payload = _as_dict(research_payload)
    data = value.model_dump() if hasattr(value, "model_dump") else _as_dict(value)
    fallback = build_news_brief_deterministic(payload) if payload else build_news_brief_fallback()

    sentiment = str(data.get("sentiment") or "").upper()
    if sentiment not in NEWS_BRIEF_SENTIMENTS:
        sentiment = fallback["sentiment"]

    momentum_strength = _normalize_momentum(data.get("momentum_strength"))
    source_count = data.get("source_count")
    try:
        source_count = int(source_count)
    except (TypeError, ValueError):
        source_count = fallback["source_count"]

    return {
        "sentiment": sentiment,
        "momentum_strength": momentum_strength,
        "key_positive_factors": _sanitize_string_list(
            data.get("key_positive_factors"), 4, 180
        ),
        "key_risks": _sanitize_string_list(data.get("key_risks"), 3, 180),
        "price_reflection": _trim_text(
            data.get("price_reflection") or PRICE_REFLECTION_NOTE,
            300,
        ),
        "summary": _trim_text(data.get("summary") or fallback["summary"], 900),
        "final_impact": _trim_text(
            data.get("final_impact") or fallback["final_impact"],
            300,
        ),
        "source_count": max(0, source_count),
        "freshness_note": _trim_text(
            data.get("freshness_note") or fallback["freshness_note"],
            300,
        ),
        "evidence_items": _sanitize_evidence_items(data.get("evidence_items")),
    }


def build_news_brief_messages(news_brief_input: dict) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "You generate a compact news_brief for a stock report. Use only "
                "the provided search results and research payload. Do not invent "
                "article facts, dates, sources, prices, analyst names, or URLs. "
                "Do not treat news as audited financial data. Distinguish positive "
                "catalysts from risks. If price reflection is uncertain, say it is "
                "uncertain. Keep evidence_items compact and do not quote full "
                "article text. Write natural Korean text for text fields, while "
                "enum fields must use fixed English enum values. sentiment must "
                "be POSITIVE, NEUTRAL, or NEGATIVE. momentum_strength must be "
                "HIGH, MEDIUM, or LOW. source_count must reflect provided "
                "result_count or available results. If evidence is weak or noisy, "
                "be conservative."
            ),
        },
        {
            "role": "user",
            "content": (
                "Build news_brief from this compact research payload:\n"
                + json.dumps(news_brief_input, ensure_ascii=False, indent=2)
            ),
        },
    ]


def call_news_brief_structured_output(research_payload: dict) -> dict:
    news_brief_input = build_news_brief_input(research_payload)

    from openai import OpenAI

    client = OpenAI()
    completion = client.beta.chat.completions.parse(
        model=get_openai_news_brief_model(),
        messages=build_news_brief_messages(news_brief_input),
        response_format=NewsBriefOutput,
    )
    parsed = completion.choices[0].message.parsed
    return sanitize_news_brief_output(parsed, research_payload)


def build_news_brief_fallback(
    research_payload: dict | None = None,
    reason: str | None = None,
) -> dict:
    payload = _as_dict(research_payload)
    results = _as_list(payload.get("results"))
    summary = str(payload.get("news_summary") or DEFAULT_SUMMARY).strip()
    if reason and not payload.get("news_summary"):
        summary = str(reason).strip()

    return {
        "sentiment": "NEUTRAL",
        "momentum_strength": "LOW",
        "key_positive_factors": [],
        "key_risks": [],
        "price_reflection": PRICE_REFLECTION_NOTE,
        "summary": summary[:600],
        "final_impact": "단독으로 투자 의견을 바꾸기에는 근거가 제한적입니다.",
        "source_count": int(payload.get("result_count") or len(results) or 0),
        "freshness_note": DEFAULT_FRESHNESS_NOTE,
        "evidence_items": [],
    }


def build_news_brief_deterministic(research_payload: dict) -> dict:
    payload = _as_dict(research_payload)
    if not payload or not payload.get("is_data_valid"):
        return build_news_brief_fallback(payload)

    brief_input = build_news_brief_input(payload)
    issue_breakdown = brief_input["issue_breakdown"]
    results = _as_list(payload.get("results"))
    sentiment = _map_sentiment(brief_input.get("sentiment_score"))
    momentum_strength = _normalize_momentum(brief_input.get("momentum_strength"))
    evidence_items = brief_input["evidence_items"]

    positive_items = _collect_issue_items(issue_breakdown, "positive")
    negative_items = _collect_issue_items(issue_breakdown, "negative")

    key_positive_factors = [
        _compact_factor(item, "수집 뉴스 기준 긍정 이슈")
        for item in positive_items[:4]
    ]
    key_risks = [
        _compact_factor(item, "수집 뉴스 기준 리스크 이슈")
        for item in negative_items[:3]
    ]

    summary = str(brief_input.get("news_summary") or DEFAULT_SUMMARY).strip()

    return {
        "sentiment": sentiment,
        "momentum_strength": momentum_strength,
        "key_positive_factors": key_positive_factors,
        "key_risks": key_risks,
        "price_reflection": PRICE_REFLECTION_NOTE,
        "summary": summary[:900],
        "final_impact": _build_final_impact(sentiment, momentum_strength),
        "source_count": int(payload.get("result_count") or len(results) or 0),
        "freshness_note": _build_freshness_note(evidence_items),
        "evidence_items": evidence_items,
    }


def attach_news_brief(research_payload: dict) -> dict:
    payload = dict(_as_dict(research_payload))
    if not payload:
        payload["news_brief"] = build_news_brief_fallback()
        return payload

    if is_news_brief_llm_enabled():
        try:
            payload["news_brief"] = call_news_brief_structured_output(payload)
            return payload
        except Exception as exc:
            logger.warning("news_brief LLM failed; using deterministic fallback: %s", exc)

    payload["news_brief"] = build_news_brief_deterministic(payload)
    return payload
