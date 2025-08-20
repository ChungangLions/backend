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

    # 모델이 반드시 이 키들만 포함하도록 딱 박아두자
    # recipient는 서버에서 채울 것이므로 응답에는 포함하지 않게 명시
    # expected_json_schema = dedent(f"""
    # 다음 키만 포함한 JSON을 반환해:
    # {{
    #   "title": string,
    #   "contents": string,
    #   "expected_effects": string,
    #   "partnership_type": [string, ...],  // 예: ["할인형", "리뷰형", "서비스제공형", "타임형"] 중 하나 이상
    #   "contact_info": string,   // 기본값: "{author_contact}"
    #   "apply_target": one of {ALLOWED_APPLY_TARGETS},
    #   "apply_target_other": string or "",
    #   "time_windows": [{{"days": [string,...], "start": "HH:MM", "end": "HH:MM"}}],
    #   "benefit_type": one of {ALLOWED_BENEFIT_TYPES},
    #   "benefit_description": string,
    #   "period_start": "YYYY-MM-DD" or null,
    #   "period_end":   "YYYY-MM-DD" or null,
    # }}
    # 주의:
    # - "recipient" 키는 절대 포함하지 마. (서버에서 채움)
    # - 한국어로 자연스럽게 작성해.
    # - title은 30자 이내로 간결하게 작성해. 예를들어 프로필에서 profile_name과 업종을 얻어서 결합해. 결합 순서는 업종 + 가게 이름이야. 예를들어 업종이 카페이고 이름이 "Middle Door"라면 title은 "카페 'Middle Door' 제휴 요청 제안서"가 되어야 해.
    # - contents는 100자 이내로 작성해. 내용은 주로 제휴 목적에 대한 내용이 들어가야 함. 사장님 profiles의 partnership_goal을 참고해. 만약 partnership_goal이 없다면 "제휴를 통해 상호 이익을 도모하고자 합니다."라고 작성해. 또한 partnership_goal_other의 내용이 있다면, 그 내용도 고려해서 작성해야 함.
    # - expected_effects는 100자 이내로 작성해. 제휴를 통해 기대되는 효과를 간단히 작성해. 사장님 profiles의 margin_rate를 참고해서 averages_sales과 관련하여 예상 기대효과를 작성해줘. 너무 과장되게 쓰지 말고 현실적인 수치를 이용하는 것이 좋을 것 같음
    # - partnership_type은 제휴 방식을 나타내는 거야. list 형태로 반환을 해야하는데 "할인형", "리뷰형", "서비스제공형", "타임형" 중 하나 이상을 선택해야 해. margin_rate가 30% 이상이 되는 경우 할인형을 선택하는 것이 좋겠고, 리뷰형은 리뷰를 작성해주는 조건이 필요해. 서비스제공형은 사장님이 제공하는 서비스가 있어야 하고, 타임형은 특정 시간대에만 적용되는 제휴야.
    # - partnership_type의 경우 사장님 프로필에서 partnership_goal도 고려하면 좋을 것 같아. input으로 들어오는 partnership_goal은 json 필드의 리스트로 들어오는데 들어올 수 있는 값이 정해져 있어.
    # - input으로 들어오는 partnership_goal은 "NEW_CUSTOMERS", "REVISIT", "CLEAR_STOCK" (이는 재고 정리를 의미), "SPREAD_PEAK" (이는 피크 타임 분산을 의미), "SNS_MARKETING", "COLLECT_REVIEWS", 그리고 "OTHER"중 하나 이상이 들어올 수 있어. 예를들어 partnership_goal이 "REVISIT"인 경우, 기존 고객 유치를 위한 제휴 방식을 고려해야 해. "OTHER"이 포함되어 있을 때에는 사장님 프로필의 partnership_goal_other도 고려하면 좋을 것 같아.
    # - apply_target은 ALLOWED_APPLY_TARGETS 중 하나여야 해. 만약 "OTHER"를 선택했다면 apply_target_other에 이유를 간단히 적어야 해.
    # - apply_target_other에는 사장님이 제휴를 원하는 구체적인 대상을 적어야 해. 100자 이내로 작성해주면 될거 같아. 필수로 작성할 필드는 아니고 apply_target에서 OTHER이 들어왔을 때만을 고려하면 될거 같아.
    # - time_windows의 경우 제휴 적용 시간대를 나타내는 거야. 그렇다면 사장님 프로필에서 한산 시간대를 활용하는 것이 좋겠지. off_peak_time의 내용을 참고해. 주말과 평일 모두 포함하진 않아도 됨.
    # - benefit_type은 ALLOWED_BENEFIT_TYPES 중 하나여야 해. 만약 "OTHER"를 선택했다면 benefit_description에 이유를 간단히 적어야 해.
    # - apply_target이 "OTHER"면 apply_target_other에 간단히 이유를 적어.
    # - input으로 들어오는 available_service는 ["SIDE_MENU", "DRINK", "OTHERS"]와 같은 json list의 형태로 들어와. 입력으로 들어올 때는 해당 리스트의 원소 중에서 한 개 이상이 들어올거야.
    # - input으로 들어오는 available_service의 원소 중에서 OTHERS가 있다면 available_service_other의 내용도 읽어봐야 해. 이 내용은 사장님이 제공할 수 있는 추가 서비스를 조금 자세히 적은 경우야.
    # - period_start와 period_end는 반드시 설정해, null이 될 수 없어. 그리고 사장님 프로필의 comment에 오래 협업하고 싶다는 내용이 있다면 period_start와 period_end를 적절히 길게 설정해.
    # - contact_info 기본값으로 "{author_contact}"를 사용해.

    # - 이제 위의 조건을 이용해 사장님 프로필을 바탕으로 제휴 제안서 초안의 예시를 보여줄게.
    # 아래는 profiles의 입력 예시야.
    # [입력 예시]
    # {
    #   "campus_name": "중앙대학교",
    #   "profile_name": "Middle Door",
    #   "business_type": "카페",
    #   "partnership_goal": ["REVISIT", "NEW_CUSTOMERS", "OTHER"],
    #   "partnership_goal_other": "신메뉴가 나왔을 때도 대학생들의 의견을 먼저 들어보고 싶습니다.",
    #   "margin_rate": 45,
    #   "average_sales": 12000,
    #   "peak_time": [
    #     {"days": ["금요일", "토요일"], "start": "14:00", "end": "16:00"}
    #   ],
    #   "off_peak_time": [
    #     {"days": ["월요일", "화요일"], "start": "10:00", "end": "12:00"},
    #     {"days": ["수요일", "목요일"], "start": "14:00", "end": "16:00"}
    #   ],
    #   "available_service": ["SIDE_MENU", "DRINK"],
    #   "available_service_other": "",
    #   "comment": "오래 협업하고 싶습니다."
    # }

    # 다음은 위의 입력 예시를 바탕으로 작성된 제휴 제안서 초안의 예시야.
    # [출력 예시]
    # {
    #     "title": "카페 'Middle Door' 제휴 요청 제안서",
    #     "contents": "제휴를 통해 상호 이익을 증진 및 장기적인 협력을 통해 장기 고객 유치를 도모하고자 합니다.",
    #     "expected_effects": "제휴를 통해 10%의 매출 증가가 예상됩니다.",
    #     "partnership_type": ["할인형"],
    #     "contact_info": "{author_contact}",
    #     "apply_target": "STUDENTS",
    #     "apply_target_other": "",
    #     "time_windows": [
    #         {"days": ["금요일", "토요일"], "start": "14:00", "end": "16:00"}
    #     ],
    #     "benefit_type": "PERCENT_DISCOUNT",
    #     "benefit_description": "음료 10% 할인",
    #     "period_start": "2025-10-01",
    #     "period_end": "2025-12-31"
    # }
    # """)

    # user = dedent(f"""
    # [작성자 이름]: {author_name}
    # [작성자 연락처 기본값]: {author_contact}

    # [업체 프로필(JSON)]:
    # {json.dumps(owner_profile, ensure_ascii=False, indent=2)}

    # 위 자료를 바탕으로 제휴 제안서 초안을 만들어.
    # 출력은 오직 위에서 정의한 JSON 하나만 반환해. 추가 설명, 코드블록 금지.
    # """)

    # resp = client.chat.completions.create(
    #     model="gpt-4o",
    #     response_format={"type": "json_object"},
    #     temperature=0.2,
    #     messages=[
    #         {"role": "system", "content": system},
    #         {"role": "user", "content": expected_json_schema},
    #         {"role": "user", "content": user},
    #     ],
    # )

    # 수정본
    # 규칙/스키마 설명(중괄호 직접 쓰지 말고 문자열로만 설명하거나, 예시는 dumps로 주입)
    schema_rules = dedent(f"""
    다음 키만 포함한 JSON을 반환해:
    - title: string (30자 이내, 업종 + 상호 조합. 예: 카페 'Middle Door' 제휴 요청 제안서)
    - contents: string (100자 이내, 주로 제휴 목적 요약. partnership_goal/other 반영)
    - expected_effects: string (100자 이내, margin_rate/average_sales를 참고한 현실적 기대효과)
    - partnership_type: string[] (["할인형","리뷰형","서비스제공형","타임형"] 중 하나 이상)
    - contact_info: string (기본값: "{author_contact}")
    - apply_target: {ALLOWED_APPLY_TARGETS} 중 하나
    - apply_target_other: string 또는 빈 문자열 (apply_target=OTHER일 때만 필요)
    - time_windows: object[]  // 형식: {{"days": ["월","화"], "start":"HH:MM", "end":"HH:MM"}}
    - benefit_type: {ALLOWED_BENEFIT_TYPES} 중 하나
    - benefit_description: string
    - period_start: "YYYY-MM-DD" 또는 null
    - period_end:   "YYYY-MM-DD" 또는 null

    주의:
    - "recipient" 키는 절대 포함하지 마. (서버에서 채움)
    - 한국어로 자연스럽게 작성해.
    - partnership_type는 margin_rate, available_service, partnership_goal을 함께 고려해 선택해.
    - apply_target=OTHER면 apply_target_other에 100자 이내로 간단히 이유를 적어.
    - time_windows는 off_peak_time(한산 시간대)을 우선적으로 활용해.
    - available_service가 OTHERS면 available_service_other 설명도 반영해.
    - contact_info 기본값으로 "{author_contact}"를 사용해.
    """)

    # 입력/출력 예시는 파이썬 dict로 만들고 dumps로 삽입 (f-string 중괄호 문제 없음)
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
        "apply_target": "STUDENTS",  # ← 실제 enum에 맞춤
        "apply_target_other": "",
        "time_windows": [{"days": ["금요일", "토요일"], "start": "14:00", "end": "16:00"}],
        "benefit_type": "PERCENT_DISCOUNT",  # ← 실제 enum에 맞춤
        "benefit_description": "음료 10% 할인",
        "period_start": "2025-10-01",
        "period_end": "2025-12-31",
    }

    user = dedent(f"""
    [작성자 이름]: {author_name}
    [작성자 연락처 기본값]: {author_contact}

    [업체 프로필(JSON)]
    {_j(owner_profile)}

    [출력 형식 규칙]
    {schema_rules}

    [입력 예시]
    {_j(example_input)}

    [출력 예시]
    {_j(example_output)}

    위 자료를 바탕으로 제휴 제안서 초안을 만들어.
    출력은 오직 위에서 정의한 JSON 하나만 반환해. 추가 설명, 코드블록 금지.
    """)

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