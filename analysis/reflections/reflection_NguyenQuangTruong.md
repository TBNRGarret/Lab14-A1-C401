# Lab 14 — AI Evaluation Factory

**Họ và tên:** Nguyễn Quang Trường   
**Vai trò:** Member B - Data Analyst  
**MSSV:** 2A202600196   
**Ngày:** 2026-04-21

---

## 1. Engineering Contribution 

### Task 1: Red Teaming Test Cases (24 cases)

Thiết kế 24 adversarial/hard test cases cho domain CS + IT Helpdesk:
- **7 Adversarial:** Prompt injection, goal hijacking, privilege escalation
- **6 Edge Cases:** Out-of-context, ambiguous questions
- **3 Conflict Cases:** Version conflicts, effective date conflicts
- **8 Multi-turn & Reasoning:** Context carry-over, correction, complex reasoning

**File:** `data/golden_set_B.jsonl`

**Commit 1: Red Teaming Test Cases**
```
feat: Red Teaming Test Cases
- 24 adversarial/hard test cases for CS+IT Helpdesk
- Mapped to real corpus from data/docs/
```
🔗 https://github.com/TBNRGarret/Lab14-A1-C401/commit/bf52130

---

### Task 7: Failure Analysis Report

Phân tích 53 test cases với kết quả thực tế:
- **Pass rate:** 81.13% (43/53)
- **Failure clustering:** 4 nhóm lỗi (Out-of-Context 40%, Retrieval 30%, Prompt Injection 20%, Incomplete 10%)
- **5 Whys analysis:** 3 worst cases với root causes:
  - System Prompt thiếu defensive instructions
  - Thiếu Input Validation layer
  - Hit Rate thấp (56.6%) do thiếu query rewriting
- **Action Plan:** Priority 1/2/3 với dự kiến cải thiện cụ thể

**File:** `analysis/failure_analysis.md`

**Commit 2: Failure Analysis Report**
```
update: Failure Analysis Report
- Analyzed 53 test cases (81.13% pass rate)
- 5 Whys analysis with root causes
- Action plan with priorities
```
🔗 https://github.com/TBNRGarret/Lab14-A1-C401/commit/f4ae8e5

---

## 2. Technical Depth 

### MRR (Mean Reciprocal Rank)
**Định nghĩa:** Đo vị trí trung bình của tài liệu đúng đầu tiên trong kết quả retrieval.

**Công thức:** MRR = (1/pos₁ + 1/pos₂ + ... + 1/posₙ) / N

**Ví dụ thực tế từ Lab 14:**
- Case 1: Doc đúng ở vị trí 1 → RR = 1/1 = 1.0
- Case 2: Doc đúng ở vị trí 3 → RR = 1/3 = 0.33
- Case 3: Không tìm thấy → RR = 0
- **MRR = (1.0 + 0.33 + 0) / 3 = 0.44**

**Kết quả Lab 14:** MRR = 0.2761 → doc đúng ở vị trí trung bình ~3.6 (thấp)

**Tại sao quan trọng:** LLM đọc context theo thứ tự, doc ở vị trí 1 có ảnh hưởng lớn hơn vị trí 10. MRR thấp → cần reranking.

---

### Cohen's Kappa
**Định nghĩa:** Đo độ tin cậy của sự đồng thuận giữa 2 judge, loại bỏ yếu tố ngẫu nhiên.

**Công thức:** κ = (Pₒ - Pₑ) / (1 - Pₑ)
- Pₒ = % đồng ý thực tế
- Pₑ = % đồng ý ngẫu nhiên

**Thang đo:**
- κ < 0.4: Đồng thuận yếu
- 0.4 ≤ κ < 0.6: Trung bình
- 0.6 ≤ κ < 0.8: Tốt
- κ ≥ 0.8: Rất tốt

**Ví dụ tính toán:**
- 2 judge chấm 100 cases
- Đồng ý: 80 cases → Pₒ = 0.8
- Nếu ngẫu nhiên: Pₑ = 0.5
- κ = (0.8 - 0.5) / (1 - 0.5) = 0.6 (Tốt)

**Kết quả Lab 14:** Agreement Rate = 97.47% → κ rất cao, chứng tỏ 2 judge (GPT-4o + Gemini) đồng thuận tốt, rubric rõ ràng.

---

### Position Bias
**Định nghĩa:** Judge có xu hướng ưu tiên response ở vị trí đầu tiên (A) hơn vị trí thứ hai (B).

**Nguyên nhân:** LLM có "primacy effect" - chú ý nhiều hơn vào thông tin đầu tiên.

**Cách phát hiện:**
1. Chạy judge với thứ tự: Response A, Response B → Score A₁, B₁
2. Đảo thứ tự: Response B, Response A → Score B₂, A₂
3. Nếu |A₁ - A₂| > 1 điểm → có position bias

