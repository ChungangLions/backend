import json
from textwrap import dedent
from openai import OpenAI

from config.settings import get_secret

OPENAI_API_KEY = get_secret("OPEN_API_SECRET_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

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
        "business_type_other": "",
        "business_day": [{"월": ["09:00-21:00"], "화": ["09:00-21:00"], "수": ["09:00-21:00"], "목": ["09:00-21:00"], "금": ["09:00-21:00"], "토": ["10:00-17:00"]}],
        "goal_new_customers": True,
        "goal_revisit": False,
        "goal_clear_stock": False,
        "goal_spread_peak": False,
        "goal_sns_marketing": False,
        "goal_collect_reviews": False,
        "goal_other": False,
        "goal_other_detail": "",
        "margin_rate": 45,
        "average_sales": 12000,
        "peak_time": [{"주말": ["13:00-15:00"], "평일": ["09:00-11:00"]}],
        "off_peak_time": [
            {"주말": ["09:00-11:00"], "평일": ["18:00-21:00"]}
        ],
        "service_drink": True,
        "service_side_menu": True,
        "service_other": False,
        "service_other_detail": "",
        "comment": "오래 협업하고 싶습니다.",
    }
    example_output = {
        "expected_effects": "합리적 할인과 시간대 최적화로 약 10% 매출 증대를 기대합니다.",
        "partnership_type": ["할인형"],
        "contact_info": author_contact,
        "apply_target": "학생회에 속한 모든 인원 및 관련 학과 학생 전부",
        "time_windows": [{"days": ["금요일", "토요일"], "start": "14:00", "end": "16:00"}],
        "benefit_description": "음료 10% 할인",
        "period_start": "2025-10-01",
        "period_end": "2025-12-31",
    }

    rules = dedent("""
    반환 JSON 스키마(키만 허용):
    - expected_effects: string (100자 이내, margin_rate/average_sales 참고)
    - partnership_type: string[] (["할인형","리뷰형","서비스제공형","타임형"] 중 하나 이상), 마진율이 30% 이상이면 할인형을 고려하는 것처럼 입력 요소를 기준으로 합리적인 추론 부탁
    - contact_info: string (기본값은 위에 준 작성자 연락처)
    - apply_target: string (제안서를 작성하는 대상이 사장님이라면, 대학생들 혹은 학생회에 속한 대상을 위주로 작성, 만약 작성자가 학생회라면 마찬가지로 학생회를 위주로 작성하면 좋을 것 같음)
    - time_windows: object[]  // 형식: {{"days":["월요일","화요일"], "start":"HH:MM", "end":"HH:MM"}}
    - benefit_description: string (30자 이내로 짧게 어떠한 혜택을 제공하는지 작성하면 됨)
    - period_start: "YYYY-MM-DD" 또는 null (제안서가 시작되는 날짜, period_start는 최대한 null을 피하고 제안서를 생성한 이후 1~2일 이후로 시작 날짜를 설정하는 것이 좋을 것으로 생각 됨.)
    - period_end:   "YYYY-MM-DD" 또는 null (제안서가 종료되는 날짜, null이면 기간 없음)

    주의:
    - "recipient" 키는 절대 포함하지 마(서버에서 채움)
    - off_peak_time를 우선 고려해 time_windows를 제안
    - period_start는 최대한 null을 피하고 제안서를 생성한 이후 1~2일 이후로 시작 날짜를 설정하는 것이 좋을 것으로 생각 됨.
    - period_end는 제휴하고자하는 기간의 영향을 많이 받게 되는데, 사장님 혹은 학생단체가 제휴 기간을 길게 잡고자 한다면 3개월 이상으로 설정하고, 그렇지 않는다면 14일 이내로 기간을 설정하자
    - period_end는 period_start보다 빠를 수는 없다는 것을 명심했으면 좋겠음.
    """)

    user = (
        f"[작성자 이름]: {author_name}\n"
        f"[작성자 연락처 기본값]: {author_contact}\n\n"
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