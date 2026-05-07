import logging
import os
import re


logger = logging.getLogger(__name__)

SUMMARY_FILE_NAME = "summary.md"
SUMMARY_SEPARATOR = "\n\n---\n\n"


def extract_report_summary(md_report: str):
    if not md_report or not isinstance(md_report, str):
        return ""

    return normalize_summary_card_format(md_report.split("\n---")[0].strip())


def normalize_summary_card_format(summary: str):
    summary = re.sub(
        r"^#\s+(?!📈)(.+ 심층 투자 전략 리포트)",
        r"# 📈 \1",
        summary,
        count=1,
    )
    summary = summary.replace("**목표 매수가**", "**권장 매수가**")
    summary = summary.replace("**방어선**", "**하락 시 방어선/저항선**")
    summary = summary.replace("### 한 줄 결론", "### 💡 수석 애널리스트 한 줄 결론")
    summary = summary.replace(
        "### 3줄 요약 (Executive Summary)",
        "### 🎯 3줄 요약 (Executive Summary)",
    )

    return summary


def build_failed_report_card(company: str, report: str):
    reason = str(report or "분석 실패").strip()

    return (
        f"# 📈 {company} 심층 투자 전략 리포트\n\n"
        f"| 구분 | 상태 |\n"
        f"| :--- | :--- |\n"
        f"| **분석 결과** | **분석 중단** |\n\n"
        f"### ⚠️ 분석 중단 사유\n"
        f"> {reason}\n"
    )


def normalize_report_for_summary_item(item):
    company = item.get("company", "N/A")
    status = item.get("status")
    report = item.get("report", "")

    if status == "SUCCESS":
        return report

    return build_failed_report_card(company, report)


def build_summary_from_output_reports(output):
    header = extract_summary_header(output.get("summary", ""))
    summary_cards = []

    for item in output.get("reports", []):
        company = item.get("company", "N/A")
        status = item.get("status")
        report = item.get("report", "")

        if status == "SUCCESS":
            report_summary = extract_report_summary(report)

            if report_summary:
                summary_cards.append(report_summary)
            else:
                summary_cards.append(
                    f"# 📈 {company} 심층 투자 전략 리포트\n\n"
                    f"> 리포트 요약 추출 실패"
                )
        else:
            summary_cards.append(
                f"# 📈 {company} 심층 투자 전략 리포트\n\n"
                f"> {report or '분석 실패'}"
            )

    if not summary_cards:
        return output.get("summary", "")

    if header:
        return header + SUMMARY_SEPARATOR + SUMMARY_SEPARATOR.join(summary_cards)

    return SUMMARY_SEPARATOR.join(summary_cards)


def extract_summary_header(summary_text: str):
    if not summary_text or not isinstance(summary_text, str):
        return ""

    header = summary_text.split(SUMMARY_SEPARATOR, 1)[0].strip()
    first_report_index = header.find("\n# ")

    if first_report_index >= 0:
        header = header[:first_report_index].strip()

    return header


def build_merged_summary(result_dir: str, current_summary: str):
    summaries = load_existing_summaries(result_dir, current_summary)
    merged_summary = render_summary_content(summaries["header"], summaries["items"])

    if not merged_summary:
        return current_summary

    return merged_summary


def load_existing_summaries(result_dir: str, current_summary: str = ""):
    header = extract_summary_header(current_summary)
    summary_file = os.path.join(result_dir, SUMMARY_FILE_NAME)

    if not header and os.path.isfile(summary_file):
        try:
            with open(summary_file, "r", encoding="utf-8") as f:
                header = extract_summary_header(f.read())
        except Exception as e:
            logger.warning(f"summary header load failed: path={summary_file}, error={e}")

    report_candidates = {}

    if not os.path.isdir(result_dir):
        return {
            "header": header,
            "items": report_candidates,
        }

    for filename in sorted(os.listdir(result_dir)):
        if not filename.endswith(".md") or filename == SUMMARY_FILE_NAME:
            continue

        file_path = os.path.join(result_dir, filename)

        if not os.path.isfile(file_path):
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                report_summary = extract_report_summary(f.read())
        except Exception as e:
            logger.warning(f"summary merge skip failed: path={file_path}, error={e}")
            continue

        if not report_summary or "[분석 중단]" in report_summary:
            continue

        filename_without_ext = filename[:-3]
        ticker = filename_without_ext.rsplit("_", 1)[-1]
        summary_item = {
            "ticker": ticker,
            "summary": report_summary,
            "modified_at": os.path.getmtime(file_path),
        }
        upsert_summary_item(summary_item, report_candidates)

    return {
        "header": header,
        "items": report_candidates,
    }


