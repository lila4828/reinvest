import yfinance as yf
from crewai.tools import tool

@tool("Fetch Macro Economy API")
def fetch_macro_data(query: str = "macro") -> str:
    """
    글로벌 거시경제 지표(원/달러 환율, 나스닥 지수, 미국 10년물 국채 금리)를 가져옵니다.
    """
    try:
        # 안전하게 최근 종가를 가져오는 헬퍼 함수
        def get_latest_price(ticker):
            hist = yf.Ticker(ticker).history(period="1d")
            return round(hist['Close'].iloc[-1], 2) if not hist.empty else "N/A"

        krw = get_latest_price("KRW=X")   # 원/달러 환율
        nasdaq = get_latest_price("^IXIC") # 나스닥 종합 지수
        tnx = get_latest_price("^TNX")    # 미국 10년물 국채 금리

        return f"""
        [현재 글로벌 거시경제(Macro) 지표]
        - 원/달러 환율 (KRW/USD): {krw} 원
        - 미국 나스닥 지수 (NASDAQ): {nasdaq} 포인트
        - 미국 10년물 국채 금리: {tnx}%
        """
    except Exception as e:
        return f"매크로 데이터를 가져오는 중 에러 발생: {str(e)}"