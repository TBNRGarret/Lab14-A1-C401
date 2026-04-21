# Individual Reflection - Lab 14

**Họ và tên:** Đàm Lê Văn Toàn  
**Vai trò:** Thành viên 6 - DevOps/Analyst  
**Task:** Task 6 (Regression Gate + Tích hợp `main.py`)

## 1. Engineering Contribution (15đ)

**Module phụ trách:** Hệ thống Regression Testing & Cổng kiểm duyệt (Release Gate) trong hệ thống điều phối `main.py`.

**Giải trình kỹ thuật:**
Tôi đã phụ trách việc thiết lập vòng kiểm thử hồi quy (Regression Testing) nhằm so sánh đối chiếu chất lượng giữa phiên bản RAG Agent V1 (Baseline) và V2 (Optimized) trước khi cho phép mã nguồn được cung cấp ra môi trường "Release".
Các công việc chính tôi đã thực hiện bao gồm:
- Tích hợp gọi chạy song song 2 phiên bản Agent vào luồng Benchmark chính của hệ thống.
- Xây dựng module **Delta Analysis** tự động đo lường độ chênh lệch của các chỉ số hiệu năng (Hit Rate, Average Score, Cost, Agreement Rate) giữa bản cải tiến V2 so với V1. Xử lý triệt để các rủi ro tính toán (như chia cho số 0) thông qua việc vận dụng linh hoạt hàm `max()`.
- Thiết kế và lập trình luồng **Release Gate tự động chấm điểm Pass/Reject**:
  - Gắn thẻ `[BLOCK]` và từ chối Release nếu: Điểm số trung bình (avg_score) bị sụt giảm, hoặc Hit Rate của module Retrieval giảm quá ngưỡng biên 5% so với bản cũ.
  - Gắn thẻ `[WARNING]` nếu: Tốc độ đốt ngân sách (Cost) tăng vọt trên 20% hoặc có nghi ngờ về độ ổn định của liên minh Giám khảo AI (Agreement Rate < 0.7).
- Tổng hợp toàn diện bộ log cảnh báo, đóng gói chúng cùng các metrics liên đới thành một file `reports/summary.json` có cấu trúc rõ ràng phục vụ cho các Analyst (Task 7) phân tích hậu kỳ dễ dàng.

**Minh chứng Git Commits:**
- `feat(Task F): Implement Regression Release Gate with detailed warnings and blocks`
- `Merge stash (Task F Release Gate) into main.py`

---

## 2. Technical Depth (15đ)

### a. MRR (Mean Reciprocal Rank) là gì, tại sao quan trọng?
MRR là chỉ số đo lường chất lượng hệ thống tìm kiếm (Retrieval) dựa trên thứ hạng của tài liệu đúng *đầu tiên* mà nó truy xuất ra được.
- **Công thức:** $MRR = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{rank_i}$ (với $rank_i$ là vị trí của tài liệu chuẩn trong mảng Retrieved).
- **Tại sao quan trọng:** Khác với Hit Rate (chỉ cần biết có mò ra tài liệu hay không), MRR quan tâm thiết thực đến việc tài liệu chuẩn được đặt ở Top 1, Top 2 hay tuốt bên dưới Top 5. Trong bối cảnh RAG, nếu context chuẩn nằm ở Top 1, mô hình LLM sẽ dễ theo dõi và đưa ra câu trả lời chuẩn xác hơn rất nhiều so với việc tài liệu rác chèn ép lên trên (LLM sẽ dễ bị ảo giác do hiện tượng "Lost in the Middle").

### b. Cohen's Kappa và Agreement Rate
- **Agreement Rate:** Tỷ lệ phần trăm các tình huống mà tập hợp các LLM Judge (như GPT-4o và Gemini) đưa ra điểm số hoặc phán quyết giống nhau. Nó đo lường sự nhất quán thô bề mặt.
- **Cohen's Kappa:** Là một phép đo đánh giá sự đồng thuận khắt khe và mạnh mẽ hơn vì nó trừ đi yếu tố "đồng thuận nhẫu nhiên" (ví dụ: nếu cả 2 model hay vote bừa "Pass", tỷ lệ trùng khớp vẫn cao). Nếu Cohen's Kappa trong Benchmark của chúng ta quá thấp (< 0.4), điều này chứng minh bộ Rubric chấm điểm của chúng ta chưa đủ rõ ràng khiến các Judge hiểu sai ý nhau.

