import logging
import os

from services.summary_service import (
    build_summary_from_output_reports,
    normalize_ticker_for_summary,
    save_report_summary,
)


logger = logging.getLogger(__name__)


def sanitize_filename(value: str):
    invalid_chars = '<>:"/\\|?*'
    text = str(value)

    for ch in invalid_chars:
        text = text.replace(ch, "_")

    return text.strip()


def save_report_files(output, status_callback=None):
    try:
        result_date = output["date"]
        result_dir = os.path.join("result", result_date)
        os.makedirs(result_dir, exist_ok=True)

        reports = output.get("reports", [])
        report_states = output.get("_report_states", [])
        state_by_ticker = {
            normalize_ticker_for_summary(state.get("ticker")): state
            for state in report_states
            if state.get("ticker")
        }
        summary_header = build_summary_from_output_reports(output)

        logger.info(f"save_report_files input reports count: {len(reports)}")

        for item in reports:
            state = state_by_ticker.get(normalize_ticker_for_summary(item["ticker"]))

            if state is not None:
                state["current_step"] = "report_save"

                if status_callback:
                    status_callback(state)

            try:
                ticker = sanitize_filename(item["ticker"])
                company = sanitize_filename(item["company"])

                file_name = f"{company}_{ticker}.md"
                file_path = os.path.join(result_dir, file_name)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(item["report"])

                if state is not None:
                    state["result_dir"] = result_dir
                    state["report_file_path"] = file_path
                    state["summary_header"] = summary_header

                    if item.get("status") == "SUCCESS" and not state.get("final_report"):
                        state["final_report"] = {
                            "markdown": item.get("report", ""),
                        }

                    if status_callback:
                        status_callback(state)

                logger.info(f"report file saved: {file_path}")

            except Exception as e:
                error_message = f"report file save failed: {e}"
                logger.exception(error_message)

                if state is not None:
                    state["summary_saved"] = False
                    state["status"] = "partial_failed" if state.get("final_report") else "failed"
                    state.setdefault("errors", []).append(error_message)

                    if status_callback:
                        status_callback(state)

                continue

        summary_states = [
            state
            for state in state_by_ticker.values()
            if state.get("final_report")
            and state.get("report_file_path")
            and (state.get("output_report") or {}).get("status") == "SUCCESS"
        ]

        if not summary_states:
            summary_states = build_summary_states_from_reports(
                reports,
                result_dir,
                summary_header,
            )

        for state in summary_states:
            state["current_step"] = "summary_save"
            if status_callback:
                status_callback(state)
            save_report_summary(state)
            if status_callback:
                status_callback(state)

        summary_file = os.path.join(result_dir, "summary.md")
        logger.info(
            f"summary save handled: path={summary_file}, "
            f"summary state count={len(summary_states)}, report count={len(reports)}"
        )

        return result_dir

    except Exception as e:
        logger.exception(f"report output save failed: {e}")
        raise


def build_summary_states_from_reports(reports, result_dir, summary_header):
    states = []

    for item in reports:
        if item.get("status") != "SUCCESS":
            continue

        ticker = item.get("ticker")
        company = item.get("company")

        if not ticker or not company:
            continue

        file_name = f"{sanitize_filename(company)}_{sanitize_filename(ticker)}.md"
        file_path = os.path.join(result_dir, file_name)
        states.append({
            "ticker": ticker,
            "company_name": company,
            "status": "report_generated",
            "summary_saved": False,
            "errors": [],
            "result_dir": result_dir,
            "report_file_path": file_path,
            "summary_header": summary_header,
            "final_report": {
                "markdown": item.get("report", ""),
            },
        })

    return states
