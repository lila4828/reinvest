from datetime import datetime

from services.summary_service import extract_report_summary


def build_run_summary_output(macro_json, all_reports):
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    summary_output = f"> **최근 업데이트 일시:** {now_text}\n\n"
    summary_output += "<!-- MACRO_DATA\n"
    summary_output += macro_json
    summary_output += "\n-->\n\n"

    summary_cards = []

    for item in all_reports:
        if item.get("status") == "SUCCESS":
            summary_cards.append(extract_report_summary(item.get("report", "")))
        else:
            summary_cards.append(
                f"# 📈 {item.get('company', 'N/A')} 심층 투자 전략 리포트\n\n"
                f"> {item.get('report', '분석 실패')}"
            )

    summary_output += "\n\n---\n\n".join(summary_cards)

    return summary_output


def build_output_report_item(state):
    final_report = state.get("final_report") or {}
    report = final_report.get("markdown") or final_report.get("raw")

    if report is None:
        report = "\n".join(state.get("errors", [])) or "분석 실패"

    return {
        "ticker": state.get("ticker"),
        "company": state.get("company_name"),
        "status": "SUCCESS" if state.get("status") in ["report_generated", "completed"] else "FAILED",
        "report": report,
    }
