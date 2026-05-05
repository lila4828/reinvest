import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta
from rebuild_stock_master import rebuild_stock_master

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(exist_ok=True)

STOCK_MASTER_KR_PATH = DATA_DIR / "stock_master_kr.json"

API_KEY = os.getenv("DATA_GO_KR_API_KEY")

API_URL = "https://apis.data.go.kr/1160100/service/GetKrxListedInfoService/getItemInfo"

def get_recent_business_dates(days=10):
    today = datetime.now()

    dates = []

    for i in range(days):
        target = today - timedelta(days=i)

        # 주말 제외
        if target.weekday() >= 5:
            continue

        dates.append(target.strftime("%Y%m%d"))

    return dates


def market_to_yahoo_suffix(market):
    if market == "KOSPI":
        return ".KS"

    if market == "KOSDAQ":
        return ".KQ"

    return None


def fetch_krx_items(base_date):
    params = {
        "serviceKey": API_KEY,
        "resultType": "json",
        "numOfRows": 5000,
        "pageNo": 1,
        "basDt": base_date,
    }

    response = requests.get(API_URL, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()

    items = (
        data.get("response", {})
        .get("body", {})
        .get("items", {})
        .get("item", [])
    )

    if isinstance(items, dict):
        items = [items]

    return items


def convert_to_stock_master(items):
    results = []

    seen = set()

    for item in items:
        code = str(item.get("srtnCd", "")).strip()
        name = str(item.get("itmsNm", "")).strip()
        company = str(item.get("corpNm", "")).strip() or name
        market = str(item.get("mrktCtg", "")).strip()

        suffix = market_to_yahoo_suffix(market)

        if not code or not name or not suffix:
            continue

        ticker = f"{code}{suffix}"

        if ticker in seen:
            continue

        seen.add(ticker)

        results.append({
            "ticker": ticker,
            "company": name,
            "exchange": market,
            "quote_type": "EQUITY",
            "keywords": [
                code,
                ticker,
                name,
                company,
                market,
            ],
        })

    return results

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


def main():
    if not API_KEY:
        raise RuntimeError("DATA_GO_KR_API_KEY가 .env에 없습니다.")

    for base_date in get_recent_business_dates(days=10):
        print(f"KRX 상장종목 조회 중: {base_date}")

        items = fetch_krx_items(base_date)

        if not items:
            print(f"{base_date}: 데이터 없음")
            continue

        stocks = convert_to_stock_master(items)

        if not stocks:
            print(f"{base_date}: 변환 가능한 종목 없음")
            continue

        save_json_list(STOCK_MASTER_KR_PATH, stocks)

        print(f"국장 종목 저장 완료: {len(stocks)}개")
        print(f"저장 위치: {STOCK_MASTER_KR_PATH}")

        rebuild_stock_master()

        return
    
    raise RuntimeError("최근 영업일 기준으로도 KRX 종목 데이터를 찾지 못했습니다.")


if __name__ == "__main__":
    main()