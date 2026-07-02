"""
test_chatbot_core.py — 화면(Streamlit) 없이 챗봇 부품만 단독 테스트
실행: python test_chatbot_core.py
"""
from chatbot_core import get_chatbot_response

print("\n=== 테스트 1: 병용금기 (도구 호출) ===")
meds = ["클래리시드정", "브릴린타정"]
msgs = [{"role": "user", "content": "내 약들 같이 먹어도 돼?"}]
print("답변:", get_chatbot_response(msgs, meds))

print("\n=== 테스트 2: 약-음식 ===")
meds2 = ["와파린"]
msgs2 = [{"role": "user", "content": "조심해야 할 음식 있어?"}]
print("답변:", get_chatbot_response(msgs2, meds2))

print("\n=== 테스트 3: 일반 질문 + 이어지는 대화 ===")
history = [
    {"role": "user", "content": "타이레놀은 무슨 약이야?"},
    {"role": "assistant", "content": "타이레놀은 해열진통제예요."},
    {"role": "user", "content": "부작용은?"},
]
print("답변:", get_chatbot_response(history, []))
