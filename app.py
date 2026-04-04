import streamlit as st
import sqlite3
import json
import pandas as pd
import uuid
import re
from datetime import datetime

# ─── 페이지 설정 ───────────────────────────────────────────────
st.set_page_config(
    page_title="APA 7판 참고문헌 실습",
    page_icon="📚",
    layout="wide",
)

st.markdown("""
<style>
    .question-header {
        background: #1a73e8;
        color: white;
        border-radius: 8px 8px 0 0;
        padding: 0.6rem 1.2rem;
        font-size: 1rem;
        font-weight: 700;
        margin-bottom: 0;
    }
    .question-body {
        border: 2px solid #1a73e8;
        border-top: none;
        border-radius: 0 0 8px 8px;
        padding: 1.2rem;
        margin-bottom: 2rem;
    }
    .format-box {
        background: #e8f0fe;
        border-radius: 6px;
        padding: 0.65rem 1rem;
        font-size: 0.88rem;
        font-family: monospace;
        color: #1a56db;
        margin-bottom: 1rem;
    }
    .ref-box {
        background: #f8f9fa;
        border-left: 4px solid #1a73e8;
        border-radius: 4px;
        padding: 0.8rem 1.1rem;
        font-size: 0.88rem;
        line-height: 1.9;
        margin-bottom: 0.8rem;
    }
    .correct-box {
        background: #e6f4ea;
        border-radius: 6px;
        padding: 0.65rem 1rem;
        font-size: 0.88rem;
        font-family: monospace;
        color: #137333;
        margin: 0.4rem 0 0.8rem;
    }
    .wrong-box {
        background: #fce8e6;
        border-radius: 6px;
        padding: 0.65rem 1rem;
        font-size: 0.88rem;
        color: #c0392b;
        margin: 0.4rem 0;
    }
    .result-header {
        background: #34a853;
        color: white;
        border-radius: 8px 8px 0 0;
        padding: 0.6rem 1.2rem;
        font-size: 1rem;
        font-weight: 700;
    }
    .result-body {
        border: 2px solid #34a853;
        border-top: none;
        border-radius: 0 0 8px 8px;
        padding: 1.2rem;
        margin-bottom: 2rem;
    }
    .result-header-fail {
        background: #ea4335;
        color: white;
        border-radius: 8px 8px 0 0;
        padding: 0.6rem 1.2rem;
        font-size: 1rem;
        font-weight: 700;
    }
    .result-body-fail {
        border: 2px solid #ea4335;
        border-top: none;
        border-radius: 0 0 8px 8px;
        padding: 1.2rem;
        margin-bottom: 2rem;
    }
    div[data-testid="stSidebar"] { background: #f0f4ff; }
    .student-info-box {
        background: #f0f4ff;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin-bottom: 1.5rem;
        border: 1px solid #c7d9f8;
    }
</style>
""", unsafe_allow_html=True)

