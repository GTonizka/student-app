import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import io

# 1. 페이지 설정
st.set_page_config(page_title="학생생활지도 관리시스템", layout="wide")

# ==========================================
# 🔒 로그인 (자물쇠) 기능
# ==========================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 학생생활지도 관리시스템")
    st.info("학생 개인정보 보호를 위해 비밀번호를 입력해 주세요.")
    
    with st.form("login_form"):
        pwd_input = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
        submit_button = st.form_submit_button("접속하기")
        
        if submit_button:
            if pwd_input == st.secrets["app_password"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ 비밀번호가 일치하지 않습니다.")
    st.stop()

# ==========================================
# 🔓 로그인 성공 시 실행되는 메인 프로그램
# ==========================================
@st.cache_resource
def init_connection():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    return client

client = init_connection()
sheet_url = st.secrets["spreadsheet_url"]
doc = client.open_by_url(sheet_url)

student_sheet = doc.worksheet("학생명부")
record_sheet = doc.worksheet("지도기록")

def get_data(sheet):
    data = sheet.get_all_values()
    if not data or len(data) < 1:
        return pd.DataFrame()
    headers = data.pop(0)
    return pd.DataFrame(data, columns=headers)

st.title("🏫 학생생활지도 관리시스템")

students_df = get_data(student_sheet)
records_df = get_data(record_sheet)

tab1, tab2 = st.tabs(["🔍 학생 기록 및 작성", "📊 통계 및 다운로드"])

with tab1:
    search_name = st.text_input("학생 이름을 입력하세요", placeholder="이름 입력 후 엔터")
    
    if search_name:
        student_info = students_df[students_df['이름'] == search_name]
        
        if not student_info.empty:
            info = student_info.iloc[0]
            st.success(f"📍 {info['학년']}학년 {info['반']}반 {info['번호']}번 {info['이름']} (상태: {info['학적상태']})")
            
            if not records_df.empty and '이름' in records_df.columns:
                student_records = records_df[records_df['이름'] == search_name]
            else:
                student_records = pd.DataFrame()

            st.subheader("📌 학생 지도 현황")
            c1, c2, c3, c4 = st.columns(4)
            if not student_records.empty:
                c1.metric("외출(공식)", len(student_records[student_records['분류'] == '외출증 사용(공식)']))
                c2.metric("외출(포상)", len(student_records[student_records['분류'] == '외출증 사용(포상)']))
                c3.metric("무단 외출", len(student_records[student_records['분류'] == '무단 외출 적발']))
                c4.metric("흡연(교내/외)", len(student_records[student_records['분류'].str.contains('흡연', na=False)]))
            else:
                for c, title in zip([c1, c2, c3, c4], ["외출(공식)", "외출(포상)", "무단 외출", "흡연(교내/외)"]): 
                    c.metric(title, 0)

            st.divider()
            
            st.subheader("📝 신규 지도 내용 작성")
            category = st.radio("기록 종류 선택", ["일반 지도", "생활교육위원회 징계"], horizontal=True)
            
            with st.form("input_form", clear_on_submit=True):
                if category == "일반 지도":
                    rtype = st.selectbox("항목", ["외출증 사용(공식)", "외출증 사용(포상)", "무단 외출 적발", "교외 흡연 적발", "교내 흡연 적발"])
                    content = st.text_area("상세 내용")
                else:
                    level = st.selectbox("징계 단계", ["교내봉사", "사회봉사", "특별교육", "출석정지(5일)", "출석정지(10일)", "퇴학"])
                    rtype = "생활교육위원회 징계"
                    content = f"[{level}] " + st.text_area("징계 사유")
                
                col_l, col_a = st.columns(2)
                loc = col_l.text_input("장소")
                aut = col_a.text_input("작성자(교사명)")
                
                if st.form_submit_button("기록 저장하기"):
                    if not aut or not loc:
                        st.error("장소와 작성자를 입력해주세요.")
                    else:
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        record_sheet.append_row([search_name, rtype, content, loc, aut, now])
                        st.success("데이터가 구글 시트에 안전하게 저장되었습니다.")
                        st.rerun()

            st.divider()
            st.subheader("📜 학생 기록")
            if not student_records.empty:
                st.dataframe(student_records.sort_values('작성일시', ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info("이 학생에 대한 이전 기록이 없습니다.")
        else:
            st.warning("해당 이름의 학생을 찾을 수 없습니다.")

with tab2:
    st.header("📈 학교 전체 통계 및 다운로드")
    
    if not records_df.empty and '작성일시' in records_df.columns:
        st.subheader("📂 엑셀(.xlsx) 파일 다운로드")
        
        # 진짜 엑셀 파일로 변환하는 마법의 코드
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            records_df.to_excel(writer, index=False, sheet_name='지도기록')
        excel_data = output.getvalue()
        
        st.download_button(
            label="📊 전체 지도기록 엑셀 다운로드",
            data=excel_data,
            file_name=f"학생지도기록_전체_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.divider()
        st.subheader("📅 월별 누적 지도 건수 그래프")
       # (기존 코드) st.subheader("📅 월별 누적 지도 건수 그래프") 바로 아래부터 덮어쓰세요!
        try:
            stats_df = records_df.copy()
            
            # errors='coerce'를 추가하면 빈칸이나 이상한 글자를 만나도 에러를 내지 않고 무시(NaT)합니다.
            stats_df['변환된일시'] = pd.to_datetime(stats_df['작성일시'], errors='coerce')
            
            # 무시된 데이터(비어있는 칸 등)는 빼고 정상적인 날짜만 남깁니다.
            stats_df = stats_df.dropna(subset=['변환된일시'])
            
            # 'YYYY년 MM월' 형태로 추출
            stats_df['월'] = stats_df['변환된일시'].dt.strftime('%Y년 %m월')
            
            monthly_data = stats_df['월'].value_counts().sort_index()
            
            if not monthly_data.empty:
                st.bar_chart(monthly_data)
            else:
                st.info("그래프를 그릴 정상적인 날짜 데이터가 없습니다.")
        except Exception as e:
            st.info(f"통계 처리 중 오류가 발생했습니다: {e}")

