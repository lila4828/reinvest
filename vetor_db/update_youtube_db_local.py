import os
import yt_dlp
from faster_whisper import WhisperModel
from tqdm import tqdm

def build_local_youtube_db_with_gpu():
    print("🎥 [로컬 변환] youtube_video_ids.txt 파일에서 전체 영상 ID를 읽어옵니다...")
    
    file_path = "youtube_video_ids.txt"
    
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
        
    # 💡 텍스트/오디오 파일을 개별 저장할 폴더 생성
    os.makedirs("transcripts", exist_ok=True)
    os.makedirs("audios", exist_ok=True)
    
    skip_expected_count = 0
    skip_other_count = 0
    print("\n📝 [로컬 STT] 내 PC의 GPU(RTX 3070 Ti)를 사용하여 무료로 텍스트 변환을 진행합니다.")
    
    # 💡 [핵심] 로컬 Whisper 모델 로드 (CUDA GPU 사용, float16으로 VRAM 최적화)
    print("🧠 로컬 Whisper 모델(large-v3)을 그래픽카드 메모리에 올리는 중입니다. 잠시만 기다려주세요...")
    model_size = "large-v3"
    model = WhisperModel(model_size, device="cuda", compute_type="float16")
    print("✅ 모델 로드 완료! 변환을 시작합니다.\n")
    
    for vid in tqdm(video_ids, desc="로컬 음성 변환 중", ncols=100, colour="green"):
        transcript_path = f"transcripts/{vid}.txt"
        audio_path = f"audios/{vid}.m4a"
        
        # 💡 이미 변환된 파일이 있으면 즉시 스킵
        if os.path.exists(transcript_path):
            print(f"\n⏩ [{vid}] 이미 변환된 텍스트가 존재하여 스킵합니다.")
            skip_expected_count += 1
            continue
            
        try:
            # 1. 오디오 파일 다운로드 (이미 있으면 스킵)
            if not os.path.exists(audio_path):
                ydl_opts = {
                    'format': 'm4a/bestaudio/best',
                    'outtmpl': audio_path,
                    'quiet': True,
                    'no_warnings': True
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f"https://www.youtube.com/watch?v={vid}"])
            else:
                print(f"\n💡 [{vid}] 오디오 파일 존재함. 다운로드를 스킵하고 바로 AI 변환에 들어갑니다.")
                
            # 2. 로컬 GPU로 Whisper 변환 (STT) 수행
            print(f"👂 [{vid}] GPU가 오디오를 듣고 텍스트로 타이핑 중입니다...")
            segments, info = model.transcribe(audio_path, beam_size=5, language="ko")
            
            full_text = " ".join([segment.text for segment in segments])
                
            # 3. 변환된 텍스트를 개별 파일로 즉시 저장
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(full_text)
                
            print(f"🎉 [{vid}] 변환 성공 및 저장 완료! ({len(full_text)}자)")
            
        except Exception as e:
            print(f"\n⚠️ [{vid}] 로컬 변환 실패 (사유: {type(e).__name__} - {str(e)})")
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
