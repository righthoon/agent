"""
example_usage.py — 챗봇 부품을 '다른 앱에서 갖다 쓰는' 최소 예시
================================================================
팀원 전달용. 이 3줄이 핵심이다:

    from chatbot_core import get_chatbot_response
    answer = get_chatbot_response(messages, meds)

[함께 필요한 파일]  chatbot_core.py, dur_agent_starter.py, 병용금기 CSV, .env
[필요 패키지]       pip install anthropic python-dotenv rapidfuzz
================================================================
"""

from chatbot_core import get_chatbot_response

# 1) 복용 중인 약 목록 (너희 앱에서 관리하는 리스트를 그대로 넘기면 됨)
my_meds = ["클래리시드정", "브릴린타정"]

# 2) 대화 기록 (역할 role 은 "user" 또는 "assistant", 내용 content 는 글자)
conversation = []

def ask(user_text):
    """사용자 한마디 -> 챗봇 답변. 대화 기록을 이어서 관리한다."""
    conversation.append({"role": "user", "content": user_text})
    answer = get_chatbot_response(conversation, my_meds)   # ★ 부품 호출
    conversation.append({"role": "assistant", "content": answer})
    return answer

# 3) 실제 사용 예
if __name__ == "__main__":
    print("Q: 내 약들 같이 먹어도 돼?")
    print("A:", ask("내 약들 같이 먹어도 돼?"))
    print("\nQ: 그럼 그 약이랑 조심할 음식은?")
    print("A:", ask("그럼 그 약이랑 조심할 음식은?"))
