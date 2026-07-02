"""
chat_connect_test.py — API 키가 잘 작동하는지 확인하는 최소 테스트
실행:  python chat_connect_test.py
"""

import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()                                  # .env 파일에서 키를 읽어옴
key = os.environ.get("ANTHROPIC_API_KEY", "")

# 1) 키가 제대로 들어있는지 먼저 점검
if not key or key.startswith("여기에"):
    print("[안내] .env 파일의 ANTHROPIC_API_KEY 에 아직 진짜 키가 없어요.")
    print("       .env 를 열어 sk-... 로 시작하는 키를 붙여넣고 저장한 뒤 다시 실행하세요.")
    raise SystemExit(0)

# 2) Claude 에게 짧게 말 걸어보기
client = Anthropic()                           # 키는 위에서 읽은 환경변수를 자동 사용
msg = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=100,
    messages=[{"role": "user", "content": "한국어로 '연결 성공'이라고만 짧게 답해줘."}],
)
print("Claude 응답:", msg.content[0].text)
print("[성공] API 키가 정상 작동합니다.")
