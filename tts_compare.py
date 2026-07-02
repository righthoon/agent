"""
tts_compare.py — 더 자연스러운 목소리 비교 (gpt-4o-mini-tts)
실행: python tts_compare.py
결과: voice_sage.mp3, voice_coral.mp3, voice_shimmer.mp3
"""
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

text = ("안녕하세요. 약속 복약 안전 도우미입니다. "
        "드시는 약 중에 함께 먹으면 안 되는 약이 있는지 확인해 드릴게요.")

# gpt-4o-mini-tts 는 'instructions'로 말투를 조절 (speed 대신)
instructions = "밝고 생기 있는 목소리로, 친근하고 활기차게, 어르신께 또박또박 다정하게 말해주세요."

for voice in ["nova", "coral", "shimmer"]:
    resp = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=text,
        instructions=instructions,
    )
    fname = f"voice_{voice}.mp3"
    with open(fname, "wb") as f:
        f.write(resp.content)
    print(f"[완료] {fname}")

print("\n세 파일을 각각 열어(더블클릭) 들어보고 마음에 드는 목소리를 고르세요.")
