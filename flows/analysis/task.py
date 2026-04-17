from crewai import Task

class AnalysisTask:
    def report_writing_task(self, agent, company_name, financial_context, context_tasks):
        return Task(
            description=f'''
            리서처가 수집한 최신 뉴스 데이터와 다음 재무 데이터를 결합하여 심층 분석하세요.
            [재무 데이터]: {financial_context}
            
            단순한 정보 나열을 넘어, 거시경제적 상황(금리 등)과 결합하여 {company_name}의 단기 주가 방향성과 투자 심리를 예측하세요.
            ''',
            # 💡 expected_output에 구체적인 목차를 지정해 주면, 에이전트가 이 양식에 맞춰 빈칸을 채우듯 완벽한 리포트를 써냅니다.
            expected_output=f'''
            반드시 아래 구조를 갖춘 {company_name} 마크다운 투자 리포트:
            
            # 📈 {company_name} 종합 투자 전략 리포트
            ## 1. 📊 재무 펀더멘털 요약 (회계 데이터 기반)
            ## 2. 📰 시장 모멘텀 및 뉴스 센티먼트 요약
            ## 3. 🎯 단기 주가 방향성 예측
            ## 4. 💡 시니어 전략가의 최종 의견 (Buy / Hold / Sell 및 사유)
            ''',
            agent=agent,
            context=context_tasks
        )