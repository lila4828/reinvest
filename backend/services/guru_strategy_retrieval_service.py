"""Recent local RAG retrieval for batch-level guru strategy context.

This module reads from the existing local YouTube Chroma path only. It does not
update YouTube data, process media, rebuild Chroma, or add documents.
"""

import logging
import re
from datetime import date, datetime, timedelta
from typing import Any

from services.runtime_config_service import (
    get_guru_strategy_rag_lookback_days,
    get_guru_strategy_rag_max_docs,
    get_guru_strategy_rag_max_videos,
    is_guru_strategy_recent_rag_enabled,
)


logger = logging.getLogger(__name__)

RECENT_RAG_SOURCE_POLICY = "recent_local_rag_docs_not_youtube_live_latest"
NO_RECENT_RAG_SOURCE_POLICY = "no_recent_local_rag_docs_fallback"
CONTENT_EXCERPT_LIMIT = 1000

DATE_METADATA_KEYS = (
    "date",
    "published_at",
    "upload_date",
    "video_date",
    "created_at",
    "source_date",
)


def build_guru_strategy_search_queries() -> list[str]:
    return [
        "주알홍쌤 시장관 투자전략 주도주 리스크 관리",
        "주도주 대형주 분산 매수 가격 규율",
        "잡주 부실주 우하향 회피 투자 원칙",
        "현금 비중 분할 매수 손절 리스크 관리",
        "최근 시장 흐름 반도체 조선 금융 주도주",
    ]


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _trim_text(value: Any, limit: int = CONTENT_EXCERPT_LIMIT) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def parse_strategy_doc_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None

    iso_match = re.search(r"\d{4}-\d{1,2}-\d{1,2}", text)
    dot_match = re.search(r"\d{4}\.\d{1,2}\.\d{1,2}", text)
    slash_match = re.search(r"\d{4}/\d{1,2}/\d{1,2}", text)
    compact_match = re.search(r"\d{8}", text)

    candidates = []
    if iso_match:
        candidates.append((iso_match.group(0), "%Y-%m-%d"))
    if dot_match:
        candidates.append((dot_match.group(0), "%Y.%m.%d"))
    if slash_match:
        candidates.append((slash_match.group(0), "%Y/%m/%d"))
    if compact_match:
        candidates.append((compact_match.group(0), "%Y%m%d"))

    for candidate, fmt in candidates:
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue

    return None


def _extract_date_text(doc: dict) -> str:
    metadata = _as_dict(doc.get("metadata"))
    for key in DATE_METADATA_KEYS:
        value = doc.get(key) or metadata.get(key)
        if value:
            return str(value)
    return ""


def normalize_strategy_doc(doc: dict) -> dict:
    source = _as_dict(doc)
    metadata = _as_dict(source.get("metadata"))
    date_text = _extract_date_text(source)
    parsed_date = parse_strategy_doc_date(date_text)
    content = (
        source.get("content_excerpt")
        or source.get("content")
        or source.get("transcript")
        or source.get("snippet")
        or source.get("page_content")
        or ""
    )

    return {
        "title": _trim_text(source.get("title") or metadata.get("title") or "제목 없음", 180),
        "date": date_text or "N/A",
        "parsed_date": parsed_date,
        "video_id": str(source.get("video_id") or metadata.get("video_id") or "").strip(),
        "url": str(source.get("url") or metadata.get("url") or source.get("source") or "").strip(),
        "source": "local_youtube_rag",
        "search_type": str(source.get("search_type") or "STRATEGY")[:80],
        "theme_hint": str(source.get("theme_hint") or "guru_strategy")[:80],
        "query": str(source.get("query") or "")[:180],
        "content_excerpt": _trim_text(content, CONTENT_EXCERPT_LIMIT),
        "content": _trim_text(content, CONTENT_EXCERPT_LIMIT),
        "reason": _trim_text(
            source.get("reason")
            or source.get("theme_hint")
            or "최근 RAG DB에서 확인된 구루 전략 맥락",
            180,
        ),
        "metadata": {
            "source_policy": RECENT_RAG_SOURCE_POLICY,
        },
    }


