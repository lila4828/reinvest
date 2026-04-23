from crewai import Task

class YoutubeTask:
    def extract_guru_view(self, agent, company_name):
        return Task(
            description=f'''
            '주알홍쌤' 유튜브 채널을 검색하여 다음 지시를 수행하세요.

            1. 플랜 A: 먼저 채널 내에 '{company_name}'와 관련된 최근 영상이 있는지 검색하고, 있다면 그 영상의 핵심 논리를 추출하세요.
            2. 🚨 플랜 B [매우 중요]: 만약 '{company_name}'에 대한 개별 영상이 없다면, 주알홍쌤의 **가장 최근 시장 시황 분석 영상(시장 심리, 금리, 투자 마인드 등)**을 찾아서 요약하세요.
            3. 영상 스크립트는 매우 깁니다. 인사말 등 불필요한 내용은 버리고, 현재 시장을 대하는 투자자의 자세나 핵심 투자 포인트 딱 3가지만 개조식(-, *)으로 요약하세요.
            ''',
            expected_output='주알홍쌤 채널에서 추출한 해당 종목 또는 현재 시장 상황에 대한 핵심 투자 인사이트 3가지 요약',
            agent=agent
        )