**Cách khắc phục:**
- Shuffle thứ tự A/B ngẫu nhiên
- Chạy 2 lần và lấy trung bình
- Dùng rubric chi tiết để giảm subjectivity

**Tại sao quan trọng:** Position bias làm sai lệch kết quả benchmark, có thể chọn nhầm agent tốt hơn.

---

### Trade-off Chi phí vs Chất lượng
**Kết quả thực tế Lab 14 (V1):**

| Judge Model | Cost | % Total Cost | Accuracy |
|-------------|------|--------------|----------|
| GPT-4o | $0.0742 | 13.1% | ~95% |
| Gemini Flash | $0.002226 | 0.4% | ~90% |

**Insight:** Gemini rẻ hơn 33x nhưng vẫn accurate (Agreement Rate 97.47%)!

**Chiến lược tối ưu:**
1. **Tiered Judging:** Dùng Gemini cho easy/medium cases (60%), GPT-4o cho hard/adversarial (40%)
2. **Early Termination:** Nếu 2 judge đồng ý (score lệch ≤ 0.5) → skip judge thứ 3
3. **Kết quả:** Tiết kiệm ~40% chi phí judge, chỉ giảm ~5% accuracy

**Trade-off trong Lab 14:**
- V2 tăng top_k từ 5→7 → tăng 40% token input → tăng cost từ $0.565 → $0.796
- Nhưng avg_score tăng 4.09 → 4.19 (+2.4%)
- **Quyết định:** APPROVE vì quality improvement đáng giá

---

## 3. Problem Solving 

### Problem 1: Red Teaming cases không map được với corpus IDs

**Vấn đề phát sinh:**
Khi tạo 24 Red Teaming cases, tôi dùng format `expected_retrieval_ids` như `["access_level_01", "hr_remote_04"]` theo SDG Playbook. Nhưng khi Member D implement TF-IDF retrieval, agent trả về IDs dạng `["it_helpdesk_faq_chunk000", "access_control_sop_chunk012"]` → không match được.

**Nguyên nhân:**
- Không có schema thống nhất cho ID format giữa các thành viên
- SDG Playbook chỉ đưa ví dụ nhưng không enforce format
- Thiếu communication về ID naming convention

**Giải pháp:**
1. **Ngắn hạn:** Thêm logic trong `retrieval_eval.py` để filter chỉ cases có `expected_retrieval_ids` hợp lệ. Cases không match vẫn được eval về answer quality, chỉ skip retrieval metrics.
2. **Dài hạn:** Update `data/golden_case.schema.json` để enforce ID format pattern: `{source}_{section}_{index}`
3. **Communication:** Sync với Member D về ID format trước khi finalize golden set

**Kết quả:**
- Retrieval eval chạy thành công cho 30/53 cases có IDs hợp lệ
- 23 cases còn lại vẫn được eval về answer quality
- Không có case nào bị crash do ID mismatch

---


### Problem 2: Benchmark chạy quá lâu (>5 phút cho 53 cases)

**Vấn đề phát sinh:**
Lần đầu chạy benchmark, mất >5 phút cho 53 cases (target: <2 phút). Bottleneck ở judge eval (mỗi case ~8 giây).

**Nguyên nhân:**
- 2 judge (GPT-4o + Gemini) chạy tuần tự (sequential) thay vì song song
- Không có rate limiting → API throttling
- Mỗi judge call riêng lẻ thay vì batch

**Giải pháp (do Member E implement):**
1. **Async concurrent calls:** Dùng `asyncio.gather()` để gọi 2 judge song song
2. **Semaphore rate limiting:** `asyncio.Semaphore(5)` để tránh API throttling
3. **Circuit breaker:** Tự động retry khi API fail

**Kết quả:**
- Thời gian giảm từ >5 phút → 85 giây (V1) và 94 giây (V2)
- Meets SLA: <2 phút cho 50 cases 
- Bottleneck vẫn là judge eval nhưng đã tối ưu tốt

---

## 4. Lessons Learned

**Điều tốt:**
- Agreement Rate 97.47% → 2 judge đồng thuận tốt
- Pass rate 81.13% → Agent xử lý tốt cases bình thường
- Cost efficiency → Chỉ dùng 11.3% budget

**Cần cải thiện:**
- Retrieval Quality (Hit Rate 56.6%) → bottleneck lớn nhất
- Adversarial Defense (40% failed cases) → cần input validation
- Out-of-Context handling → Agent không consistent

**Insight từ Red Teaming:**
- Agent tốt: Multi-turn, reasoning, conflict detection
- Agent yếu: Adversarial prompts, out-of-context, ambiguous questions

---

**Tổng kết:** Vai trò Data Analyst giúp tôi hiểu sâu về test case design, root cause analysis, và trade-offs trong AI evaluation. Kinh nghiệm quý giá cho AI Engineering.

---

**All commits:**
🔗 https://github.com/TBNRGarret/Lab14-A1-C401/commits/luckyman2907?author=luckyman2907