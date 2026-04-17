from crewai import Task

class ResearchTask:
    def collect_news_task(self, agent, company_name):
        return Task(
            description=f'오늘 기준 {company_name}의 주가 및 금리 관련 최신 주요 뉴스 기사를 3개 수집하세요.',
            expected_output=f'{company_name} 관련 최신 뉴스 3개의 요약 및 출처 링크',
            agent=agent
        )