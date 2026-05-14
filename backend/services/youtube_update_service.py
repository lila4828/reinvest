import logging
import os
import subprocess
import sys

from dotenv import load_dotenv

from vector_db.fetch_latest_youtube_ids import fetch_all_latest_youtube_ids
from vector_db.youtube_update_guard import filter_processable_video_ids


load_dotenv()

logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YOUTUBE_UPDATE_TIMEOUT_SECONDS = int(
    os.getenv("YOUTUBE_UPDATE_TIMEOUT_SECONDS", "60")
)
REPORT_GENERATION_YOUTUBE_UPDATE_ENABLED = (
    os.getenv("REPORT_GENERATION_YOUTUBE_UPDATE_ENABLED", "false").lower()
    in ["1", "true", "yes", "on"]
)


def run_python_module_call_with_timeout(step_name: str, code: str, timeout_seconds: int):
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
        logger.warning(
            "%s timeout(%s초). 기존 YouTube Vector DB를 사용해 계속 진행합니다.",
            step_name,
            timeout_seconds,
        )
        return False
    except Exception as e:
        logger.warning(
            "%s 실행 실패. 기존 YouTube Vector DB를 사용해 계속 진행합니다. %s",
            step_name,
            e,
        )
        return False

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        detail = stderr or stdout or f"returncode={result.returncode}"
        logger.warning(
            "%s 실패. 기존 YouTube Vector DB를 사용해 계속 진행합니다. %s",
            step_name,
            detail[-1000:],
        )
        return False

    logger.info("%s 완료", step_name)
    return True


def update_youtube_vector_db():
    if not REPORT_GENERATION_YOUTUBE_UPDATE_ENABLED:
        logger.info("리포트 생성 중 YouTube DB 업데이트는 비활성화되어 기존 Chroma DB를 사용합니다.")
        return

    logger.debug("[0단계] YouTube 최신 영상 확인...")

    try:
        new_vids = fetch_all_latest_youtube_ids(fetch_limit=5)

        if not new_vids:
            logger.info("YouTube 신규 영상 없음. 기존 DB를 사용합니다.")
            return

        processable_vids, skipped_vids = filter_processable_video_ids(new_vids)

        if skipped_vids:
            logger.warning(
                "YouTube 최신 영상 %s개는 live/upcoming/처리 불가 상태라 pending 저장 후 건너뜁니다.",
                len(skipped_vids),
            )

        if not processable_vids:
            logger.info(
                "이번 리포트 생성 중 처리 가능한 YouTube 신규 영상이 없어 기존 DB를 사용합니다."
            )
            return

        logger.info(
            "YouTube 최신 영상 %s개 감지. YouTube Vector DB를 제한 시간 안에서 업데이트합니다.",
            len(processable_vids),
        )

        if not run_python_module_call_with_timeout(
            "YouTube transcript update",
            "from vector_db.update_youtube_db import build_local_youtube_db; build_local_youtube_db()",
            YOUTUBE_UPDATE_TIMEOUT_SECONDS,
        ):
            return

        run_python_module_call_with_timeout(
            "YouTube vector DB rebuild",
            "from vector_db.build_vector_db import build_db_from_transcripts; build_db_from_transcripts()",
            YOUTUBE_UPDATE_TIMEOUT_SECONDS,
        )

    except Exception as e:
        logger.exception(f"YouTube DB 업데이트 실패. 기존 DB로 진행합니다. {e}")
