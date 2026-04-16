from crewai import Agent

class AccountingAgents:
    def __init__(self, llm):
        self.llm = llm

    def financial_analyst(self):
        return Agent(
            role='재무 제표 분석 전문가',
            goal='기업의 실적 발표문과 재무 상태표를 분석하여 수익성 및 재무 건전성을 진단합니다.',
            backstory='''당신은 공인회계사 출신의 재무 분석가입니다. 
            매출, 영업이익, 부채비율 등 딱딱한 숫자 뒤에 숨겨진 기업의 진짜 가치를 찾아내는 데 결벽증이 있을 정도로 철저합니다.''',
            verbose=True,
            llm=self.llm
        )