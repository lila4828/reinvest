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

    raw_documents = []
    files = [f for f in os.listdir(transcripts_dir) if f.endswith(".txt")]
    
    if not files:
        print("🚨 폴더에 txt 파일이 없습니다.")
        return
        
    print(f"📂 총 {len(files)}개의 텍스트 파일을 읽어옵니다...")
    for file_name in files:
        with open(os.path.join(transcripts_dir, file_name), "r", encoding="utf-8") as f:
            raw_documents.append(f.read())
            
    print("\n🔪 [1단계] 텍스트 쪼개기(Chunking)...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.create_documents(raw_documents)
    
    print(f"🧠 [2단계] {len(chunks)}개 조각 임베딩 및 DB 저장 중...")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    Chroma.from_documents(documents=chunks, embedding=embeddings, persist_directory="./chroma_db")
    print("\n🎉 완벽합니다! 로컬 벡터 DB(chroma_db) 구축이 완료되었습니다.")

if __name__ == "__main__":
    build_db_from_transcripts()