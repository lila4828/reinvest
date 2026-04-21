import yfinance as yf
from crewai.tools import tool

@tool("Fetch Macro Economy API")
def fetch_macro_data(query: str = "macro") -> str:
    """
    글로벌 거시경제 지표(환율, 나스닥, 금리, VIX 공포지수, 유가)의 현재 값과 1개월 추세를 가져옵니다.
    """
    try:
        # 💡 [헬퍼 함수] 1개월 전 데이터와 비교하여 추세(%) 계산
        def get_macro_trend(ticker, name):
            hist = yf.Ticker(ticker).history(period="1mo")
            if len(hist) < 2:
                return f"- {name}: 데이터 부족"
            
            current = hist['Close'].iloc[-1]
            past = hist['Close'].iloc[0]
            change_pct = ((current - past) / past) * 100
            
            sign = "+" if change_pct > 0 else ""
            trend = f"{sign}{round(change_pct, 2)}%"
            
            return f"- {name}: 현재 {round(current, 2)} (1개월 전 대비 {trend})"

        # 각 지표 수집
        krw = get_macro_trend("KRW=X", "원/달러 환율")
        nasdaq = get_macro_trend("^IXIC", "미국 나스닥 지수")
        tnx = get_macro_trend("^TNX", "미국 10년물 국채 금리")
        wti = get_macro_trend("CL=F", "WTI 국제 원유 가격")
        
        # 💡 [VIX 특별 판정 로직] 공포 온도계
        vix_hist = yf.Ticker("^VIX").history(period="1d")
        vix_val = vix_hist['Close'].iloc[-1] if not vix_hist.empty else 0
        
        if vix_val >= 30:
            vix_status = f"{round(vix_val, 2)} 🚨 [극도의 공포장 - 글로벌 위험자산 투매 주의]"
        elif vix_val >= 20:
            vix_status = f"{round(vix_val, 2)} ⚠️ [불안정장 - 외국인 수급 이탈 보수적 접근]"
        else:
            vix_status = f"{round(vix_val, 2)} ✅ [안정장 - 투자 심리 양호]"

        return f"""
        [글로벌 거시경제(Macro) 지표 및 1개월 추세]
        {krw}
        {nasdaq}
        {tnx}
        {wti}
        
        [글로벌 투자 심리 (공포 지수)]
        - VIX 지수: {vix_status}
        """
    except Exception as e:
        return f"매크로 데이터를 가져오는 중 에러 발생: {str(e)}"