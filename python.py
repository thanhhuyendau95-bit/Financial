# python.py

import streamlit as st
import pandas as pd
from google import genai
from google.genai.errors import APIError

# --- Cấu hình Trang Streamlit ---
st.set_page_config(
    page_title="App Phân Tích Báo Cáo Tài Chính",
    layout="wide"
)

st.title("Ứng dụng Phân Tích Báo Cáo Tài Chính 📊")

# --- Hàm tính toán chính (Sử dụng Caching để Tối ưu hiệu suất) ---
@st.cache_data
def process_financial_data(df):
    """Thực hiện các phép tính Tăng trưởng và Tỷ trọng."""
    
    # Đảm bảo các giá trị là số để tính toán
    numeric_cols = ['Năm trước', 'Năm sau']
    for col in numeric_cols:
        df[col] = pd.to_numeric(col, errors='coerce').fillna(0) # Sửa lỗi tiềm ẩn: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 1. Tính Tốc độ Tăng trưởng
    # Dùng .replace(0, 1e-9) cho Series Pandas để tránh lỗi chia cho 0
    df['Tốc độ tăng trưởng (%)'] = (
        (df['Năm sau'] - df['Năm trước']) / df['Năm trước'].replace(0, 1e-9)
    ) * 100

    # 2. Tính Tỷ trọng theo Tổng Tài sản
    # Lọc chỉ tiêu "TỔNG CỘNG TÀI SẢN"
    tong_tai_san_row = df[df['Chỉ tiêu'].str.contains('TỔNG CỘNG TÀI SẢN', case=False, na=False)]
    
    if tong_tai_san_row.empty:
        # Nếu không tìm thấy, thử tìm kiếm một số biến thể thường gặp
        tong_tai_san_row = df[df['Chỉ tiêu'].str.contains('TỔNG TÀI SẢN', case=False, na=False)]
        if tong_tai_san_row.empty:
             raise ValueError("Không tìm thấy chỉ tiêu 'TỔNG CỘNG TÀI SẢN' hoặc 'TỔNG TÀI SẢN'.")

    tong_tai_san_N_1 = tong_tai_san_row['Năm trước'].iloc[0]
    tong_tai_san_N = tong_tai_san_row['Năm sau'].iloc[0]

    # Xử lý giá trị 0 thủ công cho mẫu số để tránh lỗi chia cho 0
    divisor_N_1 = tong_tai_san_N_1 if tong_tai_san_N_1 != 0 else 1e-9
    divisor_N = tong_tai_san_N if tong_tai_san_N != 0 else 1e-9

    # Tính tỷ trọng với mẫu số đã được xử lý
    df['Tỷ trọng Năm trước (%)'] = (df['Năm trước'] / divisor_N_1) * 100
    df['Tỷ trọng Năm sau (%)'] = (df['Năm sau'] / divisor_N) * 100
    
    return df

# --- Hàm gọi API Gemini (Dành cho Phân tích Tổng quan - Chức năng 5) ---
def get_ai_analysis(data_for_ai, api_key):
    """Gửi dữ liệu phân tích đến Gemini API và nhận nhận xét."""
    try:
        client = genai.Client(api_key=api_key)
        model_name = 'gemini-2.5-flash' 

        prompt = f"""
        Bạn là một chuyên gia phân tích tài chính chuyên nghiệp. Dựa trên các chỉ số tài chính sau, hãy đưa ra một nhận xét khách quan, ngắn gọn (khoảng 3-4 đoạn) về tình hình tài chính của doanh nghiệp. Đánh giá tập trung vào tốc độ tăng trưởng, thay đổi cơ cấu tài sản và khả năng thanh toán hiện hành.
        
        Dữ liệu thô và chỉ số:
        {data_for_ai}
        """

        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        return response.text

    except APIError as e:
        return f"Lỗi gọi Gemini API: Vui lòng kiểm tra Khóa API hoặc giới hạn sử dụng. Chi tiết lỗi: {e}"
    except KeyError:
        return "Lỗi: Không tìm thấy Khóa API 'GEMINI_API_KEY'. Vui lòng kiểm tra cấu hình Secrets trên Streamlit Cloud."
    except Exception as e:
        return f"Đã xảy ra lỗi không xác định: {e}"


