from typing import Any, Optional, TypedDict


class ReportState(TypedDict, total=False):
    ticker: str
    company_name: str
    status: str
    current_step: str

    price_data: Optional[dict[str, Any]]
    accounting_data: Optional[dict[str, Any]]
    macro_data: Optional[dict[str, Any]]
    macro_json: Optional[str]
    macro_score: Optional[int]
    macro_score_reasons: Optional[list[str]]
    research_data: Optional[dict[str, Any]]
    youtube_context: Optional[str]
    final_report: Optional[dict[str, Any]]
    markdown_report: Optional[str]
    output_report: Optional[dict[str, Any]]
    agents: Optional[dict[str, Any]]
    tasks: Optional[dict[str, Any]]
    macro_context: Optional[dict[str, Any]]
    acc_data: Optional[dict[str, Any]]
    research_result: Optional[Any]
    youtube_result: Optional[Any]
    current_price: Optional[float]
    target_buy_price: Optional[float]
    defense_price: Optional[float]
    summary_deferred: bool

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
