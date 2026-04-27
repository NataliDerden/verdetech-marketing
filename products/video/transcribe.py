import sys, os, glob, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from faster_whisper import WhisperModel

videos = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "video_*.mp4")))
videos = [v for v in videos if not os.path.exists(v.replace(".mp4", ".txt"))]
print(f"Найдено {len(videos)} видео без txt", flush=True)

print("Загружаю модель small (русский, CPU)...", flush=True)
t0 = time.time()
model = WhisperModel("small", device="cpu", compute_type="int8")
print(f"  модель загружена за {time.time()-t0:.0f}с", flush=True)

for v in videos:
    name = os.path.basename(v)
    print(f"\n=== {name} ===", flush=True)
    t1 = time.time()
    segments, info = model.transcribe(v, language="ru", vad_filter=True, beam_size=1)
    out_path = v.replace(".mp4", ".txt")
    with open(out_path, "w", encoding="utf-8") as f:
        for seg in segments:
            line = f"[{int(seg.start)//60:02d}:{int(seg.start)%60:02d}] {seg.text.strip()}"
            f.write(line + "\n")
            print(line, flush=True)
    print(f"  -> сохранено {out_path} ({time.time()-t1:.0f}с)", flush=True)
