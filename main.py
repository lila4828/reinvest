import os
from dotenv import load_dotenv
from crewai import Crew, Process, LLM
from datetime import datetime

from flows.research.agent import ResearchAgent
from flows.research.task import ResearchTask
from flows.analysis.agent import AnalysisAgent
from flows.analysis.task import AnalysisTask
from flows.accounting.agent import AccountingAgent
from flows.accounting.task import AccountingTask
from flows.macro.agent import MacroAgent
from flows.macro.task import MacroTask

# 0. 환경 변수 로드
load_dotenv()

def run_financial_crew():    
    # 1-1. 가벼운 업무용 모델 (리서치, 재무 수집)
    fast_llm = LLM(
        model="gpt-4o-mini",
        api_key=os.getenv('OPENAI_API_KEY'),
        temperature=0.3,
        stream=True
    )
    # 1-2. 깊은 사고용 모델 (최종 투자 전략 분석)
    smart_llm = LLM(
        model="gpt-4o",
        api_key=os.getenv('OPENAI_API_KEY'),
        temperature=0.5,
        stream=True
    )

    # ---------------------------------------------------------
    # 2. 글로벌 거시경제 분석 (전체 프로세스 시작 전 딱 한 번 수행)
    # ---------------------------------------------------------
    print(f"\n🌍 [0단계] 글로벌 거시경제 지표 분석을 시작합니다...")
    macro_admin = MacroAgent(fast_llm)
    macro_tasks = MacroTask()
    
    macro_economist = macro_admin.macro_economist()
    task_macro = macro_tasks.analyze_macro_economy(macro_economist)

    macro_crew = Crew(
        agents=[macro_economist],
        tasks=[task_macro],
        verbose=False
    )
    macro_result = macro_crew.kickoff()
    print(f"✅ 매크로 분석 완료: 환율/금리 상황 파악 성공.")

    # ---------------------------------------------------------
    # 3. 다중 종목 스캔 루프 (옵션 C: 3개 종목 연속 처리)
    # ---------------------------------------------------------
    stock_pool = [
        ("005930.KS", "삼성전자"),        # (기존) "PASS (주의)" 받고 리포트까지 나오는지 확인
        ("0009K0.KQ", "에임드바이오"),    # (테스트용) 1년 미만 신규 상장! "FAIL" 컷오프 확인
    ]

    # 모든 종목의 최종 결과를 모아둘 리스트
    all_reports = []

    print("\n🏭 [시스템] 다중 종목 재무 필터링 및 분석 공장을 가동합니다...")

    for target_ticker, target_company in stock_pool:
        print(f"\n{'='*60}")
        print(f"🎯 [시스템] 타겟 종목 스캔: {target_company} ({target_ticker})")
        print(f"{'='*60}")

        # 에이전트 소집
        res_admin = ResearchAgent(fast_llm)      
        res_tasks = ResearchTask()
        acc_admin = AccountingAgent(fast_llm)    
        acc_tasks = AccountingTask()
        ana_admin = AnalysisAgent(smart_llm)      
        ana_tasks = AnalysisTask()

        # [1단계] 재무 및 상장 검토 (Filter)
        print(f"📊 [1단계] 재무 건전성 및 999일 이평선 검토 중...")
        accounting_agent = acc_admin.financial_analyst()
        task_accounting = acc_tasks.analyze_financial_statements(accounting_agent, target_company, target_ticker)

        financial_crew = Crew(
            agents=[accounting_agent],
            tasks=[task_accounting],
            verbose=False
        )
        acc_result = financial_crew.kickoff()

        # FAIL 조건 체크
        if "FAIL" in acc_result.raw or "부적격" in acc_result.raw:
            skip_msg = f"🚫 [분석 중단] {target_company}: 기준 미달\n{acc_result.raw}"
            print(skip_msg)
            all_reports.append(skip_msg)
            continue

        print(f"✅ [1단계 통과] {target_company} 합격.")

        # [2단계] 뉴스 리서치 및 종합 분석
        # 💡 매크로 결과(macro_result)를 시니어 분석가에게 Context로 함께 전달합니다.
        researcher_agent = res_admin.news_researcher()
        analyst_agent = ana_admin.investment_analyst()

        task_research = res_tasks.collect_news_task(researcher_agent, target_company)
        
        # 💡 분석 태스크에 재무결과(acc_result)와 매크로결과(macro_result)를 모두 태워 보냅니다.
        task_analysis = ana_tasks.report_writing_task(
            analyst_agent, 
            target_company, 
            acc_result.raw,           # 재무/이평선/배당 데이터
            macro_result.raw,         # 환율/금리/나스닥 데이터
            [task_research]           # 최신 뉴스 데이터
        )

        analysis_crew = Crew(
            agents=[researcher_agent, analyst_agent],
            tasks=[task_research, task_analysis],
            process=Process.sequential,
            verbose=True
        )
        
        print(f"📰 [2단계] {target_company} 종합 리포트 생성 중...")
        final_result = analysis_crew.kickoff()
        all_reports.append(f"📈 [{target_company} 최종 리포트]\n{final_result.raw}")

    return "\n\n" + "★"*60 + "\n\n".join(all_reports)

if __name__ == "__main__":
    final_output = run_financial_crew()
    
    print("\n\n" + "="*60)
    print("🏆 [전체 분석 결과]")
    print("="*60)
    print(final_output)
    
    # ---------------------------------------------------------
    # 💡 최종 리포트 마크다운 파일 자동 저장 로직 (하루 1개 덮어쓰기)
    # ---------------------------------------------------------
    try:
        # PM님이 미리 만들어두신 result 폴더를 타겟으로 합니다.
        os.makedirs("result", exist_ok=True) 
        
        # YYYY-MM-DD 형식으로 파일명 지정 (예: 2026-04-21.md)
        today_str = datetime.now().strftime("%Y-%m-%d")
        file_name = f"result/{today_str}.md"
        
        # 파일 작성 ("w" 모드이므로 오늘 날짜 안에서는 계속 덮어쓰기가 됩니다)
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(f"> **최근 업데이트 일시:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(final_output)
            
        print(f"\n💾 [저장 완료] 오늘의 종합 투자 리포트가 성공적으로 저장되었습니다.")
        print(f"👉 확인 경로: {file_name}\n")
        
    except Exception as e:
        print(f"\n❌ [저장 실패] 파일 저장 중 오류가 발생했습니다: {str(e)}\n")