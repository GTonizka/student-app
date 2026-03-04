import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# 1. 페이지 및 환경 설정
st.set_page_config(page_title="학생생활지도 프로그램", layout="wide")

# 2. 구글 스프레드시트 연결 함수
@st.cache_resource
def init_connection():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    return client

client = init_connection()
sheet_url = st.secrets["spreadsheet_url"]
doc = client.open_by_url(sheet_url)

# 시트 불러오기
student_sheet = doc.worksheet("학생명부")
record_sheet = doc.worksheet("지도기록")

# 데이터프레임으로 변환하는 함수 (데이터가 비어있어도 오류 안 나게 수정됨)
def get_data(sheet):
    data = sheet.get_all_values()
    if not data:
        return pd.DataFrame()
    headers = data.pop(0)
    return pd.DataFrame(data, columns=headers)

st.title("📋 학생생활지도 프로그램")

# 3. 데이터 불러오기
students_df = get_data(student_sheet)
records_df = get_data(record_sheet)

st.header("학생 조회 및 기록")

# 4. 이름 검색창
search_name = st.text_input("학생 이름을 입력하세요 (예: 김철수)", placeholder="이름 입력 후 Enter")

if search_name:
    # 학생명부에서 학생 찾기
    student_info = students_df[students_df['이름'] == search_name]
    
    if not student_info.empty:
        info = student_info.iloc[0]
        st.success(f"✅ {info['학년']}학년 {info['반']}반 {info['번호']}번 {info['이름']} ({info['학적상태']})")
        
        # 지도기록에서 해당 학생의 기록만 필터링 (비어있을 경우 대비)
        if not records_df.empty and '이름' in records_df.columns:
            student_records = records_df[records_df['이름'] == search_name]
        else:
            student_records = pd.DataFrame(columns=['이름', '분류', '내용', '장소', '작성자', '작성일시'])
        
        # 누적 횟수 계산
        st.subheader("📊 누적 지도 현황")
        col1, col2, col3, col4 = st.columns(4)
        if not student_records.empty and '분류' in student_records.columns:
            col1.metric("외출증(공식)", len(student_records[student_records['분류'] == '외출증 사용(공식)']))
            col2.metric("외출증(포상)", len(student_records[student_records['분류'] == '외출증 사용(포상)']))
            col3.metric("무단 외출", len(student_records[student_records['분류'] == '무단 외출 적발']))
            col4.metric("흡연 적발(교내/외)", len(student_records[student_records['분류'].str.contains('흡연', na=False)]))
        else:
            col1.metric("외출증(공식)", 0)
            col2.metric("외출증(포상)", 0)
            col3.metric("무단 외출", 0)
            col4.metric("흡연 적발(교내/외)", 0)
        
        st.divider()
        st.subheader("📝 신규 기록 작성")
        
        # ==========================================
        # ★ 수정된 부분: 기록 종류 선택 (일반 vs 징계)
        # ==========================================
        record_category = st.radio(
            "어떤 기록을 작성하시겠습니까?", 
            ["일반 지도 기록", "생활교육위원회 징계 기록"], 
            horizontal=True
        )
        
        if record_category == "일반 지도 기록":
            with st.form("general_record_form", clear_on_submit=True):
                record_type = st.selectbox("분류", [
                    "외출증 사용(공식)", "외출증 사용(포상)", "무단 외출 적발", 
                    "교외 흡연 적발", "교내 흡연 적발"
                ])
                content = st.text_area("상세 내용")
                
                col_a, col_b = st.columns(2)
                location = col_a.text_input("발생/작성 장소")
                author = col_b.text_input("작성자(교사명)")
                
                submit_button = st.form_submit_button("구글 시트에 일반 기록 저장")
                
                if submit_button:
                    if not author or not location:
                        st.error("장소와 작성자를 모두 입력해주세요.")
                    else:
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        new_row = [search_name, record_type, content, location, author, now_str]
                        record_sheet.append_row(new_row)
                        st.success("일반 지도 기록이 저장되었습니다!")
                        st.rerun()
                        
        elif record_category == "생활교육위원회 징계 기록":
            with st.form("punishment_record_form", clear_on_submit=True):
                # 징계 단계 선택 추가
                punishment_level = st.selectbox("징계 단계", [
                    "교내봉사", "사회봉사", "특별교육", 
                    "출석정지(5일)", "출석정지(10일)", "퇴학"
                ])
                punishment_reason = st.text_area("징계 사유 (구체적으로 작성)")
                author = st.text_input("작성자(교사명)")
                
                submit_button = st.form_submit_button("구글 시트에 징계 기록 저장", type="primary")
                
                if submit_button:
                    if not author or not punishment_reason:
                        st.error("징계 사유와 작성자를 모두 입력해주세요.")
                    else:
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        # 징계 단계와 사유를 하나로 묶어서 구글 시트 '내용' 칸에 저장
                        combined_content = f"[{punishment_level}] {punishment_reason}"
                        # 장소 칸은 '생교위'로 고정 기록
                        new_row = [search_name, "생활교육위원회 징계", combined_content, "생교위", author, now_str]
                        record_sheet.append_row(new_row)
                        st.success(f"[{punishment_level}] 징계 기록이 저장되었습니다!")
                        st.rerun()
        
        st.divider()
        st.subheader("📜 상세 기록 내역")
        
        # ==========================================
        # ★ 수정된 부분: 조회 내역을 탭으로 완벽 분리
        # ==========================================
        if not student_records.empty and '분류' in student_records.columns:
            # 판다스를 이용해 일반 기록과 징계 기록을 나눔
            general_records = student_records[student_records['분류'] != '생활교육위원회 징계']
            punishment_records = student_records[student_records['분류'] == '생활교육위원회 징계']
            
            tab_gen, tab_pun = st.tabs(["📂 일반 지도 내역", "🚨 생활교육위원회 징계 내역"])
            
            with tab_gen:
                if not general_records.empty:
                    st.dataframe(general_records, use_container_width=True, hide_index=True)
                else:
                    st.info("작성된 일반 지도 기록이 없습니다.")
                    
            with tab_pun:
                if not punishment_records.empty:
                    st.dataframe(punishment_records, use_container_width=True, hide_index=True)
                else:
                    st.info("작성된 징계 기록이 없습니다.")
        else:
            st.info("아직 작성된 기록이 없습니다.")
            
    else:
        st.warning("등록되지 않은 학생이거나 이름을 잘못 입력하셨습니다.")