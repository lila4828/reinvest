import os
import glob
import subprocess
from dotenv import load_dotenv

import yt_dlp
from openai import OpenAI
from tqdm import tqdm

from vector_db.youtube_update_guard import get_live_skip_reason, upsert_pending_live_video

load_dotenv()


MAX_WHISPER_FILE_SIZE = 25 * 1024 * 1024  # 25MB = 26,214,400 bytes
CHUNK_SECONDS = 1500  # 25분 단위 분할
YTDLP_TIMEOUT_SECONDS = int(os.getenv("YOUTUBE_YTDLP_TIMEOUT_SECONDS", "30"))
FFMPEG_TIMEOUT_SECONDS = int(os.getenv("YOUTUBE_FFMPEG_TIMEOUT_SECONDS", "60"))
WHISPER_TIMEOUT_SECONDS = int(os.getenv("YOUTUBE_WHISPER_TIMEOUT_SECONDS", "180"))


def run_ffmpeg(command):
    result = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=FFMPEG_TIMEOUT_SECONDS,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 실행 실패: {result.stderr[-1000:]}")


def split_audio_to_96k_chunks(input_path, chunks_dir, vid):
    """
    오디오를 자르지 않고, 전체 오디오를 10분 단위 조각으로 분할합니다.
    각 조각은 96k mp3로 저장되어 Whisper 25MB 제한을 피합니다.
    """
    os.makedirs(chunks_dir, exist_ok=True)

    # 기존 같은 영상 chunk 제거
    old_chunks = glob.glob(os.path.join(chunks_dir, f"{vid}_part_*.mp3"))
    for old_chunk in old_chunks:
        os.remove(old_chunk)

    output_pattern = os.path.join(chunks_dir, f"{vid}_part_%03d.mp3")

    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            "96k",
            "-f",
            "segment",
            "-segment_time",
            str(CHUNK_SECONDS),
            "-reset_timestamps",
            "1",
            output_pattern,
        ]
    )

    chunk_paths = sorted(glob.glob(os.path.join(chunks_dir, f"{vid}_part_*.mp3")))

    if not chunk_paths:
        raise FileNotFoundError(f"분할된 오디오 파일이 생성되지 않았습니다: {vid}")

    for chunk_path in chunk_paths:
        chunk_size = os.path.getsize(chunk_path)

        if chunk_size == 0:
            raise ValueError(f"분할 오디오 파일 크기가 0입니다: {chunk_path}")

        if chunk_size >= MAX_WHISPER_FILE_SIZE:
            raise ValueError(
                f"분할 후에도 chunk가 25MB를 초과했습니다: {chunk_path} "
                f"크기: {chunk_size:,} bytes"
            )

    return chunk_paths


def prepare_audio_files_for_whisper(audio_path, audios_dir, vid):
    """
    Whisper API 전송 전에 파일 크기를 확인합니다.

    - 25MB 미만이면 원본 1개 사용
    - 25MB 이상이면 96k mp3 10분 단위 chunk로 분할해서 여러 개 사용
    """
    original_size = os.path.getsize(audio_path)

    if original_size < MAX_WHISPER_FILE_SIZE:
        return [audio_path], "원본 사용", original_size

    chunks_dir = os.path.join(audios_dir, "chunks")

    chunk_paths = split_audio_to_96k_chunks(
        input_path=audio_path,
        chunks_dir=chunks_dir,
        vid=vid,
    )

    return chunk_paths, "96k 청크 분할", original_size


