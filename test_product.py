"""
test_product.py — '제품 이름'으로 병용금기 확인 (초보자용)
실행:  python test_product.py
"""

from dur_agent_starter import (
    load_contraindications, load_product_index, check_by_product_names,
)

CSV = "한국의약품안전관리원_병용금기약물_20240625.csv"

print("데이터 불러오는 중... (두 번 읽어서 조금 걸려요)")
partners, name_of = load_contraindications(CSV)   # 금기 판정용
product_to_code   = load_product_index(CSV)        # 제품이름 -> 성분코드
print(f"  제품 이름 {len(product_to_code):,}개 색인 완료\n")


def show(name1, name2):
    """한 쌍을 검사해서 보기 좋게 출력."""
    print("=" * 60)
    print(f"질문:  '{name1}'  +  '{name2}'  같이 먹어도 될까?")
    res = check_by_product_names(name1, name2, partners, name_of, product_to_code)
    for key, value in res.items():
        print(f"  {key:8}: {value}")
    print()


# ── 실제 약 이름으로 테스트 ─────────────────────────────
# 1) 진짜 병용금기인 조합 (오타 섞어서 rapidfuzz 동작도 확인)
show("클래리시드", "브릴린타")

# 2) 이름을 살짝 틀리게 적어도 찾아주는지
show("클래리시드정", "브릴린타정")

# 3) 금기가 아닐 법한 흔한 조합 (대조군)
show("타이레놀", "겔포스")
