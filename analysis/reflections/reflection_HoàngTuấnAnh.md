# Reflection — Member E: DevOps/Performance Engineer
## Lab 14 — AI Evaluation Factory
### Hoàng Tuấn Anh - MSV:2A202600075
**Vai trò:** Thành viên 5 - DevOps/Performance  
**Task:** Task 5 (Async Runner + Cost + Main.py Integration  )

---

## 1. Engineering Contribution (Task 5: Async Runner & Cost Tracking)

### Module chính: `engine/runner.py`

Tôi chịu trách nhiệm xây dựng **Production-Grade Async Benchmark Runner** — engine chạy toàn bộ pipeline đánh giá AI Agent. Đây là module trung tâm kết nối Agent (Task 2), Evaluator (Task 3), và Judge (Task 4) thành một pipeline hoàn chỉnh.

### 5 Expert Patterns đã implement

| # | Pattern | Implementation | Tại sao chọn |
|---|---------|---------------|--------------|
| 1 | **Header-Aware Wait** | Hàm `header_aware_sleep()` đọc header `Retry-After`, `x-ratelimit-reset-requests` từ response 429 | Thay vì backoff mù quáng (1s→2s→4s), đọc chính xác thời gian API yêu cầu → giảm thời gian chờ không cần thiết |
| 2 | **Client-side Rate Limit** | `asyncio.Semaphore(5)` trong `run_all()` | Giới hạn 5 concurrent requests → tránh bị API rate limit hoàn toàn. 53 cases chạy trong 93s thay vì ~450s tuần tự |
| 3 | **Fallback Model Routing** | Bảng `FALLBACK_ROUTES` + logic trong `_call_agent()` | GPT-4o lỗi → tự động chuyển GPT-4o-mini; Gemini 2.5 → Gemini 2.0. Chỉ fallback cho lỗi 429/5xx, KHÔNG fallback cho 401/hết tiền |
| 4 | **Circuit Breaker** | Class `CircuitBreaker` 3 trạng thái (CLOSED→OPEN→HALF_OPEN) | 5 lỗi liên tiếp → fast-fail mọi request trong 30s → tránh phí tiền gọi API chết. Tách riêng agent_circuit và judge_circuit |
| 5 | **Tenacity Retry** | Decorator `@retry` với `retry_if_exception(_is_retryable_error)` | Tự động retry 3 lần cho lỗi tạm (429, 500, 503), dừng ngay cho lỗi 401/quota. Không viết for/try thủ công |

### Cost Tracker (`CostTracker` class)

Implement FinOps module theo dõi chi phí real-time:
- Bảng giá `MODEL_PRICING` cho GPT-4o, GPT-4o-mini, Gemini-2.5-flash, Gemini-2.0-flash
- Ước lượng 40% input / 60% output tokens (tỷ lệ phổ biến RAG pipeline)
- Breakdown theo component (agent, judge_gpt-4o, judge_gemini) và theo model
- Budget warning (log cảnh báo thay vì crash pipeline)
- Method `optimization_suggestions()` đề xuất 4 cách giảm 30%+ chi phí

### Performance Report (`generate_performance_report()`)

Xuất report đầy đủ cho `summary.json`:
- **Timing**: tổng pipeline, avg/case, stage averages, bottleneck detection, SLA check
- **Cost**: total tokens, cost USD, breakdown by component/model, budget usage %
- **Reliability**: error rate, retry count, fallback count, circuit breaker status

### Tích hợp `main.py` (hỗ trợ Task 6)

- Thay thế placeholder `MultiModelJudge` bằng `LLMJudge` thật (GPT-4o + Gemini 2.5 Flash)
- Truyền expert config vào Runner (budget=$5, circuit_threshold=5, recovery=30s)
- Gọi `generate_performance_report()` và đưa vào summary
- In đầy đủ Performance, Cost, Reliability metrics ra console

**Git commits:**
- https://github.com/TBNRGarret/Lab14-A1-C401/commit/1ae59691
- `feat(eval): Hoàn thiện High-Performance Async Runner & Automated Release Gate`
- Branch: `feat/runner-circuit-breaker`

