import json
from textwrap import dedent
from openai import OpenAI

from config.settings import get_secret
from datetime import date, timedelta

OPENAI_API_KEY = get_secret("OPEN_API_SECRET_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

today = date.today()
today_str = today.strftime("%Y-%m-%d")
start_hint = (today + timedelta(days=2)).strftime("%Y-%m-%d")
end_hint = (today + timedelta(days=30)).strftime("%Y-%m-%d")

def _j(obj):  # JSON pretty string (한글 보존)
    return json.dumps(obj, ensure_ascii=False, indent=2)

def generate_proposal_from_owner_profile(
    *,
    owner_profile: dict,
    author_name: str,
    author_contact: str = "",
    student_group_profile: dict | None = None,
) -> dict:
    """
    owner_profile: OwnerProfileForAISerializer(data).data 결과(dict)
    응답(JSON)은 ProposalWriteSerializer의 입력 스키마와 1:1 매칭되도록 요청
    """
    # 프롬프트: 시스템+유저
    system = dedent(f"""
    너는 제휴 제안서를 작성하는 어시스턴트야. 제휴 제안서를 작성할 때에는 입력으로 주어진 '업체 프로필'과 '학생회 프로필'을 바탕으로 작성해야 해.
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
        "goal_spread_peak": True,
        "goal_sns_marketing": False,
        "goal_collect_reviews": False,
        "goal_other": False,
        "goal_other_detail": "",
        "margin_rate": 45,
        "average_sales": 4500,
        "peak_time": [{"주말": ["13:00-15:00"], "평일": ["09:00-11:00"]}],
        "off_peak_time": [
            {"주말": ["09:00-11:00"], "평일": ["15:00-17:00"]}
        ],
        "service_drink": False,
        "service_side_menu": False,
        "service_other": True,
        "service_other_detail": "사이즈 업 이벤트",
        "comment": "오래 협업하고 싶습니다.",
        "menus": [
        {"name": "아메리카노", "price": 4000},
        {"name": "카페라떼", "price": 5000}
        ],
    }

    example_student_group_profile_input = {
        "council_name": "경영학부 학생회",
        "department": "경영학부",
        "student_size": 1000,
        "term_start": "2025-03-01",
        "term_end": "2026-02-28",
        "partnership_count": 3,
        "university_name": "중앙대학교"
    }

    example_output = {
        "expected_effects": "경영학부 재학생 약 1,000명 대상 홍보. 방문 학생 약 30% 증가 예상. 한산 시간대 유입 증가. 3개월 기준 약 300명 방문 (30% 방문 가정) -> 예상 추가 매출 약 150만 원 (인당 매출 4,500원 가정 시)",
        "partnership_type": ["타임형", "할인형"],
        "contact_info": author_contact,
        "apply_target": "중앙대학교 경영학부에 소속된 재학생들",
        "time_windows": [{"days": ["월", "화", "수", "목", "금"], "start": "15:00", "end": "17:00"}],
        "benefit_description": "커피음료 10% 할인 (에이드, 아인슈페너는 제외)",
        "period_start": "2025-10-01",
        "period_end": "2025-12-31",
    }

    # 입력으로 들어오는 필드 설명 (사장님 프로필, 학생회 (= 학생 단체) 프로필)
    explain_fields = dedent(f"""
    [업체 프로필 필드 설명]
    - campus_name: 업장 주변에 있는 대학교를 의미함 (예: 중앙대학교)
    - profile_name: 업체의 명칭을 말함
    - business_type: 업종을 말함 (예: 카페, 식당, 주점 등 ...)
    - business_type_other: business_type에서 기타가 들어왔을 때 상세히 설명하는 필드
    - business_day: 영업 요일 및 시간을 말함
    - goal_new_customers: 신규 고객 유치를 목표하는 필드로 True일 때 원하는 것 False일 때는 필수는 아닌 것
    - goal_revisit: 재방문 고객 유치 목표를 목표하는 필드로 True일 때 원하는 것 False일 때는 필수는 아닌 것
    - goal_clear_stock: 재고 소진 목표를 목표하는 필드로 True일 때 원하는 것 False일 때는 필수는 아닌 것
    - goal_spread_peak: 피크 시간대 분산 목표를 목표하는 필드로 True일 때 원하는 것 False일 때는 필수는 아닌 것
    - goal_sns_marketing: SNS 마케팅 목표를 목표하는 필드로 True일 때 원하는 것 False일 때는 필수는 아닌 것
    - goal_collect_reviews: 리뷰 수집 목표를 목표하는 필드로 True일 때 원하는 것 False일 때는 필수는 아닌 것
    - goal_other: 기타 목표이며 위의 boolean field 외의 목표를 가지고 있을 때 True로 설정
    - goal_other_detail: goal_other 필드가 True일 때 상세히 설명하는 필드
    - margin_rate: 마진율을 나타내는 필드 ((총매출 - 총원가) ÷ 총매출 * 100의 결과로 산출됨. 산출된 결과가 들어오며 숫자가 들어오는데 %가 붙지는 않으나, 45가 들어오면 마진율이 45%로 인식하면 됨)
    - average_sales: 인당 평균 매출을 나타내는 필드 (단위: 원)
    - peak_time: 피크 시간대로 사람이 붐비는 시간대를 알려주는 필드
    - off_peak_time: 한산한 시간대로 사람이 적은 시간대를 알려주는 필드
    - service_drink: 서비스를 제공할 때 음료 제공 여부를 나타내는 bool 필드
    - service_side_menu: 서비스를 제공할 때 사이드 메뉴 제공 여부를 나타내는 bool 필드
    - service_other: 서비스를 제공할 때 기타 서비스 제공 여부를 나타내는 bool 필드
    - service_other_detail: 기타 서비스 상세를 설명하는 필드
    - comment: 기타 요청 사항을 설명하는 필드
    - menus: 제공하는 메뉴 목록을 반환 해주는 필드 (메뉴명과 가격이 묶여서 표현됨)
                            
    [학생회(= 학생 단체) 프로필 필드 설명]
    - council_name: 학생회 명칭을 나타내는 필드
    - department: 학생회가 속한 소속 학과/학부를 나타내는 필드
    - student_size: 학생회가 속한 department에 속한 모든 학생의 규모를 나타내는 필드로 학생수를 나타냄 (예: 1000(명))
    - term_start: 임기 시작일 (학생회의 임기 시작)
    - term_end: 임기 종료일 (학생회의 임기 종료)
    - partnership_count: 제휴 경험 수를 나타내며 int형태로 저장되어 있음
    - university_name: 학생회가 속한 대학교
    """)

    rules = dedent(f"""
    반환 JSON 스키마(키만 허용):
    - expected_effects: string (100자 이내, margin_rate/average_sales 참고)
    - partnership_type: string[] (["할인형","리뷰형","서비스제공형","타임형"] 중 하나 이상), 마진율이 30% 이상이면 할인형을 고려하는 것처럼 입력 요소를 기준으로 합리적인 추론 부탁
    - contact_info: string (기본값은 위에 준 작성자 연락처)
    - apply_target: string (제안서를 작성하는 대상이 사장님이라면, 대학생들 혹은 학생회에 속한 대상을 위주로 작성, 만약 작성자가 학생회라면 마찬가지로 학생회를 위주로 작성하면 좋을 것 같음)
    - time_windows: object[]  // 형식: {{"days":["월요일","화요일"], "start":"HH:MM", "end":"HH:MM"}}
    - benefit_description: string (100자 이내로 어떠한 혜택을 제공하는지 작성하면 됨, 단 메뉴명을 활용하는 것이 바람직함)
    - period_start: "YYYY-MM-DD" 또는 null (제안서가 시작되는 날짜, period_start는 최대한 null을 피하고 제안서를 생성한 이후 1~2일 이후로 시작 날짜를 설정하는 것이 좋을 것으로 생각 됨.)
    - period_end:   "YYYY-MM-DD" 또는 null (제안서가 종료되는 날짜, null이면 기간 없음)

    [출력 값 도출을 위한 중요한 규칙 (expected_effects, partnership_type, benefit_description 필드에 대한 중요한 내용)]:
    - expected_effects, partnership_type, benefit_description 필드는 아래의 로직과 조건에 따라서 작성해주어야 함.

    1) partnership_type(= 제휴 유형)의 값을 산출할때, 다음과 같은 사항을 참고할 것
    a. 만약 업종이 '음식점', '카페' 중 하나라면 "할인형", "타임형"에 가중치를 줌. 만약 업종이 '주점'이라면 "서비스제공형", "리뷰형"에 가중치를 줌.
    b. 마진율 가중치: 마진율이 20% 이상이라면 "할인형"에 가중치를 줌. 마진율이 15% 이하라면 "서비스제공형", "리뷰형"에 가중치를 줌.
    c. 한산 시간대 입력 여부: 한산 시간대 존재한다면 "타임형"에 가중치를 줌.

    2) benefit_description(= 혜택) 필드는 다음과 같은 사항을 참고할 것.
    a. partnership_type(= 제휴 유형)이 할인형 이라면, 혜택에 할인율을 포함하되, 마진율x0.7% 와 20% 사이의 값이어야 함.
    b. partnership_type(= 제휴 유형)이 서비스제공형 이라면, 서비스 제공을 포함하되, 제공 품목은 추가 제공 가능 서비스 중에서 하나를 골라서 제공.
    c. partnership_type(= 제휴 유형)이 타임형 이라면, 혜택에 한산 시간대에 서비스 제공을 포함함.
    d. partnership_type(= 제휴 유형)이 리뷰형 이라면, 혜택에 후기 업로드 시 서비스 제공을 포함함.
    e. partnership_type의 내용을 기반으로 작성해야 한다. 예를 들어 partnership_type이 ["할인형", "서비스제공형"]이라면, 혜택에 할인율과 서비스 제공 관련 내용을 포함해야 한다, 이 경우 타임형, 리뷰형의 내용은 삼가하면 좋을 것 같음.
    f. 출력 방식은 다음의 예시를 참고하면 좋을 것 같다. 특히 혜택의 내용이 바뀔때는 마침표를 찍어야 함: ex) 의과대학 학생회 약 84명 대상 홍보. 방문 학생 약 30% 증가 예상 3개월 기준 약 84명 방문. 예상 추가 매출 약 134만 원.

    3) 모든 partnership_type(= 제휴 유형)에서 expected_effects(= 기대효과)에 잠재 제휴 이용자 수, 기대 매출을 반드시 포함할 것. 
    잠재 제휴 이용자 수는 0.52 * 업종별 선호도 * student_size(= 소속 단위 학생 수)로 산출함. 이때, 업종별 선호도는 업종이 음식점일때 0.23, 카페일때 0.21, 술집일때 0.07로 계산함.
    기대 매출은 잠재 제휴 이용자 수 * average_sales(= 평균 인당 매출)로 산출함.
    노출 건수는 잠재 제휴 이용자 수와 같음.
    menus 배열이 주어졌다면, benefit_description에 해당 메뉴명을 활용하는 것이 바람직함.
    만약 partnership_type(= 제휴 유형)이 "리뷰형"이라면, expected_effects(= 기대 효과)에 기대 매출과 노출 건수를 반드시 포함할 것.               
    input으로 들어온 boolean field 내용 중에서 "goal_*" 형태의 필드 값이 True인 항목의 내용을 포함하여 문장형식으로 expected_effects(= 기대효과)에 추가해주면 좋을 것 같아.
    문장이 끝나면 마침표를 찍어줄 것(.).

    [출력 값 도출을 위한 중요한 규칙 (apply_target, time_windows, period_start, period_end 필드에 대한 중요한 내용)]:
    - apply_target는 학생회의 프로필 필드에 있는 department와 council_name을 활용하라. 예를 들면, department가 경영학부이고 council_name이 '중앙사랑'이라면 "중앙사랑 학생회에 속한 학생회 인원 및 경영학부 학생"으로 작성할 수 있다. 이것 외에 추가적인 미사여구와 같은 내용은 GPT 너의 재량을 어느정도 맡김.
    - off_peak_time를 우선 고려해 time_windows를 제안하자. 즉 off_peak_time의 시간대에 맞춰 제안하자는 의미이다. peak_time도 고려하여 이 시간대는 피하는 것으로 진행하자.
    - business_day 필드를 보면 주어진 날짜와 시간 안에 포함되는 시간만을 time_windows에 고려해야 한다. 그외의 시간은 영업 시간이 아니므로 포함하지 말자.
    - partnership_type에 "타임형"이 포함되어 있지 않다면, input으로 들어온 business_day를 기반으로 time_windows를 설정하자. (형식이 동일한 것으로 판명되니, 이 경우 해당 값을 그대로 출력해도 됨.)
    - 오늘 날짜는 {today_str}이다.
    - period_start는 오늘 날짜 이후로 해야하고 학생회 프로필의 필드의 term_start이후로 설정해라.
    - period_end는 period_start 이후, 보통 14일~3개월 범위로 설정하라. 단, 학생회 프로필 필드의 term_end 이전으로 설정해라.
    - period_end는 period_start보다 빠를 수는 없다는 것을 명심해라.


    [주의 및 필수 사항]:
    - 해당 주의 사항 및 중요 규칙을 반드시 숙지하고, 출력 JSON에 절대 어긋나지 않도록 해.
    - [업체 프로필 필드 설명]과 [학생회 프로필 필드 설명]을 반드시 숙지하라.
    - 출력 필드는 [출력 값 도출을 위한 중요한 규칙]에 의거하여 최대한으로 반영해야 함.
    - "recipient" 키는 절대 포함하지 마(서버에서 채움)
    """)

    user = (
        f"[작성자 이름]: {author_name}\n"
        f"[작성자 연락처 기본값]: {author_contact}\n\n"
        "[업체 프로필(JSON)]\n" + _j(owner_profile) + "\n\n"
        "[학생회 프로필(JSON)]\n" + (_j(student_group_profile) if student_group_profile else "없음") + "\n\n"
        "[사장님 프로필 및 학생회 프로필 필드 설명]\n" + explain_fields + "\n\n"
        "[출력 형식 규칙 및 주의사항]\n" + rules + "\n"
        "[입력 예시(사장님 프로필)]\n" + _j(example_input) + "\n\n"
        "[입력 예시(학생회 프로필)]\n" + _j(example_student_group_profile_input) + "\n\n"
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