# ─── 지정 자료 및 채점 기준 ─────────────────────────────────────
REFS = [
    {
        "no": 1,
        "label": "도서 (Book)",
        "id": "book",
        "fields": [
            ("저자",    "최재천"),
            ("출판연도", "2012"),
            ("제목",    "다윈 지능"),
            ("출판사",  "사이언스북스"),
        ],
        "format_hint": "저자. (출판연도). 제목. 출판사.",
        "correct_display": "최재천. (2012). 다윈 지능. 사이언스북스.",
        "checks": [
            {"name": "저자",    "score": 25, "pattern": r"최재천",      "error": "저자 '최재천'이 없거나 잘못 표기되었습니다."},
            {"name": "연도",    "score": 25, "pattern": r"\(2012\)",    "error": "출판연도가 (2012) 형식으로 없습니다."},
            {"name": "제목",    "score": 25, "pattern": r"다윈\s*지능", "error": "제목 '다윈 지능'이 없거나 잘못 표기되었습니다."},
            {"name": "출판사",  "score": 25, "pattern": r"사이언스북스", "error": "출판사 '사이언스북스'가 없거나 잘못 표기되었습니다."},
        ],
        "extra_checks": [
            {"pattern": r"최재천\.\s*\(2012\)",  "error": "저자 뒤 마침표가 없습니다. 예: 최재천. (2012)", "penalty": 10},
            {"pattern": r"2012\)\.\s*다윈",      "error": "연도 괄호 뒤 마침표가 없습니다. 예: (2012). 다윈", "penalty": 10},
            {"pattern": r"지능\.\s*사이언스",    "error": "제목 뒤 마침표가 없습니다. 예: 다윈 지능. 사이언스북스", "penalty": 10},
        ],
    },
    {
        "no": 2,
        "label": "학술논문 (Journal)",
        "id": "journal",
        "fields": [
            ("저자",    "김민수, 이지영"),
            ("출판연도", "2021"),
            ("논문제목", "코로나19 이후 비대면 교육의 효과성 분석"),
            ("학술지명", "교육학연구"),
            ("권(호)",  "59(3)"),
            ("페이지",  "25-52"),
            ("DOI",    "https://doi.org/10.30916/kera.59.3.25"),
        ],
        "format_hint": "저자. (출판연도). 논문제목. 학술지명, 권(호), 페이지. DOI",
        "correct_display": "김민수, 이지영. (2021). 코로나19 이후 비대면 교육의 효과성 분석. 교육학연구, 59(3), 25-52. https://doi.org/10.30916/kera.59.3.25",
        "checks": [
            {"name": "저자",    "score": 15, "pattern": r"김민수.{0,5}이지영",                                    "error": "저자 '김민수, 이지영'이 없거나 잘못 표기되었습니다."},
            {"name": "연도",    "score": 15, "pattern": r"\(2021\)",                                              "error": "출판연도가 (2021) 형식으로 없습니다."},
            {"name": "논문제목","score": 15, "pattern": r"코로나19\s*이후\s*비대면\s*교육의\s*효과성\s*분석",     "error": "논문제목이 없거나 잘못 표기되었습니다."},
            {"name": "학술지명","score": 15, "pattern": r"교육학연구",                                            "error": "학술지명 '교육학연구'가 없거나 잘못 표기되었습니다."},
            {"name": "권호",    "score": 15, "pattern": r"59\s*\(\s*3\s*\)",                                      "error": "권호가 59(3) 형식으로 없습니다."},
            {"name": "페이지",  "score": 15, "pattern": r"25[-–]52",                                              "error": "페이지 '25-52'가 없거나 잘못 표기되었습니다."},
            {"name": "DOI",     "score": 10, "pattern": r"doi\.org/10\.30916/kera\.59\.3\.25",                    "error": "DOI 주소가 없거나 잘못 표기되었습니다."},
        ],
        "extra_checks": [
            {"pattern": r"이지영\.\s*\(2021\)", "error": "마지막 저자 뒤 마침표가 없습니다. 예: 이지영. (2021)", "penalty": 10},
            {"pattern": r"교육학연구,\s*59",    "error": "학술지명과 권호 사이 쉼표가 없습니다. 예: 교육학연구, 59(3)", "penalty": 10},
        ],
    },
    {
        "no": 3,
        "label": "웹사이트 (Website)",
        "id": "website",
        "fields": [
            ("저자/기관",  "한국교육개발원"),
            ("게시일",     "2023, May 10"),
            ("제목",      "2023 교육통계 연보"),
            ("웹사이트명", "한국교육개발원"),
            ("URL",       "https://kedi.re.kr/kedi/main/main.do"),
        ],
        "format_hint": "저자/기관. (연도, Month Day). 제목. 웹사이트명. URL",
        "correct_display": "한국교육개발원. (2023, May 10). 2023 교육통계 연보. 한국교육개발원. https://kedi.re.kr/kedi/main/main.do",
        "checks": [
            {"name": "저자/기관", "score": 20, "pattern": r"한국교육개발원",              "error": "저자/기관 '한국교육개발원'이 없거나 잘못 표기되었습니다."},
            {"name": "날짜",      "score": 25, "pattern": r"\(2023,?\s*May\s*10\)",       "error": "날짜가 (2023, May 10) 형식으로 없습니다. 월은 영어(May)로 씁니다."},
            {"name": "제목",      "score": 20, "pattern": r"2023\s*교육통계\s*연보",      "error": "제목 '2023 교육통계 연보'가 없거나 잘못 표기되었습니다."},
            {"name": "웹사이트명","score": 15, "pattern": r"한국교육개발원.{1,30}한국교육개발원", "error": "웹사이트명 '한국교육개발원'이 저자와 웹사이트명으로 두 번 나와야 합니다."},
            {"name": "URL",       "score": 20, "pattern": r"kedi\.re\.kr",                "error": "URL 'https://kedi.re.kr/...'이 없거나 잘못 표기되었습니다."},
        ],
        "extra_checks": [],
    },
    {
        "no": 4,
        "label": "신문기사 (News)",
        "id": "news",
        "fields": [
            ("기자",    "박지수"),
            ("게시일",  "2023, September 15"),
            ("기사제목", "인공지능 교육, 초등학교부터 의무화 추진"),
            ("신문사",  "한겨레"),
            ("URL",    "https://www.hani.co.kr/arti/society/education/example"),
        ],
        "format_hint": "저자. (연도, Month Day). 기사제목. 신문사. URL",
        "correct_display": "박지수. (2023, September 15). 인공지능 교육, 초등학교부터 의무화 추진. 한겨레. https://www.hani.co.kr/arti/society/education/example",
        "checks": [
            {"name": "저자",    "score": 20, "pattern": r"박지수",                                          "error": "저자 '박지수'가 없거나 잘못 표기되었습니다."},
            {"name": "날짜",    "score": 25, "pattern": r"\(2023,?\s*September\s*15\)",                     "error": "날짜가 (2023, September 15) 형식으로 없습니다. 월은 영어(September)로 씁니다."},
            {"name": "기사제목","score": 20, "pattern": r"인공지능\s*교육.{0,5}초등학교부터\s*의무화\s*추진","error": "기사제목이 없거나 잘못 표기되었습니다."},
            {"name": "신문사",  "score": 20, "pattern": r"한겨레",                                          "error": "신문사 '한겨레'가 없거나 잘못 표기되었습니다."},
            {"name": "URL",     "score": 15, "pattern": r"hani\.co\.kr",                                    "error": "URL 'https://www.hani.co.kr/...'이 없거나 잘못 표기되었습니다."},
        ],
        "extra_checks": [
            {"pattern": r"박지수\.\s*\(2023", "error": "저자 뒤 마침표가 없습니다. 예: 박지수. (2023", "penalty": 10},
        ],
    },
]

