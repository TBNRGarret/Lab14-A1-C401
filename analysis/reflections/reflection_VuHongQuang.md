# Reflection — Member A: Golden Dataset & SDG Engineer
## Lab 14 — AI Evaluation Factory

**Họ và tên:** Vũ Hồng Quang - 2A202600341
**Vai trò:** Member A - Golden Dataset & SDG Engineer  
**Task chính:** Task 1 — Corpus, Golden Dataset Schema và Synthetic Data Generation  
**File phụ trách:** `data/build_corpus.py`, `data/corpus.jsonl`, `data/golden_case.schema.json`, `data/synthetic_gen.py`, `data/validate_golden_set.py`, `data/SDG_PLAYBOOK.md`, `data/SDG_USAGE.md`

---

## 1. Engineering Contribution

### a. Xây dựng corpus chuẩn cho Retrieval Evaluation

Điểm nghẽn lớn nhất của Task 1 là bộ dữ liệu gốc chưa có `doc_id`/`chunk_id` ổn định, trong khi rubric lại yêu cầu đánh giá Retrieval bằng Hit Rate và MRR. Tôi xử lý vấn đề này bằng cách thiết kế lại tầng dữ liệu nền:

- Chuẩn hóa 5 tài liệu trong `data/docs/` thành corpus JSONL có cấu trúc.
- Viết script `data/build_corpus.py` để tự động tách tài liệu thành chunk theo section.
- Áp dụng quy tắc đặt id ổn định theo mẫu `{source}_{section}_{index}`.
- Loại bỏ các section chỉ mang tính contact/tooling để chunk có giá trị retrieval tốt hơn.
- Tách riêng các subsection quan trọng trong HR policy để tạo granularity phù hợp cho QA.

Kết quả là `data/corpus.jsonl` được sinh tự động với **26 chunks** có `id`, `source`, `section`, `text` nhất quán. Đây là nền tảng để toàn bộ pipeline benchmark có thể tính retrieval metrics đúng nghĩa, thay vì chỉ chấm answer quality.

### b. Thiết kế schema và chuẩn hóa Golden Dataset

Tôi phụ trách chuẩn hóa format của một testcase trong `data/golden_case.schema.json` với các trường cốt lõi:

- `id`
- `question`
- `expected_answer`
- `expected_retrieval_ids`
- `metadata`

Ngoài ra, tôi bổ sung các trường hỗ trợ phân tích như `context`, `source_doc`, `tags`, đồng thời thống nhất taxonomy của hard cases theo các nhóm:

- `fact-check`
- `reasoning`
- `ambiguous`
- `out-of-context`
- `conflict`
- `prompt-injection`
- `goal-hijacking`
- `multi-turn`

Điểm kỹ thuật quan trọng nhất ở đây là tôi chỉnh lại schema để cho phép case `out-of-context` dùng `expected_retrieval_ids = []`. Nếu không sửa điểm này, dataset sẽ mâu thuẫn với chính playbook thiết kế hard cases và validator sẽ reject các case chống hallucination một cách sai logic.

### c. Xây dựng pipeline SDG hoàn chỉnh

Tôi triển khai bộ công cụ SDG đầy đủ thay vì chỉ tạo dữ liệu thủ công:

- `data/synthetic_gen.py`: đọc trực tiếp từ `data/corpus.jsonl` và sinh `data/golden_set.jsonl`
- `data/validate_golden_set.py`: kiểm tra schema logic, duplicate IDs, enum values và đặc biệt là đối soát `expected_retrieval_ids` với corpus thật
- `data/SDG_PLAYBOOK.md`: playbook thiết kế dataset cho team
- `data/SDG_USAGE.md`: hướng dẫn chạy theo quy trình chuẩn

Generator hiện sinh **53 test cases** theo đúng quota cố định trong playbook:

- `fact-check`: 12
- `reasoning`: 8
- `out-of-context`: 6
- `ambiguous`: 5
- `conflict`: 5
- `prompt-injection`: 7
- `goal-hijacking`: 5
- `multi-turn`: 5

Tôi còn thêm logic `validate_quotas()` ngay trong generator để nếu ai sửa script và làm lệch phân bổ, chương trình sẽ fail ngay thay vì âm thầm sinh dataset sai.

