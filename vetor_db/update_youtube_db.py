import os
from dotenv import load_dotenv

import yt_dlp
from openai import OpenAI
from tqdm import tqdm

load_dotenv()

def build_local_youtube_db():
    print("🎥 [테스트] youtube_video_ids.txt 파일에서 첫 번째 영상 ID를 읽어옵니다...")
    
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
        
    # 💡 텍스트 파일을 개별 저장할 폴더를 생성합니다.
    os.makedirs("transcripts", exist_ok=True)
    # 💡 오디오 파일을 개별 저장할 폴더를 생성합니다.
    os.makedirs("audios", exist_ok=True)
    
    skip_expected_count = 0
    skip_other_count = 0
    print("\n📝 [최종 수단] Whisper API를 사용하여 유튜브 오디오를 직접 텍스트로 변환합니다.")
    print("💰 [비용 알림] 제한을 해제하고 전체 목록에 대해 오디오 추출 및 텍스트 변환을 진행합니다.")
    
    client = OpenAI()
    test_video_ids = video_ids # 💡 제한 해제: 전체 영상 추출 진행
    
    for vid in tqdm(test_video_ids, desc="음성 추출 및 변환 중", ncols=100, colour="blue"):
        transcript_path = f"transcripts/{vid}.txt"
        audio_path = f"audios/{vid}.m4a"
        
        # 💡 이미 변환된 파일이 있으면 요금/시간 절약을 위해 즉시 스킵! (완벽한 이어하기)
        if os.path.exists(transcript_path):
            print(f"\n⏩ [{vid}] 이미 변환된 파일이 존재하여 스킵합니다.")
            skip_expected_count += 1
            continue
            
        try:
            # 1. 오디오 파일이 없으면 yt-dlp로 다운로드 (이미 있으면 스킵)
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
                print(f"\n💡 [{vid}] 오디오 파일이 이미 존재하여 다운로드를 스킵합니다.")
                
            # 2. OpenAI Whisper API(STT)를 호출하여 텍스트로 변환
            with open(audio_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file,
                    language="ko" # 한국어
                )
                
            # 3. 변환된 텍스트를 개별 파일로 즉시 저장
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(transcription.text)
                
            print(f"\n🎉 [{vid}] 음성 변환 성공 및 '{transcript_path}' 저장 완료! ({len(transcription.text)}자)")
            
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            
            print(f"\n⚠️ [{vid}] 변환 실패 (사유: {error_type} - {error_msg})")
            skip_other_count += 1
            continue
            
    print("\n" + "="*50)
    print("📊 [유튜브 자막 수집 결과 요약]")
    print("="*50)
    print(f"⏩ 스킵됨 (이미 존재함/기타사유): {skip_expected_count}개")
    print(f"⚠️ 스킵됨 (기타 에러): {skip_other_count}개")
    print("="*50 + "\n")
    
    print("\n💡 [안내] 벡터 DB 임베딩 작업은 추후 별도로 진행할 예정이므로 텍스트 저장만 하고 종료합니다.")

if __name__ == "__main__":
    build_local_youtube_db()