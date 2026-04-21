import asyncio
import json
import os
import re
import statistics
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────
# Judge Rubric Prompt — Dùng chung cho cả GPT và Gemini
# ─────────────────────────────────────────────────────────
JUDGE_SYSTEM_PROMPT = """Bạn là một AI Judge chuyên nghiệp, chuyên đánh giá chất lượng câu trả lời của AI Agent.

Hãy chấm điểm câu trả lời theo 3 tiêu chí dưới đây, mỗi tiêu chí từ 1 đến 5:

### 1. Accuracy (Độ chính xác) — 1-5
- 5: Hoàn toàn chính xác, khớp với Ground Truth, không sai sót.
- 4: Đúng phần lớn, chỉ thiếu vài chi tiết nhỏ.
- 3: Đúng một phần, có thiếu sót đáng kể hoặc thông tin thừa.
- 2: Sai nhiều điểm quan trọng hoặc bịa thông tin (hallucination).
- 1: Hoàn toàn sai hoặc không liên quan.

### 2. Completeness (Độ đầy đủ) — 1-5
- 5: Trả lời đầy đủ mọi khía cạnh của câu hỏi.
- 4: Trả lời tốt nhưng thiếu 1-2 chi tiết phụ.
- 3: Trả lời được ý chính nhưng thiếu nhiều chi tiết.
- 2: Trả lời rất sơ sài.
- 1: Không trả lời được câu hỏi.

### 3. Tone (Ngữ điệu chuyên nghiệp) — 1-5
- 5: Ngôn ngữ chuyên nghiệp, rõ ràng, dễ hiểu.
- 4: Khá chuyên nghiệp, có thể cải thiện nhỏ.
- 3: Bình thường, không nổi bật.
- 2: Ngôn ngữ thiếu chuyên nghiệp hoặc khó hiểu.
- 1: Ngôn ngữ rất kém hoặc thiếu tôn trọng.

⚠️ BẮT BUỘC trả về ĐÚNG định dạng JSON sau (không thêm bất kỳ text nào khác):
```json
{
  "accuracy": <1-5>,
  "completeness": <1-5>,
  "tone": <1-5>,
  "reasoning": "<giải thích ngắn gọn lý do chấm điểm>"
}
```"""

JUDGE_USER_PROMPT_TEMPLATE = """Hãy đánh giá câu trả lời sau:

**Câu hỏi:** {question}

**Câu trả lời của Agent:** {answer}

**Ground Truth (Đáp án chuẩn):** {ground_truth}

Hãy trả về JSON đánh giá."""


# ─────────────────────────────────────────────────────────
# Position Bias Check Prompt
# ─────────────────────────────────────────────────────────
POSITION_BIAS_PROMPT = """So sánh 2 câu trả lời dưới đây cho cùng một câu hỏi và chọn câu trả lời TỐT HƠN.

**Câu hỏi:** {question}

**Response A:** {response_a}

**Response B:** {response_b}

Trả về JSON: {{"winner": "A" hoặc "B", "reasoning": "..."}}"""


