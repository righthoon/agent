"""
test_api.py — API 서버에 샘플 질문을 보내보는 테스트
사용법:
  1) 다른 터미널에서 서버 실행:  uvicorn api_server:app --port 8000
  2) 이 파일 실행:              python test_api.py
"""
import json
import urllib.request

URL = "http://localhost:8000/chat"

payload = {
    "message": "내 약들 같이 먹어도 돼?",
    "meds": ["클래리시드정", "브릴린타정"],
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(URL, data=data,
                            headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req) as resp:
    result = json.loads(resp.read().decode("utf-8"))

print("=== 보낸 요청 ===")
print(json.dumps(payload, ensure_ascii=False, indent=2))
print("\n=== 받은 응답 ===")
print(json.dumps(result, ensure_ascii=False, indent=2))
