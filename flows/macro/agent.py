from crewai import Agent
from flows.macro.tool import fetch_macro_data

class MacroAgent:
    def __init__(self, llm):
        self.llm = llm

    def macro_economist(self):
        return Agent(
            role='글로벌 거시경제 애널리스트',
            goal='현재 글로벌 매크로 지표(환율, 금리, 나스닥 등)를 분석하여 주식 시장에 미칠 영향을 진단합니다.',
            backstory='당신은 월스트리트 출신의 거시경제 전문가입니다. 금리와 환율 트렌드가 한국 증시(KOSPI/KOSDAQ)와 개별 종목에 미치는 영향을 아주 날카롭고 직관적으로 분석하는 능력이 있습니다.',
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            tools=[fetch_macro_data] # 방금 만든 매크로 도구 장착!
        )