# --- Chức năng 1: Tải File ---
uploaded_file = st.file_uploader(
    "1. Tải file Excel Báo cáo Tài chính (Chỉ tiêu | Năm trước | Năm sau)",
    type=['xlsx', 'xls']
)

if uploaded_file is not None:
    try:
        df_raw = pd.read_excel(uploaded_file)
        
        # Tiền xử lý: Đảm bảo chỉ có 3 cột quan trọng
        if len(df_raw.columns) >= 3:
             df_raw.columns = ['Chỉ tiêu', 'Năm trước', 'Năm sau'] + list(df_raw.columns[3:])
             df_raw = df_raw[['Chỉ tiêu', 'Năm trước', 'Năm sau']]
        else:
            raise ValueError("File Excel cần ít nhất 3 cột: Chỉ tiêu, Năm trước, Năm sau.")
        
        # Xử lý dữ liệu
        df_processed = process_financial_data(df_raw.copy())

        if df_processed is not None:
            
            # --- Chức năng 2 & 3: Hiển thị Kết quả ---
            st.subheader("2. Tốc độ Tăng trưởng & 3. Tỷ trọng Cơ cấu Tài sản")
            st.dataframe(df_processed.style.format({
                'Năm trước': '{:,.0f}',
                'Năm sau': '{:,.0f}',
                'Tốc độ tăng trưởng (%)': '{:.2f}%',
                'Tỷ trọng Năm trước (%)': '{:.2f}%',
                'Tỷ trọng Năm sau (%)': '{:.2f}%'
            }), use_container_width=True)
            
            # --- Chức năng 4: Tính Chỉ số Tài chính ---
            st.subheader("4. Các Chỉ số Tài chính Cơ bản")
            
            try:
                # Lấy Tài sản ngắn hạn
                tsnh_n = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]
                tsnh_n_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]

                # Lấy Nợ ngắn hạn
                no_ngan_han_N = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]  
                no_ngan_han_N_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]

                # Tính toán
                thanh_toan_hien_hanh_N = tsnh_n / (no_ngan_han_N if no_ngan_han_N != 0 else 1e-9)
                thanh_toan_hien_hanh_N_1 = tsnh_n_1 / (no_ngan_han_N_1 if no_ngan_han_N_1 != 0 else 1e-9)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        label="Chỉ số Thanh toán Hiện hành (Năm trước)",
                        value=f"{thanh_toan_hien_hanh_N_1:.2f} lần"
                    )
                with col2:
                    st.metric(
                        label="Chỉ số Thanh toán Hiện hành (Năm sau)",
                        value=f"{thanh_toan_hien_hanh_N:.2f} lần",
                        delta=f"{thanh_toan_hien_hanh_N - thanh_toan_hien_hanh_N_1:.2f}"
                    )
                    
            except IndexError:
                 st.warning("Thiếu chỉ tiêu 'TÀI SẢN NGẮN HẠN' hoặc 'NỢ NGẮN HẠN' để tính chỉ số.")
                 thanh_toan_hien_hanh_N = "N/A"
                 thanh_toan_hien_hanh_N_1 = "N/A"
            
            # --- Chức năng 5: Nhận xét AI ---
            st.subheader("5. Nhận xét Tình hình Tài chính (AI)")
            
            # Chuẩn bị dữ liệu để gửi cho AI
            data_for_ai = pd.DataFrame({
                'Chỉ tiêu': [
                    'Toàn bộ Bảng phân tích (dữ liệu thô)', 
                    'Tăng trưởng Tài sản ngắn hạn (%)', 
                    'Thanh toán hiện hành (N-1)', 
                    'Thanh toán hiện hành (N)'
                ],
                'Giá trị': [
                    df_processed.to_markdown(index=False),
                    f"{df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Tốc độ tăng trưởng (%)'].iloc[0]:.2f}%" if tsnh_n_1 != "N/A" else "N/A", 
                    f"{thanh_toan_hien_hanh_N_1}", 
                    f"{thanh_toan_hien_hanh_N}"
                ]
            }).to_markdown(index=False) 

            if st.button("Yêu cầu AI Phân tích"):
                api_key = st.secrets.get("GEMINI_API_KEY") 
                
                if api_key:
                    with st.spinner('Đang gửi dữ liệu và chờ Gemini phân tích...'):
                        ai_result = get_ai_analysis(data_for_ai, api_key)
                        st.markdown("**Kết quả Phân tích từ Gemini AI:**")
                        st.info(ai_result)
                else:
                    # FIX LỖI SyntaxError: unterminated string literal TẠI ĐÂY (dòng 177 cũ)
                    st.error("Lỗi: Không tìm thấy Khóa API. Vui lòng cấu hình Khóa 'GEMINI_API_KEY' trong Streamlit Secrets.")

    except ValueError as ve:
        st.error(f"Lỗi cấu trúc dữ liệu: {ve}")
    except Exception as e:
        st.error(f"Có lỗi xảy ra khi đọc hoặc xử lý file: {e}. Vui lòng kiểm tra định dạng file.")

