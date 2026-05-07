from typing import Any, Optional, TypedDict


class ReportState(TypedDict, total=False):
    ticker: str
    company_name: str
    status: str
    current_step: str

    price_data: Optional[dict[str, Any]]
    accounting_data: Optional[dict[str, Any]]
    macro_data: Optional[dict[str, Any]]
    research_data: Optional[dict[str, Any]]
    youtube_context: Optional[str]
    final_report: Optional[dict[str, Any]]
    markdown_report: Optional[str]
    output_report: Optional[dict[str, Any]]

    chart_data: Optional[dict[str, Any]]
    summary_saved: bool
    result_dir: Optional[str]
    report_file_path: Optional[str]
    summary_header: Optional[str]

    errors: list[str]


def create_initial_report_state(ticker: str, company_name: str) -> ReportState:
    return {
        "ticker": ticker,
        "company_name": company_name,
        "status": "pending",
        "current_step": "initialized",
        "summary_saved": False,
        "errors": [],
    }
