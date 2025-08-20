import json
import os
from textwrap import dedent
from openai import OpenAI  # pip install openai>=1.0

from config.settings import get_secret
from proposals.models import ApplyTarget, BenefitType

OPENAI_API_KEY = get_secret("OPEN_API_SECRET_KEY")  # 또는 settings/get_secret 사용
client = OpenAI(api_key=OPENAI_API_KEY)

ALLOWED_APPLY_TARGETS = [c for c, _ in ApplyTarget.choices]
ALLOWED_BENEFIT_TYPES  = [c for c, _ in BenefitType.choices]

def _j(obj):  # JSON pretty string (한글 보존)
    return json.dumps(obj, ensure_ascii=False, indent=2)

def generate_proposal_from_owner_profile(
    *,
    owner_profile: dict,
    author_name: str,
    author_contact: str = "",
) -> dict:
    """
    owner_profile: OwnerProfileForAISerializer(data).data 결과(dict)
    응답(JSON)은 ProposalWriteSerializer의 입력 스키마와 1:1 매칭되도록 요청
    """
    # 프롬프트: 시스템+유저
    system = dedent(f"""
    너는 제휴 제안서를 작성하는 어시스턴트야.
    아래 '업체 프로필'을 바탕으로 제휴 제안서 초안을 JSON으로 만들어.
    출력은 반드시 JSON 객체 하나여야 하고, 지정된 키만 포함해야 한다.
    """)

    # 규칙/스키마 설명(중괄호 직접 쓰지 말고 문자열로만 설명하거나, 예시는 dumps로 주입)
    
    example_input = {
        "campus_name": "중앙대학교",
        "profile_name": "Middle Door",
        "business_type": "카페",
        "partnership_goal": ["REVISIT", "NEW_CUSTOMERS", "OTHER"],
        "partnership_goal_other": "신메뉴 의견을 먼저 듣고 싶습니다.",
        "margin_rate": 45,
        "average_sales": 12000,
        "peak_time": [{"days": ["금요일", "토요일"], "start": "14:00", "end": "16:00"}],
        "off_peak_time": [
            {"days": ["월요일", "화요일"], "start": "10:00", "end": "12:00"},
            {"days": ["수요일", "목요일"], "start": "14:00", "end": "16:00"},
        ],
        "available_service": ["SIDE_MENU", "DRINK"],
        "available_service_other": "",
        "comment": "오래 협업하고 싶습니다.",
    }
    example_output = {
        "title": "카페 'Middle Door' 제휴 요청 제안서",
        "contents": "제휴를 통해 상호 이익을 도모하고 장기 고객 유치를 추진하고자 합니다.",
        "expected_effects": "합리적 할인과 시간대 최적화로 약 10% 매출 증대를 기대합니다.",
        "partnership_type": ["할인형"],
        "contact_info": author_contact,
        "apply_target": "STUDENTS",
        "apply_target_other": "",
        "time_windows": [{"days": ["금요일", "토요일"], "start": "14:00", "end": "16:00"}],
        "benefit_type": "PERCENT_DISCOUNT",
        "benefit_description": "음료 10% 할인",
        "period_start": "2025-10-01",
        "period_end": "2025-12-31",
    }

    allowed_targets = _j(ALLOWED_APPLY_TARGETS)
    allowed_benefits = _j(ALLOWED_BENEFIT_TYPES)

    rules = dedent("""
    반환 JSON 스키마(키만 허용):
    - title: string (30자 이내, 업종+상호 조합)
    - contents: string (100자 이내, partnership_goal/other 반영)
    - expected_effects: string (100자 이내, margin_rate/average_sales 참고)
    - partnership_type: string[] (["할인형","리뷰형","서비스제공형","타임형"] 중 하나 이상)
    - contact_info: string (기본값은 위에 준 작성자 연락처)
    - apply_target: 허용 enum 중 하나
    - apply_target_other: string 또는 ""
    - time_windows: object[]  // 형식: {{"days":["월","화"], "start":"HH:MM", "end":"HH:MM"}}
    - benefit_type: 허용 enum 중 하나
    - benefit_description: string
    - period_start: "YYYY-MM-DD" 또는 null
    - period_end:   "YYYY-MM-DD" 또는 null

    주의:
    - "recipient" 키는 절대 포함하지 마(서버에서 채움)
    - off_peak_time를 우선 고려해 time_windows를 제안
    - available_service에 OTHERS가 포함되면 available_service_other 설명 반영
    """)

    user = (
        f"[작성자 이름]: {author_name}\n"
        f"[작성자 연락처 기본값]: {author_contact}\n\n"
        "[허용 enum]\n"
        f"- apply_target: {allowed_targets}\n"
        f"- benefit_type: {allowed_benefits}\n\n"
        "[업체 프로필(JSON)]\n" + _j(owner_profile) + "\n\n"
        "[출력 형식 규칙]\n" + rules + "\n"
        "[입력 예시]\n" + _j(example_input) + "\n\n"
        "[출력 예시]\n" + _j(example_output) + "\n\n"
        "위 자료를 바탕으로 제휴 제안서 초안을 만들어.\n"
        "출력은 오직 위에서 정의한 JSON 하나만 반환해. 추가 설명, 코드블록 금지."
    )

    resp = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        temperature=0.2,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )

    content = resp.choices[0].message.content
    data = json.loads(content)

    # 사전 방어: 누락 키를 기본값으로 보정
    data.setdefault("contact_info", author_contact or "")
    data.setdefault("time_windows", [])
    data.setdefault("apply_target_other", "")
    data.setdefault("partnership_type", [])

    return data