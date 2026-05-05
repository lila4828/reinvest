import json
from pathlib import Path
from threading import Lock

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(exist_ok=True)

STOCK_MASTER_PATH = DATA_DIR / "stock_master.json"
STOCK_CACHE_PATH = DATA_DIR / "stock_search_cache.json"

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


def make_dedupe_key(item):
    ticker = str(item.get("ticker", "")).strip().upper()
    company = str(item.get("company", "")).strip().lower()
    exchange = str(item.get("exchange", "")).strip().upper()

    # 한국 종목은 005930 / 005930.KS / 005930.KQ를 같은 종목으로 취급
    if (
        exchange in ["KOSPI", "KOSDAQ"]
        or ticker.endswith(".KS")
        or ticker.endswith(".KQ")
    ):
        base_code = (
            ticker
            .replace(".KS", "")
            .replace(".KQ", "")
        )

        return f"KR:{base_code}"

    # 미국 종목 등은 거래소 + 티커 기준으로 중복 제거
    if exchange:
        return f"{exchange}:{ticker}"

    # 거래소 정보가 없는 경우 fallback
    return f"{ticker}:{company}"


def dedupe_stock_results(results):
    seen = set()
    deduped = []

    for item in results:
        normalized_item = normalize_stock_item(item)

        if not normalized_item:
            continue

        dedupe_key = make_dedupe_key(normalized_item)

        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        deduped.append(normalized_item)

    return deduped


def get_match_score(item, clean_keyword):
    ticker = normalize_text(item.get("ticker"))
    company = normalize_text(item.get("company"))
    exchange = normalize_text(item.get("exchange"))

    keywords = [
        normalize_text(keyword)
        for keyword in (item.get("keywords") or [])
        if keyword
    ]

    # 사용자가 공백 포함해서 검색할 때 대비
    compact_keyword = clean_keyword.replace(" ", "")
    compact_company = company.replace(" ", "")
    compact_ticker = ticker.replace(" ", "")

    compact_keywords = [
        keyword.replace(" ", "")
        for keyword in keywords
    ]

    # 1순위: 티커 정확히 일치
    if clean_keyword == ticker:
        return 1000

    # 2순위: 공백 제거 티커 정확히 일치
    if compact_keyword == compact_ticker:
        return 950

    # 3순위: 회사명 정확히 일치
    if clean_keyword == company:
        return 900

    # 4순위: 공백 제거 회사명 정확히 일치
    if compact_keyword == compact_company:
        return 850

    # 5순위: 키워드 정확히 일치
    if clean_keyword in keywords:
        return 800

    # 6순위: 공백 제거 키워드 정확히 일치
    if compact_keyword in compact_keywords:
        return 750

    # 7순위: 티커가 검색어로 시작
    if ticker.startswith(clean_keyword):
        return 700

    # 8순위: 회사명이 검색어로 시작
    if company.startswith(clean_keyword):
        return 600

    # 9순위: 공백 제거 회사명이 검색어로 시작
    if compact_company.startswith(compact_keyword):
        return 550

    # 10순위: 키워드가 검색어로 시작
    if any(keyword.startswith(clean_keyword) for keyword in keywords):
        return 500

    # 11순위: 공백 제거 키워드가 검색어로 시작
    if any(keyword.startswith(compact_keyword) for keyword in compact_keywords):
        return 450

    # 12순위: 회사명 안에 포함
    if clean_keyword in company:
        return 400

    # 13순위: 공백 제거 회사명 안에 포함
    if compact_keyword in compact_company:
        return 350

    # 14순위: 키워드 안에 포함
    if any(clean_keyword in keyword for keyword in keywords):
        return 300

    # 15순위: 공백 제거 키워드 안에 포함
    if any(compact_keyword in keyword for keyword in compact_keywords):
        return 250

    # 16순위: 기존처럼 반대 포함도 허용
    searchable_values = [
        ticker,
        company,
        exchange,
        *keywords,
    ]

    if any(value and value in clean_keyword for value in searchable_values):
        return 200

    return 0


def get_stock_options(limit=30):
    master_items = load_json_list(STOCK_MASTER_PATH)
    cache_items = load_json_list(STOCK_CACHE_PATH)

    results = dedupe_stock_results([
        *master_items,
        *cache_items,
    ])

    return results[:limit]


def search_json_stocks(keyword, limit=20):
    clean_keyword = normalize_text(keyword)

    if not clean_keyword:
        return []

    master_items = load_json_list(STOCK_MASTER_PATH)
    cache_items = load_json_list(STOCK_CACHE_PATH)

    all_items = dedupe_stock_results([
        *master_items,
        *cache_items,
    ])

    scored_matches = []

    for item in all_items:
        score = get_match_score(item, clean_keyword)

        if score > 0:
            scored_matches.append((score, item))

    scored_matches.sort(
        key=lambda pair: (
            -pair[0],
            normalize_text(pair[1].get("company")),
            normalize_text(pair[1].get("ticker")),
        )
    )

    return [
        item
        for _, item in scored_matches[:limit]
    ]


def save_stock_to_cache(stock):
    normalized_stock = normalize_stock_item(stock)

    if not normalized_stock:
        return False

    with cache_lock:
        cache_items = load_json_list(STOCK_CACHE_PATH)
        normalized_cache_items = dedupe_stock_results(cache_items)

        existing_keys = {
            make_dedupe_key(item)
            for item in normalized_cache_items
        }

        new_key = make_dedupe_key(normalized_stock)

        if new_key in existing_keys:
            return False

        normalized_cache_items.append(normalized_stock)
        save_json_list(STOCK_CACHE_PATH, normalized_cache_items)

    return True