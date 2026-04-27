import os
from crewai.tools import BaseTool
from pydantic import Field
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

class LocalYoutubeSearchTool(BaseTool):
    name: str = "local_youtube_search_tool"
    description: str = "주알홍쌤의 유튜브 영상이 저장된 로컬 데이터베이스를 검색하는 도구(local_youtube_search_tool)입니다. 종목명(예: '테슬라', '삼성전자')이나 시장 키워드(예: '시황', '금리', '마인드')를 입력하여 관련된 핵심 발언을 찾아냅니다."

    def _run(self, query: str) -> str:
        # 1. 저장해둔 로컬 DB(chroma_db) 불러오기
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        db_path = "./chroma_db"
        
        if not os.path.exists(db_path):
            return "🚨 로컬 DB가 존재하지 않습니다. 먼저 update_youtube_db.py를 실행하여 DB를 구축하세요."
            
        vector_db = Chroma(persist_directory=db_path, embedding_function=embeddings)
        
        # 2. 🎯 순수 유사도 검색(Similarity Search)으로 타격점 집중
        # 💡 MMR(다양성) 검색은 여러 주제를 섞어버려 종목 고유의 뷰(30만 전자 등)를 희석시킬 수 있습니다.
        # 💡 [핵심 수정] k=6으로만 뽑으면 400개 영상 중 과거(2022년 등) 영상이 유사도에서 밀고 들어올 수 있습니다.
        # 💡 따라서 넉넉하게 30개를 뽑은 뒤, 최신순으로 정렬하여 가장 최근의 유의미한 6개만 추려냅니다.
        docs = vector_db.similarity_search(query, k=30)
        
        if not docs:
            return f"'{query}'에 대한 주알홍쌤의 언급을 찾을 수 없습니다."
            
        # 💡 날짜(date) 메타데이터를 기준으로 최신순(내림차순) 정렬
        docs.sort(key=lambda x: x.metadata.get('date', '0000-00-00'), reverse=True)
        latest_docs = docs[:6] # 💡 [핵심] 30개 중 가장 최신 발언 6개만 에이전트에게 전달

        # 3. 뽑아온 조각들을 하나로 합쳐서 에이전트에게 전달
        formatted_docs = []
        for doc in latest_docs:
            meta_header = f"[📅 {doc.metadata.get('date', '알 수 없음')} 방송 | 🎬 {doc.metadata.get('title', '제목 없음')} | ID: {doc.metadata.get('source', '알 수 없음')}]"
            formatted_docs.append(f"{meta_header}\n{doc.page_content}")
            
        result_text = "\n\n---\n\n".join(formatted_docs)
        
        # 💡 [안전장치] AI가 엉뚱한 검색 결과를 보고 억지로 소설을 쓰지 않도록 도구 자체에 경고문 부착
        warning_msg = f"\n\n🚨 [시스템 경고]: 위 검색 결과에 '{query}'에 대한 직접적이고 의미 있는 언급이 보이지 않는다면, 억지로 연관 지어 요약하지 마세요. 이는 해당 종목에 대한 영상이 없는 것이므로 즉시 '플랜 B'로 넘어가 '시황', '투자 마인드' 등의 키워드로 다시 검색해야 합니다."
        
        return f"[검색 키워드: {query}에 대한 홍쌤의 관련 발언 조각들]\n{result_text}{warning_msg}"

def get_guru_youtube_tool():
    """
    CrewAI 에이전트에게 쥐어줄 인스턴스를 반환합니다.
    """
    return LocalYoutubeSearchTool()