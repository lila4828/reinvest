from crewai import Agent
from .tool import fetch_financial_data

class AccountingAgent:
    def __init__(self, llm):
        self.llm = llm

    def financial_analyst(self):
        return Agent(
            role='기술 가치 투자 애널리스트',
            goal='기업의 재무 안정성, R&D 투자 효율성, 그리고 실제 현금 창출력을 종합 분석하여 투자 적격성을 판정합니다.',
            backstory='''당신은 워런 버핏의 '안정성'과 하이테크 기업의 '성장성'을 동시에 분석하는 전문가입니다. 
            장부상 이익뿐만 아니라 R&D 비용이 미래 수익으로 이어지는지, 잉여현금흐름(FCF)이 탄탄하여 
            위기 상황에서도 살아남을 수 있는 기업인지를 판단하는 데 탁월한 능력을 갖추고 있습니다.''',
            verbose=True,
            tools=[fetch_financial_data],
            llm=self.llm
        )