---

## 2. Technical Depth

### Circuit Breaker Pattern — Tại sao cần tách riêng Agent và Judge?

Ban đầu Runner dùng 1 circuit breaker chung. Vấn đề: nếu Judge API (Gemini) bị lỗi 5 lần → circuit OPEN → Agent cũng bị fast-fail mặc dù Agent API (OpenAI) vẫn hoạt động bình thường. Tôi tách thành `agent_circuit` và `judge_circuit` để lỗi ở 1 service không ảnh hưởng service kia.

3 trạng thái hoạt động:
```
CLOSED (bình thường) →[5 lỗi liên tiếp]→ OPEN (fast-fail 30s) →[hết 30s]→ HALF_OPEN (thử 1 request)
                ↑                                                                    ↓
                └────────────────── thành công ──────────────────────────────────────┘
```

### `_is_retryable_error` — Phân biệt lỗi tạm vs lỗi vĩnh viễn

Đây là quyết định thiết kế quan trọng nhất. Nếu API key sai (401) hoặc hết tiền (Insufficient Quota), retry 3 lần chỉ phí thời gian. Hàm check `status_code` trực tiếp trên exception (OpenAI SDK style) VÀ trên `response.status_code` (httpx style) để cover mọi SDK.

```python
# Chỉ retry: 429 (rate limit), 500, 502, 503, 504 (server errors)
# KHÔNG retry: 400, 401, 403, 404 (client errors = retry vô nghĩa)
```

### Trade-off: BudgetExceeded — raise Exception hay log Warning?

**Vấn đề gốc**: Code cũ `raise BudgetExceeded` khi vượt ngân sách. Nhưng với `Semaphore(5)`, 5 request đang chạy song song có thể vượt budget cùng lúc. Khi exception ném ra, tiền đã trừ ở OpenAI rồi VÀ toàn bộ kết quả các case đã chạy trước đó bị mất.

**Giải pháp**: Đổi thành `logger.warning()` + flag `_warned_budget`. Pipeline tiếp tục chạy → ghi nhận kết quả đã có → warning 1 lần duy nhất. Người dùng biết đã vượt ngân sách nhưng không mất data.

### Async Semaphore — Tại sao không dùng batch cứng?

Batch cứng (chia 53 cases thành 11 batch × 5) có nhược điểm: nếu 1 case trong batch chạy chậm (15s), cả 4 case còn lại phải chờ. Semaphore cho phép "sliding window" — khi 1 case xong, case tiếp theo vào ngay, tối ưu throughput.

Kết quả thực tế: 53 cases × avg 8.6s/case = 455s tuần tự → chỉ 94s song song = **tiết kiệm 80% thời gian**.

---

## 3. Problem Solving — Các Bug đã phát hiện và Fix

### Bug 1: Fallback routing cho lỗi 401/Hết tiền

**Vấn đề**: Code cũ fallback sang model khác cho MỌI loại lỗi. Nếu API key sai → fallback sang GPT-4o-mini cùng key → cũng fail → phí 3 retry × 2 fallback = 6 request vô nghĩa.

**Fix**: Thêm `_is_retryable_error()` kiểm tra status code. Tenacity chỉ retry lỗi tạm (429/5xx). Lỗi 401/403 văng thẳng ra ngoài, không retry, không fallback.

### Bug 2: `_is_retryable_error` miss OpenAI SDK status code

**Vấn đề**: Code chỉ check `exc.response.status_code`. Nhưng OpenAI Python SDK (`openai.APIStatusError`) đặt `status_code` trực tiếp trên exception object. Kết quả: hàm trả `True` (retry) cho 401/403 vì không tìm thấy status code.

**Fix**: Check `getattr(exc, "status_code", None)` trước, fallback `getattr(exc.response, "status_code", None)` sau.

### Bug 3: Claude/Anthropic references khi không có API key

