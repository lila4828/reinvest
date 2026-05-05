import csv
import json
import requests
from io import StringIO
from pathlib import Path
from rebuild_stock_master import rebuild_stock_master

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(exist_ok=True)

STOCK_MASTER_US_PATH = DATA_DIR / "stock_master_us.json"


NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"


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


def normalize_company_name(name):
    company = str(name or "").strip()

    remove_phrases = [
        " - Common Stock",
        " - Class A Common Stock",
        " - Class B Common Stock",
        " - Class C Capital Stock",
        " - Ordinary Shares",
        " Common Stock",
        " Class A Common Stock",
        " Class B Common Stock",
        " Class C Capital Stock",
    ]

    for phrase in remove_phrases:
        company = company.replace(phrase, "")

    return company.strip()


def is_valid_symbol(symbol):
    symbol = str(symbol or "").strip()

    if not symbol:
        return False

    # Nasdaq Trader 마지막 줄 File Creation Time 제거
    if symbol.lower().startswith("file creation time"):
        return False

    # 테스트 종목 제거용
    if symbol.endswith("Z"):
        # Z가 들어간 정상 종목도 있을 수 있으니 완전 배제는 위험하지만,
        # 아래 Test Issue 필터가 우선이라 여기서는 크게 의존하지 않음
        return True

    return True


def normalize_us_symbol(symbol):
    symbol = str(symbol or "").strip().upper()

    # Nasdaq Trader는 BRK.A 같은 종목을 BRK.A 형태로 줄 수 있음
    # yfinance는 보통 BRK-A 형태를 사용
    return symbol.replace(".", "-")


def convert_nasdaq_market_category(category):
    category = str(category or "").strip().upper()

    if category == "Q":
        return "NASDAQ Global Select"
    if category == "G":
        return "NASDAQ Global Market"
    if category == "S":
        return "NASDAQ Capital Market"

    return "NASDAQ"


def convert_other_exchange(exchange):
    exchange = str(exchange or "").strip().upper()

    if exchange == "N":
        return "NYSE"
    if exchange == "A":
        return "NYSE American"
    if exchange == "P":
        return "NYSE Arca"
    if exchange == "Z":
        return "Cboe BZX"
    if exchange == "V":
        return "IEXG"

    return exchange or "US"


def fetch_text(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def parse_pipe_text(text):
    f = StringIO(text)
    reader = csv.DictReader(f, delimiter="|")

    rows = []

    for row in reader:
        # 마지막 File Creation Time 라인 방어
        first_value = next(iter(row.values()), "")

        if isinstance(first_value, str) and first_value.lower().startswith("file creation time"):
            continue

        rows.append(row)

    return rows


def convert_nasdaq_listed(rows):
    results = []

    for row in rows:
        symbol = row.get("Symbol", "")
        security_name = row.get("Security Name", "")
        market_category = row.get("Market Category", "")
        test_issue = row.get("Test Issue", "")
        etf = row.get("ETF", "")

        if not is_valid_symbol(symbol):
            continue

        if str(test_issue).strip().upper() == "Y":
            continue

        # 일단 ETF는 제외. 나중에 ETF 검색까지 넣고 싶으면 이 조건 제거
        if str(etf).strip().upper() == "Y":
            continue

        ticker = normalize_us_symbol(symbol)
        company = normalize_company_name(security_name)
        exchange = convert_nasdaq_market_category(market_category)

        if not ticker or not company:
            continue

        results.append({
            "ticker": ticker,
            "company": company,
            "exchange": exchange,
            "quote_type": "EQUITY",
            "keywords": [
                ticker,
                symbol,
                company,
                "NASDAQ",
                exchange,
            ],
        })

    return results


def convert_other_listed(rows):
    results = []

    for row in rows:
        symbol = row.get("ACT Symbol", "")
        security_name = row.get("Security Name", "")
        exchange_code = row.get("Exchange", "")
        test_issue = row.get("Test Issue", "")
        etf = row.get("ETF", "")

        if not is_valid_symbol(symbol):
            continue

        if str(test_issue).strip().upper() == "Y":
            continue

        # 일단 ETF는 제외. 나중에 ETF 검색까지 넣고 싶으면 이 조건 제거
        if str(etf).strip().upper() == "Y":
            continue

        ticker = normalize_us_symbol(symbol)
        company = normalize_company_name(security_name)
        exchange = convert_other_exchange(exchange_code)

        if not ticker or not company:
            continue

        results.append({
            "ticker": ticker,
            "company": company,
            "exchange": exchange,
            "quote_type": "EQUITY",
            "keywords": [
                ticker,
                symbol,
                company,
                exchange,
            ],
        })

    return results


def dedupe_us_stocks(items):
    seen = set()
    results = []

    for item in items:
        ticker = str(item.get("ticker", "")).strip().upper()
        exchange = str(item.get("exchange", "")).strip().upper()

        if not ticker:
            continue

        key = f"{exchange}:{ticker}"

        if key in seen:
            continue

        seen.add(key)
        results.append(item)

    return results

def main():
    print("NASDAQ 상장종목 조회 중...")
    nasdaq_text = fetch_text(NASDAQ_LISTED_URL)
    nasdaq_rows = parse_pipe_text(nasdaq_text)
    nasdaq_stocks = convert_nasdaq_listed(nasdaq_rows)

    print(f"NASDAQ 변환 완료: {len(nasdaq_stocks)}개")

    print("NYSE/AMEX/기타 상장종목 조회 중...")
    other_text = fetch_text(OTHER_LISTED_URL)
    other_rows = parse_pipe_text(other_text)
    other_stocks = convert_other_listed(other_rows)

    print(f"기타 거래소 변환 완료: {len(other_stocks)}개")

    us_stocks = dedupe_us_stocks([
        *nasdaq_stocks,
        *other_stocks,
    ])

    save_json_list(STOCK_MASTER_US_PATH, us_stocks)

    print(f"미국 종목 저장 완료: {len(us_stocks)}개")
    print(f"저장 위치: {STOCK_MASTER_US_PATH}")

    rebuild_stock_master()


if __name__ == "__main__":
    main()