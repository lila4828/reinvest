from crewai import Task

class MacroTask:
    def analyze_macro_economy(self, agent):
        return Task(
            description='''
            'Fetch Macro Economy API' 도구를 사용하여 글로벌 거시경제 지표(환율, 나스닥, 국채 금리, 유가)와 VIX 공포 지수를 가져오세요.
            
            가져온 데이터를 바탕으로 다음 양식에 맞춰 간결하게 브리핑을 작성하세요.
            
            [거시경제 브리핑 양식]
            1. 🌍 주요 지표 현재 수치 및 트렌드: (환율, 나스닥, 국채 금리, 유가의 **현재 정확한 수치**와 **1개월 전 대비 등락 추세(%)**를 모두 빠짐없이 나열할 것)
            2. 😨 글로벌 투자 심리: (VIX 공포 지수의 현재 수치 및 시장 상태 판정 결과 요약)
            3. 🇰🇷 한국 시장 영향 진단: (위 지표들이 외국인 수급, 수출주, 기술주 등 한국 증시에 유리한지 불리한지 3줄 이내로 날카롭게 요약)
            ''',
            expected_output='현재 거시경제 지표 수치, 1개월 트렌드 및 한국 시장 영향 분석 요약본',
            agent=agent
        )