from crewai import Task

class MacroTask:
    def analyze_macro_economy(self, agent):
        return Task(
            description='''
            'Fetch Macro Economy API' 도구를 사용하여 현재 거시경제 데이터(환율, 나스닥, 금리)를 가져오세요.
            
            가져온 데이터를 바탕으로 다음 양식에 맞춰 간결하게 브리핑을 작성하세요.
            
            [거시경제 브리핑 양식]
            1. 주요 지표 팩트: (가져온 환율, 나스닥, 국채 금리 수치 나열)
            2. 한국 시장 영향 진단: (현재 지표들이 수출주, 기술주 등 한국 증시에 유리한지 불리한지 3줄 이내로 요약)
            ''',
            expected_output='현재 거시경제 지표 수치 및 한국 시장 영향 분석 요약본',
            agent=agent
        )