### d. Minh chứng kỹ thuật

Các artifact thể hiện trực tiếp phần việc của tôi:

- `data/build_corpus.py`
- `data/corpus.jsonl`
- `data/golden_case.schema.json`
- `data/synthetic_gen.py`
- `data/validate_golden_set.py`
- `data/SDG_PLAYBOOK.md`
- `data/SDG_USAGE.md`

---

## 2. Technical Depth

### a. Vì sao `expected_retrieval_ids` là bắt buộc nếu muốn đo MRR đúng nghĩa?

MRR không thể tính nếu không biết tài liệu/chunk nào là ground truth. Nếu testcase chỉ có `question` và `expected_answer`, hệ thống chỉ đánh giá được generation, còn phần retrieval sẽ trở thành "hộp đen".

Vì vậy, thiết kế dataset cho RAG phải tách rõ hai lớp:

- **Answer Ground Truth**: mô hình nên trả lời gì
- **Retrieval Ground Truth**: mô hình nên tìm thấy chunk nào

Đó là lý do tôi buộc mọi case retrieval-aware phải có `expected_retrieval_ids`, và chỉ miễn trừ riêng cho `out-of-context` vì trong trường hợp này retrieval đúng chính là **không có tài liệu phù hợp**.

### b. Hit Rate cao nhưng dataset thiết kế kém vẫn có thể làm benchmark sai

Nếu chunk quá to, một `expected_retrieval_id` có thể vô tình chứa rất nhiều thông tin không liên quan. Khi đó agent retrieve đúng id nhưng không chứng minh được retrieval thật sự tốt; nó chỉ "trúng to" vì chunk bao phủ quá rộng.

Ngược lại, nếu chunk quá nhỏ hoặc id không ổn định, Hit Rate và MRR sẽ thấp giả tạo vì ground truth không phản ánh retrieval granularity thực tế. Do đó, phần thiết kế corpus ảnh hưởng trực tiếp đến độ tin cậy của toàn bộ benchmark, không chỉ là bước tiền xử lý đơn giản.

### c. Agreement Rate và Cohen's Kappa nhìn từ góc độ người thiết kế dataset

Người làm SDG không trực tiếp viết Judge, nhưng lại ảnh hưởng mạnh đến độ đồng thuận của Judge. Nếu testcase mơ hồ, thiếu context, hoặc `expected_answer` viết quá dài và không có tiêu chí chấm rõ, agreement giữa các judge sẽ giảm không phải vì judge kém mà vì dữ liệu mơ hồ.

Từ góc nhìn đó:

- **Agreement Rate** cho tôi biết testcase có đang dễ hiểu và rubric-friendly hay không.
- **Cohen's Kappa** quan trọng hơn khi cần biết sự đồng thuận đó có thực chất hay chỉ là ngẫu nhiên.

Vì vậy trong SDG, tôi ưu tiên viết `expected_answer` ngắn, kiểm chứng được, và tách loại case rõ ràng thay vì để nhiều câu hỏi nhập nhằng trong cùng một mẫu.

### d. Position Bias ảnh hưởng gì đến cách tạo multi-turn và adversarial cases?

Position Bias thường được nhắc ở tầng Judge, nhưng nó cũng liên quan đến SDG. Với các case adversarial hoặc multi-turn, nếu prompt được viết dài và cài nhiễu ở đầu câu quá nhiều, judge hoặc thậm chí agent có thể bị lệch tập trung vào phần đầu hơn phần yêu cầu thật ở sau.

Do đó khi thiết kế các case `prompt-injection` và `goal-hijacking`, tôi giữ cấu trúc nhất quán:

- phần nhiễu/tấn công xuất hiện rõ ràng
- phần câu hỏi thật vẫn xác định được
- `expected_answer` luôn bám vào nội dung chuẩn trong corpus

Thiết kế này giúp benchmark đo đúng khả năng chống nhiễu của agent, thay vì biến testcase thành một prompt quá lộn xộn và khó chấm.

### e. Trade-off giữa dataset thủ công và dataset sinh tự động

Dataset viết tay cho chất lượng cao hơn, nhưng chi phí thời gian rất lớn và khó mở rộng. Dataset sinh tự động từ corpus thì nhanh, nhất quán và tái tạo được, nhưng nếu không có validator sẽ rất dễ sinh ra câu hỏi hời hợt hoặc lệch quota.

