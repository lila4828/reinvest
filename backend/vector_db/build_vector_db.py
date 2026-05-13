import os
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()

def get_existing_sources(vectorstore):
    """
    ChromaDB에 이미 저장된 source(video_id) 목록을 가져온다.
    source는 각 chunk metadata에 저장된 영상 ID다.
    """
    try:
        collection = vectorstore._collection
        total_count = collection.count()

        if total_count == 0:
            return set()

        # metadata만 가져와서 source 목록 추출
        result = collection.get(include=["metadatas"])
        metadatas = result.get("metadatas", [])

        existing_sources = {
            metadata.get("source")
            for metadata in metadatas
            if metadata and metadata.get("source")
        }

        return existing_sources

    except Exception as e:
        print(f"⚠️ 기존 ChromaDB source 목록 확인 실패: {e}")
        print("⚠️ 안전을 위해 전체 재임베딩은 하지 않고 작업을 중단합니다.")
        raise


def build_db_from_transcripts():
    # 스크립트 파일 위치 기준으로 경로 고정
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.abspath(os.path.join(script_dir, ".."))

    transcripts_dir = os.path.join(backend_dir, "transcripts")
    chroma_dir = os.path.join(backend_dir, "chroma_db")

    if not os.path.exists(transcripts_dir):
        print(f"🚨 '{transcripts_dir}' 폴더가 없습니다. 먼저 텍스트 추출을 완료해주세요.")
        return

    os.makedirs(chroma_dir, exist_ok=True)

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    vectorstore = Chroma(
        persist_directory=chroma_dir,
        embedding_function=embeddings,
    )

    existing_sources = get_existing_sources(vectorstore)

    print(f"📦 기존 ChromaDB 저장 영상 수: {len(existing_sources)}개")

    files = [
        file_name
        for file_name in os.listdir(transcripts_dir)
        if file_name.endswith(".txt") and not file_name.endswith("_meta.txt")
    ]

    if not files:
        print("🚨 transcripts 폴더에 txt 파일이 없습니다.")
        return

    new_files = []

    for file_name in files:
        vid = file_name.replace(".txt", "")

        if vid in existing_sources:
            continue

        new_files.append(file_name)

    if not new_files:
        print("✅ 신규 임베딩 대상이 없습니다. 기존 ChromaDB를 그대로 사용합니다.")
        print(f"📊 현재 Chroma chunk 개수: {vectorstore._collection.count()}")
        return

    print(f"🆕 신규 임베딩 대상 영상 수: {len(new_files)}개")
    print(f"📂 신규 텍스트 파일을 읽어옵니다...")

    texts = []
    metadatas = []

    for file_name in new_files:
        vid = file_name.replace(".txt", "")
        transcript_path = os.path.join(transcripts_dir, file_name)

        with open(transcript_path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            print(f"⚠️ [{vid}] transcript 내용이 비어 있어 스킵합니다.")
            continue

        meta_path = os.path.join(transcripts_dir, f"{vid}_meta.txt")
        date, title = "날짜 모름", "제목 없음"

        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as mf:
                lines = mf.read().splitlines()
                if len(lines) >= 1:
                    date = lines[0]
                if len(lines) >= 2:
                    title = lines[1]

        enriched_text = f"[영상 제목: {title}]\n[업로드 날짜: {date}]\n\n{content}"

        texts.append(enriched_text)
        metadatas.append(
            {
                "source": vid,
                "date": date,
                "title": title,
            }
        )

    if not texts:
        print("🚨 신규 임베딩할 유효한 텍스트가 없습니다.")
        return

    print("\n🔪 [1단계] 신규 텍스트 Chunking...")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", "? ", "! ", " ", ""],
    )

    chunks = text_splitter.create_documents(texts, metadatas=metadatas)

    print(f"🧠 [2단계] 신규 chunk {len(chunks)}개 임베딩 및 ChromaDB 추가 중...")

    batch_size = 5000

    for start in range(0, len(chunks), batch_size):
        end = start + batch_size
        batch = chunks[start:end]

        print(
            f"   - ChromaDB 추가 중: {start + 1:,} ~ {min(end, len(chunks)):,} / {len(chunks):,}"
        )

        vectorstore.add_documents(batch)

    print("\n🎉 증분 임베딩 완료!")
    print(f"📊 현재 Chroma chunk 개수: {vectorstore._collection.count()}")
    print(f"📁 ChromaDB 경로: {chroma_dir}")


if __name__ == "__main__":
    build_db_from_transcripts()
