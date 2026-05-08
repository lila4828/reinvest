import logging

from langgraph.graph import END, StateGraph

from schemas.report_state import ReportState, create_initial_report_state
from services.summary_service import save_report_summary


logger = logging.getLogger(__name__)


def append_graph_error(state: ReportState, message: str):
    state.setdefault("errors", []).append(message)


def validate_input_node(state: ReportState):
    ticker = str(state.get("ticker") or "").strip()
    company_name = str(state.get("company_name") or "").strip()

    if not ticker or not company_name:
        message = "ticker/company_name 값이 비어 있습니다."
        state["status"] = "failed"
        state["current_step"] = "validate_input"
        state["summary_saved"] = False
        append_graph_error(state, message)
        return state

    state["ticker"] = ticker
    state["company_name"] = company_name
    state["status"] = "running"
    state["current_step"] = "validate_input"
    return state


def macro_node(state: ReportState):
    macro_context = state.get("macro_context") or {}

    if state.get("macro_json") and state.get("macro_score") is not None:
        state["current_step"] = "macro"
        state["macro_context"] = {
            "macro_data": state.get("macro_data"),
            "macro_score": state.get("macro_score"),
            "macro_score_reasons": state.get("macro_score_reasons", []),
            "macro_json": state.get("macro_json"),
        }
        return state

    if macro_context.get("macro_json") and macro_context.get("macro_score") is not None:
        state["macro_context"] = macro_context
        state["macro_data"] = macro_context.get("macro_data")
        state["macro_json"] = macro_context["macro_json"]
        state["macro_score"] = macro_context["macro_score"]
        state["macro_score_reasons"] = macro_context.get("macro_score_reasons", [])
        state["current_step"] = "macro"
        return state

    agents = state.get("agents") or {}
    tasks = state.get("tasks") or {}

    try:
        from main import run_macro_step

        macro_score, macro_score_reasons, macro_json = run_macro_step(
            agents["macro"],
            tasks["macro"],
            state=state,
        )
        state["macro_context"] = {
            "macro_data": state.get("macro_data"),
            "macro_score": macro_score,
            "macro_score_reasons": macro_score_reasons,
            "macro_json": macro_json,
        }
        state["macro_json"] = macro_json
        state["macro_score"] = macro_score
        state["macro_score_reasons"] = macro_score_reasons
    except Exception as e:
        message = f"macro node 실패: {e}"
        logger.exception(message)
        state["status"] = "failed"
        state["current_step"] = "macro"
        append_graph_error(state, message)

    return state


def accounting_node(state: ReportState):
    agents = state.get("agents") or {}
    tasks = state.get("tasks") or {}
    ticker = state.get("ticker")
    company_name = state.get("company_name")

    try:
        from main import run_accounting_step

        acc_data, failed_item = run_accounting_step(
            agents["accounting"],
            tasks["accounting"],
            ticker,
            company_name,
            state=state,
        )

        if failed_item:
            state["output_report"] = failed_item
            state["status"] = "failed"
            return state

        state["acc_data"] = acc_data
    except Exception as e:
        message = f"accounting node 실패: {company_name} ({ticker}) 예외 발생: {e}"
        logger.exception(message)
        state["status"] = "failed"
        state["current_step"] = "accounting"
        state["summary_saved"] = False
        append_graph_error(state, message)

    return state


def research_node(state: ReportState):
    agents = state.get("agents") or {}
    tasks = state.get("tasks") or {}
    company_name = state.get("company_name")

    try:
        from main import run_research_step

        state["research_result"] = run_research_step(
            agents["research"],
            tasks["research"],
            company_name,
            state=state,
        )
    except Exception as e:
        message = f"research node 실패: {company_name} 예외 발생: {e}"
        logger.exception(message)
        state["current_step"] = "research"
        append_graph_error(state, message)

    return state


def youtube_rag_node(state: ReportState):
    agents = state.get("agents") or {}
    tasks = state.get("tasks") or {}
    company_name = state.get("company_name")

    try:
        from main import run_youtube_rag_step

        state["youtube_result"] = run_youtube_rag_step(
            agents["youtube"],
            tasks["youtube"],
            company_name,
            state=state,
        )
    except Exception as e:
        message = f"youtube_rag node 실패: {company_name} 예외 발생: {e}"
        logger.exception(message)
        state["current_step"] = "youtube_rag"
        append_graph_error(state, message)

    return state


def price_node(state: ReportState):
    company_name = state.get("company_name")

    try:
        from main import run_price_step

        current_price, target_buy_price, defense_price = run_price_step(
            state.get("acc_data"),
            company_name,
            state=state,
        )
        state["current_price"] = current_price
        state["target_buy_price"] = target_buy_price
        state["defense_price"] = defense_price
    except Exception as e:
        message = f"price node 실패: {company_name} 예외 발생: {e}"
        logger.exception(message)
        state["status"] = "failed"
        state["current_step"] = "price"
        append_graph_error(state, message)

    return state


