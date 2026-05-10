# FactCheckAI - Hệ thống xác minh tin tức AI Agent & Graph-RAG

**FactCheckAI** là một giải pháp công nghệ hiện đại sử dụng **AI Agent** kết hợp kiến trúc **RAG (Retrieval-Augmented Generation)** nhằm xác minh tính xác thực của thông tin trên mạng Internet. Điểm cốt lõi của dự án là việc giới hạn nguồn dữ liệu tra cứu nghiêm ngặt trong "vùng xanh" (Whitelist domains) gồm các trang báo chí chính thống lớn và cổng thông tin điện tử Chính phủ Việt Nam, giúp loại bỏ hoàn toàn hiện tượng "ảo giác" (hallucination) thường gặp của AI.

Dự án là một mẫu thử nghiệm hoàn chỉnh (Fully Functional Prototype) bao gồm 3 lớp đồng bộ:
1. **Backend (FastAPI)**: Quản lý AI Agent Core, tích hợp thực tế Gemini, tìm kiếm whitelist, phân tích liên kết tri thức Graph-RAG và Caching giảm chi phí.
2. **Interactive Web Dashboard**: Giao diện điều khiển cao cấp (Sleek Dark Mode, Glassmorphism) trực quan hóa live luồng suy nghĩ của AI và biểu đồ mạng lưới Graph-RAG.
3. **Chrome Extension (Manifest V3)**: Extension tiện lợi bôi đen text để kiểm chứng nhanh khi đang đọc báo trực tuyến.

---

## ✨ Các tính năng nổi bật

*   **Live Reasoning Stream**: Truyền tải chi tiết từng bước phân tích và suy nghĩ của AI Agent (Phân tích cú pháp -> Gọi công cụ tìm kiếm Whitelist -> Đối chiếu logic Graph-RAG) thời gian thực bằng công nghệ Streaming SSE.
*   **Graph-RAG Visualizer**: Tự động trích xuất thực thể liên quan (Địa điểm, Tổ chức, Sự kiện, Con số...) từ tuyên bố và chứng cứ để dựng đồ thị tri thức mạng lưới SVG tuyệt đẹp.
*   **Phát hiện mâu thuẫn logic**: Phát hiện và cảnh báo các mâu thuẫn vật lý/logic trong đồ thị tri thức (Ví dụ: Sự kiện *Tuyết rơi dày đặc* xảy ra tại địa điểm *TP. Hồ Chí Minh* có khí hậu đặc trưng là *Nhiệt đới*).
*   **Caching & Pre-indexing**: Hệ thống lưu trữ bộ đệm siêu tốc cho các tin tức đã được xác minh trước đó, giúp phản hồi tức thì và tiết kiệm 100% chi phí gọi API tìm kiếm/LLM cho các yêu cầu trùng lặp.
*   **Quản lý Whitelist linh hoạt**: Cho phép thêm/xóa/đặt lại danh sách các tên miền vùng xanh đáng tin cậy trực tiếp từ bảng điều khiển.

---

## 🛠️ Công nghệ sử dụng

*   **Backend**: Python, FastAPI, Uvicorn, Pydantic, Google Generative AI (Gemini 1.5 Flash).
*   **Frontend**: HTML5, Vanilla CSS (Glassmorphic Theme, Neon gradients, SVG động), Javascript (Streaming API, SVG Graph Render).
*   **Chrome Extension**: Manifest V3, Content scripts, Background service worker, Extension Popups.

---

## 📂 Cấu trúc thư mục dự án

