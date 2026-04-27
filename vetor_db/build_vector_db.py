import os
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

load_dotenv()

def build_db_from_transcripts():
    transcripts_dir = "transcripts"
    if not os.path.exists(transcripts_dir):
        print(f"🚨 '{transcripts_dir}' 폴더가 없습니다. 먼저 텍스트 추출을 완료해주세요.")
        return

    texts = []
    metadatas = []
    # 💡 순수 자막 파일만 읽고, 메타데이터 파일은 분리해서 처리
    files = [f for f in os.listdir(transcripts_dir) if f.endswith(".txt") and not f.endswith("_meta.txt")]
    
    if not files:
        print("🚨 폴더에 txt 파일이 없습니다.")
        return
        
    print(f"📂 총 {len(files)}개의 텍스트 파일을 읽어옵니다...")
    for file_name in files:
        vid = file_name.replace(".txt", "")
        with open(os.path.join(transcripts_dir, file_name), "r", encoding="utf-8") as f:
            content = f.read().strip()
            
        if not content:
            continue

        # 💡 만들어둔 메타데이터 파일(날짜, 제목) 가져오기
        meta_path = os.path.join(transcripts_dir, f"{vid}_meta.txt")
        date, title = "날짜 모름", "제목 없음"
        
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as mf:
                lines = mf.read().splitlines()
                if len(lines) >= 1: date = lines[0]
                if len(lines) >= 2: title = lines[1]
                
        # 💡 [핵심 최적화] RAG 검색 시 쪼개진 조각만 보고도 AI가 문맥을 알 수 있도록 텍스트 자체에 제목/날짜 강제 주입
        enriched_text = f"[영상 제목: {title}]\n[업로드 날짜: {date}]\n\n{content}"
        texts.append(enriched_text)

        # 꼬리표에 날짜와 제목 추가!
        metadatas.append({"source": vid, "date": date, "title": title})
            
    print("\n🔪 [1단계] 텍스트 쪼개기(Chunking)...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,       # 💡 구어체 특유의 긴 설명(예: 에베레스트 비유 등)이 중간에 잘리지 않도록 1000자로 확장
        chunk_overlap=200,     # 💡 문단 구분이 없는 텍스트 특성을 고려해 문맥이 부드럽게 이어지도록 꼬리물기 200자로 확대
        separators=["\n\n", "\n", ". ", "? ", "! ", " ", ""] # 💡 마침표 등 의미가 끝나는 단위에서 우선적으로 자르도록 유도
    )
    chunks = text_splitter.create_documents(texts, metadatas=metadatas)
    
    print(f"🧠 [2단계] {len(chunks)}개 조각 임베딩 및 DB 저장 중...")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    Chroma.from_documents(documents=chunks, embedding=embeddings, persist_directory="./chroma_db")
    print("\n🎉 완벽합니다! 로컬 벡터 DB(chroma_db) 구축이 완료되었습니다.")

if __name__ == "__main__":
    build_db_from_transcripts()