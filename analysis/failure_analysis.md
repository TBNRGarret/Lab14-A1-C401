# Báo cáo Phân tích Thất bại (Failure Analysis Report)
**Dự án:** Trợ lý nội bộ CS + IT Helpdesk  
**Người phân tích:** Thành viên B (Data Analyst)  
**Ngày:** [Điền sau khi chạy benchmark]

---

## 1. Tổng quan Benchmark

### 1.1 Thống kê tổng quan
- **Tổng số cases:** 50+ (30+ từ Member A + 24 từ Member B)
- **Tỉ lệ Pass/Fail:** [Điền sau khi chạy] / [Điền sau khi chạy]
- **Pass Rate:** [XX]%

### 1.2 Điểm số trung bình
- **Điểm RAGAS trung bình:**
    - Faithfulness: 0.XX (độ trung thực - không bịa chuyện)
    - Relevancy: 0.XX (độ liên quan - câu trả lời có liên quan không)
- **Điểm LLM-Judge trung bình:** X.X / 5.0
    - GPT-4o Judge: X.X / 5.0
    - Gemini Judge: X.X / 5.0
    - Agreement Rate: XX% (% câu hỏi mà 2 judge đồng ý)

### 1.3 Retrieval Metrics
- **Hit Rate:** 0.XX (XX% câu hỏi tìm được tài liệu đúng trong top-K)
- **MRR (Mean Reciprocal Rank):** 0.XX (tài liệu đúng ở vị trí trung bình 1/MRR)

### 1.4 Performance Metrics
- **Tổng thời gian chạy:** [XX] phút [XX] giây
- **Thời gian trung bình/case:** [XX] giây
- **Total tokens used:** [XXXXX] tokens
- **Total cost:** $[XX.XX] USD

---

## 2. Phân nhóm lỗi (Failure Clustering)

| Nhóm lỗi | Số lượng | % | Nguyên nhân dự kiến | Ví dụ case |
|----------|----------|---|---------------------|------------|
| **Hallucination** | [X] | [XX]% | Retriever lấy sai context hoặc LLM bịa thông tin | case_XXX |
| **Incomplete Answer** | [X] | [XX]% | Prompt quá ngắn, không yêu cầu chi tiết đầy đủ | case_XXX |
| **Tone Mismatch** | [X] | [XX]% | Agent trả lời không chuyên nghiệp (quá suồng sã hoặc quá cứng nhắc) | case_XXX |
| **Out of Context Failure** | [X] | [XX]% | Agent không nói "Tôi không biết" khi không có thông tin | case_XXX |
| **Prompt Injection Success** | [X] | [XX]% | Agent bị lừa thực hiện lệnh adversarial | case_XXX |
| **Ambiguity Not Handled** | [X] | [XX]% | Agent không hỏi lại khi câu hỏi mập mờ | case_XXX |
| **Conflict Not Recognized** | [X] | [XX]% | Agent không nhận ra mâu thuẫn giữa 2 tài liệu | case_XXX |
| **Latency Timeout** | [X] | [XX]% | Xử lý quá lâu, vượt quá thời gian cho phép | case_XXX |

**Phân tích:**
- Nhóm lỗi chiếm tỉ lệ cao nhất: [Tên nhóm] ([XX]%)
- Nhóm lỗi nghiêm trọng nhất: [Tên nhóm] (ảnh hưởng đến [mô tả])

---

## 3. Phân tích 5 Whys (Chọn 3 case tệ nhất)

### Case #1: [ID case] - [Mô tả ngắn gọn]

**Symptom (Triệu chứng):**
- **Question:** [Câu hỏi]
- **Expected Answer:** [Câu trả lời kỳ vọng]
- **Actual Answer:** [Câu trả lời thực tế của Agent]
- **Judge Score:** [X]/5 (GPT: [X]/5, Gemini: [X]/5)
- **Retrieval:** Hit Rate = [0/1], MRR = [X.XX]

**5 Whys Analysis:**

1. **Why 1:** Tại sao Agent trả lời sai/không đúng?
   - **Trả lời:** [Mô tả nguyên nhân trực tiếp]

2. **Why 2:** Tại sao [nguyên nhân từ Why 1]?
   - **Trả lời:** [Đào sâu hơn]

3. **Why 3:** Tại sao [nguyên nhân từ Why 2]?
   - **Trả lời:** [Đào sâu hơn nữa]

4. **Why 4:** Tại sao [nguyên nhân từ Why 3]?
   - **Trả lời:** [Gần đến root cause]

