# Reflection — Member D: Backend Engineer
## Lab 14 — AI Evaluation Factory

---

## 1. Engineering Contribution (Task 2 + Task 3)

### Task 2: RAG Agent thực tế (`agent/main_agent.py`)

Tôi đã thay thế hoàn toàn placeholder `MainAgent` bằng một RAG pipeline thực tế:

**Kiến trúc TF-IDF In-Memory Retrieval:**
- Viết class `TFIDFStore` để load và chunk 5 tài liệu trong `data/docs/` (chunk_size=300 words, overlap=50).
- Implement TF-IDF tokenization, IDF pre-computation, cosine similarity search.
- Không cần Vector DB bên ngoài — toàn bộ chạy trong memory, đơn giản và nhanh.

**Hai phiên bản Agent:**
- **V1 (`MainAgent`)**: System prompt ngắn gọn, top_k=5, temperature=0.2.
- **V2 (`MainAgentV2`)**: System prompt nâng cao (yêu cầu trích dẫn nguồn, xử lý mâu thuẫn), top_k=7, temperature=0.1.

Agent trả về `retrieved_ids` theo format `doc_chunk{index}`, là input trực tiếp cho Retrieval Evaluator.

**Git commits liên quan:**
- `feat(agent): implement TF-IDF RAG pipeline with V1 and V2 agents`

---

### Task 3: Retrieval Evaluation (`engine/retrieval_eval.py`)

Implement đầy đủ `evaluate_batch` và 4 metrics:

| Metric | Công thức | Ý nghĩa |
|--------|-----------|---------|
| **Hit Rate@K** | `1 if ∃ id ∈ expected ∩ retrieved[:K]` | Agent có lấy đúng tài liệu không? |
| **MRR** | `1 / rank_of_first_relevant` | Tài liệu đúng xếp hạng ở vị trí nào? |
| **Precision@K** | `|relevant ∩ retrieved[:K]| / K` | Tỷ lệ kết quả đúng trong top-K |
| **NDCG@K** | `DCG / IDCG` | Chất lượng xếp hạng có trọng số vị trí |

`evaluate_batch` dùng `asyncio.Semaphore` để gọi agent song song và tránh rate limit.

---

## 2. Technical Depth

### MRR (Mean Reciprocal Rank) là gì, tại sao quan trọng?

MRR đo vị trí trung bình của tài liệu đúng đầu tiên trong kết quả retrieval. Không giống Hit Rate chỉ biết "có hay không", MRR coi retrieval ở rank 1 tốt hơn rank 5. Điều này quan trọng trong RAG vì LLM thường đọc context theo thứ tự — tài liệu ở đầu có ảnh hưởng lớn hơn đến câu trả lời. Hit Rate cao nhưng MRR thấp = tìm đúng nhưng không xếp hạng đúng → LLM có thể bỏ qua tài liệu quan trọng.

### Trade-off Chi phí vs Chất lượng

V2 dùng top_k=7 (thêm 2 chunks so với V1) → tăng ~40% token input → tăng chi phí. Nhưng coverage rộng hơn giúp Hit Rate cao hơn. Ngưỡng quyết định: nếu Hit Rate tăng >5% thì đáng đánh đổi chi phí thêm.

TF-IDF (không cần embedding API) giúp tiết kiệm 100% chi phí retrieval so với dùng `text-embedding-3-small`. Chi phí duy nhất là API generation.

---

## 3. Problem Solving — Vấn đề gặp phải

**Vấn đề**: `expected_retrieval_ids` trong golden set dùng format như `doc_metrics_01`, nhưng TF-IDF store tạo ra IDs dạng `it_helpdesk_faq_chunk000`.

**Giải pháp**: `evaluate_batch` lọc filter chỉ các case có `expected_retrieval_ids`. Các case không có trường này (chỉ đánh giá answer quality) vẫn được đưa vào benchmark bình thường — chỉ bỏ qua bước retrieval eval. Điều này giúp hệ thống không crash ngay cả khi dataset không đồng nhất.

**Bài học**: Không nên assume format ID nhất quán giữa các thành viên. Cần define schema sớm (→ `data/golden_case.schema.json` đã có sau pull request mới nhất).
