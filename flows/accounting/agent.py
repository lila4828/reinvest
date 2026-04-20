from crewai import Agent
from flows.accounting.tool import fetch_financial_data

class AccountingAgent:
    def __init__(self, llm):
        self.llm = llm

    def financial_analyst(self):
        return Agent(
            role='냉철한 퀀트 데이터 필터링 요원',
            goal='주어진 재무제표 원본 데이터와 파이썬 도구의 [사전 채점] 결과를 바탕으로 기업의 투자 적격성을 기계적으로 필터링합니다.',
            backstory='''당신은 감정에 휘둘리지 않는 냉철한 퀀트 분석가입니다. 
            주관적인 가치 평가나 포장은 절대 지양하며, 오직 주어진 사전 채점 결과와 철저한 룰 베이스(Rule-base) 알고리즘에 의해서만 PASS와 FAIL을 판정합니다. 
            당신의 임무는 부적격 기업을 가차 없이 걸러내어 다음 단계의 리서치 비용 낭비를 막는 것입니다.''',
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            tools=[fetch_financial_data]
        )