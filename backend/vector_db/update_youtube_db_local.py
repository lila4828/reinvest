import os
import yt_dlp
from faster_whisper import WhisperModel
from tqdm import tqdm
import time

def build_local_youtube_db_with_gpu():
    print("🎥 [로컬 변환] youtube_video_ids.txt 파일에서 전체 영상 ID를 읽어옵니다...")
    
    file_path = "vector_db/youtube_video_ids.txt"
    
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

    # 💡 [수정] 스크립트 파일의 위치를 기준으로 절대 경로 설정 (어디서 실행하든 경로 보장)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.abspath(os.path.join(script_dir, '..'))

    transcripts_dir = os.path.join(backend_dir, "transcripts")
    audios_dir = os.path.join(backend_dir, "audios")

    os.makedirs(transcripts_dir, exist_ok=True)
    os.makedirs(audios_dir, exist_ok=True)
    
    skip_expected_count = 0
    skip_other_count = 0
    print("\n📝 [로컬 STT] 내 PC의 GPU(RTX 3070)를 사용하여 무료로 텍스트 변환을 진행합니다.")
    
    # 💡 [핵심] 로컬 Whisper 모델 로드 (CUDA GPU 사용, float16으로 VRAM 최적화)
    print("🧠 로컬 Whisper 모델(large-v3)을 그래픽카드 메모리에 올리는 중입니다. 잠시만 기다려주세요...")
    model_size = "large-v3"
    model = WhisperModel(model_size, device="cuda", compute_type="float16")
    print("✅ 모델 로드 완료! 변환을 시작합니다.\n")
    
    for vid in tqdm(video_ids, desc="로컬 음성 변환 중", ncols=100, colour="green", position=0, leave=True):
        transcript_path = os.path.join(transcripts_dir, f"{vid}.txt")
        audio_path = os.path.join(audios_dir, f"{vid}.m4a")
        meta_path = os.path.join(transcripts_dir, f"{vid}_meta.txt") # 💡 날짜/제목을 저장할 메타데이터 파일
        
        # 💡 자막과 메타데이터가 모두 완벽히 존재할 때만 스킵
        if os.path.exists(transcript_path) and os.path.exists(meta_path):
            # print(f"\n⏩ [{vid}] 변환 텍스트와 날짜 정보가 모두 존재하여 스킵합니다.") # 💡 콘솔창 깔끔하게 유지
            skip_expected_count += 1
            continue
            
        try:
            # 1. 메타데이터(날짜, 제목) 추출 및 오디오 다운로드
            ydl_opts = {
                'format': 'm4a/bestaudio/best',
                'outtmpl': audio_path,
                'quiet': True,
                'no_warnings': True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # 💡 영상은 받지 않고 정보(날짜/제목)만 1초 만에 빠르게 추출
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
                title = info.get('title') or '제목 없음'           # 💡 None 값 원천 차단
                upload_date = info.get('upload_date') or '알수없음' # 💡 None 값 원천 차단
                
                if upload_date != '알수없음' and len(upload_date) == 8:
                    upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}" # YYYY-MM-DD 포맷팅
                    
                # 메타데이터를 별도 텍스트 파일로 저장
                with open(meta_path, "w", encoding="utf-8") as f:
                    f.write(f"{upload_date}\n{title}")
                
                # 오디오 파일이 없을 때만 다운로드 진행
                if not os.path.exists(audio_path):
                    ydl.download([f"https://www.youtube.com/watch?v={vid}"])
                # else:
                #     print(f"\n💡 [{vid}] 오디오 파일 존재함. 다운로드를 스킵합니다.")
                    
            # 💡 자막은 이미 변환해둔 상태라면 메타데이터만 생성한 채로 다음 영상으로 넘어감 (시간 절약)
            if os.path.exists(transcript_path):
                # print(f"💡 [{vid}] 날짜 및 제목 정보 업데이트 완료!")
                continue
                
            # 2. 로컬 GPU로 Whisper 변환 (STT) 수행
            # print(f"👂 [{vid}] GPU가 오디오를 듣고 텍스트로 타이핑 중입니다...") # 💡 안내문 주석 처리
            start_time = time.time()
            segments, info = model.transcribe(
                audio_path, 
                beam_size=10,                     # 💡 정확도 최우선: 5(기본값)로 복구. 더 높은 품질을 원하면 10까지 올려도 무방합니다.
                language="ko",
                vad_filter=True,                 # 💡 무음 구간 노이즈/환각 방지용으로 유지
                condition_on_previous_text=True, # 💡 이전 문맥 참조 활성화 (문맥을 이어가며 자연스러운 번역 유도)
                # 💡 Whisper의 initial_prompt는 명령이 아닌 '이전 대화 예시'로 작동합니다.
                # 마침표와 띄어쓰기가 완벽한 문장을 주면, AI가 이 스타일을 흉내 내어 문장 부호를 찍기 시작합니다.
                initial_prompt="안녕하세요. 오늘 주식 시장과 ETF, 그리고 매수와 매도 타이밍에 대해 자세히 알아보겠습니다."
            )
            
            text_list = []
            # 💡 개별 영상의 변환 진행률을 보여주는 보조 진행률 바 추가 (단위: 초)
            with tqdm(total=round(info.duration, 2), desc="  ▶ 개별", leave=False, colour="cyan", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}s", position=1) as pbar:
                previous_end = 0
                for segment in segments:
                    text_list.append(segment.text)
                    pbar.update(round(segment.end - previous_end, 2))
                    previous_end = segment.end
                
            full_text = " ".join(text_list)
            elapsed_time = time.time() - start_time
                
            # 3. 변환된 텍스트를 개별 파일로 즉시 저장
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(full_text)
                
            # print(f"🎉 [{vid}] 변환 성공 및 저장 완료! ({len(full_text)}자) - ⏱️ 소요 시간: {elapsed_time:.2f}초")
            
        except Exception as e:
            # 💡 에러 발생 시 진행률 바가 깨지지 않도록 일반 print 대신 tqdm.write 사용
            tqdm.write(f"⚠️ [{vid}] 로컬 변환 실패 (사유: {type(e).__name__} - {str(e)})")
            skip_other_count += 1
            continue
            
    print("\n" + "="*50)
    print("📊 [로컬 GPU 자막 수집 결과 요약]")
    print("="*50)
    print(f"⏩ 스킵됨 (이미 존재함/기타사유): {skip_expected_count}개")
    print(f"⚠️ 스킵됨 (기타 에러): {skip_other_count}개")
    print("="*50 + "\n")
    print("🎉 로컬 무료 변환 작업이 모두 끝났습니다! 이제 'build_vector_db.py'를 실행해 벡터 DB를 생성하세요.")

if __name__ == "__main__":
    build_local_youtube_db_with_gpu()