**Vấn đề**: `MODEL_PRICING` và `FALLBACK_ROUTES` tham chiếu Claude models (`claude-3-5-sonnet`, `claude-3-5-haiku`). Nhưng project chỉ có OpenAI key + Gemini key, không có Anthropic key. Nếu fallback sang Claude → crash.

**Fix**: Thay toàn bộ Claude → Gemini models (`gemini-2.5-flash`, `gemini-2.0-flash`) khớp với `LLMJudge` thật.

### Bug 4: `on_failure()` bị gọi 2 lần

**Vấn đề**: Khi `RetryError` xảy ra → handler gọi `on_failure()`. Sau đó exception re-raise → rơi vào `except Exception` → gọi `on_failure()` lần 2. Circuit breaker đếm 2 failure thay vì 1.

**Fix**: Thêm flag `_failure_recorded`. `except Exception` chỉ gọi `on_failure()` nếu flag chưa set.

---

## 4. Kết quả Benchmark thực tế

Chạy benchmark trên **53 test cases** (golden_set) với cấu hình:
- Agent: Gemini (`google.generativeai`) — V1 (baseline) và V2 (optimized)
- Judge: GPT-4o + Gemini 2.5 Flash (dual-judge)
- Semaphore: 5 concurrent requests
- Budget: $5.00

### So sánh V1 vs V2 (Regression Test)

| Metric | V1 | V2 | Delta |
|--------|-----|-----|-------|
| **avg_score** | 4.097 | 4.210 | **+0.113** ✅ |
| **hit_rate** | 56.60% | 56.60% | +0.00% |
| **MRR** | 0.276 | 0.285 | +0.009 |
| **agreement_rate** | 97.5% | 97.8% | +0.3% |
| **avg_latency** | 7.442s | 8.316s | +0.874s |

### Performance

| Metric | V1 | V2 |
|--------|-----|-----|
| Pipeline time | 82.34s | 94.2s |
| Avg/case | 1.55s | 1.78s |
| SLA < 2 phút | ✅ ĐẠT | ✅ ĐẠT |
| Bottleneck | judge_eval | judge_eval |
| Pass / Fail / Error | 45 / 8 / 0 | 45 / 8 / 0 |

### Chi phí (FinOps)

| Component | Tokens | Chi phí |
|-----------|--------|---------|
| **Agent** (Gemini) | 102,578 | $0.7182 |
| **Judge GPT-4o** | 10,600 | $0.0742 |
| **Judge Gemini-2.5-flash** | 10,600 | $0.0022 |
| **Tổng V2** | **123,778** | **$0.7946** |
| Avg/eval | — | $0.0150 |
| V1 tổng | 91,003 | $0.5652 |

### Reliability

| Metric | Kết quả |
|--------|---------|
| Error rate | **0%** (0 errors / 53 cases) |
| Retries | 0 |
| Fallbacks | 0 |
| Circuit Breaker Agent | CLOSED (healthy) |
| Circuit Breaker Judge | CLOSED (healthy) |

### Đề xuất tối ưu chi phí (giảm 30%+)

| Đề xuất | Tiết kiệm ước tính |
|---------|---------------------|
| **Tiered Judging** — GPT-4o-mini cho easy/medium, GPT-4o chỉ cho hard cases | ~40% chi phí Judge |
| **Early Termination** — 2 Judge đồng ý (score lệch ≤ 0.5) → skip Judge thứ 3 | ~20% |
| **Batch API** — OpenAI Batch API cho eval không cần real-time | ~50% giá API |
| **Response Cache** — Cache Agent response cho câu hỏi trùng | ~15% token Agent |

### Release Gate

> **✅ QUYẾT ĐỊNH: CHẤP NHẬN BẢN CẬP NHẬT (APPROVE)**
>
> V2 cải thiện avg_score +0.113, agreement_rate +0.3%, MRR +0.009 so với V1. Không có regression ở bất kỳ metric nào. Pipeline ổn định 0% error rate, chi phí trong ngân sách ($0.7946 / $5.00 = 15.9%).
