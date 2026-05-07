"""
CrewAI 기반 리포트 생성 파이프라인 진입점.

이번 1차 리팩토링에서는 기존 CrewAI 실행 로직과 프롬프트를 유지하고,
API 계층이 main.py 내부 구현에 직접 의존하지 않도록 얇은 pipeline 계층만 둔다.
"""


def run_report_pipeline(stock_pool=None):
    from main import run_financial_crew

    return run_financial_crew(stock_pool=stock_pool)


def save_pipeline_output(output):
    from services.report_file_service import save_report_files

    return save_report_files(output)