5. **Why 5 (Root Cause):** Tại sao [nguyên nhân từ Why 4]?
   - **Root Cause:** [Nguyên nhân gốc rễ cụ thể - ví dụ: Chunking strategy, System Prompt, Retrieval algorithm, etc.]

**Action Items:**
- [ ] [Hành động cải tiến cụ thể 1]
- [ ] [Hành động cải tiến cụ thể 2]
- [ ] [Hành động cải tiến cụ thể 3]

---

### Case #2: [ID case] - [Mô tả ngắn gọn]

**Symptom (Triệu chứng):**
- **Question:** [Câu hỏi]
- **Expected Answer:** [Câu trả lời kỳ vọng]
- **Actual Answer:** [Câu trả lời thực tế của Agent]
- **Judge Score:** [X]/5 (GPT: [X]/5, Gemini: [X]/5)
- **Retrieval:** Hit Rate = [0/1], MRR = [X.XX]

**5 Whys Analysis:**

1. **Why 1:** [Câu hỏi và trả lời]
2. **Why 2:** [Câu hỏi và trả lời]
3. **Why 3:** [Câu hỏi và trả lời]
4. **Why 4:** [Câu hỏi và trả lời]
5. **Why 5 (Root Cause):** [Root cause cụ thể]

**Action Items:**
- [ ] [Hành động cải tiến cụ thể 1]
- [ ] [Hành động cải tiến cụ thể 2]

---

### Case #3: [ID case] - [Mô tả ngắn gọn]

**Symptom (Triệu chứng):**
- **Question:** [Câu hỏi]
- **Expected Answer:** [Câu trả lời kỳ vọng]
- **Actual Answer:** [Câu trả lời thực tế của Agent]
- **Judge Score:** [X]/5 (GPT: [X]/5, Gemini: [X]/5)
- **Retrieval:** Hit Rate = [0/1], MRR = [X.XX]

**5 Whys Analysis:**

1. **Why 1:** [Câu hỏi và trả lời]
2. **Why 2:** [Câu hỏi và trả lời]
3. **Why 3:** [Câu hỏi và trả lời]
4. **Why 4:** [Câu hỏi và trả lời]
5. **Why 5 (Root Cause):** [Root cause cụ thể]

**Action Items:**
- [ ] [Hành động cải tiến cụ thể 1]
- [ ] [Hành động cải tiến cụ thể 2]

---

## 4. Kế hoạch cải tiến (Action Plan)

### Priority 1 — CRITICAL (Ảnh hưởng > 30% lỗi)
- [ ] **[Tên action]:** [Mô tả chi tiết]
  - **Dự kiến cải thiện:** [Metric] từ [XX] → [YY] (+[Z]%)
  - **Effort:** [Low/Medium/High]
  - **Owner:** [Tên thành viên]
  - **Deadline:** [Ngày]

### Priority 2 — HIGH (Ảnh hưởng 15-30% lỗi)
- [ ] **[Tên action]:** [Mô tả chi tiết]
  - **Dự kiến cải thiện:** [Metric] từ [XX] → [YY] (+[Z]%)
  - **Effort:** [Low/Medium/High]
  - **Owner:** [Tên thành viên]

### Priority 3 — MEDIUM (Ảnh hưởng < 15% lỗi)
- [ ] **[Tên action]:** [Mô tả chi tiết]
  - **Dự kiến cải thiện:** [Metric] từ [XX] → [YY] (+[Z]%)
  - **Effort:** [Low/Medium/High]

---

## 5. Dự kiến cải tiến sau khi implement Action Plan

| Metric | Hiện tại | Mục tiêu | Cải thiện |
|--------|----------|----------|-----------|
| Pass Rate | [XX]% | [YY]% | +[Z]% |
| Hit Rate | 0.XX | 0.YY | +[Z]% |
| Faithfulness | 0.XX | 0.YY | +[Z]% |
| Avg Judge Score | X.X/5 | Y.Y/5 | +[Z] |
| Agreement Rate | XX% | YY% | +[Z]% |
| Cost per eval | $X.XX | $Y.YY | -[Z]% |

---

## 6. Lessons Learned

### 6.1 Điều gì hoạt động tốt?
- [Liệt kê các điểm mạnh của hệ thống hiện tại]

### 6.2 Điều gì cần cải thiện?
- [Liệt kê các điểm yếu cần ưu tiên]

### 6.3 Insights từ Red Teaming cases
- [Phân tích kết quả từ 24 adversarial/hard cases]
- [Agent xử lý tốt loại nào, yếu loại nào]

---

**Người phân tích:** Thành viên B  
**Ngày hoàn thành:** [Điền ngày]  
**Reviewed by:** [Tên reviewer nếu có]
