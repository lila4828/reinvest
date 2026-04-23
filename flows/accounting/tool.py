import yfinance as yf
from crewai.tools import tool

@tool("Fetch Financial Data API")
def fetch_financial_data(ticker: str) -> str:
    """
    야후 파이낸스를 사용하여 핵심 재무 데이터, 시장 가치, ROE, 성장률(YoY), 3대 현금흐름 패턴 등을 가져옵니다.
    """
    try:
        stock = yf.Ticker(ticker)
        
        hist = stock.history(period="5y")
        if len(hist) < 252:
            return f"[{ticker} 치명적 결함] 상장된 지 1년이 되지 않은 신규 상장 기업입니다. 데이터 부족으로 분석 불가."

        info = stock.info
        financials = stock.financials
        cashflow = stock.cashflow
        
        result = {}

        result["sector"] = info.get('sector', 'N/A')
        result["industry"] = info.get('industry', 'N/A')
        
        current_price = info.get('currentPrice')
        result["current_price"] = current_price if current_price else 'N/A'
        result["forward_pe"] = info.get('forwardPE', 'N/A')
        
        # 💡 [PBR 직접 계산 로직 보강]
        pbr = info.get('priceToBook')
        if not pbr or pbr == "N/A" or pbr == 0:
            # 주가와 주당순자산(bookValue)으로 직접 계산 시도
            bv = info.get('bookValue')
            cp = info.get('currentPrice')
            if cp and bv and bv > 0:
                pbr = round(cp / bv, 2)
            else:
                # 이것도 안되면 최근 재무제표 자산 데이터로 시도 (자본총계 = 총자산 - 총부채)
                try:
                    total_assets = financials.loc['Total Assets'].iloc[0]
                    total_liab = financials.loc['Total Liabilities Net Minority Interest'].iloc[0]
                    shares = info.get('sharesOutstanding')
                    if total_assets and total_liab and shares:
                        equity = total_assets - total_liab
                        bps = equity / shares
                        pbr = round(cp / bps, 2)
                    else:
                        pbr = "N/A"
                except:
                    pbr = "N/A"
        result["price_to_book"] = pbr
        
        # [배당 수익률]
        div_yield = info.get('dividendYield', 'N/A')
        if isinstance(div_yield, (int, float)):
            result["dividend_yield"] = f"{round(div_yield * 100, 2)}%" if div_yield < 1 else f"{round(div_yield, 2)}%"
        else:
            result["dividend_yield"] = "N/A (배당 없음)"

        # [ROE (자기자본이익률) 추출 및 워런 버핏 프리미엄 판별]
        roe = info.get('returnOnEquity', 'N/A')
        if isinstance(roe, (int, float)):
            roe_percent = round(roe * 100, 2)
            roe_status = f"{roe_percent}% (🔥 워런 버핏 우량주 프리미엄: 15% 초과)" if roe_percent > 15 else f"{roe_percent}%"
            result["roe"] = roe_status
        else:
            result["roe"] = "N/A"

        result["ma_60"] = round(hist['Close'].rolling(window=60).mean().iloc[-1], 2) if len(hist) >= 60 else "N/A"
        result["ma_200"] = round(hist['Close'].rolling(window=200).mean().iloc[-1], 2) if len(hist) >= 200 else "N/A"
        result["ma_350"] = round(hist['Close'].rolling(window=350).mean().iloc[-1], 2) if len(hist) >= 350 else "N/A"
        result["ma_500"] = round(hist['Close'].rolling(window=500).mean().iloc[-1], 2) if len(hist) >= 500 else "N/A"
        result["ma_999"] = round(hist['Close'].rolling(window=999).mean().iloc[-1], 2) if len(hist) >= 999 else "N/A"

        result["operating_margin"] = info.get('operatingMargins', 'N/A')
        result["debt_to_equity"] = info.get('debtToEquity', 'N/A') 

        # --- 💡 [헬퍼 함수 모음] ---
        def get_raw_last_3_years(df, row_name):
            if df is not None and row_name in df.index:
                return [int(val) if val == val else "N/A" for val in df.loc[row_name].head(3).tolist()]
            return ["N/A", "N/A", "N/A"]
        
        def format_to_text(vals):
            if len(vals) == 3 and all(isinstance(x, int) for x in vals):
                return f"(최근) {vals[0]:,} -> (1년전) {vals[1]:,} -> (2년전) {vals[2]:,}"
            return str(vals)

        def calculate_yoy(recent, previous):
            if isinstance(recent, int) and isinstance(previous, int) and previous != 0:
                yoy = ((recent - previous) / abs(previous)) * 100
                sign = "+" if yoy > 0 else ""
                return f"{sign}{round(yoy, 2)}%"
            return "N/A"

        # 💡 [신규] 현금흐름 부호 판별기
        def get_cf_sign(df, row_name):
            if df is not None and row_name in df.index:
                try:
                    val = df.loc[row_name].head(1).values[0]
                    return "+" if val > 0 else "-"
                except:
                    pass
            return "?"

        raw_ni = get_raw_last_3_years(financials, 'Net Income')
        raw_rev = get_raw_last_3_years(financials, 'Total Revenue')
        raw_fcf = get_raw_last_3_years(cashflow, 'Free Cash Flow')

        # YoY 수치 계산
        rev_yoy = calculate_yoy(raw_rev[0], raw_rev[1]) if len(raw_rev) == 3 else "N/A"
        ni_yoy = calculate_yoy(raw_ni[0], raw_ni[1]) if len(raw_ni) == 3 else "N/A"

        # --- 🚨 [사전 채점 로직 모음] ---
        # 1. 순이익 트렌드
        try:
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

        # 2. 부채 비율
        try:
            debt_val = float(result["debt_to_equity"])
            debt_status = "FAIL 대상 (100% 초과)" if debt_val > 100 else "PASS (100% 이하)"
        except:
            debt_status = "PASS (데이터 없음)"

        # 3. 💡 [신규] 3대 현금흐름(OCF, ICF, FCF) 패턴
        ocf_s = get_cf_sign(cashflow, 'Operating Cash Flow')
        icf_s = get_cf_sign(cashflow, 'Investing Cash Flow')
        fcf_s = get_cf_sign(cashflow, 'Free Cash Flow')
        
        cf_pattern = f"({ocf_s}, {icf_s}, {fcf_s})"
        if cf_pattern == "(+, -, -)":
            cf_status = f"{cf_pattern} PASS (초우량: 본업 수익으로 투자와 채무상환/배당 진행)"
        elif ocf_s == "-":
            cf_status = f"{cf_pattern} WARNING 대상 (위험: 영업활동에서 현금 유출 발생)"
        elif icf_s == "+" and fcf_s == "+":
            cf_status = f"{cf_pattern} WARNING 대상 (주의: 자산 매각 또는 차입으로 연명 중)"
        else:
            cf_status = f"{cf_pattern} PASS (일반적 기업 흐름)"

        # --- 최종 문자열 반환 ---
        return f"""
        [{ticker} 심층 재무 및 시장 가치 검증 데이터]
        - 산업군(Sector/Industry): {result['sector']} / {result['industry']}
        - 상장 기간: 1년 이상 (검증 완료)
        🚨 [사전 채점 1] 순이익 3년 트렌드: {deficit_status}
        🚨 [사전 채점 2] 부채비율 위험 여부: {debt_status}
        🚨 [사전 채점 3] 현금흐름(영업,투자,잉여) 패턴: {cf_status}

        [실시간 가치, 주주환원, 자본 효율성]
        - 현재 주가: {result['current_price']}
        - PER: {result['forward_pe']} / PBR: {result['price_to_book']}
        - ROE (자기자본이익률): {result['roe']}
        - 배당 수익률 (가산점 부여용): {result['dividend_yield']}

        [단기 성장성 팩트 체크 (YoY)]
        - 최근 1년 매출 성장률 (YoY): {rev_yoy}
        - 최근 1년 순이익 성장률 (YoY): {ni_yoy}

        [장기 이동평균선 (MA)]
        - MA60: {result['ma_60']} / MA200: {result['ma_200']}
        - MA350: {result['ma_350']} / MA500: {result['ma_500']} / MA999: {result['ma_999']}

        [재무제표 원본 (시간순서 유의)]
        - 영업 이익률: {result['operating_margin']} / 부채 비율: {result['debt_to_equity']}
        - 순이익: {format_to_text(raw_ni)}
        - 매출: {format_to_text(raw_rev)}
        - FCF: {format_to_text(raw_fcf)}
        """

    except Exception as e:
        return f"데이터를 가져오는 중 에러 발생: {str(e)}"