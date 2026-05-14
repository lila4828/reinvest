import os
import logging
import subprocess
import sys
from dotenv import load_dotenv
from datetime import datetime
from logging.handlers import RotatingFileHandler

# YouTube 자동 업데이트 헬퍼
from vector_db.fetch_latest_youtube_ids import fetch_all_latest_youtube_ids
from vector_db.youtube_update_guard import filter_processable_video_ids
from services.report_file_service import save_report_files
from services.report_output_service import build_output_report_item, build_run_summary_output
from services.report_render_service import render_markdown_report
from services.runtime_config_service import require_env
from services.report_state_service import build_failed_state, finalize_state
from services.report_step_service import (
    append_report_error,
    decide_final_opinion,
    parse_research_result,
    parse_youtube_result,
    run_accounting_step,
    run_final_analysis_step,
    run_macro_step,
    run_price_step,
    run_research_step,
    run_youtube_rag_step,
)
from schemas.report_state import ReportState, create_initial_report_state

# 시스템 로깅 및 디버그 설정

# 0. 환경 변수 로드
load_dotenv()

log_file_handler = RotatingFileHandler(
    "system.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        log_file_handler,
    ],
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
YOUTUBE_UPDATE_TIMEOUT_SECONDS = int(
    os.getenv("YOUTUBE_UPDATE_TIMEOUT_SECONDS", "60")
)
REPORT_GENERATION_YOUTUBE_UPDATE_ENABLED = (
    os.getenv("REPORT_GENERATION_YOUTUBE_UPDATE_ENABLED", "false").lower()
    in ["1", "true", "yes", "on"]
)


def normalize_kr_ticker(ticker: str):
    ticker = str(ticker or "").strip().upper()

    if (
        len(ticker) == 10
        and ticker.startswith("A")
        and ticker[1:7].isalnum()
        and ticker[7:] in [".KS", ".KQ"]
    ):
        return ticker[1:]

    return ticker

def normalize_stock_pool(stock_pool):
    """
    외부 입력 종목 데이터를 main.py 내부 표준 형식으로 변환한다.
    표준 형식: [("TSLA", "Tesla"), ("005930.KS", "Samsung Electronics")]
    """

    default_stock_pool = [
        ("TSLA", "Tesla"),
        ("005930.KS", "Samsung Electronics"),
        ("000660.KS", "SK Hynix"),
    ]

    if stock_pool is None:
        return default_stock_pool

    if not isinstance(stock_pool, list) or not stock_pool:
        raise ValueError("stock_pool은 비어 있지 않은 list여야 합니다.")

    normalized = []

    for item in stock_pool:
        if isinstance(item, dict):
            ticker = item.get("ticker")
            company = item.get("company")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            ticker, company = item
        else:
            raise ValueError(f"잘못된 종목 입력 형식입니다: {item}")

        ticker = normalize_kr_ticker(ticker)
        company = str(company).strip() if company else ""

        if not ticker or not company:
            raise ValueError(f"ticker/company 값이 비어 있습니다: {item}")

        normalized.append((ticker, company))

    return normalized


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


