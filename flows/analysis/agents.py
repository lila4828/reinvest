from crewai import Agent

class AnalysisAgents:
    def __init__(self, llm):
        self.llm = llm

    def investment_analyst(self):
        return Agent(
            role='시니어 투자 전략가',
            goal='수집된 데이터를 거시경제적 관점에서 분석하여 투자 리포트를 작성합니다.',
            backstory='당신은 15년 경력의 펀드 매니저 출신으로, 단순한 뉴스를 넘어 시장의 이면과 단기적 변동성을 예측하는 데 탁월합니다.',
            tools=[], # 분석가는 검색보다 판단에 집중하므로 도구를 비워둡니다.
            verbose=True,
            llm=self.llm
        )