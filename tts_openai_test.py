"""
tts_openai_test.py — OpenAI TTS 짧은 문장 테스트
실행: python tts_openai_test.py
결과: test_voice.mp3 파일 생성 (소리 확인용)
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
key = os.environ.get("OPENAI_API_KEY", "")
if not key or key.startswith("sk-여기에"):
    print("[안내] .env 의 OPENAI_API_KEY 에 아직 진짜 키가 없어요.")
    print("       .env 를 열어 OpenAI 키를 넣고 저장한 뒤 다시 실행하세요.")
    raise SystemExit(0)

client = OpenAI()   # OPENAI_API_KEY 자동 사용

text = "안녕하세요. 약속 복약 안전 도우미입니다. 궁금한 점을 물어보세요."
resp = client.audio.speech.create(
    model="tts-1",      # 기본 TTS 모델
    voice="nova",       # 또렷한 목소리
    input=text,
    speed=0.9,          # 약간 천천히(어르신용)
)
with open("test_voice.mp3", "wb") as f:
    f.write(resp.content)

print(f"[성공] test_voice.mp3 만들었어요 (약 {len(text)}자).")