def analysis_node(state: ReportState):
    agents = state.get("agents") or {}
    tasks = state.get("tasks") or {}
    macro_context = state.get("macro_context") or {}
    ticker = state.get("ticker")
    company_name = state.get("company_name")

    try:
        from main import (
            append_report_error,
            decide_final_opinion,
            parse_research_result,
            parse_youtube_result,
            render_markdown_report,
            run_final_analysis_step,
        )

        sentiment, research_json = parse_research_result(
            state.get("research_result"),
            company_name,
            state=state,
        )
        guru_score, guru_weight, youtube_json = parse_youtube_result(
            state.get("youtube_result"),
            company_name,
            state=state,
        )
        final_opinion = decide_final_opinion(
            acc_data=state.get("acc_data"),
            macro_score=macro_context["macro_score"],
            sentiment=sentiment,
            guru_score=guru_score,
            guru_weight=guru_weight,
            company=company_name,
            state=state,
        )
        final_result = run_final_analysis_step(
            analyst_agent=agents["analysis"],
            ana_tasks=tasks["analysis"],
            company=company_name,
            acc_data=state.get("acc_data"),
            macro_json=macro_context["macro_json"],
            research_json=research_json,
            youtube_json=youtube_json,
            final_opinion=final_opinion,
            target_buy_price=state.get("target_buy_price"),
            defense_price=state.get("defense_price"),
            state=state,
        )

        if final_result.pydantic:
            md_report = render_markdown_report(
                ticker=ticker,
                company=company_name,
                final_opinion=final_opinion,
                final_result=final_result,
                current_price=state.get("current_price"),
                target_buy_price=state.get("target_buy_price"),
                defense_price=state.get("defense_price"),
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
            append_report_error(state, "Analysis 에이전트 구조화 파싱 실패")
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
            logger.error(f"[{company_name}] Analysis 에이전트 구조화 파싱 실패")
    except Exception as e:
        message = f"analysis node 실패: {company_name} ({ticker}) 예외 발생: {e}"
        logger.exception(message)
        state["status"] = "failed"
        state["current_step"] = "analysis"
        state["summary_saved"] = False
        append_graph_error(state, message)
        state["final_report"] = {
            "raw": message,
        }
        state["output_report"] = {
            "ticker": ticker,
            "company": company_name,
            "status": "FAILED",
            "report": message,
        }

    return state


def save_summary_node(state: ReportState):
    state["current_step"] = "summary_save"

    if not state.get("final_report"):
        return state

    if not state.get("result_dir") or not state.get("report_file_path"):
        state["summary_deferred"] = True
        return state

    save_report_summary(state)
    return state


def finalize_node(state: ReportState):
    has_report = bool(state.get("final_report") or state.get("markdown_report"))

    if state.get("status") == "failed":
        return state

    if has_report and state.get("summary_saved") is True:
        state["status"] = "completed"
    elif has_report:
        state["status"] = "report_generated"
    else:
        state["status"] = "failed"

    return state


def should_continue(state: ReportState):
    return "finalize" if state.get("status") == "failed" else "continue"


def build_report_graph():
    graph = StateGraph(ReportState)

    graph.add_node("validate_input", validate_input_node)
    graph.add_node("macro", macro_node)
    graph.add_node("accounting", accounting_node)
    graph.add_node("research", research_node)
    graph.add_node("youtube_rag", youtube_rag_node)
    graph.add_node("price", price_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("save_summary", save_summary_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("validate_input")
    graph.add_conditional_edges(
        "validate_input",
        should_continue,
        {
            "continue": "macro",
            "finalize": "finalize",
        },
    )
    graph.add_conditional_edges(
        "macro",
        should_continue,
        {
            "continue": "accounting",
            "finalize": "finalize",
        },
    )
    graph.add_conditional_edges(
        "accounting",
        should_continue,
        {
            "continue": "research",
            "finalize": "finalize",
        },
    )
    graph.add_edge("research", "youtube_rag")
    graph.add_edge("youtube_rag", "price")
    graph.add_conditional_edges(
        "price",
        should_continue,
        {
            "continue": "analysis",
            "finalize": "finalize",
        },
    )
    graph.add_edge("analysis", "save_summary")
    graph.add_edge("save_summary", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


REPORT_GRAPH = build_report_graph()


def cleanup_runtime_fields(state: ReportState):
    for key in [
        "agents",
        "tasks",
        "research_result",
        "youtube_result",
    ]:
        state.pop(key, None)

    return state


def run_report_graph(state: ReportState):
    return cleanup_runtime_fields(REPORT_GRAPH.invoke(state))


def run_single_report_graph(ticker, company_name, agents, tasks, macro_context):
    state = create_initial_report_state(ticker, company_name)
    state["agents"] = agents
    state["tasks"] = tasks
    state["macro_context"] = macro_context
    state["macro_data"] = macro_context.get("macro_data")
    state["macro_json"] = macro_context.get("macro_json")
    state["macro_score"] = macro_context.get("macro_score")
    state["macro_score_reasons"] = macro_context.get("macro_score_reasons", [])
    return run_report_graph(state)
