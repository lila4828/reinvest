import json
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


def _first_present(*values):
    for value in values:
        if value is not None:
            return value

    return None


def _get_chart_data(value):
    if isinstance(value, list):
        return value

    if isinstance(value, dict):
        chart_data = value.get("chart_data")
        if isinstance(chart_data, list):
            return chart_data

    return []


def _extract_failed_reason(item, state):
    if item.get("status") == "SUCCESS":
        return None

    for value in [
        item.get("failed_reason"),
        state.get("failed_reason") if state else None,
    ]:
        if value:
            return str(value).strip()

    errors = state.get("errors") if state else None
    if isinstance(errors, list) and errors:
        reason = str(errors[-1]).strip()
        for marker in ["FAIL 사유:", "FAIL ?ъ쑀:"]:
            if marker in reason:
                return reason.split(marker, 1)[1].strip()
        if ":" in reason:
            return reason.split(":", 1)[1].strip()
        return reason

    report = str(item.get("report") or "").strip()
    for line in report.splitlines():
        if "중단 사유" in line or "以묐떒" in line:
            cells = [cell.strip(" *") for cell in line.split("|") if cell.strip()]
            if len(cells) >= 2:
                return cells[-1]

    return report or None


def build_report_meta_payload(item, state=None):
    state = state or {}
    accounting_data = state.get("accounting_data") or {}
    price_data = state.get("price_data") or {}
    final_report = state.get("final_report") or {}

    company = _first_present(
        item.get("company"),
        state.get("company_name"),
        state.get("company"),
    )
    ticker = _first_present(item.get("ticker"), state.get("ticker"))
    status = item.get("status") or state.get("status")

    financial_chart_data = _get_chart_data(
        _first_present(
            state.get("chart_data"),
            item.get("chart_data"),
            final_report.get("chart_data"),
        )
    )

    return {
        "company": company or "",
        "ticker": ticker or "",
        "status": status or "",
        "investment_opinion": _first_present(
            final_report.get("investment_opinion"),
            item.get("investment_opinion"),
        ),
        "entry_strategy": _first_present(
            final_report.get("entry_strategy"),
            item.get("entry_strategy"),
        ),
        "price": {
            "current_price": _first_present(
                price_data.get("current_price"),
                accounting_data.get("current_price"),
            ),
            "split_buy_price": _first_present(
                price_data.get("target_buy_price"),
                state.get("target_buy_price"),
                item.get("target_buy_price"),
            ),
            "sell_review_price": _first_present(
                price_data.get("defense_price"),
                state.get("defense_price"),
                item.get("defense_price"),
            ),
            "moving_averages": {
                "ma_20": accounting_data.get("ma_20"),
                "ma_30": accounting_data.get("ma_30"),
                "ma_60": accounting_data.get("ma_60"),
                "ma_200": accounting_data.get("ma_200"),
                "ma_350": accounting_data.get("ma_350"),
                "ma_500": accounting_data.get("ma_500"),
                "ma_999": accounting_data.get("ma_999"),
            },
        },
        "financial_chart_data": financial_chart_data,
        "technical_chart_data": {},
        "macro": state.get("macro_data") or {},
        "failed_reason": _extract_failed_reason(item, state),
    }


def save_report_meta_file(result_dir, md_filename, meta_payload):
    meta_filename = md_filename[:-3] + ".meta.json" if md_filename.endswith(".md") else f"{md_filename}.meta.json"
    meta_path = os.path.join(result_dir, meta_filename)

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta_payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return meta_path


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

                try:
                    meta_payload = build_report_meta_payload(item, state)
                    meta_path = save_report_meta_file(result_dir, file_name, meta_payload)
                    if state is not None:
                        state["meta_file_path"] = meta_path
                    logger.info(f"report meta file saved: {meta_path}")
                except Exception as e:
                    error_message = f"report meta file save failed: {e}"
                    logger.exception(error_message)
                    if state is not None:
                        state.setdefault("errors", []).append(error_message)

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
