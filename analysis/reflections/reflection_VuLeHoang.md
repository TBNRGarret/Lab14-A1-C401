# Individual Reflection — Vũ Lê Hoàng

**Vai trò:** C — AI Engineer (Lead)  
**Task chính:** Task 4 — Multi-Judge Consensus Engine  
**File phụ trách:** `engine/llm_judge.py`, `test_llm_judge.py`

---

## 1. Engineering Contribution

Tôi thiết kế và triển khai class `LLMJudge` — thành phần cốt lõi của pipeline đánh giá AI.

**Các component chính:**
- **Dual Judge Engine**: Gọi song song GPT-4o-mini + Gemini 2.5 Flash qua `asyncio.gather()`, giảm latency xuống max thay vì sum.
- **Rubric System**: Prompt đánh giá 3 tiêu chí (Accuracy, Completeness, Tone) thang 1–5 với mô tả chi tiết từng mức.
- **Conflict Resolution**: Khi 2 judge lệch >1 điểm → gọi tie-breaker với context bất đồng → lấy median 3 kết quả.
- **Position Bias Detector**: Swap A/B và so sánh kết quả để phát hiện bias vị trí.
- **Cost Tracker**: Theo dõi token usage + chi phí USD theo từng model.

**Kỹ thuật đáng chú ý:**
- *Lazy init*: Client OpenAI/Gemini chỉ tạo khi cần, tránh overhead khởi động.
- *Robust JSON parsing*: 3 tầng fallback (direct → markdown block → regex) + fallback score=3 khi mọi cách thất bại → pipeline không bao giờ crash vì format lỗi.
- *Test suite*: 4 test scenarios (good answer, hallucination, position bias, cost tracking) — **4/4 PASS** với API keys thật.

---

## 2. Technical Depth

**MRR vs Hit Rate**: Hit Rate chỉ đo "có tìm thấy hay không"; MRR (`1/position`) phản ánh chất lượng ranking. Tài liệu đúng ở vị trí 1 sẽ được ưu tiên đưa vào context, tạo ra câu trả lời tốt hơn.

**Agreement Rate thay Cohen's Kappa**: Trên từng case đơn lẻ với 2 judge, tính Pe cho Kappa không có ý nghĩa thống kê. Tôi dùng agreement theo mức lệch (≤1 → 1.0, ≤2 → 0.5, >2 → 0.0) — trực quan và phù hợp với conflict resolution threshold.

**Position Bias**: Gọi judge 2 lần với thứ tự đảo ngược; nếu cả 2 lần đều chọn cùng vị trí (A hoặc B) thay vì cùng response → phát hiện bias. Test thực tế: GPT-4o-mini không bị position bias.

**Cost trade-off**: GPT-4o-mini (thay vì GPT-4o) giảm chi phí ~17× với chất lượng judge gần tương đương. Gemini 2.5 Flash bổ sung diversity. Tie-breaker dùng lại GPT-4o-mini thay vì gọi model thứ 3 → giảm dependency. Chi phí ước tính cho 50 cases: ~$0.10–0.15.

---

## 3. Problem Solving

**Gemini SDK synchronous trong async pipeline**: Dùng `loop.run_in_executor()` để chạy Gemini trong thread pool riêng, giữ nguyên lợi ích async khi `asyncio.gather()` với OpenAI.

**LLM trả JSON sai format**: Gemini đôi khi wrap JSON trong markdown hoặc thêm text thừa. Giải pháp: multi-fallback parser + `response_mime_type: "application/json"` trong generation config.

**Unicode trên Windows**: `cp1252` không hỗ trợ tiếng Việt → crash khi print. Fix: set `PYTHONIOENCODING=utf-8` trước khi chạy.

**Conflict resolution strategy**: Cân nhắc 4 phương án (trung bình / tin model mạnh hơn / gọi model thứ 3 / gọi lại với context bất đồng). Chọn phương án 4 — median của 3 kết quả — vì robust hơn mean với outlier, không cần thêm dependency, và tie-breaker có thêm context để judgment tốt hơn.