def run_single_report_pipeline(
    ticker,
    company_name,
    agents,
    tasks,
    macro_context,
):
    state = create_initial_report_state(ticker, company_name)

    if macro_context.get("macro_data"):
        state["macro_data"] = macro_context["macro_data"]

    try:
        logger.info(f"분석 시작: {company_name} ({ticker})")

        acc_data, failed_item = run_accounting_step(
            ticker=ticker,
            company=company_name,
            state=state,
        )

        if failed_item:
            state["output_report"] = failed_item
            return finalize_state(state)

        logger.debug(f"[{company_name}] 리서치 데이터 수집 중...")
        research_result = run_research_step(
            company=company_name,
            state=state,
        )

        logger.debug(f"[{company_name}] 유튜브 데이터 수집 중...")
        youtube_result = run_youtube_rag_step(
            company=company_name,
            state=state,
        )

        sentiment, research_json = parse_research_result(
            research_result,
            company_name,
            state=state,
        )

        guru_score, guru_weight, youtube_json = parse_youtube_result(
            youtube_result,
            company_name,
            state=state,
        )

        final_opinion = decide_final_opinion(
            acc_data=acc_data,
            macro_score=macro_context["macro_score"],
            sentiment=sentiment,
            guru_score=guru_score,
            guru_weight=guru_weight,
            company=company_name,
            state=state,
        )

        current_price, target_buy_price, defense_price = run_price_step(
            acc_data,
            company_name,
            state=state,
        )

        final_result = run_final_analysis_step(
            company=company_name,
            acc_data=acc_data,
            macro_json=macro_context["macro_json"],
            research_json=research_json,
            youtube_json=youtube_json,
            final_opinion=final_opinion,
            target_buy_price=target_buy_price,
            defense_price=defense_price,
            state=state,
        )

        if final_result.pydantic:
            md_report = render_markdown_report(
                ticker=ticker,
                company=company_name,
                final_opinion=final_opinion,
                final_result=final_result,
                current_price=current_price,
                target_buy_price=target_buy_price,
                defense_price=defense_price,
                state=state,
            )
            state["output_report"] = {
                "ticker": ticker,
                "company": company_name,
                "status": "SUCCESS",
                "report": md_report,
            }
            logger.info(f"[{company_name}] 리포트 생성 완료")
        else:
            fallback_report = f"[{company_name}]\n{final_result.raw}"
            append_report_error(state, "Analysis 데이터 구조 파싱 실패")
            state["status"] = "failed"
            state["final_report"] = {
                "raw": final_result.raw,
                "markdown": fallback_report,
            }
            state["output_report"] = {
                "ticker": ticker,
                "company": company_name,
                "status": "FAILED",
                "report": fallback_report,
            }
            logger.error(f"[{company_name}] Analysis 데이터 구조 파싱 실패")

    except Exception as e:
        msg = f"[종목 분석 실패] {company_name} ({ticker}) 예외 발생: {e}"
        logger.exception(msg)
        append_report_error(state, msg)
        state["status"] = "failed"
        state["summary_saved"] = False
        state["final_report"] = {
            "raw": msg,
        }
        state["output_report"] = {
            "ticker": ticker,
            "company": company_name,
            "status": "FAILED",
            "report": msg,
        }

    return finalize_state(state)


def build_macro_context(agents=None, tasks=None):
    macro_state: ReportState = {
        "status": "running",
        "current_step": "macro",
        "errors": [],
    }
    macro_score, macro_score_reasons, macro_json = run_macro_step(
        state=macro_state,
    )

    return {
        "macro_data": macro_state.get("macro_data"),
        "macro_score": macro_score,
        "macro_score_reasons": macro_score_reasons,
        "macro_json": macro_json,
    }


def run_multiple_report_pipeline(targets, agents, tasks, macro_context=None, status_callback=None):
    from graphs.report_graph import run_single_report_graph

    if macro_context is None:
        macro_context = build_macro_context(agents, tasks)

    results = []

    for ticker, company_name in targets:
        try:
            state = run_single_report_graph(
                ticker,
                company_name,
                agents,
                tasks,
                macro_context,
                status_callback=status_callback,
            )
        except Exception as e:
            logger.exception(f"종목별 리포트 생성 중 예외 발생: {company_name} ({ticker})")
            state = build_failed_state((ticker, company_name), e)

            if status_callback:
                status_callback(state)

        results.append(state)

    return results, macro_context


def run_financial_report_pipeline(stock_pool=None, status_callback=None):
    stock_pool = normalize_stock_pool(stock_pool)
    require_env("OPENAI_API_KEY")

    # 뉴스 리서치에서 사용
    require_env("SERPER_API_KEY")

    agents = {}
    tasks = {}

    # ---------------------------------------------------------
    # 0. YouTube DB 업데이트
    # ---------------------------------------------------------
    update_youtube_vector_db()

    logger.debug("report pipeline started")
    report_states, macro_context = run_multiple_report_pipeline(
        stock_pool,
        agents,
        tasks,
        status_callback=status_callback,
    )
    all_reports = [
        state.get("output_report") or build_output_report_item(state)
        for state in report_states
    ]
    summary_output = build_run_summary_output(macro_context["macro_json"], all_reports)

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "summary": summary_output,
        "reports": all_reports,
        "_report_states": report_states,
    }

if __name__ == "__main__":
    output = run_financial_report_pipeline()

    logger.debug("=" * 60)
    logger.debug("report pipeline started")
    logger.debug("=" * 60)

    print(output["summary"])

    save_report_files(output)
