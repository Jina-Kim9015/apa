import streamlit as st
import anthropic
import sqlite3
import json
import pandas as pd
import uuid
from datetime import datetime
import os

# ─── 페이지 설정 ───────────────────────────────────────────────
st.set_page_config(
    page_title="APA 7판 참고문헌 실습",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 스타일 ────────────────────────────────────────────────────
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
    .score-pass { color: #137333; font-weight: 700; font-size: 2rem; }
    .score-mid  { color: #b45309; font-weight: 700; font-size: 2rem; }
    .score-fail { color: #c0392b; font-weight: 700; font-size: 2rem; }
    .badge-pass { background:#e6f4ea; color:#137333; padding:3px 10px; border-radius:12px; font-size:0.8rem; font-weight:600; }
    .badge-fail { background:#fce8e6; color:#c0392b; padding:3px 10px; border-radius:12px; font-size:0.8rem; font-weight:600; }
    .stTextArea textarea { font-size: 0.95rem; }
    div[data-testid="stSidebar"] { background: #f0f4ff; }
</style>
""", unsafe_allow_html=True)

# ─── 지정 자료 ─────────────────────────────────────────────────
REFS = {
    "📗 도서 (Book)": {
        "id": "book",
        "fields": [
            ("저자",    "최재천"),
            ("출판연도", "2012"),
            ("제목",    "다윈 지능"),
            ("출판사",  "사이언스북스"),
        ],
        "hint":    "형식: 저자. (연도). *제목*. 출판사.",
        "correct": "최재천. (2012). 다윈 지능. 사이언스북스.",
        "correct_display": "최재천. (2012). <i>다윈 지능</i>. 사이언스북스.",
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
        "hint":    "형식: 저자. (연도). 논문제목. *학술지명*, *권*(호), 페이지. DOI",
        "correct": "김민수, 이지영. (2021). 코로나19 이후 비대면 교육의 효과성 분석. 교육학연구, 59(3), 25-52. https://doi.org/10.30916/kera.59.3.25",
        "correct_display": "김민수, 이지영. (2021). 코로나19 이후 비대면 교육의 효과성 분석. <i>교육학연구</i>, <i>59</i>(3), 25-52. https://doi.org/10.30916/kera.59.3.25",
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
        "hint":    "형식: 저자/기관. (연도, Month Day). *제목*. 웹사이트명. URL",
        "correct": "한국교육개발원. (2023, May 10). 2023 교육통계 연보. 한국교육개발원. https://kedi.re.kr/kedi/main/main.do",
        "correct_display": "한국교육개발원. (2023, May 10). <i>2023 교육통계 연보</i>. 한국교육개발원. https://kedi.re.kr/kedi/main/main.do",
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
        "hint":    "형식: 저자. (연도, Month Day). 기사제목. *신문사*. URL",
        "correct": "박지수. (2023, September 15). 인공지능 교육, 초등학교부터 의무화 추진. 한겨레. https://www.hani.co.kr/arti/society/education/example",
        "correct_display": "박지수. (2023, September 15). 인공지능 교육, 초등학교부터 의무화 추진. <i>한겨레</i>. https://www.hani.co.kr/arti/society/education/example",
    },
}

ADMIN_PASSWORD = "apa2025"

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

# ─── Claude API 채점 ───────────────────────────────────────────
def check_citation(ref_label: str, ref: dict, citation: str) -> dict:
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        return {"error": "API 키가 설정되지 않았습니다. Streamlit Secrets에서 ANTHROPIC_API_KEY를 설정하세요."}

    client = anthropic.Anthropic(api_key=api_key)

    fields_str = "\n".join(f"{k}: {v}" for k, v in ref["fields"])

    system = """당신은 APA 7판 참고문헌 형식 전문가입니다.
반드시 아래 JSON만 응답하세요 (마크다운 없이, 다른 텍스트 없이):
{"score":0~100,"isCorrect":true/false,"correctFormat":"올바른 형식(이탤릭은 * *로)","errors":["오류1","오류2"],"feedback":"한국어 총평 1~2문장"}
isCorrect는 score가 85 이상이고 핵심 요소가 모두 맞을 때 true입니다."""

    user = f"""자료 유형: {ref_label}
자료 정보:
{fields_str}

학생 작성 APA:
{citation}

올바른 답안(참고용):
{ref['correct']}"""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        raw = msg.content[0].text.strip().replace("```json", "").replace("```", "")
        return json.loads(raw)
    except Exception as e:
        return {"error": f"채점 중 오류 발생: {str(e)}"}


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
- 저자 성 뒤에 이니셜 → 한국어는 전체 이름
- 연도는 괄호 `(연도).`
- 제목·학술지·신문사 → *이탤릭*
- 학술지: *권*, (호), 페이지
- 웹·기사: 날짜 `(연도, Month Day)`
""")


# ═══════════════════════════════════════════════════════════════
# 학생 실습 페이지
# ═══════════════════════════════════════════════════════════════
if page == "✏️ 학생 실습":
    st.title("✏️ APA 7판 참고문헌 실습")
    st.caption("아래 자료 정보를 보고 APA 7판 형식에 맞게 참고문헌을 작성하세요.")

    # 학생 이름
    student_name = st.text_input("👤 학생 이름", placeholder="이름을 입력하세요", max_chars=30)
    st.markdown("---")

    # 자료 유형 선택
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

        with st.spinner("Claude가 채점 중입니다..."):
            result = check_citation(ref_label, ref, citation)

        if "error" in result:
            st.error(result["error"])
            st.stop()

        # 결과 표시
        st.markdown("---")
        st.subheader("📝 채점 결과")

        score = result.get("score", 0)
        is_correct = result.get("isCorrect", False)
        score_class = "score-pass" if score >= 85 else ("score-mid" if score >= 60 else "score-fail")
        badge_class = "badge-pass" if is_correct else "badge-fail"
        badge_text = "✅ 정답" if is_correct else "❌ 오답"

        r1, r2, r3 = st.columns([1, 1, 2])
        with r1:
            st.markdown(f'<p class="{score_class}">{score}<span style="font-size:1rem;font-weight:400;color:#888"> / 100</span></p>', unsafe_allow_html=True)
            st.caption("점수")
        with r2:
            st.markdown(f'<br><span class="{badge_class}">{badge_text}</span>', unsafe_allow_html=True)
        with r3:
            errors = result.get("errors", [])
            if errors:
                st.markdown("**발견된 오류**")
                for e in errors:
                    st.markdown(f"- {e}")

        st.markdown("**올바른 형식**")
        st.markdown(
            f'<div class="correct-box">{result.get("correctFormat","")}</div>',
            unsafe_allow_html=True,
        )
        st.info(f"💬 {result.get('feedback','')}")

        # DB 저장
        sub = {
            "id": str(uuid.uuid4()),
            "student_name": student_name.strip(),
            "ref_type": ref_label,
            "citation": citation,
            "score": score,
            "is_correct": is_correct,
            "errors": errors,
            "feedback": result.get("feedback", ""),
            "correct_format": result.get("correctFormat", ""),
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

    # 로그아웃
    if st.button("로그아웃"):
        st.session_state.admin_auth = False
        st.rerun()

    df = load_submissions()

    if df.empty:
        st.info("아직 제출된 답안이 없습니다.")
        st.stop()

    # 통계 카드
    total   = len(df)
    passed  = int(df["is_correct"].sum())
    avg_score = int(df["score"].mean())
    pass_rate = int(passed / total * 100)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 제출 수",  total)
    c2.metric("정답 수",     passed,  f"{pass_rate}%")
    c3.metric("평균 점수",   avg_score)
    c4.metric("정답률",      f"{pass_rate}%")

    st.markdown("---")

    # 유형별 필터
    type_filter = st.multiselect(
        "유형 필터",
        options=df["ref_type"].unique().tolist(),
        default=df["ref_type"].unique().tolist(),
    )
    filtered = df[df["ref_type"].isin(type_filter)].copy()

    # 테이블 표시
    display = filtered[["timestamp","student_name","ref_type","score","is_correct"]].copy()
    display.columns = ["제출 시간","학생 이름","유형","점수","정답여부"]
    display["정답여부"] = display["정답여부"].map({1:"✅ 정답", 0:"❌ 오답"})

    st.dataframe(display, use_container_width=True, hide_index=True)

    # 상세 보기
    st.markdown("---")
    st.subheader("🔎 개별 상세 보기")
    names = filtered["student_name"].unique().tolist()
    sel_name = st.selectbox("학생 선택", ["(선택)"] + names)

    if sel_name != "(선택)":
        student_rows = filtered[filtered["student_name"] == sel_name]
        for _, row in student_rows.iterrows():
            with st.expander(f"{row['ref_type']}  |  점수: {row['score']}  |  {row['timestamp']}"):
                st.markdown(f"**작성 내용:** {row['citation']}")
                st.markdown(f"**올바른 형식:** `{row['correct_format']}`")
                errs = json.loads(row["errors"]) if row["errors"] else []
                if errs:
                    st.markdown("**오류:**")
                    for e in errs:
                        st.markdown(f"- {e}")
                st.info(f"💬 {row['feedback']}")

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