ADMIN_PASSWORD = "apa2025"

# ─── 채점 함수 ─────────────────────────────────────────────────
def grade_citation(ref: dict, citation: str) -> dict:
    score = 0
    errors = []
    passed = []

    for check in ref["checks"]:
        if re.search(check["pattern"], citation, re.IGNORECASE):
            score += check["score"]
            passed.append(check["name"])
        else:
            errors.append(check["error"])

    penalty = 0
    for ec in ref.get("extra_checks", []):
        if not re.search(ec["pattern"], citation, re.IGNORECASE):
            if ec["penalty"] > 0:
                penalty += ec["penalty"]
                errors.append(ec["error"])

    score = max(0, score - penalty)
    is_correct = score >= 85

    if is_correct:
        feedback = "훌륭합니다! APA 형식의 핵심 요소를 모두 정확하게 작성했습니다."
    elif score >= 60:
        feedback = f"일부 요소는 맞았지만 아래 오류를 다시 확인해보세요."
    else:
        feedback = "APA 형식의 기본 구조부터 다시 확인해보세요."

    return {
        "score": score,
        "is_correct": is_correct,
        "errors": errors,
        "passed": passed,
        "feedback": feedback,
        "correct_format": ref["correct_display"],
    }

# ─── 데이터베이스 ───────────────────────────────────────────────
DB_PATH = "submissions.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id            TEXT PRIMARY KEY,
            student_class TEXT,
            student_id    TEXT,
            student_name  TEXT,
            q1_citation   TEXT,
            q1_score      INTEGER,
            q1_correct    INTEGER,
            q1_errors     TEXT,
            q2_citation   TEXT,
            q2_score      INTEGER,
            q2_correct    INTEGER,
            q2_errors     TEXT,
            q3_citation   TEXT,
            q3_score      INTEGER,
            q3_correct    INTEGER,
            q3_errors     TEXT,
            q4_citation   TEXT,
            q4_score      INTEGER,
            q4_correct    INTEGER,
            q4_errors     TEXT,
            total_score   INTEGER,
            timestamp     TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_submission(sub: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT OR REPLACE INTO submissions VALUES
        (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            sub["id"],
            sub["student_class"], sub["student_id"], sub["student_name"],
            sub["q1_citation"], sub["q1_score"], sub["q1_correct"], json.dumps(sub["q1_errors"], ensure_ascii=False),
            sub["q2_citation"], sub["q2_score"], sub["q2_correct"], json.dumps(sub["q2_errors"], ensure_ascii=False),
            sub["q3_citation"], sub["q3_score"], sub["q3_correct"], json.dumps(sub["q3_errors"], ensure_ascii=False),
            sub["q4_citation"], sub["q4_score"], sub["q4_correct"], json.dumps(sub["q4_errors"], ensure_ascii=False),
            sub["total_score"], sub["timestamp"],
        ),
    )
    conn.commit()
    conn.close()