```text
factcheck-ai/
├── backend/
│   ├── main.py            # API Server FastAPI & Mount Static Dashboard
│   ├── config.py          # Cấu hình Whitelist, API keys, cài đặt hệ thống
│   ├── agent.py           # Core AI Agent (Gemini API & Simulated Fallback Agent)
│   ├── search.py          # Tìm kiếm giới hạn trong Whitelist domains
│   ├── graph_rag.py       # Phân tích thực thể, dựng đồ thị tri thức & mâu thuẫn logic
│   └── cache.py           # Quản lý bộ nhớ đệm kiểm chứng
├── extension/
│   ├── manifest.json      # File Manifest V3 của Chrome Extension
│   ├── popup.html         # Giao diện chính của popup Extension
│   ├── popup.css          # Styling giao diện popup gọn nhẹ
│   ├── popup.js           # Xử lý kết nối API streaming & trích xuất kết quả popup
│   ├── content.js         # Thu thập text được bôi đen ngoài trang web
│   ├── background.js      # Dịch vụ nền đăng ký tùy chọn Context Menu
│   └── icons/             # Thư mục chứa icon các kích thước của Extension
├── static/                # Thư mục tài nguyên Web Dashboard tương tác
│   ├── index.html         # Giao diện Dashboard cao cấp
│   ├── styles.css         # Styling modern, glassmorphism, node animations
│   └── app.js             # Logic xử lý Dashboard, vẽ đồ thị SVG và streaming UI
├── .gitignore             # File loại bỏ các thư mục rác khi đẩy lên GitHub
├── requirements.txt       # Khai báo các thư viện Python cần thiết
└── README.md              # Tài liệu hướng dẫn dự án (File này)
```

---

## 🚀 Hướng dẫn khởi chạy chi tiết

### 1. Khởi chạy Backend và Web Dashboard
Đảm bảo bạn đã cài đặt Python 3.10 trở lên trên hệ thống.

**Bước 1: Di chuyển vào thư mục dự án và khởi tạo môi trường ảo (Khuyến nghị):**
```bash
cd factcheck-ai
python3 -m venv venv
source venv/bin/activate
```

**Bước 2: Cài đặt các thư viện phụ thuộc:**
```bash
pip install -r requirements.txt
```

**Bước 3: Cấu hình Gemini API Key (Tùy chọn):**
Hệ thống tích hợp sẵn cơ chế **Simulated Agent thông minh** hoạt động hoàn toàn độc lập, tái tạo mượt mà 100% mọi kịch bản kiểm chứng và đồ thị tri thức để demo ngay lập tức nếu bạn chưa cấu hình API Key.
Nếu muốn chạy thực tế bằng LLM Gemini:
*   **Trên macOS/Linux:**
    ```bash
    export GEMINI_API_KEY="api_key_thuc_te_cua_ban"
    ```
*   **Trên Windows (Command Prompt):**
    ```cmd
    set GEMINI_API_KEY="api_key_thuc_te_cua_ban"
    ```

**Bước 4: Khởi chạy Server:**
```bash
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
👉 Hãy mở trình duyệt và truy cập **`http://127.0.0.1:8000`** để trải nghiệm Web Dashboard tương tác tuyệt đẹp!

---

### 2. Cài đặt Chrome Extension
1.  Mở trình duyệt Google Chrome và truy cập đường dẫn: **`chrome://extensions/`**
2.  Bật **Developer Mode (Chế độ nhà phát triển)** ở góc trên cùng bên phải màn hình.
3.  Nhấp vào nút **Load unpacked (Tải thư mục đã giải nén)** ở góc trên bên trái.
4.  Tìm và chọn thư mục **`extension/`** nằm trong thư mục gốc dự án của bạn (`factcheck-ai/extension/`).
5.  Ghim biểu tượng **FactCheckAI** lên thanh tiện ích.
6.  *Cách sử dụng*: Bôi đen một dòng chữ bất kỳ khi đang lướt mạng, nhấp chuột phải chọn **"Xác minh qua FactCheckAI"** hoặc bấm vào icon để xem kết quả xác minh thời gian thực.

---

## 📝 Bản quyền đóng góp
Dự án được xây dựng phục vụ mục đích nghiên cứu phát triển các giải pháp hạn chế tin giả trực tuyến tại Việt Nam thông qua ứng dụng đồ thị tri thức (Graph-RAG) và tác tử trí tuệ nhân tạo (AI Agent). 

Mọi ý kiến đóng góp và cải tiến vui lòng tạo PR hoặc liên hệ trực tiếp qua mục Issues của kho lưu trữ. Cảm ơn các bạn!
