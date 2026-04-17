from crewai import Task

class AccountingTask:
    def analyze_financial_statements(self, agent, company_name, ticker):
        return Task(
            description=f'''
            'Fetch Financial Data API' 도구를 사용하여 {company_name}({ticker})의 최신 및 과거 3개년 데이터를 정밀 분석하세요.
            
            다음 [4대 핵심 투자 지표]를 기준으로 투자 적격 여부를 엄격히 판단하세요:

            1. **안정성 (Stability):** - 최근 3개년 당기순이익 중 단 한 번이라도 적자(음수)가 있는가? (있다면 탈락)
               - 부채비율(Debt to Equity)이 100% 이하인가? (초과 시 위험)
            
            2. **성장성 (Growth):** - 최근 3개년 매출액(Total Revenue)이 꾸준히 유지되거나 우상향하고 있는가?
            
            3. **미래 가치 (Future Readiness):** - R&D 투자 비용이 매년 유지되거나 늘어나고 있는가? (기술 경쟁력 확인)
            
            4. **현금 창출력 (Cash Flow):** - 잉여현금흐름(Free Cash Flow)이 양수(+)이며, 실제 사업을 통해 돈이 꾸준히 유입되고 있는가?

            [판단 로직]:
            - **안정성(1번)** 기준에 미달(적자 발생 혹은 고부채)하면 무조건 "FAIL"을 부여하고 분석을 즉시 중단하세요.
            - 안정성은 통과했으나 성장성이나 현금흐름이 불안정하다면 "PASS" 뒤에 (주의) 표시를 하고 사유를 적으세요.
            - 모든 기준이 우수하다면 "PASS"를 부여하고 각 지표의 요약을 작성하세요.
            ''',
            expected_output=f'{company_name}의 4대 지표 기반 심층 진단 결과 및 최종 PASS/FAIL 여부',
            agent=agent
        )