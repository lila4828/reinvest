import os
from functools import lru_cache

from stock_search.search_store import (
    STOCK_CACHE_PATH,
    STOCK_MASTER_PATH,
    dedupe_stock_results,
    load_json_list,
)


def sanitize_report_filename_part(value: str):
    invalid_chars = '<>:"/\\|?*'
    text = str(value or "")

    for ch in invalid_chars:
        text = text.replace(ch, "_")

    return text.strip()


def get_report_file_path(result_dir_abspath: str, result_date: str, company: str, ticker: str):
    filename = (
        f"{sanitize_report_filename_part(company)}_"
        f"{sanitize_report_filename_part(ticker)}.md"
    )
    return os.path.join(result_dir_abspath, result_date, filename)


def parse_report_meta_from_filename(filename: str):
    if not filename or filename == "summary.md" or not filename.endswith(".md"):
        return None

    base_name = filename.removesuffix(".md")
    separator_index = base_name.rfind("_")

    if separator_index <= 0 or separator_index >= len(base_name) - 1:
        return None

    return {
        "company": base_name[:separator_index],
        "ticker": base_name[separator_index + 1:].upper(),
    }


def format_market_label(exchange: str | None, ticker: str | None):
    exchange_text = str(exchange or "").strip()
    exchange_upper = exchange_text.upper()
    ticker_upper = str(ticker or "").strip().upper()

    if exchange_upper == "KOSPI" or ticker_upper.endswith(".KS"):
        return "코스피"

    if exchange_upper == "KOSDAQ" or ticker_upper.endswith(".KQ"):
        return "코스닥"

    if "NASDAQ" in exchange_upper:
        return "나스닥"

    if "NYSE AMERICAN" in exchange_upper or exchange_upper in ["AMEX", "ASE"]:
        return "NYSE American"

    if "NYSE ARCA" in exchange_upper or exchange_upper == "ARCA":
        return "NYSE Arca"

    if (
        "NEW YORK STOCK EXCHANGE" in exchange_upper
        or exchange_upper in ["NYSE", "NYQ"]
    ):
        return "뉴욕증권거래소"

    if "OTC" in exchange_upper:
        return "OTC"

    if ticker_upper:
        return exchange_text or "미국"

    return None


@lru_cache(maxsize=1)
def get_stock_market_index():
    market_index = {}
    stock_items = dedupe_stock_results([
        *load_json_list(STOCK_MASTER_PATH),
        *load_json_list(STOCK_CACHE_PATH),
    ])

    for item in stock_items:
        ticker = str(item.get("ticker", "")).strip().upper()

        if not ticker:
            continue

        exchange = item.get("exchange")
        market_index[ticker] = {
            "exchange": exchange,
            "market_label": format_market_label(exchange, ticker),
        }

    return market_index


def get_report_market_info(filename: str):
    meta = parse_report_meta_from_filename(filename)

    if not meta:
        return {
            "ticker": None,
            "company": None,
            "exchange": None,
            "market_label": None,
        }

    ticker = meta["ticker"]
    market_info = get_stock_market_index().get(ticker, {})

    return {
        "ticker": ticker,
        "company": meta["company"],
        "exchange": market_info.get("exchange"),
        "market_label": market_info.get("market_label") or format_market_label(None, ticker),
    }


def find_existing_daily_reports(
    stock_pool: list[tuple[str, str]],
    result_date: str,
    result_dir_abspath: str,
):
    existing_reports = []

    for ticker, company in stock_pool:
        if os.path.exists(get_report_file_path(result_dir_abspath, result_date, company, ticker)):
            existing_reports.append({
                "ticker": ticker,
                "company": company,
                "date": result_date,
            })

    return existing_reports
