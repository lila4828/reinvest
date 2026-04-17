import os
from dotenv import load_dotenv
from crewai import Crew, Process, LLM

from flows.research.agent import ResearchAgent
from flows.research.task import ResearchTask
from flows.analysis.agent import AnalysisAgent
from flows.analysis.task import AnalysisTask
from flows.accounting.agent import AccountingAgent
from flows.accounting.task import AccountingTask

# 1. 환경 변수 로드
load_dotenv()

def run_financial_crew():
    '''
    # Gemini 엔진 선택
    # 2-1. 가벼운 업무용 모델 (리서치, 재무 수집)
    fast_llm = LLM(
        model="gemini/gemini-2.5-flash",
        api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.3,
        stream=True
    )
    # 2-2. 깊은 사고용 모델 (최종 투자 전략 분석)
    smart_llm = LLM(
        model="gemini/gemini-2.5-pro",
        api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.5,
        stream=True
    )
    '''
    
    # OpenAI 엔진 선택
    # 2-1. 가벼운 업무용 모델 (리서치, 재무 수집)
    fast_llm = LLM(
        model="gpt-4o-mini",
        api_key=os.getenv('OPENAI_API_KEY'),
        temperature=0.3,
        stream=True
    )
    # 2-2. 깊은 사고용 모델 (최종 투자 전략 분석)
    smart_llm = LLM(
        model="gpt-4o",
        api_key=os.getenv('OPENAI_API_KEY'),
        temperature=0.5,
        stream=True
    )
    

    # 3. 타겟 종목 랜덤 선택 로직
    # .KS는 코스피, .KQ는 코스닥
    stock_pool = [
        ("005930.KS", "삼성전자"),
        ("000660.KS", "SK하이닉스"),
        ("086520.KQ", "에코프로")
    ]
    target_ticker, target_company = stock_pool[0]
    print(f"\n🎯 [시스템] 타겟 종목 선정: {target_company} ({target_ticker})")

    # 4. 팀 매니저들 소집
    res_admin = ResearchAgent(fast_llm)      
    res_tasks = ResearchTask()
    acc_admin = AccountingAgent(fast_llm)    
    acc_tasks = AccountingTask()
    ana_admin = AnalysisAgent(smart_llm)      
    ana_tasks = AnalysisTask()

    # ---------------------------------------------------------
    # [1단계] 재무 분석 에이전트 가동 (조건부 필터링)
    # ---------------------------------------------------------
    print(f"\n📊 [1단계] {target_company} 재무 건전성 검토를 시작합니다...")
    accounting_agent = acc_admin.financial_analyst()
    
    # Task에 변수(company, ticker) 전달
    task_accounting = acc_tasks.analyze_financial_statements(accounting_agent, target_company, target_ticker)

    financial_crew = Crew(
        agents=[accounting_agent],
        tasks=[task_accounting],
        max_rpm=10,
        verbose=True
    )
    acc_result = financial_crew.kickoff()

    # 재무 결과 판단 (FAIL 조건)
    if "FAIL" in acc_result.raw or "부적격" in acc_result.raw:
        return f"🚫 [분석 중단] {target_company}의 재무 상태가 기준에 미달하여 리서치 및 심층 분석을 진행하지 않습니다.\n\n[재무 요약]\n{acc_result.raw}"

    print(f"\n✅ [1단계 통과] {target_company} 재무 기준 합격. 뉴스 리서치 및 최종 분석을 진행합니다.")

    # ---------------------------------------------------------
    # [2단계] 리서치 및 최종 분석 에이전트 가동
    # ---------------------------------------------------------
    researcher_agent = res_admin.news_researcher()
    analyst_agent = ana_admin.investment_analyst()

    # Task에 변수 전달 및 1단계 결과를 Context로 활용
    task_research = res_tasks.collect_news_task(researcher_agent, target_company)
    task_analysis = ana_tasks.report_writing_task(analyst_agent, target_company, acc_result.raw, [task_research])

    analysis_crew = Crew(
        agents=[researcher_agent, analyst_agent],
        tasks=[task_research, task_analysis],
        process=Process.sequential,
        max_rpm=10,
        verbose=True
    )
    
    print("\n📰 [2단계] 시장 뉴스 수집 및 종합 투자 리포트 작성을 시작합니다...")
    final_result = analysis_crew.kickoff()
    
    return final_result.raw

if __name__ == "__main__":
    final_result = run_financial_crew()
    
    print("\n" + "="*50)
    print("📈 [최종 투자 분석 리포트]")
    print("="*50)
    print(final_result)