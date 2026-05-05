import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

STOCK_MASTER_KR_PATH = DATA_DIR / "stock_master_kr.json"
STOCK_MASTER_US_PATH = DATA_DIR / "stock_master_us.json"
STOCK_ALIAS_KO_PATH = DATA_DIR / "stock_alias_ko.json"
STOCK_CACHE_PATH = DATA_DIR / "stock_search_cache.json"

HANGUL_PATTERN = re.compile(r"[가-힣]")


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


def load_json_dict(file_path: Path):
    if not file_path.exists():
        return {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data

        return {}

    except json.JSONDecodeError:
        return {}


def save_json_dict(file_path: Path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def has_hangul(value):
    return bool(HANGUL_PATTERN.search(str(value or "")))


def normalize_text(value):
    return str(value or "").strip()


def normalize_ticker(ticker):
    return str(ticker or "").strip().upper()


def merge_unique(existing_values, new_values):
    merged = []

    for value in [*existing_values, *new_values]:
        text = normalize_text(value)

        if not text:
            continue

        if text not in merged:
            merged.append(text)

    return merged


def build_master_ticker_set():
    kr_items = load_json_list(STOCK_MASTER_KR_PATH)
    us_items = load_json_list(STOCK_MASTER_US_PATH)

    tickers = set()

    for item in [*kr_items, *us_items]:
        ticker = normalize_ticker(item.get("ticker"))

        if ticker:
            tickers.add(ticker)

    return tickers


def extract_hangul_keywords(item):
    candidates = []

    company = item.get("company")
    keywords = item.get("keywords", [])

    if has_hangul(company):
        candidates.append(company)

    if isinstance(keywords, list):
        for keyword in keywords:
            if has_hangul(keyword):
                candidates.append(keyword)

    return merge_unique([], candidates)


def suggest_aliases():
    cache_items = load_json_list(STOCK_CACHE_PATH)
    existing_aliases = load_json_dict(STOCK_ALIAS_KO_PATH)
    master_tickers = build_master_ticker_set()

    suggestions = {}

    for item in cache_items:
        ticker = normalize_ticker(item.get("ticker"))

        if not ticker:
            continue

        # master에 없는 종목이면 아직 공식 종목 DB와 매칭 불확실
        if ticker not in master_tickers:
            continue

        hangul_keywords = extract_hangul_keywords(item)

        if not hangul_keywords:
            continue

        existing_values = existing_aliases.get(ticker, [])

        new_keywords = [
            keyword
            for keyword in hangul_keywords
            if keyword not in existing_values
        ]

        if not new_keywords:
            continue

        suggestions[ticker] = merge_unique(
            suggestions.get(ticker, []),
            new_keywords,
        )

    return suggestions


def print_suggestions(suggestions):
    if not suggestions:
        print("추가할 별칭 후보가 없습니다.")
        return

    print("아래 내용을 stock_alias_ko.json에 추가 후보로 검토하세요.")
    print()

    print(json.dumps(suggestions, ensure_ascii=False, indent=2))


def apply_suggestions(suggestions):
    if not suggestions:
        print("적용할 별칭 후보가 없습니다.")
        return

    aliases = load_json_dict(STOCK_ALIAS_KO_PATH)

    for ticker, suggested_keywords in suggestions.items():
        aliases[ticker] = merge_unique(
            aliases.get(ticker, []),
            suggested_keywords,
        )

    save_json_dict(STOCK_ALIAS_KO_PATH, aliases)

    print(f"stock_alias_ko.json 업데이트 완료: {len(suggestions)}개 티커")


def main():
    suggestions = suggest_aliases()

    print_suggestions(suggestions)

    # 자동 적용하고 싶을 때만 아래 주석 해제
    # apply_suggestions(suggestions)


if __name__ == "__main__":
    main()