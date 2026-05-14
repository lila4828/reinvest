from schemas.report_state import create_initial_report_state
from services.report_output_service import build_output_report_item


def finalize_state(state):
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


def build_failed_state(target, error):
    if isinstance(target, dict):
        ticker = target.get("ticker")
        company_name = target.get("company_name") or target.get("company")
    else:
        ticker, company_name = target

    state = create_initial_report_state(ticker, company_name)
    state["status"] = "failed"
    state["current_step"] = "failed"
    state["summary_saved"] = False
    state.setdefault("errors", []).append(str(error))
    state["final_report"] = {
        "raw": f"[종목 분석 실패] {company_name} ({ticker}) 예외 발생: {error}",
    }
    state["output_report"] = build_output_report_item(state)
    return state
