import yfinance as yf
from crewai.tools import tool

@tool("Fetch Financial Data API")
def fetch_financial_data(ticker: str) -> str:
    """
    야후 파이낸스를 사용하여 핵심 재무 데이터, 시장 가치, 산업군, 배당, 장기 이동평균선을 가져옵니다.
    """
    try:
        stock = yf.Ticker(ticker)
        
        # [신규 상장 필터링] 999일 이평선을 위해 5년치 주가 데이터 확보
        hist = stock.history(period="5y")
        if len(hist) < 200:
            return f"[{ticker} 치명적 결함] 상장된 지 1년이 되지 않은 신규 상장 기업입니다. 데이터 부족으로 분석 불가."

        info = stock.info
        financials = stock.financials
        cashflow = stock.cashflow
        
        result = {}

        # 1. 기업 실시간 가치 및 [섹터/산업군]
        result["sector"] = info.get('sector', 'N/A')
        result["industry"] = info.get('industry', 'N/A')
        
        current_price = info.get('currentPrice')
        result["current_price"] = current_price if current_price else 'N/A'
        result["forward_pe"] = info.get('forwardPE', 'N/A')
        
        # 💡 [PBR 직접 계산 로직] API 누락 방어
        pbr = info.get('priceToBook')
        if not pbr or pbr == "N/A":
            book_value = info.get('bookValue')
            if current_price and book_value and book_value > 0:
                pbr = round(current_price / book_value, 2)
            else:
                pbr = 'N/A'
        result["price_to_book"] = pbr
        
        # 2. [주주 환원 - 배당 수익률 버그 방어]
        div_yield = info.get('dividendYield', 'N/A')
        if isinstance(div_yield, (int, float)):
            if div_yield > 1: # 이미 퍼센트이거나 오류값인 경우
                result["dividend_yield"] = f"{round(div_yield, 2)}%"
            else:
                result["dividend_yield"] = f"{round(div_yield * 100, 2)}%"
        else:
            result["dividend_yield"] = "N/A (배당 없음)"

        # 3. [초장기 이동평균선 계산]
        result["ma_60"] = round(hist['Close'].rolling(window=60).mean().iloc[-1], 2) if len(hist) >= 60 else "N/A"
        result["ma_200"] = round(hist['Close'].rolling(window=200).mean().iloc[-1], 2) if len(hist) >= 200 else "N/A"
        result["ma_350"] = round(hist['Close'].rolling(window=350).mean().iloc[-1], 2) if len(hist) >= 350 else "N/A"
        result["ma_500"] = round(hist['Close'].rolling(window=500).mean().iloc[-1], 2) if len(hist) >= 500 else "N/A"
        result["ma_999"] = round(hist['Close'].rolling(window=999).mean().iloc[-1], 2) if len(hist) >= 999 else "N/A"

        # 4. 재무 및 마진 지표
        result["operating_margin"] = info.get('operatingMargins', 'N/A')
        result["debt_to_equity"] = info.get('debtToEquity', 'N/A') 

        # 💡 [데이터 분리] 계산용 숫자 배열 헬퍼 함수
        def get_raw_last_3_years(df, row_name):
            if df is not None and row_name in df.index:
                return [int(val) if val == val else "N/A" for val in df.loc[row_name].head(3).tolist()]
            return ["N/A", "N/A", "N/A"]
        
        # 💡 [LLM 전달용] AI가 헷갈리지 않게 글자로 풀어주는 헬퍼 함수
        def format_to_text(vals):
            if len(vals) == 3 and all(isinstance(x, int) for x in vals):
                return f"(최근) {vals[0]:,} -> (1년전) {vals[1]:,} -> (2년전) {vals[2]:,}"
            return str(vals)

        raw_ni = get_raw_last_3_years(financials, 'Net Income')
        raw_rev = get_raw_last_3_years(financials, 'Total Revenue')
        raw_fcf = get_raw_last_3_years(cashflow, 'Free Cash Flow')

        # [파이썬의 철퇴] 순이익 패턴 판별 로직 (원래 질문자님 로직 적용!)
        try:
            # 원본 [최근, 1년전, 2년전] 배열을 인간의 시간순서인 [2년전, 1년전, 최근]으로 뒤집음
            chronological_ni = list(reversed(raw_ni)) 
            signs = ['+' if isinstance(x, (int, float)) and x > 0 else '-' for x in chronological_ni]
            pattern = "".join(signs)

            if pattern in ["---", "+--"]:
                deficit_status = f"[{pattern}] FAIL 대상 (만성 또는 연속 적자)"
            elif pattern == "-+-":
                deficit_status = f"[{pattern}] WARNING 대상 (퐁당퐁당 불안정)"
            elif pattern == "++-":
                 deficit_status = f"[{pattern}] PASS 대상 (최근 1년 일시적 적자)"
            else: 
                deficit_status = f"[{pattern}] PASS 대상 (흑자 유지 또는 턴어라운드)"
        except:
            deficit_status = "데이터 오류 (FAIL 대상)"

        try:
            debt_val = float(result["debt_to_equity"])
            debt_status = "FAIL 대상 (100% 초과)" if debt_val > 100 else "PASS (100% 이하)"
        except:
            debt_status = "PASS (데이터 없음)"

        return f"""
        [{ticker} 심층 재무 및 시장 가치 검증 데이터]
        - 산업군(Sector/Industry): {result['sector']} / {result['industry']}
        - 상장 기간: 1년 이상 (검증 완료)
        🚨 [사전 채점 1] 순이익 3년 트렌드: {deficit_status}
        🚨 [사전 채점 2] 부채비율 위험 여부: {debt_status}

        [실시간 가치 및 주주환원]
        - 현재 실시간 주가: {result['current_price']}
        - PER: {result['forward_pe']} / PBR: {result['price_to_book']}
        - 배당 수익률 (0.1점 가산점 부여용): {result['dividend_yield']}

        [장기 이동평균선 (장기 추세 확인용)]
        - MA60: {result['ma_60']} / MA200: {result['ma_200']}
        - MA350: {result['ma_350']} / MA500: {result['ma_500']} / MA999: {result['ma_999']}

        [재무제표 원본 (시간순서 유의)]
        - 영업 이익률: {result['operating_margin']}
        - 부채 비율: {result['debt_to_equity']}
        - 순이익: {format_to_text(raw_ni)}
        - 매출: {format_to_text(raw_rev)}
        - FCF: {format_to_text(raw_fcf)}
        """

    except Exception as e:
        return f"데이터를 가져오는 중 에러 발생: {str(e)}"