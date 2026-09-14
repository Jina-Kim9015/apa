import re
import json
import sqlite3
from datetime import datetime
from xml.sax.saxutils import escape as xml_escape

import pandas as pd
import streamlit as st


# ============================================================
# 참고문헌 데이터
# ============================================================

REFS = [
    {
        "no": 1,
        "label": "도서 (Book) - 판수 포함",
        "id": "book1",
        "fields": [
            ("저자", "이진범, 고석찬, 문병용, 박인호, 박훤범, 전현식"),
            ("2판 1쇄", "2016.3.1."),
            ("제목", "식물생리학 제2판"),
            ("출판사", "(주)라이프사이언스"),
        ],
        "format_hint": "저자. (출판연도). 제목 (판수). 출판사.",
        "correct_display": (
            "이진범, 고석찬, 문병용, 박인호, 박훤범, 전현식. "
            "(2016). 식물생리학 (2판). 라이프사이언스."
        ),
        "checks": [
            {
                "name": "저자",
                "score": 25,
                "pattern": (
                    r"이진범.{0,10}고석찬.{0,10}문병용.{0,10}"
                    r"박인호.{0,10}박훤범.{0,10}전현식"
                ),
                "error": (
                    "저자 '이진범, 고석찬, 문병용, 박인호, "
                    "박훤범, 전현식'이 없거나 잘못 표기되었습니다."
                ),
            },
            {
                "name": "연도",
                "score": 25,
                "pattern": r"$2016$",
                "error": "출판연도가 (2016) 형식으로 없습니다.",
            },
            {
                "name": "제목",
                "score": 25,
                "pattern": r"식물생리학",
                "error": "제목 '식물생리학'이 없거나 잘못 표기되었습니다.",
            },
            {
                "name": "출판사",
                "score": 25,
                "pattern": r"라이프사이언스",
                "error": "출판사 '라이프사이언스'가 없거나 잘못 표기되었습니다.",
            },
        ],
        "extra_checks": [
            {
                "pattern": r"전현식\.",
                "error": (
                    "마지막 저자 뒤 마침표가 없습니다. "
                    "예: 전현식."
                ),
                "penalty": 10,
            },
            {
                "pattern": r"2016$\.\s*식물생리학",
                "error": (
                    "연도 괄호 뒤 마침표가 없습니다. "
                    "예: (2016)."
                ),
                "penalty": 10,
            },
            {
                "pattern": (
                    r"식물생리학\s*$2판$\.\s*"
                    r"(?:$주$)?라이프사이언스"
                ),
                "error": (
                    "제목 또는 판수 뒤 마침표가 없습니다. "
                    "예: 식물생리학 (2판)."
                ),
                "penalty": 10,
            },
        ],
    },
    {
        "no": 2,
        "label": "도서 (Book)",
        "id": "book2",
        "fields": [
            ("저자", "정인경, 김영민, 손영운, 이재붕, 이준기"),
            ("초판 발행", "2019.3.1."),
            ("8쇄 발행", "2026.3.1."),
            ("제목", "고등학교 과학사"),
            ("출판사", "씨마스"),
        ],
        "format_hint": "저자. (출판연도). 제목. 출판사.",
        "correct_display": (
            "정인경, 김영민, 손영운, 이재붕, 이준기. "
            "(2019). 고등학교 과학사. 씨마스."
        ),
        "checks": [
            {
                "name": "저자",
                "score": 25,
                "pattern": (
                    r"정인경.{0,10}김영민.{0,10}손영운."
                    r"{0,10}이재붕.{0,10}이준기"
                ),
                "error": (
                    "저자 '정인경, 김영민, 손영운, 이재붕, "
                    "이준기'가 없거나 잘못 표기되었습니다."
                ),
            },
            {
                "name": "연도",
                "score": 25,
                "pattern": r"$2019$",
                "error": (
                    "출판연도는 쇄 연도(2026)가 아닌 "
                    "초판 연도인 (2019) 형식으로 작성해야 합니다."
                ),
            },
            {
                "name": "제목",
                "score": 25,
                "pattern": r"고등학교\s*과학사",
                "error": (
                    "제목 '고등학교 과학사'가 없거나 "
                    "잘못 표기되었습니다."
                ),
            },
            {
                "name": "출판사",
                "score": 25,
                "pattern": r"씨마스",
                "error": "출판사 '씨마스'가 없거나 잘못 표기되었습니다.",
            },
        ],
        "extra_checks": [
            {
                "pattern": r"이준기\.",
                "error": (
                    "마지막 저자 뒤 마침표가 없습니다. "
                    "예: 이준기."
                ),
                "penalty": 10,
            },
            {
                "pattern": r"2019$\.\s*고등학교",
                "error": (
                    "연도 괄호 뒤 마침표가 없습니다. "
                    "예: (2019)."
                ),
                "penalty": 10,
            },
            {
                "pattern": r"고등학교\s*과학사\.\s*씨마스",
                "error": (
                    "제목 뒤 마침표가 없습니다. "
                    "예: 고등학교 과학사."
                ),
                "penalty": 10,
            },
        ],
    },
    {
        "no": 3,
        "label": "학술논문 (Journal)",
        "id": "journal",
        "fields": [
            ("저자", "김민수, 이지영"),
            ("출판연도", "2021"),
            ("논문제목", "코로나19 이후 비대면 교육의 효과성 분석"),
            ("학술지명", "교육학연구"),
            ("권(호)", "59(3)"),
            ("페이지", "25-52"),
            ("DOI", "https://doi.org/10.30916/kera.59.3.25"),
        ],
        "format_hint": (
            "저자. (출판연도). 논문제목. "
            "학술지명, 권(호), 페이지. DOI"
        ),
        "correct_display": (
            "김민수, 이지영. (2021). "
            "코로나19 이후 비대면 교육의 효과성 분석. "
            "교육학연구, 59(3), 25-52. "
            "https://doi.org/10.30916/kera.59.3.25"
        ),
        "checks": [
            {
                "name": "저자",
                "score": 15,
                "pattern": r"김민수.{0,5}이지영",
                "error": (
                    "저자 '김민수, 이지영'이 없거나 "
                    "잘못 표기되었습니다."
                ),
            },
            {
                "name": "연도",
                "score": 15,
                "pattern": r"$2021$",
                "error": "출판연도가 (2021) 형식으로 없습니다.",
            },
            {
                "name": "논문제목",
                "score": 15,
                "pattern": (
                    r"코로나19\s*이후\s*비대면\s*교육의\s*"
                    r"효과성\s*분석"
                ),
                "error": "논문제목이 없거나 잘못 표기되었습니다.",
            },
            {
                "name": "학술지명",
                "score": 15,
                "pattern": r"교육학연구",
                "error": (
                    "학술지명 '교육학연구'가 없거나 "
                    "잘못 표기되었습니다."
                ),
            },
            {
                "name": "권호",
                "score": 15,
                "pattern": r"59\s*$\s*3\s*$",
                "error": "권호가 59(3) 형식으로 없습니다.",
            },
            {
                "name": "페이지",
                "score": 15,
                "pattern": r"25[-–]52",
                "error": "페이지 '25-52'가 없거나 잘못 표기되었습니다.",
            },
            {
                "name": "DOI",
                "score": 10,
                "pattern": r"doi\.org/10\.30916/kera\.59\.3\.25",
                "error": "DOI 주소가 없거나 잘못 표기되었습니다.",
            },
        ],
        "extra_checks": [
            {
                "pattern": r"이지영\.",
                "error": (
                    "마지막 저자 뒤 마침표가 없습니다. "
                    "예: 이지영."
                ),
                "penalty": 10,
            },
            {
                "pattern": r"교육학연구,\s*59",
                "error": (
                    "학술지명과 권호 사이 쉼표가 없습니다. "
                    "예: 교육학연구,"
                ),
                "penalty": 10,
            },
        ],
    },
    {
        "no": 4,
        "label": "웹사이트 (Website)",
        "id": "website",
        "fields": [
            ("저자/기관", "한국교육개발원"),
            ("게시일", "2023.5.10"),
            ("제목", "2023 교육통계 연보"),
            ("웹사이트명", "한국교육개발원"),
            ("URL", "https://kedi.re.kr/kedi/main/main.do"),
        ],
        "format_hint": (
            "저자/기관. (연도. 월. 일). "
            "제목. 웹사이트명. URL"
        ),
        "correct_display": (
            "한국교육개발원. (2023. 5. 10). "
            "2023 교육통계 연보. 한국교육개발원. "
            "https://kedi.re.kr/kedi/main/main.do"
        ),
        "checks": [
            {
                "name": "저자/기관",
                "score": 20,
                "pattern": r"한국교육개발원",
                "error": (
                    "저자/기관 '한국교육개발원'이 없거나 "
                    "잘못 표기되었습니다."
                ),
            },
            {
                "name": "날짜",
                "score": 25,
                "pattern": r"$2023[\.,]\s*5[\.,]\s*10\.?$",
                "error": (
                    "날짜가 (2023. 5. 10) 형식으로 "
                    "작성되지 않았습니다."
                ),
            },
            {
                "name": "제목",
                "score": 20,
                "pattern": r"2023\s*교육통계\s*연보",
                "error": (
                    "제목 '2023 교육통계 연보'가 없거나 "
                    "잘못 표기되었습니다."
                ),
            },
            {
                "name": "웹사이트명",
                "score": 15,
                "pattern": r"한국교육개발원.{1,200}한국교육개발원",
                "error": (
                    "웹사이트명 '한국교육개발원'이 "
                    "저자와 웹사이트명으로 두 번 나와야 합니다."
                ),
            },
            {
                "name": "URL",
                "score": 20,
                "pattern": r"kedi\.re\.kr",
                "error": (
                    "URL 'https://kedi.re.kr/...'이 "
                    "없거나 잘못 표기되었습니다."
                ),
            },
        ],
        "extra_checks": [],
    },
    {
        "no": 5,
        "label": "신문기사 (News)",
        "id": "news",
        "fields": [
            ("기자", "박지수"),
            ("게시일", "2023.9.15"),
            ("기사제목", "인공지능 교육, 초등학교부터 의무화 추진"),
            ("신문사", "한겨레"),
            (
                "URL",
                "https://www.hani.co.kr/arti/society/education/example",
            ),
        ],
        "format_hint": (
            "저자. (연도. 월. 일). 기사제목. 신문사. URL"
        ),
        "correct_display": (
            "박지수. (2023. 9. 15). "
            "인공지능 교육, 초등학교부터 의무화 추진. "
            "한겨레. "
            "https://www.hani.co.kr/arti/society/education/example"
        ),
        "checks": [
            {
                "name": "저자",
                "score": 20,
                "pattern": r"박지수",
                "error": "저자 '박지수'가 없거나 잘못 표기되었습니다.",
            },
            {
                "name": "날짜",
                "score": 25,
                "pattern": r"$2023[\.,]\s*9[\.,]\s*15\.?$",
                "error": (
                    "날짜가 (2023. 9. 15) 형식으로 "
                    "작성되지 않았습니다."
                ),
            },
            {
                "name": "기사제목",
                "score": 20,
                "pattern": (
                    r"인공지능\s*교육.{0,5}"
                    r"초등학교부터\s*의무화\s*추진"
                ),
                "error": "기사제목이 없거나 잘못 표기되었습니다.",
            },
            {
                "name": "신문사",
                "score": 20,
                "pattern": r"한겨레",
                "error": "신문사 '한겨레'가 없거나 잘못 표기되었습니다.",
            },
            {
                "name": "URL",
                "score": 15,
                "pattern": r"hani\.co\.kr",
                "error": (
                    "URL 'https://www.hani.co.kr/...'이 "
                    "없거나 잘못 표기되었습니다."
                ),
            },
        ],
        "extra_checks": [
            {
                "pattern": r"박지수\.",
                "error": (
                    "저자 뒤 마침표가 없습니다. "
                    "예: 박지수."
                ),
                "penalty": 10,
            },
        ],
    },
]


