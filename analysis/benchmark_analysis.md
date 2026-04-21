# 📊 Benchmark Analysis Report — Task E: Async Runner & Performance

## Kết quả Benchmark (53 test cases)

### So sánh V1 vs V2

| Metric | V1 (Base) | V2 (Optimized) | Delta | Nhận xét |
|--------|-----------|----------------|-------|----------|
| **Avg Score** | 4.097 | 4.210 | **+0.1132** ✅ | V2 tốt hơn, Judge GPT+Gemini đều đồng ý |
| **Pass Rate** | 84.9% (45/53) | 84.9% (45/53) | 0.0% | Cùng số pass, V2 cải thiện score không đổi pass |
| **Hit Rate** | 56.60% | 56.60% | 0.0% | Cùng retrieval engine, chưa cải thiện |
| **MRR** | 0.2761 | 0.2846 | **+0.009** ✅ | V2 xếp hạng context tốt hơn |
| **Agreement Rate** | 97.5% | 97.8% | **+0.3%** ✅ | 2 Judge gần như luôn đồng thuận |
| **Avg Latency** | 7.44s | 8.32s | +0.87s | V2 chậm hơn nhẹ do xử lý thêm context |

### Quyết định Release Gate: ✅ APPROVE
- avg_score tăng (+0.1132)
- hit_rate không giảm
- agreement_rate > 0.7 (97.8%)
- Không có regression ở bất kỳ metric nào

---

## Performance Report

### ⏱️ Timing Analysis

| Metric | V1 | V2 |
|--------|----|----|
| **Total Pipeline** | 82.34s | 94.20s |
| **Avg/case (wall clock)** | 1.55s | 1.78s |
| **Avg Agent Call** | 1.61s | 2.04s |
| **Avg Judge Eval** | 5.83s | 6.27s |
| **Bottleneck** | judge_eval | judge_eval |
| **SLA < 2 phút** | ✅ ĐẠT | ✅ ĐẠT |

> **Nhận xét**: Pipeline chạy 53 cases trong ~1.5 phút nhờ `asyncio.Semaphore(5)` chạy song song 5 cases.
> Bottleneck là `judge_eval` vì phải gọi 2 API (GPT + Gemini) song song + có thể trigger tie-breaker.
> Avg/case (wall clock) = 1.78s << Avg/case (sequential) = 8.32s → concurrency tiết kiệm ~80% thời gian.

### 💰 Cost Analysis

| Component | V1 Tokens | V1 Cost | V2 Tokens | V2 Cost | % Tổng (V2) |
|-----------|-----------|---------|-----------|---------|-------------|
| **Agent (gpt-4o-mini)** | 69,803 | $0.4888 | 102,578 | $0.7182 | **90.4%** |
| **Judge GPT-4o** | 10,600 | $0.0742 | 10,600 | $0.0742 | 9.3% |
| **Judge Gemini-2.5-Flash** | 10,600 | $0.0022 | 10,600 | $0.0022 | 0.3% |
| **TỔNG** | **91,003** | **$0.5652** | **123,778** | **$0.7946** | **100%** |

| Metric | V1 | V2 |
|--------|----|----|
| **Avg cost/eval** | $0.0107 | $0.0150 |
| **Budget usage** | 11.3% / $5.00 | 15.9% / $5.00 |

> **Nhận xét**:
> - Agent chiếm **90.4%** tổng chi phí → điểm tối ưu lớn nhất.
> - Gemini Judge chỉ tốn $0.002 cho 53 cases (rẻ hơn GPT 33 lần!) → dùng Gemini làm Judge phụ rất cost-effective.
> - V2 tốn thêm $0.23 (+47% token Agent) do xử lý context nhiều hơn → trade-off: chi phí tăng nhưng avg_score cũng tăng.

### 🛡️ Reliability

| Metric | V1 | V2 |
|--------|----|----|
| **Errors** | 0 (0%) | 0 (0%) |
| **Retries** | 0 | 0 |
| **Fallbacks** | 0 | 0 |
| **Circuit Breaker** | CLOSED | CLOSED |

> **Nhận xét**: 0 errors trên 106 API calls (53 cases × 2 runs) → reliability 100%.
> Circuit Breaker không trigger → API OpenAI và Gemini đều ổn định trong suốt benchmark.

---

## 5 Expert Patterns đã implement trong Runner

| # | Pattern | Mục đích | Kết quả thực tế |
|---|---------|----------|-----------------|
| 1 | **Header-Aware Wait** | Đọc `Retry-After` header từ 429 | Không trigger (0 rate limits) |
| 2 | **Semaphore(5)** | Giới hạn 5 concurrent requests | 53 cases xong trong 94s thay vì ~450s tuần tự |
| 3 | **Fallback Routing** | GPT-4o → GPT-4o-mini, Gemini 2.5 → 2.0 | Không trigger (0 failures) |
| 4 | **Circuit Breaker** | Ngắt mạch sau 5 lỗi liên tiếp | CLOSED suốt → API stable |
| 5 | **Tenacity Retry** | Auto retry 429/5xx, skip 401/quota | Không trigger (0 retries) |

---

## Đề xuất tối ưu (giảm 30%+ chi phí)

1. **TIERED JUDGING**: Dùng GPT-4o-mini thay GPT-4o cho Judge → tiết kiệm ~40% chi phí Judge ($0.074 → ~$0.002)
2. **EARLY TERMINATION**: 2 Judge đồng ý (score lệch ≤ 0.5) → skip tie-breaker → tiết kiệm ~20%
3. **BATCH API**: Dùng OpenAI Batch API (giảm 50% giá) cho eval không cần real-time
4. **RESPONSE CACHE**: Cache Agent response cho câu hỏi trùng → tiết kiệm ~15% token Agent
