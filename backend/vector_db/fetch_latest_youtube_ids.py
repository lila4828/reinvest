import os
import yt_dlp


YOUTUBE_CHANNEL_FETCH_TIMEOUT_SECONDS = int(
    os.getenv("YOUTUBE_CHANNEL_FETCH_TIMEOUT_SECONDS", "15")
)

TARGET_CHANNEL_URLS = [
    "https://www.youtube.com/@주알홍쌤/videos",
    "https://www.youtube.com/@주알홍쌤/streams",
]


def get_default_video_ids_path():
    """
    스크립트 위치 기준으로 youtube_video_ids.txt 경로를 반환한다.
    main.py가 어디서 실행되든 경로가 흔들리지 않게 하기 위한 함수.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "youtube_video_ids.txt")


def read_existing_ids(file_path):
    if not os.path.exists(file_path):
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]


def write_video_ids(file_path, video_ids):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        for vid in video_ids:
            f.write(f"{vid}\n")


def fetch_video_ids_from_channel(channel_url, fetch_limit=15):
    print(f"🔍 유튜브 채널에서 최신 영상 {fetch_limit}개를 스캔합니다: {channel_url}")

    ydl_opts = {
        "extract_flat": "in_playlist",
        "playlistend": fetch_limit,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": YOUTUBE_CHANNEL_FETCH_TIMEOUT_SECONDS,
        "retries": 1,
        "fragment_retries": 1,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)

    if "entries" not in info:
        print("🚨 채널에서 영상을 찾을 수 없습니다. URL을 확인해 주세요.")
        return []

    return [
        entry["id"]
        for entry in info["entries"]
        if entry and entry.get("id")
    ]


def fetch_and_update_video_ids(channel_url, file_path=None, fetch_limit=15):
    """
    단일 URL(videos 또는 streams)을 스캔해서 youtube_video_ids.txt를 업데이트한다.
    기존 코드 호환을 위해 유지.
    """
    if file_path is None:
        file_path = get_default_video_ids_path()

    try:
        fetched_ids = fetch_video_ids_from_channel(
            channel_url=channel_url,
            fetch_limit=fetch_limit,
        )

        existing_ids = read_existing_ids(file_path)

        new_ids = [
            vid
            for vid in fetched_ids
            if vid not in existing_ids
        ]

        if not new_ids:
            print("⏩ 새로운 영상이 없습니다. 기존 목록이 이미 최신 상태입니다.")
            return []

        print(f"🎉 {len(new_ids)}개의 새로운 영상이 발견되었습니다: {new_ids}")

        updated_ids = new_ids + existing_ids
        write_video_ids(file_path, updated_ids)

        print(f"💾 '{file_path}' 파일 업데이트가 완료되었습니다!")
        return new_ids

    except Exception as e:
        print(f"🚨 채널 정보 추출 중 오류 발생: {e}")
        return []


def fetch_all_latest_youtube_ids(file_path=None, fetch_limit=15):
    """
    videos / streams 탭을 모두 스캔해서 youtube_video_ids.txt를 한 번만 갱신한다.
    main.py에서는 이 함수만 호출하면 된다.
    """
    if file_path is None:
        file_path = get_default_video_ids_path()

    existing_ids = read_existing_ids(file_path)
    all_fetched_ids = []

    for url in TARGET_CHANNEL_URLS:
        try:
            fetched_ids = fetch_video_ids_from_channel(
                channel_url=url,
                fetch_limit=fetch_limit,
            )
            all_fetched_ids.extend(fetched_ids)
        except Exception as e:
            print(f"🚨 채널 정보 추출 중 오류 발생: {url} / {e}")

    # 중복 제거, 최신순 유지
    unique_fetched_ids = []
    seen = set()

    for vid in all_fetched_ids:
        if vid in seen:
            continue

        seen.add(vid)
        unique_fetched_ids.append(vid)

    new_ids = [
        vid
        for vid in unique_fetched_ids
        if vid not in existing_ids
    ]

    if not new_ids:
        print("⏩ 새로운 영상이 없습니다. 기존 목록이 이미 최신 상태입니다.")
        return []

    print(f"🎉 총 {len(new_ids)}개의 새로운 영상이 발견되었습니다: {new_ids}")

    updated_ids = new_ids + existing_ids
    write_video_ids(file_path, updated_ids)

    print(f"💾 '{file_path}' 파일 업데이트가 완료되었습니다!")
    return new_ids


if __name__ == "__main__":
    new_ids = fetch_all_latest_youtube_ids(fetch_limit=15)

    if new_ids:
        print(f"✅ 신규 영상 ID 업데이트 완료: {new_ids}")
    else:
        print("✅ 신규 영상 없음")