# ============================================================
# 기본 설정
# ============================================================

st.set_page_config(
    page_title="APA 7판 참고문헌 작성 연습",
    layout="wide",
)

CLASSES = ["G", "H", "I1", "I2", "J1", "J2"]

TEACHER_PASSWORD = "1234"

DB_PATH = "reference_results.db"


# ============================================================
# 화면 디자인
# ============================================================

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        min-width: 280px;
        max-width: 320px;
    }

    [data-testid="stSidebar"] * {
        font-size: 17px;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        font-size: 23px !important;
        line-height: 1.5 !important;
        margin-bottom: 20px !important;
    }

    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
        font-size: 18px !important;
        font-weight: 600 !important;
        line-height: 1.6 !important;
        margin-bottom: 14px !important;
    }

    [data-testid="stSidebar"] [role="radiogroup"] {
        gap: 14px !important;
    }

    [data-testid="stSidebar"] [role="radiogroup"] label {
        min-height: 44px !important;
        padding: 8px 6px !important;
        margin-bottom: 8px !important;
        line-height: 1.6 !important;
        font-size: 18px !important;
    }

    [data-testid="stSidebar"] [role="radiogroup"] label p {
        font-size: 18px !important;
        line-height: 1.6 !important;
        margin: 0 !important;
    }

    [data-testid="stSidebar"]
    [role="radiogroup"]
    label:has(input:checked) {
        font-weight: 700 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 세션 상태
# ============================================================

if "show_result" not in st.session_state:
    st.session_state["show_result"] = False

if "last_result" not in st.session_state:
    st.session_state["last_result"] = None


# ============================================================
# 채점 함수
# ============================================================

def evaluate_submission(user_input, ref_data):
    """학생 답안을 검사하고 점수와 오류 목록을 반환합니다."""

    if not user_input.strip():
        return 0, ["답안이 입력되지 않았습니다."]

    score = 0
    errors = []

    for check in ref_data["checks"]:
        if re.search(check["pattern"], user_input):
            score += check["score"]
        else:
            errors.append(check["error"])

    for extra in ref_data.get("extra_checks", []):
        if not re.search(extra["pattern"], user_input):
            score = max(0, score - extra["penalty"])
            errors.append(extra["error"])

    return score, errors


# ============================================================
# 데이터베이스 함수
# ============================================================

def init_database():
    """결과 저장용 데이터베이스를 생성합니다."""

    conn = sqlite3.connect(DB_PATH)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submitted_at TEXT NOT NULL,
            class_name TEXT NOT NULL,
            student_number TEXT,
            student_name TEXT NOT NULL,
            total_score REAL NOT NULL,
            detail_json TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


def save_submission(
    class_name,
    student_number,
    student_name,
    details,
    total_score,
):
    """학생 제출 결과를 저장합니다."""

    conn = sqlite3.connect(DB_PATH)

    submitted_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn.execute(
        """
        INSERT INTO submissions (
            submitted_at,
            class_name,
            student_number,
            student_name,
            total_score,
            detail_json
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            submitted_at,
            class_name,
            student_number,
            student_name,
            total_score,
            json.dumps(
                details,
                ensure_ascii=False,
            ),
        ),
    )

    conn.commit()
    conn.close()


def delete_submission(submission_id):
    """제출 결과 한 건을 삭제합니다."""

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.execute(
        "DELETE FROM submissions WHERE id = ?",
        (submission_id,),
    )

    deleted = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return deleted


def find_reference(detail):
    """저장된 결과에 연결되는 참고문헌 자료를 찾습니다."""

    detail_no = detail.get("no")
    detail_id = detail.get("id")

    for ref in REFS:
        if detail_no is not None and ref["no"] == detail_no:
            return ref

        if detail_id and ref["id"] == detail_id:
            return ref

    return None


def get_correct_display(detail):
    """
    기존 데이터에 모범 답안이 없어도
    현재 참고문헌 데이터에서 모범 답안을 찾아 반환합니다.
    """

    saved_correct_display = detail.get(
        "correct_display"
    )

    if saved_correct_display:
        return saved_correct_display

    matching_ref = find_reference(detail)

    if matching_ref:
        return matching_ref["correct_display"]

    return None


def load_submissions(
    class_filter="전체",
    name_filter="",
):
    """교사용 제출 결과를 불러옵니다."""

    conn = sqlite3.connect(DB_PATH)

    query = """
        SELECT
            id,
            submitted_at,
            class_name,
            student_number,
            student_name,
            total_score,
            detail_json
        FROM submissions
        WHERE 1 = 1
    """

    params = []

    if class_filter != "전체":
        query += " AND class_name = ?"
        params.append(class_filter)

    if name_filter.strip():
        query += " AND student_name LIKE ?"
        params.append(
            f"%{name_filter.strip()}%"
        )

    query += " ORDER BY submitted_at DESC"

    rows = conn.execute(
        query,
        params,
    ).fetchall()

    conn.close()

    records = []

    for row in rows:
        (
            submission_id,
            submitted_at,
            class_name,
            student_number,
            student_name,
            total_score,
            detail_json,
        ) = row

        details = json.loads(detail_json)

        record = {
            "제출번호": submission_id,
            "제출일시": submitted_at,
            "학급": class_name,
            "학번": student_number,
            "학생이름": student_name,
            "총점": total_score,
            "_details": details,
        }

        for detail in details:
            question_no = detail.get("no")

            record[f"문항 {question_no} 점수"] = (
                detail.get("score", 0)
            )

            record[f"문항 {question_no} 학생 답안"] = (
                detail.get("answer", "")
            )

            errors = detail.get("errors", [])

            if errors:
                record[f"문항 {question_no} 오류"] = (
                    " | ".join(errors)
                )
            else:
                record[f"문항 {question_no} 오류"] = "없음"

        records.append(record)

    return records


# ============================================================
# 결과표 생성
# ============================================================

def make_summary_dataframe(records):
    """
    교사용 상단 결과표에 표시할 열만 구성합니다.
    """

    summary_rows = []

    for record in records:
        summary_rows.append(
            {
                "제출일시": record["제출일시"],
                "학급": record["학급"],
                "학번": record["학번"],
                "학생이름": record["학생이름"],
                "총점": record["총점"],
                "문항 1 점수": record.get(
                    "문항 1 점수",
                    0,
                ),
                "문항 2 점수": record.get(
                    "문항 2 점수",
                    0,
                ),
                "문항 3 점수": record.get(
                    "문항 3 점수",
                    0,
                ),
                "문항 4 점수": record.get(
                    "문항 4 점수",
                    0,
                ),
                "문항 5 점수": record.get(
                    "문항 5 점수",
                    0,
                ),
            }
        )

    return pd.DataFrame(summary_rows)


# ============================================================
# XLS 다운로드 함수
# ============================================================

def make_xls_file(records):
    """Excel에서 열 수 있는 XLS 파일을 생성합니다."""

    if not records:
        return b""

    export_records = []

    for record in records:
        export_record = {
            key: value
            for key, value in record.items()
            if key != "_details"
        }

        export_records.append(export_record)

    headers = list(export_records[0].keys())

    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<?mso-application progid="Excel.Sheet"?>',
        (
            '<Workbook '
            'xmlns="urn:schemas-microsoft-com:office:spreadsheet" '
            'xmlns:o="urn:schemas-microsoft-com:office:office" '
            'xmlns:x="urn:schemas-microsoft-com:office:excel" '
            'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'
        ),
        '<Worksheet ss:Name="채점결과">',
        "<Table>",
        "<Row>",
    ]

    for header in headers:
        xml_parts.append(
            '<Cell><Data ss:Type="String">'
            f"{xml_escape(str(header))}"
            "</Data></Cell>"
        )

    xml_parts.append("</Row>")

    for record in export_records:
        xml_parts.append("<Row>")

        for header in headers:
            value = record.get(header, "")

            if value is None:
                value = ""

            if isinstance(value, (int, float)):
                data_type = "Number"
                value_text = str(value)
            else:
                data_type = "String"
                value_text = str(value)

            xml_parts.append(
                f'<Cell><Data ss:Type="{data_type}">'
                f"{xml_escape(value_text)}"
                "</Data></Cell>"
            )

        xml_parts.append("</Row>")

    xml_parts.extend(
        [
            "</Table>",
            "</Worksheet>",
            "</Workbook>",
        ]
    )

    return "\n".join(xml_parts).encode(
        "utf-8-sig"
    )


# ============================================================
# 다시 풀기
# ============================================================

def retry_questions():
    """기존 입력 내용을 유지한 채 문제 풀이 화면으로 돌아갑니다."""

    result = st.session_state.get("last_result")

    if result:
        st.session_state["student_class"] = (
            result["class_name"]
        )

        st.session_state["student_number"] = (
            result["student_number"]
        )

        st.session_state["student_name"] = (
            result["student_name"]
        )

        for detail in result["details"]:
            st.session_state[
                f"answer_{detail['id']}"
            ] = detail["answer"]

    st.session_state["show_result"] = False
    st.rerun()


# ============================================================
# 학생용 화면
# ============================================================

def render_student_form():
    """학생 입력 화면을 표시합니다."""

    st.title("APA 7판 참고문헌 작성 연습")

    st.write(
        "제시된 정보를 참고하여 모든 문항을 작성한 뒤 "
        "한 번에 제출하고 채점할 수 있습니다."
    )

    st.info(
        "모든 문항이 한 페이지에 표시됩니다. "
        "아래로 스크롤하면서 작성하세요."
    )

    with st.form("student_submission_form"):
        st.subheader("학생 정보")

        col1, col2, col3 = st.columns(
            [1, 1, 2]
        )

        with col1:
            class_name = st.selectbox(
                "학급",
                CLASSES,
                key="student_class",
            )

        with col2:
            student_number = st.text_input(
                "학번",
                key="student_number",
            )

        with col3:
            student_name = st.text_input(
                "학생 이름",
                key="student_name",
            )

        st.divider()

        answers = {}

        for ref in REFS:
            st.subheader(
                f"문항 {ref['no']}: {ref['label']}"
            )

            st.markdown("**제시된 정보**")

            information_text = []

            for key, value in ref["fields"]:
                information_text.append(
                    f"- **{key}**: {value}"
                )

            st.markdown(
                "\n".join(information_text)
            )

            st.info(
                f"작성 형식: `{ref['format_hint']}`"
            )

            answers[ref["id"]] = st.text_area(
                "참고문헌 작성",
                key=f"answer_{ref['id']}",
                height=100,
            )

            st.divider()

        submitted = st.form_submit_button(
            "전체 답안 제출 및 한 번에 채점",
            width="stretch",
        )

    if submitted:
        if not student_number.strip():
            st.error("학번을 입력해 주세요.")
            return

        if not student_name.strip():
            st.error("학생 이름을 입력해 주세요.")
            return

        details = []
        scores = []

        for ref in REFS:
            answer = answers.get(
                ref["id"],
                "",
            ).strip()

            score, errors = evaluate_submission(
                answer,
                ref,
            )

            scores.append(score)

            details.append(
                {
                    "no": ref["no"],
                    "id": ref["id"],
                    "label": ref["label"],
                    "answer": answer,
                    "score": score,
                    "errors": errors,
                    "correct_display": (
                        ref["correct_display"]
                    ),
                }
            )

        total_score = round(
            sum(scores) / len(scores),
            1,
        )

        save_submission(
            class_name=class_name,
            student_number=student_number.strip(),
            student_name=student_name.strip(),
            details=details,
            total_score=total_score,
        )

        st.session_state["last_result"] = {
            "class_name": class_name,
            "student_number": student_number.strip(),
            "student_name": student_name.strip(),
            "total_score": total_score,
            "details": details,
        }

        st.session_state["show_result"] = True
        st.rerun()


def render_student_result(result):
    """학생에게 점수와 틀린 이유만 표시합니다."""

    st.title("채점 결과")

    st.info(
        "각 문항에서 틀렸거나 확인이 필요한 부분만 표시됩니다."
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("학급", result["class_name"])

    with col2:
        st.metric("학번", result["student_number"])

    with col3:
        st.metric("학생", result["student_name"])

    with col4:
        st.metric(
            "총점",
            f"{result['total_score']} / 100",
        )

    st.divider()

    if result["total_score"] == 100:
        st.success(
            "모든 문항을 정확하게 작성했습니다."
        )
    else:
        st.warning(
            "아래 문항에서 틀린 이유를 확인해 주세요."
        )

    for detail in result["details"]:
        st.subheader(
            f"문항 {detail['no']}: "
            f"{detail['label']}"
        )

        st.write(
            f"점수: **{detail['score']} / 100점**"
        )

        if detail["errors"]:
            st.markdown("**틀린 이유**")

            for error in detail["errors"]:
                st.error(error)
        else:
            st.success(
                "이 문항은 모든 채점 기준을 통과했습니다."
            )

        st.divider()

    if st.button(
        "다시 풀기",
        width="stretch",
    ):
        retry_questions()


# ============================================================
# 교사용 상세 결과 화면
# ============================================================

def render_teacher_detail(record):
    """선택한 학생의 상세 결과를 표시합니다."""

    st.subheader("선택한 학생의 상세 결과")

    st.write(
        f"제출일시: **{record['제출일시']}**"
    )

    st.write(
        f"학급: **{record['학급']}**"
    )

    st.write(
        f"학번: **{record['학번']}**"
    )

    st.write(
        f"학생이름: **{record['학생이름']}**"
    )

    st.write(
        f"총점: **{record['총점']}점**"
    )

    st.divider()

    details = record.get("_details", [])

    for detail in details:
        question_no = detail.get("no")
        label = detail.get("label", "")
        score = detail.get("score", 0)
        answer = detail.get("answer", "")
        errors = detail.get("errors", [])

        st.markdown(
            f"### 문항 {question_no}: {label}"
        )

        st.write(
            f"점수: **{score} / 100점**"
        )

        st.markdown("**학생이 작성한 답안**")

        st.code(
            answer or "입력된 답안이 없습니다.",
            language="text",
        )

        if errors:
            st.markdown("**틀린 이유**")

            for error in errors:
                st.warning(error)
        else:
            st.success(
                "이 문항은 모든 채점 기준을 통과했습니다."
            )

        st.markdown("**모범 답안**")

        correct_display = get_correct_display(
            detail
        )

        if correct_display:
            st.code(
                correct_display,
                language="text",
            )
        else:
            st.warning(
                "이 문항의 모범 답안을 찾을 수 없습니다."
            )

        st.divider()

    st.subheader("제출 결과 삭제")

    delete_confirm = st.checkbox(
        "이 제출 결과를 삭제하는 것에 동의합니다.",
        key=f"delete_confirm_{record['제출번호']}",
    )

    if st.button(
        "이 제출 결과 삭제",
        key=f"delete_button_{record['제출번호']}",
        width="content",
    ):
        if not delete_confirm:
            st.warning(
                "삭제하려면 먼저 확인란을 선택해 주세요."
            )
        else:
            deleted = delete_submission(
                record["제출번호"]
            )

            if deleted:
                st.success(
                    "해당 제출 결과가 삭제되었습니다."
                )
                st.rerun()
            else:
                st.error(
                    "삭제할 제출 결과를 찾지 못했습니다."
                )


# ============================================================
# 교사용 화면
# ============================================================

def render_teacher_page():
    """교사용 결과 확인 화면을 표시합니다."""

    st.title("교사용 참고문헌 채점 결과")

    st.write(
        "비밀번호를 입력하면 제출 결과를 확인할 수 있습니다."
    )

    password = st.text_input(
        "교사 비밀번호",
        type="password",
    )

    if password != TEACHER_PASSWORD:
        if password:
            st.error("교사 비밀번호가 올바르지 않습니다.")
        else:
            st.info(
                "교사 비밀번호를 입력하면 "
                "결과를 확인할 수 있습니다."
            )

        return

    st.success("교사 페이지에 로그인했습니다.")

    filter_col1, filter_col2 = st.columns(
        [1, 2]
    )

    with filter_col1:
        class_filter = st.selectbox(
            "조회할 학급",
            ["전체"] + CLASSES,
        )

    with filter_col2:
        name_filter = st.text_input(
            "학생 이름 검색",
        )

    records = load_submissions(
        class_filter=class_filter,
        name_filter=name_filter,
    )

    if not records:
        st.info(
            "조건에 해당하는 제출 결과가 없습니다."
        )
        return

    st.divider()

    st.subheader("제출 결과")

    st.caption(
        "상세 결과를 확인하려면 학생이름이 있는 행을 클릭하세요."
    )

    summary_df = make_summary_dataframe(
        records
    )

    table_event = st.dataframe(
        summary_df,
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="teacher_summary_table",
    )

    selected_rows = []

    try:
        selected_rows = table_event.selection.rows
    except AttributeError:
        selected_rows = []

    if selected_rows:
        selected_index = selected_rows[0]

        if 0 <= selected_index < len(records):
            selected_record = records[selected_index]

            st.divider()

            render_teacher_detail(
                selected_record
            )

    st.divider()

    st.subheader("결과 다운로드")

    xls_data = make_xls_file(records)

    st.download_button(
        label="Excel XLS 파일 다운로드",
        data=xls_data,
        file_name="참고문헌_채점결과.xls",
        mime="application/vnd.ms-excel",
        width="stretch",
    )

    csv_data = summary_df.to_csv(
        index=False,
        encoding="utf-8-sig",
    )

    st.download_button(
        label="CSV 파일 다운로드",
        data=csv_data,
        file_name="참고문헌_채점결과.csv",
        mime="text/csv",
        width="stretch",
    )

    st.caption(
        "Excel 파일에는 학생별 제출 결과와 문항별 점수가 포함됩니다."
    )


# ============================================================
# 앱 실행
# ============================================================

init_database()

st.sidebar.title("메뉴")

page = st.sidebar.radio(
    "페이지 선택",
    [
        "학생용 문제 풀이",
        "교사용 결과 확인",
    ],
)

if page == "학생용 문제 풀이":
    if st.session_state["show_result"]:
        render_student_result(
            st.session_state["last_result"]
        )
    else:
        render_student_form()
else:
    render_teacher_page()
