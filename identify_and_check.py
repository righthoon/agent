"""
identify_and_check.py — 알약 사진 -> 어떤 약인지 식별 -> 우리 도구로 주의사항 확인
실행:  python identify_and_check.py images.jpg

흐름:
  1) Claude 비전으로 각인/모양/색 근거 알약 식별 (신뢰도 포함)
  2) 식별된 약 이름을 기존 도구에 연결
     - check_food         : 같이 먹으면 안 좋은 음식
     - check_interactions : (약이 2개 이상일 때) 병용금기 여부
주의: 알약 사진만으로 100% 확정은 어렵다. 신뢰도와 확인처를 함께 안내한다.
"""

import sys
import re
import json
import base64

# 기존에 만든 기능들을 그대로 재사용 (챗봇 모듈 = 데이터/도구/클라이언트 포함)
from pharma_chatbot import (
    client, MODEL, safe_print,
    tool_check_food, tool_check_interactions,
)

IMAGE = sys.argv[1] if len(sys.argv) > 1 else "images.jpg"


def _media_type(path):
    p = path.lower()
    if p.endswith(".png"):
        return "image/png"
    if p.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def identify_drug(image_path):
    """Claude 비전으로 알약을 식별해 dict로 반환."""
    with open(image_path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode()

    prompt = (
        "이 사진은 알약(정제) 실물이다. 각인(글자/숫자), 모양, 색을 근거로 어떤 약인지 식별하라. "
        "국제적으로 잘 알려진 각인은 아는 대로 특정하라.\n"
        "오직 아래 형식의 JSON만 출력하라(설명 문장 금지):\n"
        '{"각인":"", "모양_색":"", "약이름_후보":"", "주성분":"", "제형_함량":"", '
        '"신뢰도":0, "확인방법":""}\n'
        "규칙:\n"
        "- 주성분: 성분명 '한 단어'만. 예: 아세트아미노펜  (괄호·함량·'추정' 같은 수식어 절대 금지)\n"
        "- 약이름_후보: 대표 제품명 하나만 짧게. 모르면 빈 문자열 \"\".\n"
        "- 제형_함량: 예 '정제 500mg'\n"
        "- 불확실성은 문장이 아니라 오직 '신뢰도'(0~100 정수)로만 표현하라.\n"
        "- 한국에서 통용되는 성분명을 쓰라(예: 아세트아미노펜)."
    )

    resp = client.messages.create(
        model=MODEL, max_tokens=600,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64",
                                          "media_type": _media_type(image_path), "data": b64}},
            {"type": "text", "text": prompt},
        ]}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"\{.*\}", text, re.DOTALL)      # ```json 감싸도 안전하게 추출
    return json.loads(m.group(0)) if m else {"약이름_후보": "", "주성분_추정": "", "신뢰도": 0}


def main():
    safe_print(f"\n[1] 알약 식별 중... ({IMAGE})")
    info = identify_drug(IMAGE)
    safe_print("  각인      : " + str(info.get("각인", "")))
    safe_print("  모양/색   : " + str(info.get("모양_색", "")))
    safe_print("  약 이름   : " + str(info.get("약이름_후보", "")))
    safe_print("  주성분    : " + str(info.get("주성분", "")))
    safe_print("  제형/함량 : " + str(info.get("제형_함량", "")))
    safe_print("  신뢰도    : " + str(info.get("신뢰도", "")) + " / 100")
    safe_print("  확인방법  : " + str(info.get("확인방법", "")))

    # 식별 결과로 만든 '검색용 이름들' (제품명 + 성분명 둘 다 시도)
    names = [n for n in [info.get("약이름_후보"), info.get("주성분")] if n]

    safe_print("\n[2] 같이 먹으면 안 좋은 음식 확인 (check_food)")
    food = tool_check_food(names)
    if food["주의할_음식"]:
        for x in food["주의할_음식"]:
            safe_print(f"  - {x['약']}: {x['주의음식']}  ({x['이유']})")
    else:
        safe_print("  - 표에 등록된 주의 음식 정보 없음 (단정 불가 -> 약사 상담 권장)")

    safe_print("\n[3] 병용금기 확인 (check_interactions)")
    inter = tool_check_interactions(names)   # 약이 1개면 '2개 필요' 안내가 나옴
    safe_print("  " + json.dumps(inter, ensure_ascii=False))

    safe_print("\n[안내] 알약 사진만으로는 100% 확정이 어렵습니다. "
               "정확한 판단은 약사·의사와 상담하세요.")


if __name__ == "__main__":
    main()
