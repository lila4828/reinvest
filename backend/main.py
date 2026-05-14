from pipelines.report_pipeline import run_financial_report_pipeline
from services.report_file_service import save_report_files


if __name__ == "__main__":
    output = run_financial_report_pipeline()

    print(output["summary"])

    save_report_files(output)
