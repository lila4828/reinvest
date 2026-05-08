import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

from vector_db.build_vector_db import build_db_from_transcripts
from vector_db.youtube_update_guard import (
    LIVE_RECHECK_DELAY_MINUTES,
    MAX_PENDING_ATTEMPTS,
    extend_pending_eligible_at,
    fetch_video_metadata,
    get_live_skip_reason,
    is_pending_item_eligible,
    load_pending_live_videos,
    mark_pending_failure,
    normalize_pending_live_video_item,
    parse_iso_datetime,
    save_pending_live_videos,
    to_iso,
    utc_now,
)


logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[1]
PENDING_PROCESS_TIMEOUT_SECONDS = int(
    os.getenv(
        "PENDING_YOUTUBE_PROCESS_TIMEOUT_SECONDS",
        os.getenv("YOUTUBE_PENDING_PROCESS_TIMEOUT_SECONDS", "180"),
    )
)


def run_python_call_with_timeout(step_name: str, code: str, timeout_seconds: int) -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-B", "-c", code],
            cwd=BACKEND_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        logger.warning("%s timeout(%s초)", step_name, timeout_seconds)
        return False
    except Exception as e:
        logger.warning("%s 실행 실패: %s", step_name, e)
        return False

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        logger.warning("%s 실패: %s", step_name, detail[-1000:])
        return False

    return True


def process_transcript_for_video(video_id: str) -> bool:
    video_ids_json = json.dumps([video_id], ensure_ascii=True)
    return run_python_call_with_timeout(
        "pending YouTube transcript update",
        (
            "from vector_db.update_youtube_db import build_local_youtube_db; "
            f"build_local_youtube_db(target_video_ids={video_ids_json})"
        ),
        PENDING_PROCESS_TIMEOUT_SECONDS,
    )


def rebuild_vector_db() -> bool:
    try:
        build_db_from_transcripts()
        return True
    except Exception as e:
        logger.warning("pending YouTube vector DB rebuild 실패: %s", e)
        return False


def process_pending_live_videos(
    path: str | Path | None = None,
    now: datetime | None = None,
    metadata_fetcher: Callable[[str], dict] = fetch_video_metadata,
    transcript_processor: Callable[[str], bool] = process_transcript_for_video,
    vector_rebuilder: Callable[[], bool] = rebuild_vector_db,
    dry_run: bool = False,
    max_items: int | None = None,
    retry_failed: bool = False,
) -> dict:
    now = now or utc_now()
    items = load_pending_live_videos(path)
    remaining_items = []
    stats = {
        "total": len(items),
        "checked": 0,
        "not_eligible": 0,
        "extended": 0,
        "processed": 0,
        "failed": 0,
        "skipped_pending": 0,
        "dry_run": dry_run,
    }
    vector_db_needs_rebuild = False
    handled_count = 0

    for raw_item in items:
        item = normalize_pending_live_video_item(raw_item)
        is_terminal = (
            item.get("attempts", 0) >= MAX_PENDING_ATTEMPTS
            or item.get("status") == "failed"
        )

        if is_terminal and not retry_failed:
            item["status"] = item.get("status") or "skipped_pending"
            if item["status"] == "pending":
                item["status"] = "skipped_pending"
            stats["skipped_pending"] += 1
            logger.info(
                "pending 영상 스킵: attempts/status 제한 / %s / attempts=%s / status=%s",
                item.get("video_id"),
                item.get("attempts"),
                item.get("status"),
            )
            remaining_items.append(item)
            continue

        eligible_at = parse_iso_datetime(item.get("eligible_at"))
        is_eligible = (
            bool(eligible_at and eligible_at <= now)
            if retry_failed
            else is_pending_item_eligible(item, now=now)
        )

        if not is_eligible:
            stats["not_eligible"] += 1
            logger.info(
                "pending 영상 스킵: eligible_at 이전 / %s / eligible_at=%s",
                item.get("video_id"),
                item.get("eligible_at"),
            )
            remaining_items.append(item)
            continue

        if max_items is not None and handled_count >= max_items:
            logger.info(
                "pending 영상 스킵: max-items 제한 / %s / max_items=%s",
                item.get("video_id"),
                max_items,
            )
            remaining_items.append(item)
            continue

        video_id = item.get("video_id")
        stats["checked"] += 1
        handled_count += 1

        try:
            info = metadata_fetcher(video_id)
            reason = get_live_skip_reason(info)

            if reason:
                logger.info(
                    "pending 영상 live/upcoming 유지: %s / %s",
                    video_id,
                    reason,
                )
                if dry_run:
                    remaining_items.append(item)
                else:
                    remaining_items.append(
                        extend_pending_eligible_at(
                            item,
                            minutes=LIVE_RECHECK_DELAY_MINUTES,
                            now=now,
                            reason=reason,
                            live_status=info.get("live_status"),
                        )
                    )
                stats["extended"] += 1
                continue

            if dry_run:
                logger.info("pending 영상 처리 예정(dry-run): %s", video_id)
                remaining_items.append(item)
                continue

            processed = transcript_processor(video_id)

            if not processed:
                raise RuntimeError("transcript processing returned False")

            vector_db_needs_rebuild = True
            stats["processed"] += 1
        except Exception as e:
            if dry_run:
                logger.warning("pending 영상 dry-run 확인 실패: %s / %s", video_id, e)
                remaining_items.append(item)
            else:
                failed_item = mark_pending_failure(item, e, now=now)
                remaining_items.append(failed_item)
            stats["failed"] += 1

    if not dry_run and vector_db_needs_rebuild and not vector_rebuilder():
        checked_at = to_iso(now)
        for item in remaining_items:
            if item.get("last_checked_at") == checked_at:
                item["last_error"] = "vector DB rebuild failed"

    if not dry_run:
        save_pending_live_videos(remaining_items, path)

    return stats


def parse_args():
    parser = argparse.ArgumentParser(
        description="Process pending live/upcoming YouTube videos safely."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only inspect pending items; do not download, transcribe, rebuild DB, or save changes.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Maximum number of eligible pending items to inspect/process in this run.",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry items with attempts >= 3 or status == failed.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    args = parse_args()
    result = process_pending_live_videos(
        dry_run=args.dry_run,
        max_items=args.max_items,
        retry_failed=args.retry_failed,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
