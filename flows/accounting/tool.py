import yfinance as yf
from crewai.tools import tool

@tool("Fetch Financial Data API")
def fetch_financial_data(ticker: str) -> str:
    """
    야후 파이낸스(yfinance)를 사용하여 특정 주식의 핵심 재무 데이터,
    최근 3개년 당기순이익, 매출액, R&D 비용, 현금흐름을 가져옵니다.
    전달받은 종목코드(ticker)를 별도의 수정 없이 그대로 사용하여 검색합니다.
    """
    try:
        # yfinance 객체 생성
        stock = yf.Ticker(ticker)
        info = stock.info
        financials = stock.financials
        cashflow = stock.cashflow
        
        result = {}

        # 1. Operating Margin & Debt to Equity
        result["operating_margin"] = info.get('operatingMargins', 'N/A')
        # yfinance의 debtToEquity는 보통 백분율(%) 형태가 아닌 비율로 들어옵니다. (예: 100% = 100)
        result["debt_to_equity"] = info.get('debtToEquity', 'N/A') 

        # [헬퍼 함수] DataFrame에서 최근 3년치 데이터를 리스트로 추출
        def get_last_3_years(df, row_name):
            if df is not None and row_name in df.index:
                # 결측치(NaN) 방어 로직 포함
                return [int(val) if val == val else "N/A" for val in df.loc[row_name].head(3).tolist()]
            return ["N/A", "N/A", "N/A"]

        # 2. 3년치 리스트 데이터 추출
        result["net_income"] = get_last_3_years(financials, 'Net Income')
        result["revenue"] = get_last_3_years(financials, 'Total Revenue')
        result["rnd"] = get_last_3_years(financials, 'Research And Development')
        result["fcf"] = get_last_3_years(cashflow, 'Free Cash Flow')

        # 에이전트에게 전달할 최종 페이로드 포맷팅
        return f"""
        [{ticker} 심층 재무 및 성장성 검증 데이터]
        - 영업 이익률: {result['operating_margin']}
        - 부채 비율: {result['debt_to_equity']}
        - 순이익(최근 3년): {result['net_income']}
        - 매출(최근 3년): {result['revenue']}
        - R&D(최근 3년): {result['rnd']}
        - FCF(최근 3년): {result['fcf']}
        """

    except Exception as e:
        return f"데이터를 가져오는 중 에러 발생: {str(e)}"