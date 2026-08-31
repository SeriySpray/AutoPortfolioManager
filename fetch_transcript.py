from youtube_transcript_api import YouTubeTranscriptApi
import json

video_id = "mkzcntzznMc"
ytta = YouTubeTranscriptApi()
transcript = ytta.fetch(video_id)

raw_data = []
for item in transcript:
    raw_data.append({
        "text": item.text,
        "start": item.start,
        "duration": item.duration
    })

with open("video_transcript.json", "w", encoding="utf-8") as f:
    json.dump(raw_data, f, ensure_ascii=False, indent=2)

lines = []
for item in raw_data:
    mins = int(item["start"] // 60)
    secs = int(item["start"] % 60)
    lines.append(f"[{mins:02d}:{secs:02d}] {item['text']}")

full_text = "\n".join(lines)
with open("video_transcript.txt", "w", encoding="utf-8") as f:
    f.write(full_text)

print(f"SUCCESS: Saved {len(raw_data)} segments, {len(full_text.split())} words.")
