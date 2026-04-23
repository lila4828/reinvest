import os
import scrapetube
from youtube_transcript_api import YouTubeTranscriptApi
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from dotenv import load_dotenv
from tqdm import tqdm
import time

load_dotenv()

def build_local_youtube_db():
    print("🎥 [1단계] 영상 목록 스캔 중...")
    videos = scrapetube.get_channel(channel_url="https://www.youtube.com/@주알홍쌤")
    video_ids = [v['videoId'] for v in videos]
    print(f"✅ 총 {len(video_ids)}개 확인 완료!\n")

    print("📝 [2단계] 자막 데이터를 광폭 수집합니다 (자동 생성 포함)...")
    raw_documents = []
    
    for vid in tqdm(video_ids, desc="추출 중", ncols=100, colour="green"):
        try:
            # 💡 [핵심 변경] 사용 가능한 자막 리스트를 먼저 가져옵니다.
            transcript_list = YouTubeTranscriptApi.list_transcripts(vid)
            
            # 수동 자막이나 자동 생성 자막 중 한국어(ko) 또는 한국어-한국(ko-KR)을 찾습니다.
            transcript = transcript_list.find_transcript(['ko', 'ko-KR', 'ko-kr']).fetch()
            
            full_text = " ".join([t['text'] for t in transcript])
            raw_documents.append(full_text)
            
            # 차단 방지를 위해 살짝 쉬기
            time.sleep(0.05) 
            
        except Exception:
            # 에러가 나면 그냥 패스 (자막이 정말 없는 영상)
            continue
            
    print(f"\n✅ 최종 성공: {len(raw_documents)}개 / 실패: {len(video_ids) - len(raw_documents)}개")
    
    if len(raw_documents) == 0:
        print("🚨 여전히 0개라면 유튜브 차단(IP Block) 혹은 라이브러리 심각한 오작동입니다.")
        return

    # 이후 3, 4단계 진행...
    print("\n🔪 [3단계] 텍스트 쪼개기...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.create_documents(raw_documents)
    
    print(f"🧠 [4단계] {len(chunks)}개 조각 임베딩 및 DB 저장 중...")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    Chroma.from_documents(documents=chunks, embedding=embeddings, persist_directory="./chroma_db")
    print("\n🎉 드디어 도서관 구축에 성공했습니다!")

if __name__ == "__main__":
    build_local_youtube_db()