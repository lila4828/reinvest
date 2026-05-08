import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yt_dlp


logger = logging.getLogger(__name__)

VECTOR_DB_DIR = Path(__file__).resolve().parent
DEFAULT_VIDEO_IDS_PATH = VECTOR_DB_DIR / "youtube_video_ids.txt"
PENDING_LIVE_VIDEOS_PATH = VECTOR_DB_DIR / "pending_live_videos.json"

LIVE_SKIP_STATUSES = {"is_live", "is_upcoming"}
MAX_PENDING_ATTEMPTS = int(os.getenv("YOUTUBE_PENDING_MAX_ATTEMPTS", "3"))
INITIAL_ELIGIBLE_DELAY_MINUTES = int(
    os.getenv("YOUTUBE_PENDING_INITIAL_DELAY_MINUTES", "90")
)
LIVE_RECHECK_DELAY_MINUTES = int(
    os.getenv("YOUTUBE_PENDING_LIVE_RECHECK_DELAY_MINUTES", "60")
)
DEFAULT_METADATA_TIMEOUT_SECONDS = int(
    os.getenv("YOUTUBE_METADATA_TIMEOUT_SECONDS", "15")
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def add_minutes(value: datetime, minutes: int) -> datetime:
    return value + timedelta(minutes=minutes)


def get_youtube_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def load_pending_live_videos(path: str | Path | None = None) -> list[dict]:
    target_path = Path(path) if path else PENDING_LIVE_VIDEOS_PATH

    if not target_path.exists():
        return []

    try:
        with target_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning("pending live video 목록을 읽지 못했습니다: %s", e)
        return []

    if not isinstance(data, list):
        logger.warning("pending live video 목록 형식이 list가 아닙니다.")
        return []

    return [normalize_pending_live_video_item(item) for item in data if isinstance(item, dict)]


def save_pending_live_videos(
    items: list[dict],
    path: str | Path | None = None,
) -> None:
    target_path = Path(path) if path else PENDING_LIVE_VIDEOS_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with target_path.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def get_live_skip_reason(info: dict | None) -> str | None:
    if not isinstance(info, dict):
        return "metadata_unavailable"

    live_status = info.get("live_status")
    duration = info.get("duration")

    if live_status in LIVE_SKIP_STATUSES:
        return f"live_status={live_status}"

    if info.get("is_live") is True:
        return "is_live=True"

    if duration is None:
        return "duration is None"

    if duration == 0:
        return "duration == 0"

    return None


def should_skip_video_for_current_run(info: dict | None) -> bool:
    return get_live_skip_reason(info) is not None


def build_pending_live_video_item(
    video_id: str,
    info: dict | None,
    reason: str,
    now: datetime | None = None,
) -> dict:
    now = now or utc_now()
    detected_at = to_iso(now)
    eligible_at = to_iso(add_minutes(now, INITIAL_ELIGIBLE_DELAY_MINUTES))
    info = info if isinstance(info, dict) else {}

    return {
        "video_id": video_id,
        "title": info.get("title") or "제목 없음",
        "url": info.get("webpage_url") or get_youtube_url(video_id),
        "detected_at": detected_at,
        "eligible_at": eligible_at,
        "reason": reason,
        "live_status": info.get("live_status"),
        "attempts": 0,
        "status": "pending",
        "last_error": None,
        "last_checked_at": None,
    }


def normalize_pending_live_video_item(item: dict) -> dict:
    video_id = str(item.get("video_id") or "").strip()
    detected_at = parse_iso_datetime(item.get("detected_at")) or utc_now()
    eligible_at = parse_iso_datetime(item.get("eligible_at"))

    if eligible_at is None:
        eligible_at = add_minutes(detected_at, INITIAL_ELIGIBLE_DELAY_MINUTES)

    attempts = item.get("attempts", 0)
    if not isinstance(attempts, int):
        attempts = 0

    normalized = dict(item)
    normalized["video_id"] = video_id
    normalized["title"] = item.get("title") or "제목 없음"
    normalized["url"] = item.get("url") or get_youtube_url(video_id)
    normalized["detected_at"] = to_iso(detected_at)
    normalized["eligible_at"] = to_iso(eligible_at)
    normalized["reason"] = item.get("reason") or "unknown"
    normalized["live_status"] = item.get("live_status")
    normalized["attempts"] = attempts
    normalized["status"] = item.get("status") or "pending"
    normalized["last_error"] = item.get("last_error")
    normalized["last_checked_at"] = item.get("last_checked_at")
    return normalized


def upsert_pending_live_video(
    video_id: str,
    info: dict | None,
    reason: str,
    path: str | Path | None = None,
    now: datetime | None = None,
) -> bool:
    items = load_pending_live_videos(path)

    for index, item in enumerate(items):
        if item.get("video_id") != video_id:
            continue

        updated = normalize_pending_live_video_item(item)
        updated["title"] = updated.get("title") or (info or {}).get("title") or "제목 없음"
        updated["url"] = updated.get("url") or (info or {}).get("webpage_url") or get_youtube_url(video_id)
        updated["reason"] = reason or updated.get("reason")
        updated["live_status"] = (info or {}).get("live_status", updated.get("live_status"))
        items[index] = updated
        save_pending_live_videos(items, path)
        return False

    items.append(build_pending_live_video_item(video_id, info, reason, now=now))
    save_pending_live_videos(items, path)
    return True


def is_pending_item_eligible(item: dict, now: datetime | None = None) -> bool:
    now = now or utc_now()
    normalized = normalize_pending_live_video_item(item)

    if normalized.get("status") in {"failed", "skipped_pending"}:
        return False

    if normalized.get("attempts", 0) >= MAX_PENDING_ATTEMPTS:
        return False

    eligible_at = parse_iso_datetime(normalized.get("eligible_at"))
    return bool(eligible_at and eligible_at <= now)


def extend_pending_eligible_at(
    item: dict,
    minutes: int = LIVE_RECHECK_DELAY_MINUTES,
    now: datetime | None = None,
    reason: str | None = None,
    live_status: str | None = None,
) -> dict:
    now = now or utc_now()
    updated = normalize_pending_live_video_item(item)
    updated["eligible_at"] = to_iso(add_minutes(now, minutes))
    updated["last_checked_at"] = to_iso(now)
    updated["status"] = "pending"

    if reason:
        updated["reason"] = reason

    if live_status is not None:
        updated["live_status"] = live_status

    return updated


def mark_pending_failure(
    item: dict,
    error: Exception | str,
    now: datetime | None = None,
) -> dict:
    now = now or utc_now()
    updated = normalize_pending_live_video_item(item)
    updated["attempts"] = updated.get("attempts", 0) + 1
    updated["last_error"] = str(error)
    updated["last_checked_at"] = to_iso(now)

    if updated["attempts"] >= MAX_PENDING_ATTEMPTS:
        updated["status"] = "failed"
    else:
        updated["status"] = "pending"
        updated["eligible_at"] = to_iso(add_minutes(now, LIVE_RECHECK_DELAY_MINUTES))

    return updated


def fetch_video_metadata(
    video_id: str,
    timeout_seconds: int = DEFAULT_METADATA_TIMEOUT_SECONDS,
) -> dict:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": timeout_seconds,
        "retries": 1,
        "fragment_retries": 1,
        "skip_download": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(get_youtube_url(video_id), download=False)


def remove_video_ids_from_file(
    video_ids: list[str] | set[str],
    file_path: str | Path | None = None,
) -> None:
    ids_to_remove = set(video_ids)

    if not ids_to_remove:
        return

    target_path = Path(file_path) if file_path else DEFAULT_VIDEO_IDS_PATH

    if not target_path.exists():
        return

    with target_path.open("r", encoding="utf-8") as f:
        existing_ids = [line.strip() for line in f.readlines() if line.strip()]

    filtered_ids = [video_id for video_id in existing_ids if video_id not in ids_to_remove]

    with target_path.open("w", encoding="utf-8") as f:
        for video_id in filtered_ids:
            f.write(f"{video_id}\n")


def filter_processable_video_ids(video_ids: list[str]) -> tuple[list[str], list[str]]:
    processable_ids = []
    skipped_ids = []

    for video_id in video_ids:
        try:
            info = fetch_video_metadata(video_id)
            reason = get_live_skip_reason(info)
        except Exception as e:
            logger.warning(
                "유튜브 메타데이터 확인 실패. 이번 리포트 생성에서는 스킵합니다: %s / %s",
                video_id,
                e,
            )
            info = {"title": "제목 없음", "webpage_url": get_youtube_url(video_id)}
            reason = f"metadata_error: {type(e).__name__}"

        if reason:
            upsert_pending_live_video(video_id, info, reason)
            skipped_ids.append(video_id)
            logger.warning(
                "유튜브 영상 스킵 및 pending 저장: %s / %s",
                video_id,
                reason,
            )
            continue

        processable_ids.append(video_id)

    if skipped_ids:
        remove_video_ids_from_file(skipped_ids)

    return processable_ids, skipped_ids
