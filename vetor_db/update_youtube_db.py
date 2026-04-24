import os
from dotenv import load_dotenv

import yt_dlp
from openai import OpenAI
from tqdm import tqdm

load_dotenv()

def build_local_youtube_db():
    print("🎥 [테스트] youtube_video_ids.txt 파일에서 첫 번째 영상 ID를 읽어옵니다...")
    
    file_path = "vetor_db/youtube_video_ids.txt"
    
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
    # 🚨 [안전장치] Git 클론 후 실수로 실행하여 발생하는 막대한 API 요금을 방지합니다.
    # 전체 변환이 필요할 경우 [0:1] 슬라이싱을 제거하고 test_video_ids = video_ids 로 변경하세요.
    test_video_ids = video_ids[0:1] 
    
    for vid in tqdm(test_video_ids, desc="음성 추출 및 변환 중", ncols=100, colour="blue"):
        transcript_path = f"transcripts/{vid}.txt"
        audio_path = f"audios/{vid}.m4a"
        meta_path = f"transcripts/{vid}_meta.txt" # 💡 날짜/제목을 저장할 메타데이터 파일
        
        # 💡 자막과 메타데이터가 모두 완벽히 존재할 때만 스킵!
        if os.path.exists(transcript_path) and os.path.exists(meta_path):
            print(f"\n⏩ [{vid}] 변환 텍스트와 날짜 정보가 모두 존재하여 스킵합니다.")
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
                
                # 오디오 파일이 없으면 yt-dlp로 다운로드 (이미 있으면 스킵)
                if not os.path.exists(audio_path):
                    ydl.download([f"https://www.youtube.com/watch?v={vid}"])
                else:
                    print(f"\n💡 [{vid}] 오디오 파일이 이미 존재하여 다운로드를 스킵합니다.")
                
            # 💡 자막은 이미 변환해둔 상태라면 메타데이터만 생성한 채로 다음 영상으로 넘어감 (API 요금 절약!)
            if os.path.exists(transcript_path):
                print(f"💡 [{vid}] 날짜 및 제목 정보 업데이트 완료! (API 호출 스킵)")
                continue
                
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