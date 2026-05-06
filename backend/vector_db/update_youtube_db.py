import os
from dotenv import load_dotenv

import yt_dlp
from openai import OpenAI
from tqdm import tqdm

load_dotenv()


def build_local_youtube_db():
    # 스크립트 파일 위치 기준으로 경로 고정
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.abspath(os.path.join(script_dir, ".."))

    file_path = os.path.join(script_dir, "youtube_video_ids.txt")

    print("🎥 youtube_video_ids.txt 파일에서 영상 ID를 읽어옵니다...")

    if not os.path.exists(file_path):
        print(f"🚨 파일이 없습니다: {file_path}")
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            video_ids = [line.strip() for line in f.readlines() if line.strip()]

        if not video_ids:
            print("🚨 텍스트 파일이 비어있습니다.")
            return

        print(f"✅ 총 {len(video_ids)}개의 영상 ID 로드 완료!")

    except Exception as e:
        print(f"🚨 파일 읽기 실패: {e}")
        return

    transcripts_dir = os.path.join(backend_dir, "transcripts")
    audios_dir = os.path.join(backend_dir, "audios")

    os.makedirs(transcripts_dir, exist_ok=True)
    os.makedirs(audios_dir, exist_ok=True)

    skip_expected_count = 0
    skip_other_count = 0
    meta_only_count = 0
    success_count = 0

    print("\n📝 Whisper API를 사용하여 유튜브 오디오를 텍스트로 변환합니다.")
    print("💰 [비용 알림] 신규 자막이 없는 영상은 API 호출 없이 스킵합니다.\n")

    client = OpenAI()
    target_video_ids = video_ids

    for vid in tqdm(
        target_video_ids,
        desc="음성 추출 및 변환 중",
        ncols=100,
        colour="blue",
    ):
        transcript_path = os.path.join(transcripts_dir, f"{vid}.txt")
        audio_path = os.path.join(audios_dir, f"{vid}.m4a")
        meta_path = os.path.join(transcripts_dir, f"{vid}_meta.txt")

        # 자막과 메타데이터가 모두 존재하면 완전 스킵
        if os.path.exists(transcript_path) and os.path.exists(meta_path):
            skip_expected_count += 1
            continue

        try:
            # 1. 메타데이터 추출 및 오디오 다운로드 준비
            ydl_opts = {
                "format": "m4a/bestaudio/best",
                "outtmpl": audio_path,
                "quiet": True,
                "no_warnings": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={vid}",
                    download=False,
                )

                title = info.get("title") or "제목 없음"
                upload_date = info.get("upload_date") or "알수없음"

                if upload_date != "알수없음" and len(upload_date) == 8:
                    upload_date = (
                        f"{upload_date[:4]}-"
                        f"{upload_date[4:6]}-"
                        f"{upload_date[6:]}"
                    )

                # 메타데이터 저장
                with open(meta_path, "w", encoding="utf-8") as f:
                    f.write(f"{upload_date}\n{title}")

                # 오디오 파일이 없을 때만 다운로드
                if not os.path.exists(audio_path):
                    ydl.download([f"https://www.youtube.com/watch?v={vid}"])

            # 자막은 이미 있고 메타데이터만 새로 만든 경우
            if os.path.exists(transcript_path):
                meta_only_count += 1
                continue

            # 2. Whisper API 호출
            with open(audio_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ko",
                )

            # 3. 변환 텍스트 저장
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(transcription.text)

            success_count += 1

        except Exception:
            skip_other_count += 1
            continue

    print("\n" + "=" * 50)
    print("📊 [유튜브 자막 수집 결과 요약]")
    print("=" * 50)
    print(f"✅ 신규 변환 성공: {success_count}개")
    print(f"💡 메타데이터만 업데이트: {meta_only_count}개")
    print(f"⏩ 이미 존재해서 스킵: {skip_expected_count}개")
    print(f"⚠️ 실패/기타 에러: {skip_other_count}개")
    print("=" * 50 + "\n")

    print("💡 [안내] 자막 수집 완료. 벡터 DB 임베딩은 다음 단계에서 진행됩니다.")


if __name__ == "__main__":
    build_local_youtube_db()