def filter_recent_docs_by_metadata_date(docs, lookback_days: int) -> list[dict]:
    cutoff = datetime.now().date() - timedelta(days=max(0, int(lookback_days)))
    recent_docs = []
    for doc in docs or []:
        normalized = normalize_strategy_doc(doc)
        parsed_date = normalized.get("parsed_date")
        if parsed_date and parsed_date >= cutoff:
            recent_docs.append(normalized)

    recent_docs.sort(key=lambda item: item.get("parsed_date") or date.min, reverse=True)
    return recent_docs


def _dedupe_key(doc: dict) -> tuple[str, str]:
    video_id = str(doc.get("video_id") or "").strip().lower()
    if video_id:
        return ("video_id", video_id)

    url = str(doc.get("url") or "").strip().lower()
    if url:
        return ("url", url)

    return (
        "title_date",
        f"{str(doc.get('title') or '').strip().lower()}|{str(doc.get('date') or '').strip().lower()}",
    )


def dedupe_strategy_docs_by_video(docs, max_videos: int = 3, max_docs: int = 6) -> list[dict]:
    normalized = [normalize_strategy_doc(doc) for doc in docs or [] if isinstance(doc, dict)]
    normalized.sort(key=lambda item: item.get("parsed_date") or date.min, reverse=True)

    output = []
    video_counts: dict[tuple[str, str], int] = {}
    for doc in normalized:
        key = _dedupe_key(doc)
        if key not in video_counts and len(video_counts) >= max_videos:
            continue
        if video_counts.get(key, 0) >= 2:
            continue

        video_counts[key] = video_counts.get(key, 0) + 1
        compact_doc = dict(doc)
        compact_doc.pop("parsed_date", None)
        output.append(compact_doc)
        if len(output) >= max_docs:
            break

    return output


def _query_local_rag_docs(max_docs: int) -> list[dict]:
    from flows.youtube.tool import get_guru_youtube_tool

    tool = get_guru_youtube_tool()
    docs = []
    for query in build_guru_strategy_search_queries():
        docs.extend(tool._search(query, search_type="STRATEGY", k=max_docs))
    return docs


def _attach_window_metadata(docs: list[dict], lookback_days: int) -> list[dict]:
    dates = [str(doc.get("date") or "") for doc in docs if str(doc.get("date") or "").strip()]
    video_count = len({_dedupe_key(doc) for doc in docs})
    latest_doc_date = max(dates) if dates else ""
    for doc in docs:
        metadata = dict(_as_dict(doc.get("metadata")))
        metadata.update(
            {
                "source_policy": RECENT_RAG_SOURCE_POLICY,
                "lookback_days": lookback_days,
                "broadcast_count": video_count,
                "doc_count": len(docs),
                "latest_doc_date": latest_doc_date,
            }
        )
        doc["metadata"] = metadata
    return docs


def get_recent_guru_strategy_docs(
    lookback_days: int = 3,
    fallback_days: list[int] | None = None,
    max_videos: int = 3,
    max_docs: int = 6,
) -> list[dict]:
    if not is_guru_strategy_recent_rag_enabled():
        return []

    fallback_days = fallback_days if fallback_days is not None else [7, 14]
    try:
        raw_docs = _query_local_rag_docs(max(max_docs, max_videos * 2))
    except Exception as exc:
        logger.warning("guru strategy recent RAG retrieval failed; using fallback: %s", exc)
        return []

    for window in [lookback_days, *fallback_days]:
        recent_docs = filter_recent_docs_by_metadata_date(raw_docs, window)
        deduped_docs = dedupe_strategy_docs_by_video(
            recent_docs,
            max_videos=max_videos,
            max_docs=max_docs,
        )
        if deduped_docs:
            return _attach_window_metadata(deduped_docs, window)

    return []


def get_recent_guru_strategy_docs_from_config() -> list[dict]:
    return get_recent_guru_strategy_docs(
        lookback_days=get_guru_strategy_rag_lookback_days(),
        fallback_days=[7, 14],
        max_videos=get_guru_strategy_rag_max_videos(),
        max_docs=get_guru_strategy_rag_max_docs(),
    )
