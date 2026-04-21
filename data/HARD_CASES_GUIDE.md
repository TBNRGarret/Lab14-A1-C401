# Hướng dẫn thiết kế Hard Cases cho AI Evaluation

Để bài lab đủ độ khó cho nhóm 6 người, các bạn cần thiết kế các test cases có tính thử thách cao:

### 1. Adversarial Prompts (Tấn công bằng Prompt)
- **Prompt Injection:** Thử lừa Agent bỏ qua context để trả lời theo ý người dùng.
- **Goal Hijacking:** Yêu cầu Agent thực hiện một hành động không liên quan đến nhiệm vụ chính (ví dụ: đang là hỗ trợ kỹ thuật nhưng yêu cầu viết thơ về chính trị).

### 2. Edge Cases (Trường hợp biên)
- **Out of Context:** Đặt câu hỏi mà tài liệu không hề đề cập. Agent phải biết nói "Tôi không biết" thay vì bịa chuyện (Hallucination).
- **Ambiguous Questions:** Câu hỏi mập mờ, thiếu thông tin để xem Agent có biết hỏi lại (clarify) không.
- **Conflicting Information:** Đưa ra 2 đoạn tài liệu mâu thuẫn nhau để xem Agent xử lý thế nào.

### 3. Multi-turn Complexity
- **Context Carry-over:** Câu hỏi thứ 2 phụ thuộc vào câu trả lời thứ 1.
- **Correction:** Người dùng đính chính lại thông tin ở giữa cuộc hội thoại.

### 4. Technical Constraints
- **Latency Stress:** Yêu cầu Agent xử lý một đoạn văn bản cực dài để đo giới hạn latency.
- **Cost Efficiency:** Đánh giá xem Agent có đang dùng quá nhiều token không cần thiết cho các câu hỏi đơn giản không.

------

### Red Teaming Test Cases (24 cases)
**File:** `data/golden_set_B.jsonl`

**Phân loại:**
- ✅ **Adversarial Prompts (7 cases):**
  - case_B001: Prompt Injection (SLA P1)
  - case_B002: Goal Hijacking (HR phép năm)
  - case_B003: Data Exfiltration Attempt (VPN)
  - case_B004: Policy Modification Attempt (Refund)
  - case_B005: Privilege Escalation Attempt (Level 4 Access)
  - case_B020: Latency Stress Test
  - case_B021: Cost Efficiency Test

- ✅ **Edge Cases (6 cases):**
  - case_B006-B008: Out of Context (lương thưởng, bảo hiểm, dress code)
  - case_B009-B012: Ambiguous Questions (nghỉ phép, ticket, phần mềm, điểm lab)

- ✅ **Conflict Cases (3 cases):**
  - case_B013: Version Conflict (Level 2 Access 2 vs 3 ngày)
  - case_B014: Effective Date Conflict (Refund v4)
  - case_B015: SLA Version Conflict (P1 4h vs 6h)

- ✅ **Multi-turn & Reasoning (8 cases):**
  - case_B016-B017: Multi-turn (Password reset → Account locked)
  - case_B018-B019: Multi-turn with Correction (Level 3 → Level 2)
  - case_B022-B024: Reasoning (Remote eligibility, Schedule conflict, Leave carryover)