else:
    st.info("Vui lòng tải lên file Excel để bắt đầu phân tích.")

# --------------------------------------------------------------------------------------
# --- BỔ SUNG KHUNG CHAT GEMINI TƯƠNG TÁC (CHỨC NĂNG 6) ---
# --------------------------------------------------------------------------------------
api_key_chat = st.secrets.get("GEMINI_API_KEY")

if api_key_chat:
    
    # --- Khởi tạo State và Client ---
    try:
        if "chat_client" not in st.session_state:
             st.session_state.chat_client = genai.Client(api_key=api_key_chat)

        # Khởi tạo phiên chat có nhớ ngữ cảnh và System Instruction
        if "messages" not in st.session_state:
            system_instruction = (
                "Bạn là một Trợ lý AI chuyên về Phân tích Tài chính và Kinh doanh. "
                "Hãy trả lời các câu hỏi một cách ngắn gọn, chuyên nghiệp và chỉ liên quan đến lĩnh vực Tài chính, Kế toán, và Kinh doanh."
            )

            st.session_state.chat = st.session_state.chat_client.chats.create(
                model="gemini-2.5-flash",
                config={"system_instruction": system_instruction}
            )
            # Lời chào đầu tiên
            st.session_state.messages = [
                {"role": "assistant", "content": "Chào bạn! Tôi là Trợ lý AI chuyên phân tích tài chính. Bạn có câu hỏi nào về các chỉ số, nghiệp vụ kế toán, hay kinh doanh không?"}
            ]
            
    except Exception as e:
        st.error(f"Lỗi khởi tạo Gemini Chat: {e}. Vui lòng kiểm tra API Key.")
        st.session_state.gemini_chat_error = True 
else:
    st.warning("⚠️ Không tìm thấy Khóa API 'GEMINI_API_KEY' để kích hoạt Chatbot. Vui lòng thêm key vào Streamlit Secrets.")
    st.session_state.gemini_chat_error = True


# --- Logic Hiển thị và Xử lý Chat ---
if 'gemini_chat_error' not in st.session_state or not st.session_state.gemini_chat_error:
    
    st.markdown("---")
    st.subheader("6. Chatbot Hỏi đáp Tài chính với Gemini 💬")
    
    # Hiển thị lịch sử chat
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Xử lý input từ người dùng
    if prompt := st.chat_input("Hỏi Gemini bất kỳ câu hỏi nào về tài chính..."):
        
        # 1. Thêm tin nhắn của người dùng vào lịch sử
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Gửi tin nhắn và nhận phản hồi từ Gemini
        try:
            with st.chat_message("assistant"):
                with st.spinner("Gemini đang trả lời..."):
                    # Gửi tin nhắn đến API và duy trì ngữ cảnh
                    response = st.session_state.chat.send_message(prompt)
                    
                    # Hiển thị phản hồi từ Gemini
                    st.markdown(response.text)
                    
                    # 3. Thêm phản hồi của Gemini vào lịch sử
                    st.session_state.messages.append({"role": "assistant", "content": response.text})

        except APIError as e:
            error_message = f"Lỗi gọi Gemini API: {e}. Vui lòng kiểm tra Khóa API hoặc giới hạn sử dụng."
            st.error(error_message)
            st.session_state.messages.append({"role": "assistant", "content": error_message})
        except Exception as e:
            error_message = f"Đã xảy ra lỗi không xác định trong Chatbot: {e}"
            st.error(error_message)
            st.session_state.messages.append({"role": "assistant", "content": error_message})
