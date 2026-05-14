"""
LangGraph 기반 리포트 생성 파이프라인 진입점.

API 계층은 이 모듈을 통해 리포트 생성과 결과 저장을 호출한다.
"""

import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

from graphs.report_graph import run_single_report_graph
from schemas.report_state import ReportState, create_initial_report_state
from services.report_file_service import save_report_files
from services.report_output_service import build_output_report_item, build_run_summary_output
from services.report_render_service import render_markdown_report
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
from services.runtime_config_service import require_env
from services.stock_normalization_service import normalize_stock_pool
from services.youtube_update_service import update_youtube_vector_db


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


def run_report_pipeline(stock_pool=None, status_callback=None):
    return run_financial_report_pipeline(
        stock_pool=stock_pool,
        status_callback=status_callback,
    )


def save_pipeline_output(output, status_callback=None):
    return save_report_files(
        output,
        status_callback=status_callback,
    )
