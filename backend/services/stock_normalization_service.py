def normalize_kr_ticker(ticker: str):
    ticker = str(ticker or "").strip().upper()

    if (
        len(ticker) == 10
        and ticker.startswith("A")
        and ticker[1:7].isalnum()
        and ticker[7:] in [".KS", ".KQ"]
    ):
        return ticker[1:]

    return ticker


def normalize_stock_pool(stock_pool):
    """
    외부 입력 종목 데이터를 main.py 내부 표준 형식으로 변환한다.
    표준 형식: [("TSLA", "Tesla"), ("005930.KS", "Samsung Electronics")]
    """

    default_stock_pool = [
        ("TSLA", "Tesla"),
        ("005930.KS", "Samsung Electronics"),
        ("000660.KS", "SK Hynix"),
    ]

    if stock_pool is None:
        return default_stock_pool

    if not isinstance(stock_pool, list) or not stock_pool:
        raise ValueError("stock_pool은 비어 있지 않은 list여야 합니다.")

    normalized = []

    for item in stock_pool:
        if isinstance(item, dict):
            ticker = item.get("ticker")
            company = item.get("company")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            ticker, company = item
        else:
            raise ValueError(f"잘못된 종목 입력 형식입니다: {item}")

        ticker = normalize_kr_ticker(ticker)
        company = str(company).strip() if company else ""

        if not ticker or not company:
            raise ValueError(f"ticker/company 값이 비어 있습니다: {item}")

        normalized.append((ticker, company))

    return normalized