class LLMJudge:
    """
    Multi-Judge Consensus Engine sử dụng OpenAI GPT-4o và Google Gemini 2.5 Flash.
    
    Features:
    - Gọi 2 model judge song song (async)
    - Tính Agreement Rate 
    - Xử lý xung đột tự động khi 2 judge lệch > 1 điểm
    - Check Position Bias
    - Track token usage & cost
    """

    def __init__(self):
        # ── OpenAI Client ──
        self.openai_api_key = os.getenv("OPEN_AI_API_KEY", "")
        self.openai_model = "gpt-4o-mini"
        
        # ── Gemini Client ──
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = "gemini-2.5-flash"
        
        # ── Cost Tracking ──
        self.total_tokens = {"openai_input": 0, "openai_output": 0, "gemini_input": 0, "gemini_output": 0}
        self.total_cost_usd = 0.0
        
        # Bảng giá token (USD per token)
        self.cost_table = {
            "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
            "gemini-2.5-flash": {"input": 0.075 / 1_000_000, "output": 0.30 / 1_000_000},
        }

        # ── Init clients ──
        self._openai_client = None
        self._gemini_model_instance = None

    # ═══════════════════════════════════════════════════════
    # Lazy initialization — chỉ tạo client khi cần
    # ═══════════════════════════════════════════════════════
    def _get_openai_client(self):
        if self._openai_client is None:
            from openai import AsyncOpenAI
            self._openai_client = AsyncOpenAI(api_key=self.openai_api_key)
        return self._openai_client

    def _get_gemini_model(self):
        if self._gemini_model_instance is None:
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_api_key)
            self._gemini_model_instance = genai.GenerativeModel(self.gemini_model)
        return self._gemini_model_instance

    # ═══════════════════════════════════════════════════════
    # Gọi từng Judge riêng lẻ
    # ═══════════════════════════════════════════════════════
    async def _judge_with_openai(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        """Gọi GPT-4o làm Judge. Trả về scores + token usage."""
        client = self._get_openai_client()
        user_prompt = JUDGE_USER_PROMPT_TEMPLATE.format(
            question=question, answer=answer, ground_truth=ground_truth
        )

        try:
            response = await client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )

            # Track tokens
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0
            self.total_tokens["openai_input"] += input_tokens
            self.total_tokens["openai_output"] += output_tokens

            cost = (input_tokens * self.cost_table["gpt-4o"]["input"] +
                    output_tokens * self.cost_table["gpt-4o"]["output"])
            self.total_cost_usd += cost

            result = json.loads(response.choices[0].message.content)
            result["model"] = "gpt-4o"
            result["tokens"] = {"input": input_tokens, "output": output_tokens}
            result["cost_usd"] = round(cost, 6)
            return result

        except Exception as e:
            print(f"  ⚠️ OpenAI Judge error: {e}")
            return {
                "accuracy": 3, "completeness": 3, "tone": 3,
                "reasoning": f"OpenAI error fallback: {str(e)[:100]}",
                "model": "gpt-4o", "tokens": {"input": 0, "output": 0}, "cost_usd": 0,
                "error": True
            }

    async def _judge_with_gemini(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        """Gọi Gemini 2.5 Flash làm Judge. Trả về scores + token usage."""
        model = self._get_gemini_model()
        user_prompt = JUDGE_USER_PROMPT_TEMPLATE.format(
            question=question, answer=answer, ground_truth=ground_truth
        )
        full_prompt = f"{JUDGE_SYSTEM_PROMPT}\n\n---\n\n{user_prompt}"

        try:
            # Gemini SDK là sync → chạy trong thread pool để không block event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(
                    full_prompt,
                    generation_config={"temperature": 0.0, "response_mime_type": "application/json"}
                )
            )

            # Track tokens
            usage_meta = response.usage_metadata
            input_tokens = getattr(usage_meta, "prompt_token_count", 0) if usage_meta else 0
            output_tokens = getattr(usage_meta, "candidates_token_count", 0) if usage_meta else 0
            self.total_tokens["gemini_input"] += input_tokens
            self.total_tokens["gemini_output"] += output_tokens

            cost = (input_tokens * self.cost_table["gemini-2.5-flash"]["input"] +
                    output_tokens * self.cost_table["gemini-2.5-flash"]["output"])
            self.total_cost_usd += cost

            # Parse JSON từ response text
            raw_text = response.text.strip()
            result = self._parse_json_response(raw_text)
            result["model"] = "gemini-2.5-flash"
            result["tokens"] = {"input": input_tokens, "output": output_tokens}
            result["cost_usd"] = round(cost, 6)
            return result

        except Exception as e:
            print(f"  ⚠️ Gemini Judge error: {e}")
            return {
                "accuracy": 3, "completeness": 3, "tone": 3,
                "reasoning": f"Gemini error fallback: {str(e)[:100]}",
                "model": "gemini-2.5-flash", "tokens": {"input": 0, "output": 0}, "cost_usd": 0,
                "error": True
            }

    # ═══════════════════════════════════════════════════════
    # CORE: Multi-Judge Consensus
    # ═══════════════════════════════════════════════════════
    async def evaluate_multi_judge(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        """
        Gọi 2 model Judge (GPT-4o + Gemini) song song.
        Tính Agreement Rate, xử lý xung đột, trả về final score.
        
        Interface contract (runner.py yêu cầu):
          - final_score: float
          - agreement_rate: float
        """
        # ── Bước 1: Gọi 2 judge song song ──
        openai_result, gemini_result = await asyncio.gather(
            self._judge_with_openai(question, answer, ground_truth),
            self._judge_with_gemini(question, answer, ground_truth),
        )

        # ── Bước 2: Tính trung bình mỗi tiêu chí ──
        criteria = ["accuracy", "completeness", "tone"]
        scores_openai = {c: openai_result.get(c, 3) for c in criteria}
        scores_gemini = {c: gemini_result.get(c, 3) for c in criteria}

        avg_openai = statistics.mean(scores_openai.values())
        avg_gemini = statistics.mean(scores_gemini.values())

        # ── Bước 3: Tính Agreement Rate ──
        agreements = []
        conflict_details = []
        for c in criteria:
            diff = abs(scores_openai[c] - scores_gemini[c])
            if diff <= 1:
                agreements.append(1.0)
            elif diff <= 2:
                agreements.append(0.5)
                conflict_details.append(f"{c}: GPT={scores_openai[c]}, Gemini={scores_gemini[c]} (lệch {diff})")
            else:
                agreements.append(0.0)
                conflict_details.append(f"{c}: GPT={scores_openai[c]}, Gemini={scores_gemini[c]} (lệch {diff} ⚠️)")

        agreement_rate = statistics.mean(agreements)

        # ── Bước 4: Xử lý xung đột (Conflict Resolution) ──
        overall_diff = abs(avg_openai - avg_gemini)
        resolution_method = "average"
        
        if overall_diff > 1.0:
            # Xung đột lớn → gọi lại OpenAI với yêu cầu đánh giá kỹ hơn (tie-breaker)
            resolution_method = "tie-breaker (re-evaluate)"
            tiebreak_result = await self._tiebreak_judge(question, answer, ground_truth, 
                                                          avg_openai, avg_gemini)
            final_score = statistics.median([avg_openai, avg_gemini, tiebreak_result])
        else:
            # Đồng thuận → lấy trung bình
            final_score = (avg_openai + avg_gemini) / 2

        # ── Bước 5: Tổng hợp reasoning ──
        combined_reasoning = (
            f"[GPT-4o] {openai_result.get('reasoning', 'N/A')} | "
            f"[Gemini] {gemini_result.get('reasoning', 'N/A')}"
        )

        return {
            "final_score": round(final_score, 2),
            "agreement_rate": round(agreement_rate, 2),
            "reasoning": combined_reasoning,
            "resolution_method": resolution_method,
            "individual_scores": {
                "gpt-4o": {
                    "accuracy": scores_openai["accuracy"],
                    "completeness": scores_openai["completeness"],
                    "tone": scores_openai["tone"],
                    "avg": round(avg_openai, 2),
                    "reasoning": openai_result.get("reasoning", ""),
                    "tokens": openai_result.get("tokens", {}),
                    "cost_usd": openai_result.get("cost_usd", 0),
                },
                "gemini-2.5-flash": {
                    "accuracy": scores_gemini["accuracy"],
                    "completeness": scores_gemini["completeness"],
                    "tone": scores_gemini["tone"],
                    "avg": round(avg_gemini, 2),
                    "reasoning": gemini_result.get("reasoning", ""),
                    "tokens": gemini_result.get("tokens", {}),
                    "cost_usd": gemini_result.get("cost_usd", 0),
                },
            },
            "conflicts": conflict_details if conflict_details else None,
        }

    # ═══════════════════════════════════════════════════════
    # Tie-breaker: Gọi lại khi 2 judge xung đột nặng
    # ═══════════════════════════════════════════════════════
    async def _tiebreak_judge(self, question: str, answer: str, ground_truth: str,
                               score_a: float, score_b: float) -> float:
        """
        Khi 2 Judge lệch > 1 điểm, gọi lại GPT-4o với context rằng
        có sự bất đồng, yêu cầu đánh giá cẩn thận hơn.
        """
        tiebreak_prompt = f"""Hai AI Judge đã đánh giá câu trả lời này với kết quả RẤT KHÁC NHAU:
- Judge A cho điểm trung bình: {score_a:.1f}/5
- Judge B cho điểm trung bình: {score_b:.1f}/5

Hãy đánh giá LẠI một cách cẩn thận và công bằng.

**Câu hỏi:** {question}
**Câu trả lời:** {answer}
**Ground Truth:** {ground_truth}

Chỉ trả về một số từ 1 đến 5 (float được), không thêm text khác."""

        try:
            client = self._get_openai_client()
            response = await client.chat.completions.create(
                model=self.openai_model,
                messages=[{"role": "user", "content": tiebreak_prompt}],
                temperature=0.0,
                max_tokens=10,
            )
            
            # Track tokens
            usage = response.usage
            if usage:
                self.total_tokens["openai_input"] += usage.prompt_tokens
                self.total_tokens["openai_output"] += usage.completion_tokens
                cost = (usage.prompt_tokens * self.cost_table["gpt-4o"]["input"] +
                        usage.completion_tokens * self.cost_table["gpt-4o"]["output"])
                self.total_cost_usd += cost

            raw = response.choices[0].message.content.strip()
            # Tìm số trong response
            numbers = re.findall(r"[\d.]+", raw)
            if numbers:
                score = float(numbers[0])
                return max(1.0, min(5.0, score))  # Clamp 1-5
            return (score_a + score_b) / 2  # Fallback
        except Exception as e:
            print(f"  ⚠️ Tiebreak error: {e}")
            return (score_a + score_b) / 2

    # ═══════════════════════════════════════════════════════
    # Position Bias Check
    # ═══════════════════════════════════════════════════════
    async def check_position_bias(self, question: str, response_a: str, response_b: str) -> Dict[str, Any]:
        """
        Kiểm tra Position Bias bằng cách gọi Judge 2 lần:
        - Lần 1: A trước, B sau
        - Lần 2: B trước, A sau
        Nếu kết quả khác nhau → Judge bị thiên vị vị trí.
        """
        prompt_ab = POSITION_BIAS_PROMPT.format(
            question=question, response_a=response_a, response_b=response_b
        )
        prompt_ba = POSITION_BIAS_PROMPT.format(
            question=question, response_a=response_b, response_b=response_a
        )

        try:
            client = self._get_openai_client()

            result_ab, result_ba = await asyncio.gather(
                client.chat.completions.create(
                    model=self.openai_model,
                    messages=[{"role": "user", "content": prompt_ab}],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                ),
                client.chat.completions.create(
                    model=self.openai_model,
                    messages=[{"role": "user", "content": prompt_ba}],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                ),
            )

            # Track tokens cho cả 2 calls
            for r in [result_ab, result_ba]:
                if r.usage:
                    self.total_tokens["openai_input"] += r.usage.prompt_tokens
                    self.total_tokens["openai_output"] += r.usage.completion_tokens

            judge_ab = json.loads(result_ab.choices[0].message.content)
            judge_ba = json.loads(result_ba.choices[0].message.content)

            winner_ab = judge_ab.get("winner", "A")
            winner_ba = judge_ba.get("winner", "A")

            # Nếu consistent: AB chọn A → BA phải chọn B (vì B bây giờ ở vị trí A)
            # Nếu AB chọn A và BA cũng chọn A → bias vị trí (luôn chọn cái đầu tiên)
            has_bias = (winner_ab == "A" and winner_ba == "A") or \
                       (winner_ab == "B" and winner_ba == "B")

            return {
                "has_position_bias": has_bias,
                "round_1_winner": f"Response {'A' if winner_ab == 'A' else 'B'} (A trước)",
                "round_2_winner": f"Response {'B' if winner_ba == 'A' else 'A'} (B trước, đổi vị trí)",
                "round_1_reasoning": judge_ab.get("reasoning", ""),
                "round_2_reasoning": judge_ba.get("reasoning", ""),
                "conclusion": "⚠️ PHÁT HIỆN Position Bias — Judge thiên vị vị trí xuất hiện trước!" if has_bias
                              else "✅ Không phát hiện Position Bias — Judge đánh giá nhất quán."
            }

        except Exception as e:
            return {
                "has_position_bias": None,
                "error": str(e),
                "conclusion": f"Không thể kiểm tra Position Bias: {e}"
            }

    # ═══════════════════════════════════════════════════════
    # Cost Summary
    # ═══════════════════════════════════════════════════════
    def get_cost_summary(self) -> Dict[str, Any]:
        """Trả về tổng hợp chi phí token đã dùng cho tất cả judge calls."""
        return {
            "total_cost_usd": round(self.total_cost_usd, 4),
            "tokens": {
                "openai": {
                    "input": self.total_tokens["openai_input"],
                    "output": self.total_tokens["openai_output"],
                },
                "gemini": {
                    "input": self.total_tokens["gemini_input"],
                    "output": self.total_tokens["gemini_output"],
                },
            },
            "cost_breakdown": {
                "gpt-4o": round(
                    self.total_tokens["openai_input"] * self.cost_table["gpt-4o"]["input"] +
                    self.total_tokens["openai_output"] * self.cost_table["gpt-4o"]["output"], 4
                ),
                "gemini-2.5-flash": round(
                    self.total_tokens["gemini_input"] * self.cost_table["gemini-2.5-flash"]["input"] +
                    self.total_tokens["gemini_output"] * self.cost_table["gemini-2.5-flash"]["output"], 4
                ),
            }
        }

    # ═══════════════════════════════════════════════════════
    # Helper: Parse JSON từ LLM response (có thể có markdown)
    # ═══════════════════════════════════════════════════════
    @staticmethod
    def _parse_json_response(text: str) -> Dict[str, Any]:
        """Parse JSON từ response, xử lý cả trường hợp LLM trả JSON trong markdown code block."""
        # Thử parse trực tiếp
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Thử tìm JSON trong markdown code block
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Thử tìm JSON object trong text
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        # Fallback
        return {
            "accuracy": 3, "completeness": 3, "tone": 3,
            "reasoning": f"Could not parse JSON from response: {text[:200]}"
        }
