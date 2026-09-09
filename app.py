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
                "pattern": r"전현식\.\s*$2016$",
                "error": "마지막 저자 뒤 마침표가 없습니다.",
                "penalty": 10,
            },
            {
                "pattern": r"2016$\.\s*식물생리학",
                "error": "연도 괄호 뒤 마침표가 없습니다.",
                "penalty": 10,
            },
            {
                "pattern": (
                    r"식물생리학.*?\.\s*"
                    r"(?:$주$)?라이프사이언스"
                ),
                "error": "제목 또는 판수 뒤 마침표가 없습니다.",
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
                "pattern": r"이준기\.\s*$2019$",
                "error": "마지막 저자 뒤 마침표가 없습니다.",
                "penalty": 10,
            },
            {
                "pattern": r"2019$\.\s*고등학교",
                "error": "연도 괄호 뒤 마침표가 없습니다.",
                "penalty": 10,
            },
            {
                "pattern": r"과학사\.\s*씨마스",
                "error": "제목 뒤 마침표가 없습니다.",
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
                "error": (
                    "페이지 '25-52'가 없거나 "
                    "잘못 표기되었습니다."
                ),
            },
            {
                "name": "DOI",
                "score": 10,
                "pattern": r"doi\.org/10\.30916/kera\.59\.3\.25",
                "error": (
                    "DOI 주소가 없거나 잘못 표기되었습니다."
                ),
            },
        ],
        "extra_checks": [
            {
                "pattern": r"이지영\.\s*$2021$",
                "error": "마지막 저자 뒤 마침표가 없습니다.",
                "penalty": 10,
            },
            {
                "pattern": r"교육학연구,\s*59",
                "error": "학술지명과 권호 사이 쉼표가 없습니다.",
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
        "checks": [
            {
                "name": "저자",
                "score": 20,
                "pattern": r"박지수",
                "error": (
                    "저자 '박지수'가 없거나 "
                    "잘못 표기되었습니다."
                ),
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
                "error": (
                    "신문사 '한겨레'가 없거나 "
                    "잘못 표기되었습니다."
                ),
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
                "pattern": r"박지수\.\s*$2023",
                "error": "저자 뒤 마침표가 없습니다.",
                "penalty": 10,
            },
        ],
    },
]


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
# 기본 설정
# ============================================================

st.set_page_config(
    page_title="APA 7판 참고문헌 작성 연습",
    layout="wide",
)

CLASSES = ["G", "H", "I1", "I2", "J1", "J2"]

# 교사용 페이지 비밀번호
TEACHER_PASSWORD = "1234"

# 제출 결과 저장 파일
DB_PATH = "reference_results.db"


# ============================================================
# 세션 상태 초기화
# ============================================================

if "show_result" not in st.session_state:
    st.session_state["show_result"] = False

if "last_result" not in st.session_state:
    st.session_state["last_result"] = None


# ============================================================
# 데이터베이스 함수
# ============================================================

def init_database():
    """학생 제출 결과 저장용 데이터베이스를 생성합니다."""

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
    """학생 제출 결과를 데이터베이스에 저장합니다."""

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


def load_submissions(
    class_filter="전체",
    name_filter="",
):
    """교사용 페이지에서 제출 결과를 불러옵니다."""

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
            question_no = detail["no"]

            record[f"문항 {question_no} 점수"] = detail[
                "score"
            ]

            record[f"문항 {question_no} 학생 답안"] = (
                detail["answer"]
            )

            if detail["errors"]:
                record[f"문항 {question_no} 오류"] = (
                    " | ".join(detail["errors"])
                )
            else:
                record[f"문항 {question_no} 오류"] = "없음"

        records.append(record)

    return records


# ============================================================
# XLS 파일 생성 함수
# ============================================================

def make_xls_file(records):
    """
    Excel에서 열 수 있는 XLS 파일을 생성합니다.
    """

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
# 다시 풀기 함수
# ============================================================

def retry_questions():
    """
    채점 결과를 닫고 문제 풀이 화면으로 돌아갑니다.
    기존에 입력했던 학급, 학번, 이름, 답안은 유지합니다.
    """

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
            answer_key = f"answer_{detail['id']}"

            st.session_state[answer_key] = (
                detail["answer"]
            )

    st.session_state["show_result"] = False
    st.rerun()