def load_submissions() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query("SELECT * FROM submissions ORDER BY timestamp DESC", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

init_db()

# ─── 사이드바 ──────────────────────────────────────────────────
st.sidebar.title("📚 APA 7판 실습")
st.sidebar.markdown("---")
page = st.sidebar.radio("메뉴", ["✏️ 학생 실습", "📊 관리자 대시보드"], label_visibility="collapsed")
st.sidebar.markdown("---")
st.sidebar.markdown("**APA 7판 주요 규칙**")
st.sidebar.markdown("""
- 저자 뒤 마침표 → `저자.`
- 연도는 괄호 → `(2012).`
- 제목·학술지·신문사 → *이탤릭*
- 학술지: 권(호), 페이지
- 웹·기사: `(연도, Month Day)`
- 월은 반드시 **영어**로
""")

# ═══════════════════════════════════════════════════════════════
# 학생 실습 페이지
# ═══════════════════════════════════════════════════════════════
if page == "✏️ 학생 실습":
    st.title("✏️ APA 7판 참고문헌 실습")
    st.caption("4가지 자료를 모두 APA 7판 형식에 맞게 작성한 후 제출하세요.")

    # 학생 정보
    st.markdown('<div class="student-info-box">', unsafe_allow_html=True)
    st.markdown("**👤 학생 정보 입력**")
    ci1, ci2, ci3 = st.columns(3)
    with ci1:
        student_class = st.text_input("수업반", placeholder="예: 교육학과 3학년 A반", max_chars=30)
    with ci2:
        student_id = st.text_input("학번", placeholder="예: 20231234", max_chars=20)
    with ci3:
        student_name = st.text_input("이름", placeholder="예: 홍길동", max_chars=20)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")

    # 4문항 입력
    citations = {}
    for ref in REFS:
        no = ref["no"]
        st.markdown(f'<div class="question-header">문항 {no}. {ref["label"]}</div>', unsafe_allow_html=True)
        st.markdown('<div class="question-body">', unsafe_allow_html=True)

        # APA 양식 안내
        st.markdown(f"**📌 APA 작성 양식**")
        st.markdown(f'<div class="format-box">{ref["format_hint"]}</div>', unsafe_allow_html=True)

        # 자료 정보 + 입력란 나란히
        col1, col2 = st.columns([1, 1], gap="large")
        with col1:
            st.markdown("**📋 자료 정보**")
            fields_html = "".join(
                f"<div><b style='color:#555;min-width:80px;display:inline-block'>{k}</b> {v}</div>"
                for k, v in ref["fields"]
            )
            st.markdown(f'<div class="ref-box">{fields_html}</div>', unsafe_allow_html=True)

        with col2:
            st.markdown("**✍️ 내 APA 참고문헌**")
            citations[no] = st.text_area(
                f"q{no}",
                placeholder="여기에 작성하세요...",
                height=130,
                label_visibility="collapsed",
                key=f"citation_{no}",
            )

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    submitted = st.button("📤 전체 제출 및 채점", type="primary", use_container_width=True)

    if submitted:
        # 유효성 검사
        if not student_class.strip() or not student_id.strip() or not student_name.strip():
            st.warning("⚠️ 수업반, 학번, 이름을 모두 입력해주세요.")
            st.stop()
        empty = [f"{r['no']}번" for r in REFS if not citations.get(r["no"], "").strip()]
        if empty:
            st.warning(f"⚠️ {', '.join(empty)} 문항이 비어 있습니다. 모두 작성해주세요.")
            st.stop()

        # 채점
        results = {}
        for ref in REFS:
            results[ref["no"]] = grade_citation(ref, citations[ref["no"]])

        total_score = int(sum(r["score"] for r in results.values()) / 4)

        # 결과 출력
        st.markdown("---")
        st.subheader("📝 채점 결과")

        # 총점 요약
        tc1, tc2, tc3, tc4, tc5 = st.columns(5)
        score_color = "#137333" if total_score >= 85 else ("#b45309" if total_score >= 60 else "#c0392b")
        tc1.metric("총점 (평균)", f"{total_score}점")
        for i, ref in enumerate(REFS):
            r = results[ref["no"]]
            [tc2, tc3, tc4, tc5][i].metric(
                f"{ref['no']}번 {ref['label'].split()[0]}",
                f"{r['score']}점",
                "✅ 정답" if r["is_correct"] else "❌ 오답",
            )

        st.markdown("---")

        # 문항별 상세 결과
        for ref in REFS:
            r = results[ref["no"]]
            is_correct = r["is_correct"]
            hdr_cls = "result-header" if is_correct else "result-header-fail"
            body_cls = "result-body" if is_correct else "result-body-fail"
            badge = "✅ 정답" if is_correct else "❌ 오답"

            st.markdown(
                f'<div class="{hdr_cls}">문항 {ref["no"]}. {ref["label"]} — {r["score"]}점 {badge}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(f'<div class="{body_cls}">', unsafe_allow_html=True)

            if r["passed"]:
                st.markdown("✅ **맞은 항목:** " + " · ".join(r["passed"]))
            if r["errors"]:
                st.markdown("❌ **틀린 부분:**")
                for e in r["errors"]:
                    st.markdown(f"- {e}")

            st.markdown("**올바른 형식:**")
            st.markdown(f'<div class="correct-box">{r["correct_format"]}</div>', unsafe_allow_html=True)
            st.info(f"💬 {r['feedback']}")
            st.markdown('</div>', unsafe_allow_html=True)

        # DB 저장
        sub = {
            "id": str(uuid.uuid4()),
            "student_class": student_class.strip(),
            "student_id": student_id.strip(),
            "student_name": student_name.strip(),
            "q1_citation": citations[1], "q1_score": results[1]["score"], "q1_correct": results[1]["is_correct"], "q1_errors": results[1]["errors"],
            "q2_citation": citations[2], "q2_score": results[2]["score"], "q2_correct": results[2]["is_correct"], "q2_errors": results[2]["errors"],
            "q3_citation": citations[3], "q3_score": results[3]["score"], "q3_correct": results[3]["is_correct"], "q3_errors": results[3]["errors"],
            "q4_citation": citations[4], "q4_score": results[4]["score"], "q4_correct": results[4]["is_correct"], "q4_errors": results[4]["errors"],
            "total_score": total_score,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        save_submission(sub)
        st.success("✔ 제출 완료! 관리자 대시보드에 기록되었습니다.")

# ═══════════════════════════════════════════════════════════════
# 관리자 대시보드
# ═══════════════════════════════════════════════════════════════
else:
    st.title("📊 관리자 대시보드")

    if "admin_auth" not in st.session_state:
        st.session_state.admin_auth = False

    if not st.session_state.admin_auth:
        st.markdown("### 🔒 관리자 로그인")
        pw = st.text_input("비밀번호", type="password")
        if st.button("로그인", type="primary"):
            if pw == ADMIN_PASSWORD:
                st.session_state.admin_auth = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
        st.stop()

    if st.button("로그아웃"):
        st.session_state.admin_auth = False
        st.rerun()

    df = load_submissions()

    if df.empty:
        st.info("아직 제출된 답안이 없습니다.")
        st.stop()

    total     = len(df)
    avg_total = int(df["total_score"].mean())
    avg_q1    = int(df["q1_score"].mean())
    avg_q2    = int(df["q2_score"].mean())
    avg_q3    = int(df["q3_score"].mean())
    avg_q4    = int(df["q4_score"].mean())

    st.markdown("#### 📈 전체 현황")
    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    mc1.metric("총 제출 수",   total)
    mc2.metric("평균 총점",    f"{avg_total}점")
    mc3.metric("1번 평균",     f"{avg_q1}점")
    mc4.metric("2번 평균",     f"{avg_q2}점")
    mc5.metric("3번·4번 평균", f"{int((avg_q3+avg_q4)/2)}점")

    st.markdown("---")

    # 반별 필터
    classes = df["student_class"].unique().tolist()
    class_filter = st.multiselect("수업반 필터", options=classes, default=classes)
    filtered = df[df["student_class"].isin(class_filter)].copy()

    # 목록 테이블
    display = filtered[[
        "timestamp", "student_class", "student_id", "student_name",
        "total_score", "q1_score", "q2_score", "q3_score", "q4_score",
        "q1_correct", "q2_correct", "q3_correct", "q4_correct",
    ]].copy()
    display.columns = [
        "제출 시간", "수업반", "학번", "이름",
        "총점", "1번", "2번", "3번", "4번",
        "1번정답", "2번정답", "3번정답", "4번정답",
    ]
    for col in ["1번정답","2번정답","3번정답","4번정답"]:
        display[col] = display[col].map({1:"✅", 0:"❌"})

    st.dataframe(display, use_container_width=True, hide_index=True)

    # 학생 상세
    st.markdown("---")
    st.subheader("🔎 학생별 상세 보기")
    student_options = filtered.apply(lambda r: f"{r['student_class']} / {r['student_id']} / {r['student_name']}", axis=1).tolist()
    sel = st.selectbox("학생 선택", ["(선택)"] + student_options)

    if sel != "(선택)":
        idx = student_options.index(sel)
        row = filtered.iloc[idx]
        for i, ref in enumerate(REFS, 1):
            with st.expander(f"문항 {i}. {ref['label']} — {row[f'q{i}_score']}점 {'✅' if row[f'q{i}_correct'] else '❌'}"):
                st.markdown(f"**작성 내용:** {row[f'q{i}_citation']}")
                st.markdown(f"**올바른 형식:** `{ref['correct_display']}`")
                errs = json.loads(row[f"q{i}_errors"]) if row[f"q{i}_errors"] else []
                for e in errs:
                    st.markdown(f"- {e}")

    # CSV 다운로드
    st.markdown("---")
    csv = filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ 전체 결과 CSV 다운로드",
        data=csv,
        file_name=f"apa_submissions_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        use_container_width=True,
    )
