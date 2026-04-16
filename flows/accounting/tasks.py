from crewai import Task

class AccountingTasks:
    def analyze_financial_statements(self, agent):
        return Task(
            description='''
            삼성전자와 SK하이닉스의 가장 최근 분기 실적(매출액, 영업이익)을 조사하고, 
            전년 동기 대비 성장률과 현재 부채 수준이 안정적인지 분석하세요.
            ''',
            expected_output='두 기업의 주요 재무 지표 요약 및 재무 건전성 평가 결과',
            agent=agent
        )