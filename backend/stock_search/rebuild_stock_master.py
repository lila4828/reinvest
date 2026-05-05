import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(exist_ok=True)

STOCK_MASTER_KR_PATH = DATA_DIR / "stock_master_kr.json"
STOCK_MASTER_US_PATH = DATA_DIR / "stock_master_us.json"
STOCK_ALIAS_KO_PATH = DATA_DIR / "stock_alias_ko.json"
STOCK_MASTER_PATH = DATA_DIR / "stock_master.json"


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


def save_json_list(file_path: Path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def make_dedupe_key(item):
    ticker = str(item.get("ticker", "")).strip().upper()
    exchange = str(item.get("exchange", "")).strip().upper()

    if (
        exchange in ["KOSPI", "KOSDAQ"]
        or ticker.endswith(".KS")
        or ticker.endswith(".KQ")
    ):
        base_code = ticker.replace(".KS", "").replace(".KQ", "")
        return f"KR:{base_code}"

    if exchange:
        return f"{exchange}:{ticker}"

    return ticker


def merge_keywords(*keyword_groups):
    merged = []

    for group in keyword_groups:
        if not group:
            continue

        if not isinstance(group, list):
            group = [group]

        for keyword in group:
            text = str(keyword).strip()

            if text and text not in merged:
                merged.append(text)

    return merged


def apply_aliases(items, aliases):
    results = []

    for item in items:
        ticker = str(item.get("ticker", "")).strip().upper()
        current_keywords = item.get("keywords", [])

        alias_keywords = aliases.get(ticker, [])

        item["keywords"] = merge_keywords(
            current_keywords,
            alias_keywords,
        )

        results.append(item)

    return results


def dedupe_by_ticker(items):
    seen = set()
    results = []

    for item in items:
        ticker = str(item.get("ticker", "")).strip()

        if not ticker:
            continue

        key = make_dedupe_key(item)

        if key in seen:
            continue

        seen.add(key)
        results.append(item)

    return results


def rebuild_stock_master():
    kr_items = load_json_list(STOCK_MASTER_KR_PATH)
    us_items = load_json_list(STOCK_MASTER_US_PATH)
    aliases = load_json_dict(STOCK_ALIAS_KO_PATH)

    merged_items = dedupe_by_ticker([
        *kr_items,
        *us_items,
    ])

    merged_items = apply_aliases(merged_items, aliases)

    save_json_list(STOCK_MASTER_PATH, merged_items)

    print(f"KR 종목: {len(kr_items)}개")
    print(f"US 종목: {len(us_items)}개")
    print(f"별칭 적용: {len(aliases)}개 티커")
    print(f"통합 stock_master.json 생성 완료: {len(merged_items)}개")
    print(f"저장 위치: {STOCK_MASTER_PATH}")


if __name__ == "__main__":
    rebuild_stock_master()