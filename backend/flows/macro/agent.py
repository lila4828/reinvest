from crewai import Agent
from flows.macro.tool import fetch_macro_data


class MacroAgent:
    def __init__(self, llm):
        self.llm = llm

    def macro_economist(self):
        return Agent(
            role="거시경제 데이터 구조화 요원",
            goal="Fetch Macro Economy API가 반환한 JSON 매크로 데이터를 MacroOutput 스키마에 정확히 매핑합니다.",
            backstory="""
            당신은 시장 전망을 임의로 판단하는 애널리스트가 아니라, 매크로 데이터 구조화 담당자입니다.
            환율, 금리, 나스닥, WTI, VIX 수치를 새로 만들거나 보정하지 않습니다.
            도구가 반환한 JSON의 숫자, null, 배열, 경고 문구를 그대로 유지하여 출력 스키마에 맞게 정리합니다.
            시장 점수 계산은 main.py의 Python 룰베이스가 처리합니다.
            """,
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            tools=[fetch_macro_data],
        )