def build_local_youtube_db(target_video_ids=None):
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
        print(f"🚨 파일 읽기 실패: {type(e).__name__}: {e}")
        return

    if target_video_ids is not None:
        target_video_ids = {
            str(video_id).strip()
            for video_id in target_video_ids
            if str(video_id).strip()
        }
        video_ids = list(target_video_ids)

        if not video_ids:
            print("처리할 pending 영상 ID가 없습니다.")
            return

    transcripts_dir = os.path.join(backend_dir, "transcripts")
    audios_dir = os.path.join(backend_dir, "audios")

    os.makedirs(transcripts_dir, exist_ok=True)
    os.makedirs(audios_dir, exist_ok=True)

    skip_expected_count = 0
    skip_other_count = 0
    meta_only_count = 0
    success_count = 0
    chunked_count = 0
    failed_videos = []

    print("\n📝 Whisper API를 사용하여 유튜브 오디오를 텍스트로 변환합니다.")
    print("💰 [비용 알림] 신규 자막이 없는 영상은 API 호출 없이 스킵합니다.")
    print("🎧 [용량 처리] 25MB 이상 오디오는 96k MP3 chunk로 분할 후 변환합니다.\n")

    client = OpenAI(timeout=WHISPER_TIMEOUT_SECONDS)
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

        current_stage = "초기화"

        try:
            youtube_url = f"https://www.youtube.com/watch?v={vid}"

            # 1. 메타데이터 추출
            current_stage = "유튜브 메타데이터 추출"

            ydl_opts = {
                "format": "m4a/bestaudio/best",
                "outtmpl": audio_path,
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": YTDLP_TIMEOUT_SECONDS,
                "retries": 1,
                "fragment_retries": 1,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    youtube_url,
                    download=False,
                )

                live_skip_reason = get_live_skip_reason(info)
                if live_skip_reason:
                    upsert_pending_live_video(vid, info, live_skip_reason)
                    skip_expected_count += 1
                    tqdm.write("")
                    tqdm.write(
                        f"⏭️ live/upcoming 또는 처리 불가 영상 스킵: {vid} "
                        f"({live_skip_reason})"
                    )
                    continue

                title = info.get("title") or "제목 없음"
                upload_date = info.get("upload_date") or "알수없음"

                if upload_date != "알수없음" and len(upload_date) == 8:
                    upload_date = (
                        f"{upload_date[:4]}-"
                        f"{upload_date[4:6]}-"
                        f"{upload_date[6:]}"
                    )

                # 2. 메타데이터 저장
                current_stage = "메타데이터 저장"

                with open(meta_path, "w", encoding="utf-8") as f:
                    f.write(f"{upload_date}\n{title}")

                # 자막은 이미 있고 메타데이터만 없었던 경우
                # 이 경우 오디오 다운로드/Whisper 호출 필요 없음
                if os.path.exists(transcript_path):
                    meta_only_count += 1
                    continue

                # 3. 오디오 파일이 없을 때만 다운로드
                if not os.path.exists(audio_path):
                    current_stage = "유튜브 오디오 다운로드"
                    ydl.download([youtube_url])

            # 4. 오디오 파일 생성 여부 확인
            current_stage = "오디오 파일 확인"

            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"오디오 파일이 생성되지 않았습니다: {audio_path}")

            if os.path.getsize(audio_path) == 0:
                raise ValueError(f"오디오 파일 크기가 0입니다: {audio_path}")

            # 5. Whisper API 호출 전 파일 크기 확인 및 chunk 분할
            current_stage = "Whisper API 파일 크기 확인"

            whisper_audio_paths, audio_mode, original_size = prepare_audio_files_for_whisper(
                audio_path=audio_path,
                audios_dir=audios_dir,
                vid=vid,
            )

            if audio_mode == "96k 청크 분할":
                chunked_count += 1
                tqdm.write("")
                tqdm.write(f"🎧 25MB 초과 오디오 chunk 분할 완료: {vid}")
                tqdm.write(f"   원본 크기: {original_size:,} bytes")
                tqdm.write(f"   chunk 개수: {len(whisper_audio_paths)}개")

            # 6. Whisper API 호출
            current_stage = "Whisper API 자막 변환"

            transcript_parts = []

            for index, whisper_audio_path in enumerate(whisper_audio_paths, start=1):
                tqdm.write(
                    f"   📝 Whisper 변환 중: {vid} "
                    f"({index}/{len(whisper_audio_paths)})"
                )

                with open(whisper_audio_path, "rb") as audio_file:
                    transcription = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="ko",
                    )

                transcript_parts.append(transcription.text.strip())

            final_transcript = "\n\n".join(
                part for part in transcript_parts if part
            )

            if not final_transcript:
                raise ValueError("Whisper 변환 결과가 비어 있습니다.")

            # 7. 변환 텍스트 저장
            current_stage = "자막 파일 저장"

            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(final_transcript)

            success_count += 1

        except Exception as e:
            skip_other_count += 1

            error_type = type(e).__name__
            error_msg = str(e)

            failed_videos.append(
                {
                    "video_id": vid,
                    "stage": current_stage,
                    "error_type": error_type,
                    "error_msg": error_msg,
                }
            )

            tqdm.write("")
            tqdm.write(f"⚠️ 실패한 영상 ID: {vid}")
            tqdm.write(f"   실패 단계: {current_stage}")
            tqdm.write(f"   이유: {error_type}: {error_msg}")
            continue

    print("\n" + "=" * 50)
    print("📊 [유튜브 자막 수집 결과 요약]")
    print("=" * 50)
    print(f"✅ 신규 변환 성공: {success_count}개")
    print(f"💡 메타데이터만 업데이트: {meta_only_count}개")
    print(f"⏩ 이미 존재해서 스킵: {skip_expected_count}개")
    print(f"🎧 96k chunk 분할 처리: {chunked_count}개")
    print(f"⚠️ 실패/기타 에러: {skip_other_count}개")
    print("=" * 50)

    if failed_videos:
        print("\n⚠️ [실패 영상 상세 목록]")
        for item in failed_videos:
            print("-" * 50)
            print(f"영상 ID: {item['video_id']}")
            print(f"실패 단계: {item['stage']}")
            print(f"에러 타입: {item['error_type']}")
            print(f"에러 내용: {item['error_msg']}")

    print("\n💡 [안내] 자막 수집 완료. 벡터 DB 임베딩은 다음 단계에서 진행됩니다.")


if __name__ == "__main__":
    build_local_youtube_db()
