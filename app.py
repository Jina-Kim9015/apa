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
    .ref-box {
        background: #f8f9fa;
        border-left: 4px solid #1a73e8;
        border-radius: 4px;
        padding: 1rem 1.2rem;
        font-size: 0.9rem;
        line-height: 1.9;
        margin-bottom: 1rem;
    }
    .hint-box {
        background: #e8f0fe;
        border-radius: 6px;
        padding: 0.75rem 1rem;
        font-size: 0.85rem;
        font-family: monospace;
        color: #1a56db;
        margin-bottom: 1rem;
    }
    .correct-box {
        background: #e6f4ea;
        border-radius: 6px;
        padding: 0.75rem 1rem;
        font-size: 0.85rem;
        font-family: monospace;
        color: #137333;
        margin: 0.5rem 0 1rem;
    }
    .wrong-box {
        background: #fce8e6;
        border-radius: 6px;
        padding: 0.75rem 1rem;
        font-size: 0.85rem;
        color: #c0392b;
        margin: 0.5rem 0;
    }
    div[data-testid="stSidebar"] { background: #f0f4ff; }
</style>
""", unsafe_allow_html=True)

# ─── 지정 자료 및 채점 기준 ─────────────────────────────────────
REFS = {
    "📗 도서 (Book)": {
        "id": "book",
        "fields": [
            ("저자",    "최재천"),
            ("출판연도", "2012"),
            ("제목",    "다윈 지능"),
            ("출판사",  "사이언스북스"),
        ],
        "hint": "형식: 저자. (연도). 제목. 출판사.",
        "correct_display": "최재천. (2012). 다윈 지능. 사이언스북스.",
        "checks": [
            {
                "name": "저자",
                "score": 25,
                "pattern": r"최재천",
                "error": "저자 '최재천' 이 없거나 잘못 표기되었습니다.",
            },
            {
                "name": "연도",
                "score": 25,
                "pattern": r"\(2012\)",
                "error": "출판연도가 (2012) 형식으로 없습니다.",
            },
            {
                "name": "제목",
                "score": 25,
                "pattern": r"다윈\s*지능",
                "error": "제목 '다윈 지능' 이 없거나 잘못 표기되었습니다.",
            },
            {
                "name": "출판사",
                "score": 25,
                "pattern": r"사이언스북스",
                "error": "출판사 '사이언스북스' 가 없거나 잘못 표기되었습니다.",
            },
        ],
        "extra_checks": [
            {
                "pattern": r"최재천\.\s*\(2012\)",
                "error": "저자 뒤에 마침표(.)가 있어야 합니다. 예: 최재천. (2012)",
                "penalty": 10,
            },
            {
                "pattern": r"2012\)\.\s*다윈",
                "error": "연도 괄호 뒤에 마침표(.)가 있어야 합니다. 예: (2012). 다윈",
                "penalty": 10,
            },
            {
                "pattern": r"지능\.\s*사이언스",
                "error": "제목 뒤에 마침표(.)가 있어야 합니다. 예: 다윈 지능. 사이언스북스",
                "penalty": 10,
            },
        ],
    },

    "📄 학술논문 (Journal)": {
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
        "hint": "형식: 저자. (연도). 논문제목. 학술지명, 권(호), 페이지. DOI",
        "correct_display": "김민수, 이지영. (2021). 코로나19 이후 비대면 교육의 효과성 분석. 교육학연구, 59(3), 25-52. https://doi.org/10.30916/kera.59.3.25",
        "checks": [
            {
                "name": "저자",
                "score": 15,
                "pattern": r"김민수.{0,5}이지영",
                "error": "저자 '김민수, 이지영' 이 없거나 잘못 표기되었습니다.",
            },
            {
                "name": "연도",
                "score": 15,
                "pattern": r"\(2021\)",
                "error": "출판연도가 (2021) 형식으로 없습니다.",
            },
            {
                "name": "논문제목",
                "score": 15,
                "pattern": r"코로나19\s*이후\s*비대면\s*교육의\s*효과성\s*분석",
                "error": "논문제목이 없거나 잘못 표기되었습니다.",
            },
            {
                "name": "학술지명",
                "score": 15,
                "pattern": r"교육학연구",
                "error": "학술지명 '교육학연구' 가 없거나 잘못 표기되었습니다.",
            },
            {
                "name": "권호",
                "score": 15,
                "pattern": r"59\s*\(\s*3\s*\)",
                "error": "권호가 59(3) 형식으로 없습니다.",
            },
            {
                "name": "페이지",
                "score": 15,
                "pattern": r"25[-–]52",
                "error": "페이지 '25-52' 가 없거나 잘못 표기되었습니다.",
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
                "pattern": r"이지영\.\s*\(2021\)",
                "error": "마지막 저자 뒤에 마침표(.)가 있어야 합니다. 예: 이지영. (2021)",
                "penalty": 10,
            },
            {
                "pattern": r"교육학연구,\s*59",
                "error": "학술지명과 권호 사이에 쉼표(,)가 있어야 합니다. 예: 교육학연구, 59(3)",
                "penalty": 10,
            },
        ],
    },

    "🌐 웹사이트 (Website)": {
        "id": "website",
        "fields": [
            ("저자/기관",  "한국교육개발원"),
            ("게시일",     "2023, May 10"),
            ("제목",      "2023 교육통계 연보"),
            ("웹사이트명", "한국교육개발원"),
            ("URL",       "https://kedi.re.kr/kedi/main/main.do"),
        ],
        "hint": "형식: 저자/기관. (연도, Month Day). 제목. 웹사이트명. URL",
        "correct_display": "한국교육개발원. (2023, May 10). 2023 교육통계 연보. 한국교육개발원. https://kedi.re.kr/kedi/main/main.do",
        "checks": [
            {
                "name": "저자/기관",
                "score": 20,
                "pattern": r"한국교육개발원",
                "error": "저자/기관 '한국교육개발원' 이 없거나 잘못 표기되었습니다.",
            },
            {
                "name": "연도·날짜",
                "score": 25,
                "pattern": r"\(2023,?\s*May\s*10\)",
                "error": "날짜가 (2023, May 10) 형식으로 없습니다. 월은 영어(May)로 씁니다.",
            },
            {
                "name": "제목",
                "score": 20,
                "pattern": r"2023\s*교육통계\s*연보",
                "error": "제목 '2023 교육통계 연보' 가 없거나 잘못 표기되었습니다.",
            },
            {
                "name": "웹사이트명",
                "score": 15,
                "pattern": r"한국교육개발원.{0,5}한국교육개발원",
                "error": "웹사이트명 '한국교육개발원' 이 두 번 (저자, 사이트명) 나와야 합니다.",
            },
            {
                "name": "URL",
                "score": 20,
                "pattern": r"kedi\.re\.kr",
                "error": "URL 'https://kedi.re.kr/kedi/main/main.do' 가 없거나 잘못 표기되었습니다.",
            },
        ],
        "extra_checks": [
            {
                "pattern": r"\(2023.*May.*10\)",
                "error": "날짜에 월을 숫자(5)가 아닌 영어(May)로 표기해야 합니다.",
                "penalty": 0,
            },
        ],
    },

    "📰 신문기사 (News)": {
        "id": "news",
        "fields": [
            ("기자",    "박지수"),
            ("게시일",  "2023, September 15"),
            ("기사제목", "인공지능 교육, 초등학교부터 의무화 추진"),
            ("신문사",  "한겨레"),
            ("URL",    "https://www.hani.co.kr/arti/society/education/example"),
        ],
        "hint": "형식: 저자. (연도, Month Day). 기사제목. 신문사. URL",
        "correct_display": "박지수. (2023, September 15). 인공지능 교육, 초등학교부터 의무화 추진. 한겨레. https://www.hani.co.kr/arti/society/education/example",
        "checks": [
            {
                "name": "저자",
                "score": 20,
                "pattern": r"박지수",
                "error": "저자 '박지수' 가 없거나 잘못 표기되었습니다.",
            },
            {
                "name": "날짜",
                "score": 25,
                "pattern": r"\(2023,?\s*September\s*15\)",
                "error": "날짜가 (2023, September 15) 형식으로 없습니다. 월은 영어(September)로 씁니다.",
            },
            {
                "name": "기사제목",
                "score": 20,
                "pattern": r"인공지능\s*교육.{0,5}초등학교부터\s*의무화\s*추진",
                "error": "기사제목이 없거나 잘못 표기되었습니다.",
            },
            {
                "name": "신문사",
                "score": 20,
                "pattern": r"한겨레",
                "error": "신문사 '한겨레' 가 없거나 잘못 표기되었습니다.",
            },
            {
                "name": "URL",
                "score": 15,
                "pattern": r"hani\.co\.kr",
                "error": "URL 'https://www.hani.co.kr/...' 가 없거나 잘못 표기되었습니다.",
            },
        ],
        "extra_checks": [
            {
                "pattern": r"박지수\.\s*\(2023",
                "error": "저자 뒤에 마침표(.)가 있어야 합니다. 예: 박지수. (2023",
                "penalty": 10,
            },
        ],
    },
}

ADMIN_PASSWORD = "apa2025"


# ─── 규칙 기반 채점 함수 ────────────────────────────────────────
def grade_citation(ref: dict, citation: str) -> dict:
    score = 0
    errors = []
    passed = []

    # 핵심 항목 채점
    for check in ref["checks"]:
        if re.search(check["pattern"], citation, re.IGNORECASE):
            score += check["score"]
            passed.append(check["name"])
        else:
            errors.append(check["error"])

    # 구두점 검사 (감점)
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
        feedback = f"일부 요소는 맞았지만 {', '.join([e.split(' ')[0] for e in errors[:2]])} 부분을 다시 확인해보세요."
    else:
        feedback = "APA 형식의 기본 구조부터 다시 확인해보세요. 힌트를 참고하세요."

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
            student_name  TEXT,
            ref_type      TEXT,
            citation      TEXT,
            score         INTEGER,
            is_correct    INTEGER,
            errors        TEXT,
            feedback      TEXT,
            correct_format TEXT,
            timestamp     TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_submission(sub: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO submissions VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            sub["id"], sub["student_name"], sub["ref_type"], sub["citation"],
            sub["score"], 1 if sub["is_correct"] else 0,
            json.dumps(sub["errors"], ensure_ascii=False),
            sub["feedback"], sub["correct_format"], sub["timestamp"],
        ),
    )
    conn.commit()
    conn.close()

def load_submissions() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(
            "SELECT * FROM submissions ORDER BY timestamp DESC", conn
        )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

init_db()


# ─── 사이드바 ──────────────────────────────────────────────────
st.sidebar.title("📚 APA 7판 실습")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "메뉴",
    ["✏️ 학생 실습", "📊 관리자 대시보드"],
    label_visibility="collapsed",
)
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
    st.caption("아래 자료 정보를 보고 APA 7판 형식에 맞게 참고문헌을 작성하세요.")

    student_name = st.text_input("👤 학생 이름", placeholder="이름을 입력하세요", max_chars=30)
    st.markdown("---")

    ref_label = st.selectbox("📂 자료 유형 선택", list(REFS.keys()))
    ref = REFS[ref_label]

    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("📋 자료 정보")
        fields_html = "".join(
            f"<div><b style='color:#555;min-width:90px;display:inline-block'>{k}</b> {v}</div>"
            for k, v in ref["fields"]
        )
        st.markdown(f'<div class="ref-box">{fields_html}</div>', unsafe_allow_html=True)

        with st.expander("💡 힌트 보기"):
            st.markdown(f'<div class="hint-box">{ref["hint"]}</div>', unsafe_allow_html=True)
            st.caption("이탤릭체는 *별표* 로 표시하거나 생략해도 채점에 반영합니다.")

    with col2:
        st.subheader("✍️ 내 APA 참고문헌 작성")
        citation = st.text_area(
            "APA 형식으로 작성하세요",
            placeholder="여기에 APA 참고문헌을 작성하세요...",
            height=140,
            label_visibility="collapsed",
        )
        submitted = st.button("🔍 채점하기", type="primary", use_container_width=True)

    if submitted:
        if not student_name.strip():
            st.warning("⚠️ 이름을 먼저 입력해주세요.")
            st.stop()
        if not citation.strip():
            st.warning("⚠️ 참고문헌을 작성해주세요.")
            st.stop()

        result = grade_citation(ref, citation)

        st.markdown("---")
        st.subheader("📝 채점 결과")

        score = result["score"]
        is_correct = result["is_correct"]

        r1, r2 = st.columns([1, 3])
        with r1:
            color = "#137333" if score >= 85 else ("#b45309" if score >= 60 else "#c0392b")
            st.markdown(
                f'<p style="font-size:2.5rem;font-weight:700;color:{color};margin:0">'
                f'{score}<span style="font-size:1rem;font-weight:400;color:#888"> / 100</span></p>',
                unsafe_allow_html=True,
            )
            badge = "✅ 정답" if is_correct else "❌ 오답"
            badge_style = "background:#e6f4ea;color:#137333" if is_correct else "background:#fce8e6;color:#c0392b"
            st.markdown(
                f'<span style="{badge_style};padding:4px 12px;border-radius:12px;font-size:0.85rem;font-weight:600">{badge}</span>',
                unsafe_allow_html=True,
            )

        with r2:
            if result["passed"]:
                st.markdown("**✅ 맞은 항목:** " + " · ".join(result["passed"]))
            if result["errors"]:
                st.markdown("**❌ 틀린 부분**")
                for e in result["errors"]:
                    st.markdown(f"- {e}")

        st.markdown("**올바른 형식**")
        st.markdown(
            f'<div class="correct-box">{result["correct_format"]}</div>',
            unsafe_allow_html=True,
        )
        st.info(f"💬 {result['feedback']}")

        sub = {
            "id": str(uuid.uuid4()),
            "student_name": student_name.strip(),
            "ref_type": ref_label,
            "citation": citation,
            "score": score,
            "is_correct": is_correct,
            "errors": result["errors"],
            "feedback": result["feedback"],
            "correct_format": result["correct_format"],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        save_submission(sub)
        st.success("✔ 제출 완료! 관리자 대시보드에 기록되었습니다.")


# ═══════════════════════════════════════════════════════════════
# 관리자 대시보드 페이지
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
    passed    = int(df["is_correct"].sum())
    avg_score = int(df["score"].mean())
    pass_rate = int(passed / total * 100)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 제출 수",  total)
    c2.metric("정답 수",     passed)
    c3.metric("평균 점수",   avg_score)
    c4.metric("정답률",      f"{pass_rate}%")

    st.markdown("---")

    type_filter = st.multiselect(
        "유형 필터",
        options=df["ref_type"].unique().tolist(),
        default=df["ref_type"].unique().tolist(),
    )
    filtered = df[df["ref_type"].isin(type_filter)].copy()

    display = filtered[["timestamp", "student_name", "ref_type", "score", "is_correct"]].copy()
    display.columns = ["제출 시간", "학생 이름", "유형", "점수", "정답여부"]
    display["정답여부"] = display["정답여부"].map({1: "✅ 정답", 0: "❌ 오답"})
    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("🔎 학생별 상세 보기")
    names = filtered["student_name"].unique().tolist()
    sel_name = st.selectbox("학생 선택", ["(선택)"] + names)

    if sel_name != "(선택)":
        for _, row in filtered[filtered["student_name"] == sel_name].iterrows():
            with st.expander(f"{row['ref_type']}  |  {row['score']}점  |  {row['timestamp']}"):
                st.markdown(f"**작성 내용:** {row['citation']}")
                st.markdown(f"**올바른 형식:** `{row['correct_format']}`")
                errs = json.loads(row["errors"]) if row["errors"] else []
                if errs:
                    for e in errs:
                        st.markdown(f"- {e}")
                st.info(f"💬 {row['feedback']}")

    st.markdown("---")
    csv = filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ 전체 결과 CSV 다운로드",
        data=csv,
        file_name=f"apa_submissions_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        use_container_width=True,
    )
