# 🎯 Lab 14 - Phân Công Nhiệm Vụ Chi Tiết

## 📊 Tổng quan Rubric & Hiện trạng Code

### Bảng điểm

| Hạng mục | Điểm tối đa | Hiện trạng code |
|:---|:---:|:---:|
| **Retrieval Evaluation** (Hit Rate & MRR) | 10 | ⚠️ Công thức có sẵn, nhưng `evaluate_batch` là placeholder |
| **Dataset & SDG** (50+ cases, Red Teaming) | 10 | ❌ Chỉ có 1 case mẫu giả |
| **Multi-Judge Consensus** (2+ models) | 15 | ❌ Hardcoded fake scores, chưa gọi API thật |
| **Regression Testing** (V1 vs V2, Release Gate) | 10 | ⚠️ Logic khung có sẵn, nhưng dùng evaluator giả |
| **Performance Async** (< 2 phút, Cost report) | 10 | ⚠️ Async runner có sẵn, thiếu cost tracking |
| **Failure Analysis** (5 Whys) | 5 | ❌ Template trống |
| **Điểm cá nhân** (Contribution + Depth + Problem Solving) | 40 | ❌ Chưa có reflection files |
| **TỔNG** | **100** | |

> [!CAUTION]
> **ĐIỂM LIỆT:** Nếu chỉ dùng **1 Judge đơn lẻ** hoặc **không có Retrieval Metrics** → điểm nhóm bị giới hạn tối đa **30/60 điểm**. Đây là 2 task BẮT BUỘC phải hoàn thành!

---

## 🔍 Phân tích chi tiết từng task cần làm

