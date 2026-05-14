"""
LangGraph 기반 리포트 생성 파이프라인 진입점.

API 계층이 main.py 내부 구현에 직접 의존하지 않도록 얇은 pipeline 계층을 둔다.
"""


def run_report_pipeline(stock_pool=None, status_callback=None):
    from main import run_financial_crew

    return run_financial_crew(
        stock_pool=stock_pool,
        status_callback=status_callback,
    )


def save_pipeline_output(output, status_callback=None):
    from services.report_file_service import save_report_files

    return save_report_files(
        output,
        status_callback=status_callback,
    )
