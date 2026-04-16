from crewai import Task

class AnalysisTasks:
    def report_writing_task(self, agent, context_tasks):
        return Task(
            description='''
            리서처가 수집한 최신 뉴스 데이터를 면밀히 검토하세요.
            해당 정보가 한국 IT/반도체 기업(삼성전자, SK하이닉스)의 단기 주가와 투자 심리에 미칠 영향을 분석하세요.
            독자가 이해하기 쉽도록 전문적이면서도 명확한 3문단 분량의 리포트를 작성하세요.
            ''',
            expected_output='전문적인 어조로 작성된 실시간 데이터 기반 3문단 투자 분석 보고서',
            agent=agent,
            context=context_tasks # 리서치 팀의 결과물을 여기서 이어받습니다.
        )