### Task 1: Golden Dataset & SDG (10 điểm)
**File:** [synthetic_gen.py](file:///d:/Lab14-AI-Evaluation-Benchmarking/data/synthetic_gen.py), [golden_set.jsonl](file:///d:/Lab14-AI-Evaluation-Benchmarking/data/golden_set.jsonl)

Hiện tại `synthetic_gen.py` chỉ trả về 1 object giả. Cần:
- [ ] Gọi OpenAI/Anthropic API thật để sinh QA pairs từ tài liệu
- [ ] Tạo **50+ test cases** trong `golden_set.jsonl`
- [ ] Mỗi case phải có: `question`, `expected_answer`, `context`, `metadata` (difficulty, type)
- [ ] Thêm trường `expected_retrieval_ids` (Ground Truth IDs) cho mỗi case
- [ ] Thiết kế **Red Teaming cases** theo [HARD_CASES_GUIDE.md](file:///d:/Lab14-AI-Evaluation-Benchmarking/data/HARD_CASES_GUIDE.md):
  - Adversarial Prompts (Prompt Injection, Goal Hijacking)
  - Edge Cases (Out of Context, Ambiguous, Conflicting Info)
  - Multi-turn Complexity
  - Technical Constraints (Latency, Cost)
- [ ] Phân loại rõ ràng: `easy`, `medium`, `hard`, `adversarial`

---

### Task 2: Agent thực tế (Nền tảng cho mọi thứ)
**File:** [main_agent.py](file:///d:/Lab14-AI-Evaluation-Benchmarking/agent/main_agent.py)

Hiện tại Agent chỉ trả về câu trả lời giả. Cần:
- [ ] Tích hợp RAG pipeline thực tế (Vector DB + LLM)
- [ ] Agent phải trả về `retrieved_ids` để đánh giá Retrieval
- [ ] Có 2 phiên bản Agent (V1 base, V2 optimized) để test Regression
- [ ] Track `tokens_used` thực tế

---

### Task 3: Retrieval Evaluation (10 điểm) — ⚡ CRITICAL
**File:** [retrieval_eval.py](file:///d:/Lab14-AI-Evaluation-Benchmarking/engine/retrieval_eval.py)

`calculate_hit_rate` và `calculate_mrr` đã implement nhưng `evaluate_batch` là stub:
- [ ] Implement `evaluate_batch()` thật — duyệt qua toàn bộ dataset, gọi agent, lấy `retrieved_ids` rồi tính Hit Rate & MRR
- [ ] Tích hợp vào `main.py` để kết quả xuất hiện trong `summary.json`
- [ ] Viết logic phân tích mối liên hệ Retrieval Quality → Answer Quality
- [ ] Thêm metrics nâng cao nếu có thể: NDCG, Precision@K

---

### Task 4: Multi-Judge Consensus (15 điểm) — ⚡ CRITICAL, ĐIỂM CAO NHẤT
**File:** [llm_judge.py](file:///d:/Lab14-AI-Evaluation-Benchmarking/engine/llm_judge.py)

Hiện tại hoàn toàn hardcoded. Cần:
- [ ] Gọi API thật đến **ít nhất 2 model** (ví dụ: GPT-4o + Claude 3.5 Sonnet)
- [ ] Thiết kế **rubric chấm điểm chi tiết** (Accuracy 1-5, Tone 1-5, Safety 1-5)
- [ ] Tính **Agreement Rate** thực tế (có thể dùng Cohen's Kappa)
- [ ] Logic **xử lý xung đột tự động**: khi 2 judge lệch > 1 điểm → gọi judge thứ 3 hoặc lấy median
- [ ] Implement `check_position_bias()` — đổi thứ tự response A/B để phát hiện bias
- [ ] Trả về `reasoning` chi tiết từ mỗi judge

---

### Task 5: Async Runner & Performance (10 điểm)
**File:** [runner.py](file:///d:/Lab14-AI-Evaluation-Benchmarking/engine/runner.py), [main.py](file:///d:/Lab14-AI-Evaluation-Benchmarking/main.py)

Runner đã có khung async nhưng cần hoàn thiện:
- [ ] Đảm bảo pipeline chạy **< 2 phút cho 50 cases** (dùng `asyncio.Semaphore` để rate limit)
- [ ] Thêm **Cost & Token tracking** chi tiết:
  - Total tokens used (input + output)
  - Cost per eval (USD)
  - Cost per model judge
- [ ] Thêm progress bar (tqdm)
- [ ] Error handling & retry logic cho API calls
- [ ] Timing report: tổng thời gian, thời gian trung bình mỗi case

---

### Task 6: Regression Testing & Release Gate (10 điểm)
**File:** [main.py](file:///d:/Lab14-AI-Evaluation-Benchmarking/main.py)

Logic khung có sẵn nhưng cần hoàn thiện:
- [ ] Thay `ExpertEvaluator` và `MultiModelJudge` giả bằng implementation thật
- [ ] Chạy benchmark thực sự cho V1 và V2
- [ ] Implement **Release Gate logic** tự động:
  - Nếu `avg_score` V2 < V1 → BLOCK
  - Nếu `hit_rate` giảm > 5% → BLOCK
  - Nếu `cost` tăng > 20% → WARNING
  - Nếu `agreement_rate` < 0.7 → WARNING
- [ ] Lưu kết quả regression vào `summary.json` với cả V1 và V2 metrics
- [ ] In ra **Delta Analysis** rõ ràng cho từng metric

---

### Task 7: Failure Analysis Report (5 điểm)
**File:** [failure_analysis.md](file:///d:/Lab14-AI-Evaluation-Benchmarking/analysis/failure_analysis.md)

Template có sẵn, cần điền dữ liệu thực:
- [ ] Điền số liệu benchmark thực (Pass/Fail ratio, RAGAS scores, Judge scores)
- [ ] Phân nhóm lỗi (Failure Clustering) dựa trên kết quả thực
- [ ] Viết **5 Whys analysis** cho ít nhất 3 case tệ nhất — phải sâu, chỉ ra root cause ở đâu (Chunking? Ingestion? Retrieval? Prompting?)
- [ ] Đề xuất Action Plan cải tiến cụ thể

---

### Task 8: Individual Reflections (40 điểm cá nhân)
**Path:** `analysis/reflections/reflection_[Tên_SV].md`

Mỗi thành viên cần viết:
- [ ] **Engineering Contribution** (15đ): Mô tả cụ thể module đã code, kèm giải trình kỹ thuật. Chứng minh qua Git commits
- [ ] **Technical Depth** (15đ): Giải thích được:
  - MRR (Mean Reciprocal Rank) là gì, tại sao quan trọng
  - Cohen's Kappa và Agreement Rate
  - Position Bias trong LLM Judge
  - Trade-off Chi phí vs Chất lượng
- [ ] **Problem Solving** (10đ): Mô tả vấn đề gặp phải và cách giải quyết

---

## 👥 Phân công cho nhóm 6 NGƯỜI

| Vai trò | Thành viên | Tasks chính | Giai đoạn | Điểm liên quan |
|:---|:---|:---|:---:|:---:|
| **🟢 A - Data Engineer** | Thành viên 1 | Task 1: SDG Script + Golden Dataset (50+ cases) | GĐ1 | 10đ |
| **🟢 B - Data Analyst** | Thành viên 2 | Task 1 (Red Teaming cases) + Task 7 (Failure Analysis) | GĐ1 + GĐ3 | 10đ + 5đ |
| **🔴 C - AI Engineer (Lead)** | Thành viên 3 | Task 4: Multi-Judge Consensus Engine | GĐ2 | 15đ |
| **🔴 D - Backend Engineer** | Thành viên 4 | Task 2 (Agent thật) + Task 3 (Retrieval Eval) | GĐ1-2 | 10đ |
| **🟡 E - DevOps/Performance** | Thành viên 5 | Task 5: Async Runner + Cost tracking | GĐ2 | 10đ |
| **🟡 F - DevOps/Analyst** | Thành viên 6 | Task 6: Regression Gate + Tích hợp `main.py` | GĐ2-3 | 10đ |

### Timeline nhóm 6 người

```
GĐ1 (45 phút) ──────────────────────────────────────
  A: Viết SDG script gọi API thật, sinh 30+ cases
  B: Thiết kế 20+ Red Teaming/Hard cases thủ công
  D: Setup Agent thật (RAG pipeline) hoặc cải tiến agent hiện có

GĐ2 (90 phút) ──────────────────────────────────────
  A: Hoàn thiện đủ 50+ cases, QA chất lượng
  C: Implement Multi-Judge (GPT + Claude), rubrics, conflict resolution
  D: Implement Retrieval Eval thật (evaluate_batch)
  E: Tối ưu Runner async, thêm cost tracking, semaphore
  F: Thiết kế Release Gate logic, bắt đầu tích hợp main.py

GĐ3 (60 phút) ──────────────────────────────────────
  ALL: Chạy benchmark thật lần đầu, fix bugs
  B + F: Phân tích kết quả, viết Failure Analysis
  C: Chạy Position Bias check
  E: Đo performance, tối ưu nếu > 2 phút

GĐ4 (45 phút) ──────────────────────────────────────
  F: Chạy Regression V1 vs V2, hoàn thiện summary.json
  B: Hoàn thiện failure_analysis.md
  ALL: Viết Individual Reflection
  ALL: Chạy check_lab.py, commit & push
```

---


## 🏆 Chiến lược tối ưu điểm

### Ưu tiên tuyệt đối (tránh điểm liệt)
1. **Multi-Judge** phải gọi ít nhất 2 model API thật → nếu không sẽ bị giới hạn 30đ
2. **Retrieval Metrics** (Hit Rate & MRR) phải có trong `summary.json` → nếu không cũng bị giới hạn 30đ

### Ưu tiên cao (điểm cao nhất)
3. **Multi-Judge consensus** chiếm 15đ — nên đầu tư nhiều nhất: Cohen's Kappa, conflict resolution, position bias
4. **Golden Dataset 50+ cases** với Red Teaming — đảm bảo đa dạng difficulty levels

### Ưu tiên trung bình
5. **Async < 2 phút** + Cost report chi tiết
6. **Regression Gate** tự động với logic rõ ràng
7. **5 Whys analysis** sâu, chỉ root cause cụ thể

### Mẹo tối ưu điểm cá nhân (40đ)
- Mỗi người commit **riêng biệt** trên Git → chứng minh contribution
- Trong reflection, giải thích **tại sao** chọn approach đó, không chỉ mô tả "làm gì"
- Đề cập trade-off (ví dụ: "dùng GPT-4o cho judge tốn hơn nhưng accurate hơn GPT-3.5")
- Nếu gặp bug, mô tả chi tiết cách debug → điểm Problem Solving

### Kiểm tra trước khi nộp
```bash
python check_lab.py           # Validate format
```
Đảm bảo output có:
- ✅ `Retrieval Metrics (Hit Rate: XX%)`
- ✅ `Multi-Judge Metrics (Agreement Rate: XX%)`
- ✅ `Thông tin phiên bản Agent (Regression Mode)`
- File `analysis/reflections/reflection_[Tên].md` cho **mỗi thành viên**

---

## ⚠️ Những lỗi cần tránh

| Lỗi | Hậu quả | Cách tránh |
|:---|:---|:---|
| Chỉ dùng 1 Judge | Điểm nhóm max 30đ | Bắt buộc gọi 2+ model API |
| Không có Retrieval metrics | Điểm nhóm max 30đ | Đảm bảo `hit_rate` trong summary.json |
| Golden set < 50 cases | Mất điểm Dataset | Dùng SDG script để sinh đủ số lượng |
| Push .env lên GitHub | Lộ API key | Kiểm tra .gitignore |
| Không chạy check_lab.py | Trừ 5 điểm thủ tục | Chạy trước khi nộp |
| Không có reflection cá nhân | Mất 40đ cá nhân | Mỗi người tự viết |
| Code giả/placeholder | Không được điểm thực | Phải gọi API thật, xử lý data thật |
