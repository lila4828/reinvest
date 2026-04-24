import os
import yt_dlp

def fetch_and_update_video_ids(channel_url, file_path="youtube_video_ids.txt", fetch_limit=15):
    print(f"🔍 유튜브 채널에서 최신 영상 {fetch_limit}개를 스캔합니다...")
    
    # 💡 extract_flat: 영상을 다운로드하지 않고 목록(ID 등)만 1초 만에 빠르게 긁어오는 옵션
    ydl_opts = {
        'extract_flat': 'in_playlist',
        'playlistend': fetch_limit, # 최신 N개까지만 탐색 (속도 최적화)
        'quiet': True,
        'no_warnings': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
            
        if 'entries' not in info:
            print("🚨 채널에서 영상을 찾을 수 없습니다. URL을 확인해 주세요.")
            return []
            
        # 가져온 최신 영상들의 ID 목록 추출
        fetched_ids = [entry['id'] for entry in info['entries'] if entry.get('id')]
        
        # 기존에 저장되어 있던 ID 읽어오기
        existing_ids = []
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                existing_ids = [line.strip() for line in f.readlines() if line.strip()]
                
        # 💡 새로운 영상(기존 목록에 없는 ID)만 필터링
        new_ids = [vid for vid in fetched_ids if vid not in existing_ids]
        
        if not new_ids:
            print("⏩ 새로운 영상이 없습니다. 기존 목록이 이미 최신 상태입니다.")
            return []
            
        print(f"🎉 {len(new_ids)}개의 새로운 영상이 발견되었습니다: {new_ids}")
        
        # 새로운 ID를 텍스트 파일의 **맨 위**에 추가 (최신순 유지)
        updated_ids = new_ids + existing_ids
        
        with open(file_path, "w", encoding="utf-8") as f:
            for vid in updated_ids:
                f.write(f"{vid}\n")
                
        print(f"💾 '{file_path}' 파일 업데이트가 완료되었습니다!")
        return new_ids
        
    except Exception as e:
        print(f"🚨 채널 정보 추출 중 오류 발생: {e}")
        return []

if __name__ == "__main__":
    # 💡 실제 주알홍쌤 채널의 공식 핸들로 수정 완료
    TARGET_CHANNEL_URL = "https://www.youtube.com/@주알홍쌤/videos" 
    
    fetch_and_update_video_ids(TARGET_CHANNEL_URL, file_path="vetor_db/youtube_video_ids.txt", fetch_limit=10)