# ============================================================
# 학생용 문제 풀이 페이지
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
                placeholder="예: 31025",
            )

        with col3:
            student_name = st.text_input(
                "학생 이름",
                key="student_name",
                placeholder="예: 홍길동",
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
                f"작성 힌트: `{ref['format_hint']}`"
            )

            answers[ref["id"]] = st.text_area(
                "참고문헌 작성",
                key=f"answer_{ref['id']}",
                height=100,
                placeholder=(
                    "예: 저자. (연도). 제목. 출판사."
                ),
            )

            st.divider()

        submitted = st.form_submit_button(
            "전체 답안 제출 및 한 번에 채점",
            use_container_width=True,
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
    """
    학생에게 채점 결과를 표시합니다.
    모범 답안은 표시하지 않고 틀린 이유만 표시합니다.
    """

    st.title("채점 결과")

    st.info(
        "각 문항에서 틀렸거나 확인이 필요한 부분만 표시됩니다."
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "학급",
            result["class_name"],
        )

    with col2:
        st.metric(
            "학번",
            result["student_number"],
        )

    with col3:
        st.metric(
            "학생",
            result["student_name"],
        )

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
        score = detail["score"]
        errors = detail["errors"]

        with st.container(border=True):
            st.subheader(
                f"문항 {detail['no']}: "
                f"{detail['label']}"
            )

            st.write(
                f"점수: **{score} / 100점**"
            )

            if errors:
                st.markdown("**틀린 이유**")

                for error in errors:
                    st.error(error)
            else:
                st.success(
                    "이 문항은 모든 채점 기준을 통과했습니다."
                )

    st.divider()

    if st.button(
        "다시 풀기",
        use_container_width=True,
    ):
        retry_questions()


# ============================================================
# 교사용 페이지
# ============================================================

def render_teacher_page():
    """교사용 결과 확인 화면을 표시합니다."""

    st.title("교사용 참고문헌 채점 결과")

    st.write(
        "학생들의 제출 결과를 학급별로 확인하고 "
        "Excel 파일로 다운로드할 수 있습니다."
    )

    password = st.text_input(
        "교사 비밀번호",
        type="password",
        placeholder="교사 비밀번호를 입력하세요.",
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
            placeholder="검색하지 않으려면 비워 두세요.",
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

    visible_records = []

    for record in records:
        visible_record = {
            key: value
            for key, value in record.items()
            if key != "_details"
        }

        visible_records.append(visible_record)

    result_df = pd.DataFrame(
        visible_records
    )

    st.divider()

    metric_col1, metric_col2, metric_col3 = st.columns(3)

    with metric_col1:
        st.metric(
            "제출 건수",
            f"{len(result_df)}건",
        )

    with metric_col2:
        st.metric(
            "평균 점수",
            f"{result_df['총점'].mean():.1f}점",
        )

    with metric_col3:
        st.metric(
            "최고 점수",
            f"{result_df['총점'].max():.1f}점",
        )

    st.subheader("학생별 채점 결과")

    st.dataframe(
        result_df,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.subheader("학급별 통계")

    class_statistics = []

    for class_name in CLASSES:
        class_records = [
            record
            for record in records
            if record["학급"] == class_name
        ]

        if not class_records:
            continue

        class_scores = [
            record["총점"]
            for record in class_records
        ]

        class_statistics.append(
            {
                "학급": class_name,
                "제출 건수": len(class_records),
                "평균 점수": round(
                    sum(class_scores)
                    / len(class_scores),
                    1,
                ),
                "최고 점수": max(class_scores),
                "최저 점수": min(class_scores),
            }
        )

    if class_statistics:
        statistics_df = pd.DataFrame(
            class_statistics
        )

        st.dataframe(
            statistics_df,
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    st.subheader("결과 다운로드")

    xls_data = make_xls_file(records)

    st.download_button(
        label="Excel XLS 파일 다운로드",
        data=xls_data,
        file_name="참고문헌_채점결과.xls",
        mime="application/vnd.ms-excel",
        use_container_width=True,
    )

    csv_data = result_df.to_csv(
        index=False,
        encoding="utf-8-sig",
    )

    st.download_button(
        label="CSV 파일 다운로드",
        data=csv_data,
        file_name="참고문헌_채점결과.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.caption(
        "XLS 파일에는 제출일시, 학급, 학번, 학생이름, "
        "총점, 문항별 점수, 학생 답안, 오류 내용이 포함됩니다."
    )

    st.divider()

    st.subheader("제출 결과 상세 확인")

    for record in records:
        details = record.get(
            "_details",
            [],
        )

        title = (
            f"{record['제출일시']} | "
            f"{record['학급']} | "
            f"{record['학번']} | "
            f"{record['학생이름']} | "
            f"{record['총점']}점"
        )

        with st.expander(title):
            st.write(
                f"학급: **{record['학급']}**"
            )

            st.write(
                f"학번: **{record['학번']}**"
            )

            st.write(
                f"학생이름: **{record['학생이름']}**"
            )

            for detail in details:
                st.markdown(
                    f"### 문항 {detail['no']}: "
                    f"{detail['label']}"
                )

                st.write(
                    f"점수: **{detail['score']} / 100점**"
                )

                if detail["errors"]:
                    st.markdown("**틀린 이유**")

                    for error in detail["errors"]:
                        st.warning(error)
                else:
                    st.success("오류 없음")

                st.divider()


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
        result = st.session_state["last_result"]
        render_student_result(result)
    else:
        render_student_form()
else:
    render_teacher_page()
