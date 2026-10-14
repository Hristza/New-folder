"""Добавя български глас (ElevenLabs) към видеото.

1) Генериране на гласа (по един файл на сцена: voiceover/00.mp3 ... voiceover/13.mp3):
     export ELEVENLABS_API_KEY=...
     python3 voiceover.py tts --voice <voice_id> --model <model_id>
   или ръчно в сайта на ElevenLabs: за всеки ред от NARRATION се генерира отделен файл
   и се записва като voiceover/NN.mp3 (номерът е номерът на сцената, от 00 до 13).

2) Сглобяване на видеото с глас:
     python3 voiceover.py build   ->  gmo_insulin_ecoli_voiceover.mp4
   Сцените се удължават автоматично, ако някоя реплика е по-дълга от сцената,
   а фоновата музика се приглушава под гласа.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
VO_DIR = os.path.join(HERE, "voiceover")
OUT = os.path.join(HERE, "gmo_insulin_ecoli_voiceover.mp4")
LEAD = 0.6   # пауза в началото на сцената преди гласа (сек.)
TAIL = 1.0   # пауза след края на репликата (сек.)

# По една реплика на сцена, в реда на SCENES в make_video.py.
# Чуждите имена са изписани така, както трябва да се произнесат.
NARRATION = [
    "Здравейте! Днес ще ви разкажа за една генно модифицирана бактерия, която всеки ден помага на милиони хора – "
    "Е. коли, която произвежда човешки инсулин.",
    "Над петстотин милиона възрастни по света живеят с диабет. Инсулинът е хормон, който регулира кръвната захар, "
    "и много болни трябва да си го инжектират всеки ден. Преди 1982 година той се е добивал от панкреаса на прасета "
    "и крави. Количествата обаче са били ограничени, а някои хора са получавали алергии.",
    "ГМО е организъм, чиято ДНК е променена чрез генно инженерство – например като му се добави ген от друг вид. "
    "В нашия пример учените вграждат човешкия ген за инсулин в бактерията Е. коли.",
    "Първа стъпка: изолира се човешкият ген, който кодира инсулина. Днес той може да се синтезира и в лаборатория.",
    "Втора стъпка: от бактерията се взема плазмид – малка кръгова ДНК. Той се разрязва с рестрикционен ензим, "
    "който действа като молекулярна ножица.",
    "Трета стъпка: генът за инсулин се вгражда в отвора, а ензимът ДНК лигаза залепва краищата. "
    "Така се получава рекомбинантен плазмид.",
    "Четвърта стъпка: рекомбинантният плазмид се вкарва в бактерията. Това се нарича трансформация – "
    "и вече имаме ГМО.",
    "Пета стъпка: бактериите се делят на около двайсет минути и всяка нова клетка носи гена. "
    "Теоретично за десет часа от една бактерия стават над един милиард.",
    "Бактериите се отглеждат в огромни биореактори с хиляди литри хранителна среда. "
    "После инсулинът се извлича, пречиства, проверява и се разлива във флакони.",
    "През 1973 година Коен и Бойер създават първата рекомбинантна ДНК. През 1978 година учени от Дженентек "
    "получават човешки инсулин от Е. коли. През 1982 година Хумулин става първото одобрено лекарство от ГМО. "
    "Днес рекомбинантният инсулин е стандарт в лечението.",
    "Този инсулин е идентичен с човешкия и по-рядко предизвиква алергии. Може да се произвежда в почти "
    "неограничени количества, без животни, с постоянно качество и по-ниска цена.",
    "Бактериите работят само в затворени биореактори, а лабораторните щамове трудно оцеляват в природата. "
    "Готовото лекарство е пречистено и в него няма живи бактерии. Производството се контролира строго "
    "от европейските и американските здравни агенции.",
    "Един човешки ген, вграден в бактерия, позволи инсулинът да стигне до милиони хора. Това показва, че "
    "генното инженерство има реално приложение в медицината и буквално спасява животи.",
    "Благодаря за вниманието!",
]


def clip_path(i):
    return os.path.join(VO_DIR, f"{i:02d}.mp3")


def tts(voice, model, stability, similarity):
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("Липсва ELEVENLABS_API_KEY.")
    os.makedirs(VO_DIR, exist_ok=True)
    for i, text in enumerate(NARRATION):
        if os.path.exists(clip_path(i)):
            print(f"{i:02d}: вече съществува, пропускам")
            continue
        body = {"text": text, "model_id": model,
                "voice_settings": {"stability": stability, "similarity_boost": similarity}}
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
            data=json.dumps(body).encode(), method="POST",
            headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
        with urllib.request.urlopen(req, timeout=120) as r, open(clip_path(i), "wb") as f:
            f.write(r.read())
        print(f"{i:02d}: готово")


def duration(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "csv=p=0", path])
    return float(out)


def build():
    sys.path.insert(0, HERE)
    import make_video  # noqa: E402  (само за базовите дължини на сцените)

    base = [d for _, d in make_video.SCENES]
    if len(base) != len(NARRATION):
        sys.exit("Броят реплики не съвпада с броя сцени.")
    missing = [clip_path(i) for i in range(len(NARRATION)) if not os.path.exists(clip_path(i))]
    if missing:
        sys.exit("Липсват файлове:\n  " + "\n  ".join(missing))

    clips = [duration(clip_path(i)) for i in range(len(NARRATION))]
    durs = [max(b, round(LEAD + c + TAIL, 2)) for b, c in zip(base, clips)]
    timing = os.path.join(VO_DIR, "timing.json")
    with open(timing, "w") as f:
        json.dump({"durations": durs, "clips": clips}, f, indent=1)
    for i, (b, c, d) in enumerate(zip(base, clips, durs)):
        print(f"сцена {i:02d}: глас {c:5.1f} s, сцена {b} -> {d} s")

    silent = os.path.join(HERE, "_video_music_only.mp4")
    env = dict(os.environ, GMO_TIMING=timing, GMO_OUT=silent)
    subprocess.run([sys.executable, os.path.join(HERE, "make_video.py")], env=env, check=True)

    inputs, filters, labels, start = ["-i", silent], [], [], 0.0
    for i, d in enumerate(durs):
        inputs += ["-i", clip_path(i)]
        ms = int((start + LEAD) * 1000)
        filters.append(f"[{i + 1}:a]aresample=44100,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{i}]")
        labels.append(f"[v{i}]")
        start += d
    filters.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0[voice]")
    filters.append("[voice]asplit=2[vk][vm]")
    # музиката се приглушава, докато има глас
    filters.append("[0:a][vk]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[music]")
    filters.append("[music][vm]amix=inputs=2:normalize=0,alimiter=limit=0.95[a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filters),
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", OUT], check=True)
    os.remove(silent)
    print("Готово:", OUT)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tts", help="генерира voiceover/NN.mp3 чрез ElevenLabs API")
    t.add_argument("--voice", required=True, help="ElevenLabs voice_id")
    t.add_argument("--model", required=True, help="ElevenLabs model_id (напр. eleven_v3)")
    t.add_argument("--stability", type=float, default=0.5)
    t.add_argument("--similarity", type=float, default=0.75)
    sub.add_parser("build", help="сглобява видеото с гласа")
    sub.add_parser("text", help="отпечатва репликите за ръчно генериране")
    a = ap.parse_args()
    if a.cmd == "tts":
        tts(a.voice, a.model, a.stability, a.similarity)
    elif a.cmd == "build":
        build()
    else:
        for i, s in enumerate(NARRATION):
            print(f"--- {i:02d}.mp3 ---\n{s}\n")


if __name__ == "__main__":
    main()
