import yfinance as yf
from crewai.tools import tool

@tool("Fetch Macro Economy API")
def fetch_macro_data(query: str = "macro") -> str:
    """
    글로벌 거시경제 지표(환율, 나스닥, 금리, VIX 공포지수, 유가)의 현재 값과 1개월 추세를 가져옵니다.
    동적 임계치(통계적 이상치)를 활용하여 비정상적인 급등락을 스스로 감지합니다.
    """
    try:
        # 💡 [핵심] 과거 6개월 데이터를 가져와서 통계적으로 비정상(급등/급락)인지 스스로 판단하는 함수
        def get_dynamic_trend(ticker, name, is_reverse_risk=False):
            # is_reverse_risk: 나스닥처럼 '빠지는 게' 위험한 경우 True, 환율/유가처럼 '오르는 게' 위험한 경우 False
            hist = yf.Ticker(ticker).history(period="6mo")
            if len(hist) < 60:
                return f"- {name}: 데이터 부족", False, ""

            current = hist['Close'].iloc[-1]
            past_1mo = hist['Close'].iloc[-21]  # 약 1개월 전 영업일
            change_pct = ((current - past_1mo) / past_1mo) * 100

            # 최근 60일(약 3개월) 이동평균과 표준편차 계산
            recent_60d = hist['Close'].tail(60)
            mean = recent_60d.mean()
            std = recent_60d.std()

            is_danger = False
            warning_msg = ""
            
            # 통계적 이상치 판별 (Z-Score > 2 : 상위 2% 이내의 극단적 변동)
            if not is_reverse_risk:
                # 환율, 국채 금리, 유가, VIX: 오르면 악재
                if current > mean + (2 * std):
                    is_danger = True
                    warning_msg = f"🚨 [{name} 급등 경고] 최근 60일 평균({round(mean, 2)}) 대비 통계적으로 비정상적인 급등 구간입니다. 외국인 수급 이탈 및 원가 부담 리스크가 매우 큽니다."
            else:
                # 나스닥: 내리면 악재
                if current < mean - (2 * std):
                    is_danger = True
                    warning_msg = f"🚨 [{name} 급락 경고] 최근 60일 평균({round(mean, 2)}) 대비 통계적으로 비정상적인 급락 구간입니다. 글로벌 기술주 투심 악화 리스크가 큽니다."

            sign = "+" if change_pct > 0 else ""
            trend = f"{sign}{round(change_pct, 2)}%"
            formatted_str = f"- {name}: 현재 {round(current, 2)} (1개월 전 대비 {trend})"
            
            return formatted_str, is_danger, warning_msg

        # 각 지표 수집 (동적 임계치 평가 포함)
        krw_str, _, krw_warn = get_dynamic_trend("KRW=X", "원/달러 환율")
        nasdaq_str, _, nasdaq_warn = get_dynamic_trend("^IXIC", "미국 나스닥 지수", is_reverse_risk=True)
        tnx_str, _, tnx_warn = get_dynamic_trend("^TNX", "미국 10년물 국채 금리")
        wti_str, _, wti_warn = get_dynamic_trend("CL=F", "WTI 국제 원유 가격")
        vix_str, _, vix_warn = get_dynamic_trend("^VIX", "VIX 지수")

        # --- 🚨 통계적 위험 감지 문구 취합 ---
        warning_hints = [warn for warn in [krw_warn, nasdaq_warn, tnx_warn, wti_warn, vix_warn] if warn]

        if warning_hints:
            alert_section = "\n        ".join(warning_hints)
            market_status = f"🔴 [시장 리스크 발동 - 리포트 상단 경고 배치 필수]\n        최근 매크로 지표가 통계적 정상 범위를 이탈했습니다. 수급 이탈 및 마진 악화 우려를 반영하여 '보수적인 투자 의견'을 강력히 고려하세요.\n        {alert_section}"
        else:
            market_status = "🟢 [시장 안정기] 현재 모든 주요 매크로 지표가 통계적 정상 범위(최근 60일 평균 내)에 머물고 있습니다. 종목 자체의 펀더멘털 분석에 집중하세요."

        return f"""
        [글로벌 거시경제(Macro) 지표 및 1개월 추세]
        {krw_str}
        {nasdaq_str}
        {tnx_str}
        {wti_str}
        {vix_str}

        💡 [시스템 주입 힌트: 수석 애널리스트는 아래 내용을 최종 리포트의 거시경제 파트에 반드시 반영할 것]
        {market_status}
        """
    except Exception as e:
        return f"매크로 데이터를 가져오는 중 에러 발생: {str(e)}"