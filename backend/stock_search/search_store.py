import json
from pathlib import Path
from threading import Lock

BASE_DIR = Path(__file__).resolve().parent

STOCK_MASTER_PATH = BASE_DIR / "stock_master.json"
STOCK_CACHE_PATH = BASE_DIR / "stock_search_cache.json"

cache_lock = Lock()


def normalize_text(value):
    if value is None:
        return ""

    return str(value).strip().lower()


def load_json_list(file_path: Path):
    if not file_path.exists():
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        return []

    except json.JSONDecodeError:
        return []


def save_json_list(file_path: Path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_stock_item(item):
    ticker = str(item.get("ticker", "")).strip()
    company = str(item.get("company", "")).strip()

    if not ticker or not company:
        return None

    exchange = item.get("exchange")
    quote_type = item.get("quote_type") or item.get("quoteType")

    keywords = item.get("keywords", [])

    if not isinstance(keywords, list):
        keywords = []

    base_keywords = [
        ticker,
        company,
    ]

    if exchange:
        base_keywords.append(exchange)

    merged_keywords = []

    for keyword in [*base_keywords, *keywords]:
        keyword_text = str(keyword).strip()
        if keyword_text and keyword_text not in merged_keywords:
            merged_keywords.append(keyword_text)

    return {
        "ticker": ticker,
        "company": company,
        "exchange": exchange or None,
        "quote_type": quote_type or "EQUITY",
        "keywords": merged_keywords,
    }


def dedupe_stock_results(results):
    seen = set()
    deduped = []

    for item in results:
        normalized_item = normalize_stock_item(item)

        if not normalized_item:
            continue

        ticker = normalized_item["ticker"]

        if ticker in seen:
            continue

        seen.add(ticker)
        deduped.append(normalized_item)

    return deduped


def get_stock_options(limit=30):
    master_items = load_json_list(STOCK_MASTER_PATH)
    cache_items = load_json_list(STOCK_CACHE_PATH)

    results = dedupe_stock_results([*master_items, *cache_items])

    return results[:limit]


def search_json_stocks(keyword, limit=20):
    clean_keyword = normalize_text(keyword)

    if not clean_keyword:
        return []

    master_items = load_json_list(STOCK_MASTER_PATH)
    cache_items = load_json_list(STOCK_CACHE_PATH)

    all_items = dedupe_stock_results([*master_items, *cache_items])

    matched = []

    for item in all_items:
        searchable_values = [
            item.get("ticker"),
            item.get("company"),
            item.get("exchange"),
            *(item.get("keywords") or []),
        ]

        normalized_values = [
            normalize_text(value)
            for value in searchable_values
            if value
        ]

        is_matched = any(
            clean_keyword in value or value in clean_keyword
            for value in normalized_values
        )

        if is_matched:
            matched.append(item)

    return matched[:limit]


def save_stock_to_cache(stock):
    normalized_stock = normalize_stock_item(stock)

    if not normalized_stock:
        return False

    with cache_lock:
        cache_items = load_json_list(STOCK_CACHE_PATH)
        normalized_cache_items = dedupe_stock_results(cache_items)

        existing_tickers = {
            item["ticker"]
            for item in normalized_cache_items
        }

        if normalized_stock["ticker"] in existing_tickers:
            return False

        normalized_cache_items.append(normalized_stock)
        save_json_list(STOCK_CACHE_PATH, normalized_cache_items)

    return True