Giải pháp tôi chọn là mô hình lai:

- **Tầng 1:** tự động hóa corpus + schema + generator + validator
- **Tầng 2:** con người kiểm tra playbook, quota, và các hard cases khó

Cách này giúp team có thể tái tạo dataset nhanh mà vẫn giữ được kiểm soát chất lượng.

---

## 3. Problem Solving

### Vấn đề 1: Không có `doc_id` nội bộ nên không thể gán ground truth retrieval

**Vấn đề:**
Ban đầu bộ tài liệu chỉ là các file `.txt` rời trong `data/docs/`, hoàn toàn không có `doc_id` hay `chunk_id`. Nếu giữ nguyên trạng thái này, team chỉ có thể viết testcase kiểu QA thông thường, không thể tính Hit Rate/MRR đúng chuẩn rubric.

**Cách giải quyết:**

1. Thiết kế `data/corpus.jsonl` làm nguồn chân lý cho retrieval.
2. Viết `data/build_corpus.py` để tái tạo corpus tự động từ tài liệu gốc.
3. Chuẩn hóa id chunk ổn định và có thể tham chiếu trong `expected_retrieval_ids`.

**Kết quả:**
Toàn bộ pipeline benchmark có thể chuyển từ "đánh giá câu trả lời" sang "đánh giá cả retrieval lẫn generation".

### Vấn đề 2: Schema ban đầu xung đột với hard case `out-of-context`

**Vấn đề:**
Playbook yêu cầu `out-of-context` dùng `expected_retrieval_ids = []`, nhưng schema ban đầu lại yêu cầu `minItems = 1`. Nếu giữ nguyên, validator sẽ loại bỏ chính loại testcase dùng để phát hiện hallucination.

**Cách giải quyết:**

1. Sửa schema để cho phép mảng rỗng chỉ trong trường hợp `out-of-context`.
2. Dồn logic kiểm tra điều kiện này vào `data/validate_golden_set.py` thay vì cứng nhắc trong JSON Schema.

**Kết quả:**
Dataset vừa giữ được ràng buộc mạnh cho retrieval-aware cases, vừa hỗ trợ đúng nhóm testcase chống hallucination.

### Vấn đề 3: Generator sinh đủ 50+ case nhưng sai phân bổ theo playbook

**Vấn đề:**
Phiên bản đầu của `synthetic_gen.py` sinh nhiều `fact-check` vì mỗi chunk cho ra một case, nhưng lại thiếu `reasoning`, `conflict`, `out-of-context` và hoàn toàn chưa có `multi-turn`.

**Cách giải quyết:**

1. Đặt quota cố định theo playbook cho từng nhóm case.
2. Viết riêng từng hàm sinh theo loại (`build_reasoning_cases`, `build_conflict_cases`, `build_multi_turn_cases`...).
3. Thêm `validate_quotas()` để assert đúng phân bổ trước khi ghi file.

**Kết quả:**
Generator hiện sinh đúng **53 cases** theo quota thiết kế, không còn hiện tượng thừa easy cases và thiếu hard cases như trước.

---

## 4. Lessons Learned

- Trong bài toán RAG, dữ liệu đánh giá không chỉ là list câu hỏi. Nó là một hợp đồng kỹ thuật giữa corpus, retrieval ground truth, schema, judge và runner.
- Nếu không chuẩn hóa `expected_retrieval_ids` từ đầu, mọi chỉ số retrieval về sau đều thiếu độ tin cậy.
- SDG tốt không phải là sinh ra nhiều case nhất, mà là sinh ra đúng quota, đúng taxonomy và tái tạo được.
- Validator quan trọng ngang với generator; nếu chỉ biết sinh mà không biết chặn dữ liệu xấu, benchmark sẽ sớm bị nhiễu.

---

**Tổng kết:** Vai trò Member A giúp tôi đi sâu vào phần nền tảng dữ liệu của hệ thống đánh giá AI. Tôi không chỉ tạo testcase, mà còn xây toàn bộ khung kỹ thuật để team có thể sinh, kiểm tra và tái sử dụng Golden Dataset một cách nhất quán cho các vòng benchmark sau.