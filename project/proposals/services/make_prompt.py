import json
from textwrap import dedent
from openai import OpenAI

from config.settings import get_secret
from datetime import date, timedelta

OPENAI_API_KEY = get_secret("OPEN_API_SECRET_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

today = date.today()
start_hint = (today + timedelta(days=2)).strftime("%Y-%m-%d")
end_hint = (today + timedelta(days=30)).strftime("%Y-%m-%d")

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
        "menus": [
        {"name": "아메리카노", "price": 4000},
        {"name": "카페라떼", "price": 5000}
        ],
    }
    example_output = {
        "expected_effects": "아메리카노와 카페라떼와 같은 음료를 할인함으로써 다른 메뉴를 추가 구입할 수 있는 요인이 생길 것 같습니다. 따라서 이로 인해 매출이 약 10% 증가할 것으로 예상됩니다.",
        "partnership_type": ["할인형"],
        "contact_info": author_contact,
        "apply_target": "학생회에 속한 모든 인원 및 관련 학과 학생 전부",
        "time_windows": [{"days": ["수요일", "목요일", "금요일"], "start": "16:00", "end": "21:00"}],
        "benefit_description": "커피음료 10% 할인 (에이드, 아인슈페너는 제외)",
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
    - benefit_description: string (100자 이내로 어떠한 혜택을 제공하는지 작성하면 됨, 단 메뉴명을 활용하는 것이 바람직함)
    - period_start: "YYYY-MM-DD" 또는 null (제안서가 시작되는 날짜, period_start는 최대한 null을 피하고 제안서를 생성한 이후 1~2일 이후로 시작 날짜를 설정하는 것이 좋을 것으로 생각 됨.)
    - period_end:   "YYYY-MM-DD" 또는 null (제안서가 종료되는 날짜, null이면 기간 없음)

    주의 및 추가 중요 규칙!:
    - 해당 주의 사항 및 중요 규칙을 반드시 숙지하고, 출력 JSON에 절대 어긋나지 않도록 해.
    - expected_effects는 margin_rate와 average_sales를 참고하여 작성하라. 또한, 작성할때 너무 간략하게 작성하는 것이 아닌 충분한 정보를 담아 작성하라.
    - expected_effects는 margin_rate와 average_sales도 참고해야하지만 가게의 특성과 메뉴를 고려해야 한다. 정보를 담을 때 위의 예시 출력과 같이 기대 효과를 원인과 결과와 같이 인과적으로 작성해주면 좋을 것 같다.
    - 또한 expected_effects는 경제적인면 하고 상대방이 얻을 수 있는 이득을 중심으로 작성하라. 위의 예시보다 더 자세하고 구체적으로 작성하는 것이 좋을 것 같음. 사례를 여러개로 나누어서 길고 구체적이게 작성하면 좋을 것 같음. 100자 이내로 부탁.
    - 오늘 날짜는 {today.strftime("%Y-%m-%d")}이다.
    - period_start는 오늘 이후 1~2일 뒤 날짜(예: {start_hint})로 설정하라. 그리고 최대한 null을 피하는 것이 좋을것 같음.
    - period_end는 period_start 이후, 보통 14일~3개월 범위 (예: {end_hint} 정도)로 설정하라. 사장님 혹은 학생단체가 제휴 기간을 길게 잡고자 한다면 3개월 이상으로 설정하고, 그렇지 않는다면 14일 이내로 기간을 설정하자.
    - period_end는 period_start보다 빠를 수는 없다는 것을 명심했으면 좋겠음.
    - menus 배열이 주어졌다면, benefit_description에 해당 메뉴명을 활용하는 것이 바람직함. 세부적인 디테일은 포함하면 좋을 것 같음 (예: "아메리카노 10% 할인", "치즈케익 무료 제공")
    - "recipient" 키는 절대 포함하지 마(서버에서 채움)
    - off_peak_time를 우선 고려해 time_windows를 제안하자. 즉 off_peak_time의 시간대에 맞춰 제안하자는 의미이다. peak_time도 고려하여 이 시간대는 피하는 것으로 진행하자.
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
        temperature=0.3,
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