from crewai import Task

class AnalysisTask:
    # 💡 [필수 수정] main.py와 맞춰서 macro_data 파라미터 추가!
    def report_writing_task(self, agent, company_name, accounting_data, macro_data, context_tasks):
        return Task(
            description=f'''
            리서처가 수집한 최신 뉴스 데이터와 아래 제공된 데이터를 결합하여 심층 분석하세요.
            
            [제공 데이터]
            1. 재무 및 퀀트 지표: {accounting_data}
            2. 글로벌 매크로 지표: {macro_data}
            
            [🚨 엄격한 작성 지침 및 주의사항]
            - **재무 데이터 해석 절대 주의:** 제공된 재무 데이터 리스트는 **맨 왼쪽이 가장 최신 연도**입니다. (예: [최신, 1년전, 2년전]). 만약 최신 숫자가 과거보다 작아졌거나 마이너스(-)라면 명백한 실적 '하락/악화'입니다. 절대 '성장/개선'이라고 거짓 포장하지 마세요!
            - 단순한 정보 나열을 넘어, 제공된 거시경제적 상황(환율/금리/나스닥)과 장기 이동평균선(MA60~999), 배당 수익률 등을 결합하여 {company_name}의 단기 주가 방향성과 투자 심리를 예측하세요.
            ''',
            # 💡 질문자님의 4단 구조 양식에 구체적인 작성 가이드를 살짝 첨가했습니다.
            expected_output=f'''
            반드시 아래 구조를 갖춘 {company_name} 마크다운 투자 리포트:
            
            # 📈 {company_name} 종합 투자 전략 리포트
            
            ## 1. 📊 재무 및 퀀트 펀더멘털 요약 (회계/차트 데이터 기반)
            - (매출/순이익/FCF 트렌드 팩트 체크)
            - (배당 수익률, 장기 이평선(MA60~999) 추세 등 요약)
            
            ## 2. 📰 시장 모멘텀 및 거시경제(Macro) 센티먼트
            - (최신 뉴스 핵심 요약)
            - (제공된 금리/환율 등 매크로 환경이 이 기업에 미치는 영향 분석)
            
            ## 3. 🎯 단기 주가 방향성 예측
            - (펀더멘털과 모멘텀을 종합한 주가 흐름 예측)
            
            ## 4. 💡 시니어 전략가의 최종 의견 (Buy / Hold / Sell 및 사유)
            - (명확한 포지션 제시 및 논리적 근거)
            ''',
            agent=agent,
            context=context_tasks
        )