def upsert_summary_item(summary_item, existing_summaries=None):
    if existing_summaries is None:
        existing_summaries = {}

    ticker = normalize_ticker_for_summary(summary_item.get("ticker"))
    summary = summary_item.get("summary")

    if not ticker or not summary:
        return existing_summaries

    modified_at = summary_item.get("modified_at", 0)
    current_candidate = existing_summaries.get(ticker)

    if not current_candidate or modified_at >= current_candidate.get("modified_at", 0):
        existing_summaries[ticker] = {
            **summary_item,
            "ticker": ticker,
            "modified_at": modified_at,
        }

    return existing_summaries


def build_summary_item_from_state(state):
    final_report = state.get("final_report") or {}
    markdown_report = final_report.get("markdown") or state.get("markdown_report")

    if not markdown_report:
        raise ValueError("summary 저장에 사용할 markdown report가 없습니다.")

    summary = extract_report_summary(markdown_report)

    if not summary:
        raise ValueError("markdown report에서 summary를 추출하지 못했습니다.")

    report_file_path = state.get("report_file_path")
    modified_at = (
        os.path.getmtime(report_file_path)
        if report_file_path and os.path.isfile(report_file_path)
        else 0
    )

    return {
        "ticker": state.get("ticker"),
        "company": state.get("company_name"),
        "summary": summary,
        "modified_at": modified_at,
    }


def save_report_summary(state):
    try:
        result_dir = state.get("result_dir")

        if not result_dir:
            raise ValueError("summary 저장 경로(result_dir)가 없습니다.")

        summaries = load_existing_summaries(
            result_dir,
            state.get("summary_header", ""),
        )
        summary_item = build_summary_item_from_state(state)
        upsert_summary_item(summary_item, summaries["items"])
        summary_content = render_summary_content(summaries["header"], summaries["items"])

        if not summary_content:
            raise ValueError("summary 파일에 저장할 내용이 없습니다.")

        summary_file = os.path.join(result_dir, SUMMARY_FILE_NAME)

        with open(summary_file, "w", encoding="utf-8") as f:
            f.write(summary_content)

        state["summary_saved"] = True

        if state.get("final_report"):
            state["status"] = "completed"

        logger.info(f"summary 저장 완료: path={summary_file}, ticker={state.get('ticker')}")
        return True

    except Exception as e:
        error_message = f"summary 저장 실패: {e}"
        state["summary_saved"] = False
        state.setdefault("errors", []).append(error_message)

        if state.get("final_report"):
            state["status"] = "partial_failed"

        logger.exception(error_message)
        return False


def render_summary_content(header, summary_items):
    summary_cards = [
        item["summary"]
        for item in sorted(
            summary_items.values(),
            key=lambda value: value.get("modified_at", 0),
            reverse=True,
        )
        if item.get("summary")
    ]

    if not summary_cards:
        return header or ""

    if header:
        return header + SUMMARY_SEPARATOR + SUMMARY_SEPARATOR.join(summary_cards)

    return SUMMARY_SEPARATOR.join(summary_cards)


def normalize_ticker_for_summary(ticker: str):
    ticker = str(ticker or "").strip().upper()

    if (
        len(ticker) == 10
        and ticker.startswith("A")
        and ticker[1:7].isalnum()
        and ticker[7:] in [".KS", ".KQ"]
    ):
        return ticker[1:]

    return ticker
