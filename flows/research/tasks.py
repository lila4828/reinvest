from crewai import Task

class ResearchTasks:
    def collect_news_task(self, agent):
        return Task(
            description='오늘 기준 삼성전자, SK하이닉스 금리 관련 뉴스를 2개 수집하세요.',
            expected_output='출처가 포함된 뉴스 요약 리스트',
            agent=agent
        )