import os
import yt_dlp
from faster_whisper import WhisperModel
from tqdm import tqdm
import time


def build_local_youtube_db_with_gpu():
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
    logs_dir = os.path.join(backend_dir, "logs")

    os.makedirs(transcripts_dir, exist_ok=True)
    os.makedirs(audios_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)

    skip_expected_count = 0
    skip_other_count = 0
    meta_only_count = 0
    success_count = 0
    total_elapsed_time = 0.0
    error_logs = []

    print("\n📝 [로컬 STT] 내 PC의 GPU를 사용하여 무료로 텍스트 변환을 진행합니다.")
    print("💰 [비용 알림] 이미 자막이 있는 영상은 변환 없이 스킵합니다.\n")

    model = None
    model_size = "large-v3"

    def get_whisper_model():
        """
        실제 변환이 필요한 영상이 있을 때만 모델을 로드한다.
        이미 모든 자막이 있으면 large-v3를 불필요하게 GPU에 올리지 않는다.
        """
        nonlocal model

        if model is None:
            print("🧠 로컬 Whisper 모델(large-v3)을 그래픽카드 메모리에 올리는 중입니다...")
            model = WhisperModel(
                model_size,
                device="cuda",
                compute_type="float16",
            )
            print("✅ 모델 로드 완료! 변환을 시작합니다.\n")

        return model

    for vid in tqdm(
        video_ids,
        desc="로컬 음성 변환 중",
        ncols=100,
        colour="green",
        position=0,
        leave=True,
    ):
        transcript_path = os.path.join(transcripts_dir, f"{vid}.txt")
        audio_path = os.path.join(audios_dir, f"{vid}.m4a")
        meta_path = os.path.join(transcripts_dir, f"{vid}_meta.txt")

        # 자막과 메타데이터가 모두 존재하면 완전 스킵
        if os.path.exists(transcript_path) and os.path.exists(meta_path):
            skip_expected_count += 1
            continue

        try:
            # 1. 메타데이터 추출 및 오디오 다운로드
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

            # 2. 로컬 GPU Whisper 변환
            whisper_model = get_whisper_model()

            start_time = time.time()

            segments, info = whisper_model.transcribe(
                audio_path,
                beam_size=10,
                language="ko",
                vad_filter=True,
                condition_on_previous_text=True,
                initial_prompt=(
                    "안녕하세요. 오늘 주식 시장과 ETF, 그리고 매수와 매도 타이밍에 대해 "
                    "자세히 알아보겠습니다."
                ),
            )

            text_list = []

            # 개별 영상 진행바 제거
            # 콘솔을 깔끔하게 유지하기 위해 영상별 세부 진행률은 출력하지 않는다.
            for segment in segments:
                text_list.append(segment.text)

            full_text = " ".join(text_list).strip()
            elapsed_time = time.time() - start_time
            total_elapsed_time += elapsed_time

            # 3. 변환 텍스트 저장
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(full_text)

            success_count += 1

        except Exception as e:
            skip_other_count += 1
            error_logs.append(
                f"[{vid}] {type(e).__name__}: {str(e)}"
            )
            continue

    # 에러 상세는 콘솔에 뿌리지 않고 로그 파일로 저장
    error_log_path = None

    if error_logs:
        error_log_path = os.path.join(logs_dir, "youtube_gpu_errors.log")

        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"실행 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n")

            for line in error_logs:
                f.write(line + "\n")

    print("\n" + "=" * 50)
    print("📊 [로컬 GPU 자막 수집 결과 요약]")
    print("=" * 50)
    print(f"✅ 신규 변환 성공: {success_count}개")
    print(f"💡 메타데이터만 업데이트: {meta_only_count}개")
    print(f"⏩ 이미 존재해서 스킵: {skip_expected_count}개")
    print(f"⚠️ 실패/기타 에러: {skip_other_count}개")

    if success_count > 0:
        print(f"⏱️ 총 변환 소요 시간: {total_elapsed_time:.2f}초")

    if error_log_path:
        print(f"📁 에러 상세 로그: {error_log_path}")

    print("=" * 50 + "\n")
    print("🎉 로컬 무료 변환 작업이 모두 끝났습니다. 이제 벡터 DB 임베딩 단계로 넘어가면 됩니다.")


if __name__ == "__main__":
    build_local_youtube_db_with_gpu()