### c. Position Bias trong LLM Judge
Position Bias (Thiên kiến vị trí) là một hiện tượng tâm lý (hallucination bias) của các mô hình NN lớn; khi ta đưa prompt chứa 2 tùy chọn A và B để đánh giá, LLM thường có tỷ lệ thiên vị trao điểm cao hơn cho câu trả lời được đặt ở vị trí thứ nhất (A), bất kể chất lượng thực sự của nó so với B. Để làm trong sạch hệ thống Multi-Judge, ta cần tiến hành đảo ngược vị trí hai tham số (Swap A & B) trong một lần gọi API ẩn để trích xuất điểm công tâm nhất.

### d. Trade-off Chi phí vs Chất lượng
Sử dụng các mô hình thương mại đầu bảng (SOTA) như GPT-4o để làm AI Judge đem lại độ chính xác cao nhờ khả năng reasoning đa nhịp cực tốt. Tuy nhiên sự bùng nổ token đẩy API Cost lên rất cao, dẫn tới tính bất khả thi về mặt scaling hệ thống đánh giá. Việc thiết kế hệ thống phải có tính thỏa hiệp (Trade-off) bằng định tuyến thông minh (Router/Fallback): sử dụng model giá rẻ (Gemini 2.5 Flash / GPT-4o-mini) làm trọng tài vòng 1, hễ gặp ca khó hoặc có sự xung đột phán quyết giữa 2 model yếu thì hệ thống mới nâng cấp gọi lên các model hạng nặng xử lý, từ đó cân bằng được giá trị kinh tế mà vẫn giữ tỷ lệ rủi ro thấp.

---

## 3. Problem Solving (10đ)

**Vấn đề gặp phải:**
Trong quá trình phát hành Benchmark, tôi gặp phải xung đột mã nguồn nghiêm trọng (Git Merge Conflicts) do quá trình phát triển phân tán chưa đồng bộ nhịp nhàng. Khi chuẩn bị push module Release Gate cá nhân của tôi (Task F), mã nguồn trung tâm `main.py` đã bị thay đổi đáng kể cấu trúc từ phía các thành viên đảm nhiệm Task C, D, E. Việc dùng lại các dòng push thông thường kết hợp `git stash pop` đưa máy tôi vào trạng thái giằng co Unmerged Index (lỗi 128), vô hiệu hoá toàn bộ các lệnh tương tác git thông thường. Bên cạnh đó, luồng trích xuất "Cost" không còn ở Root_Dict mà đẵ bị các thành viên khác phân tầng sâu vào nested object trong `performance.cost`.

**Cách giải quyết:**
Tôi sử dụng kỹ thuật sao lưu và thanh trừng trạng thái Git để bảo toàn công sức cá nhân:
1. Copy an toàn logic cốt lõi của cổng Release Gate ra một file nháp tạm `main_backup.py`.
2. Dùng lệnh `git reset --hard HEAD` để "bẻ gãy" hoàn toàn trạng thái Conflict cấp độ Index cản trở việc cập nhật, làm thông thoáng terminal để sử dụng `git pull origin main` tải phiên bản code mới tinh của đội về đồng bộ.
3. Cấu trúc lại phương thức parsing JSON bằng việc cấy chain hàm rẽ nhánh an toàn đệ quy `.get("performance", {}).get("cost", {})...` giúp chống Crash lỗi NoneType khi vắng mặt field cost trong API. Đắp toàn bộ logic cũ lên version code hoàn thiện và Push vượt cổng server êm xuôi. Hệ quả là bộ gate đánh chặn được vận hành chính xác với luồng data metrics mới nhất.
