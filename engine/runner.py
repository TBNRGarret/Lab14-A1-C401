"""
Engine Runner — Production-Grade Async Benchmark Pipeline
=========================================================
5 Expert Patterns (theo nhận xét Codex):
  1. Header-Aware Wait       — đọc Retry-After / x-ratelimit-reset từ 429
  2. Client-side Rate Limit  — asyncio.Semaphore (concurrency limit)
  3. Fallback Model Routing  — chuyển model dự phòng khi primary fail
  4. Circuit Breaker          — ngắt mạch khi lỗi liên tiếp
  5. Tenacity Retry           — decorator retry chuyên dụng, không viết for/try tay
"""

import asyncio
import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from tqdm.asyncio import tqdm as async_tqdm
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
    before_sleep_log,
    RetryError,
)


def _is_retryable_error(exc: BaseException) -> bool:
    """
    Chỉ retry các lỗi tạm thời: HTTP 429, 500, 502, 503, 504
    và connection/timeout errors (không có response).
    Không retry: 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found
    — những lỗi này retry bao nhiêu lần cũng không thay đổi kết quả.
    """
    # OpenAI SDK đặt status_code trực tiếp trên exception (APIStatusError)
    status = getattr(exc, "status_code", None)
    # Fallback: check response.status_code (httpx-style)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if status is not None:
        return status in {429, 500, 502, 503, 504}
    # Không có response → lỗi kết nối/timeout → retry
    return True

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  PATTERN 4: Circuit Breaker
# ═══════════════════════════════════════════════════════════════

class CircuitState(Enum):
    CLOSED    = "CLOSED"       # Bình thường
    OPEN      = "OPEN"         # Ngắt — fast-fail
    HALF_OPEN = "HALF_OPEN"    # Thử 1 request kiểm tra


class CircuitBreakerOpen(Exception):
    """Circuit đang OPEN — không gọi API."""
    pass


class CircuitBreaker:
    """
    Cầu dao tự động:
    - N lỗi liên tiếp → OPEN (fast-fail mọi request)
    - Sau T giây → HALF_OPEN (cho 1 request thử)
    - Thành công → CLOSED. Fail → OPEN lại.
    """
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    async def before_call(self):
        """Kiểm tra trước khi gọi API. Raise CircuitBreakerOpen nếu OPEN."""
        async with self._lock:
            if self.state == CircuitState.CLOSED:
                return
            if self.state == CircuitState.OPEN:
                elapsed = time.monotonic() - self.last_failure_time
                if elapsed >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    logger.info("⚡ Circuit → HALF_OPEN (thử 1 request)")
                    return
                raise CircuitBreakerOpen(
                    f"Circuit OPEN — fast-fail. Thử lại sau {self.recovery_timeout - elapsed:.0f}s"
                )
            # HALF_OPEN → cho qua 1 request
            return

    async def on_success(self):
        async with self._lock:
            self.failure_count = 0
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                logger.info("✅ Circuit → CLOSED (phục hồi)")

    async def on_failure(self):
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.monotonic()
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(
                    f"🔴 Circuit → OPEN ({self.failure_count} lỗi liên tiếp). "
                    f"Fast-fail {self.recovery_timeout}s."
                )

    @property
    def status(self) -> str:
        return self.state.value


# ═══════════════════════════════════════════════════════════════
#  PATTERN 1: Header-Aware Wait
# ═══════════════════════════════════════════════════════════════

async def header_aware_sleep(exception: Exception) -> bool:
    """
    Đọc header wait time từ API 429 response.
    OpenAI trả về: Retry-After, x-ratelimit-reset-requests, x-ratelimit-reset-tokens
    Nếu đọc được → sleep đúng thời gian API yêu cầu → return True.
    Nếu không có header → return False (để tenacity dùng backoff mặc định).
    """
    response = getattr(exception, "response", None)
    if response is None:
        return False

    headers = getattr(response, "headers", {})
    for header_name in ["retry-after", "x-ratelimit-reset-requests", "x-ratelimit-reset-tokens"]:
        value = headers.get(header_name)
        if value:
            try:
                wait_seconds = float(value)
                logger.info(f"📡 Header-Aware: API yêu cầu chờ {wait_seconds:.1f}s ({header_name})")
                await asyncio.sleep(wait_seconds)
                return True
            except (ValueError, TypeError):
                continue
    return False


# ═══════════════════════════════════════════════════════════════
#  Cost Tracker
# ═══════════════════════════════════════════════════════════════

# Bảng giá USD / 1M tokens
MODEL_PRICING = {
    "gpt-4o":            {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":       {"input": 0.15,  "output": 0.60},
    "gemini-2.5-flash":  {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash":  {"input": 0.10,  "output": 0.40},
    "default":           {"input": 2.00,  "output": 8.00},
}


@dataclass
class CostRecord:
    component: str   # "agent" | "judge_gpt-4o" | "judge_gemini-2.5-flash"
    model: str
    tokens: int      # total tokens (input + output gộp, vì Agent chỉ trả tokens_used)
    cost_usd: float


class BudgetExceeded(Exception):
    pass


class CostTracker:
    """Theo dõi token & chi phí toàn pipeline. Hỗ trợ budget limit."""

    def __init__(self, budget_usd: Optional[float] = None):
        self.budget_usd = budget_usd
        self.records: List[CostRecord] = []
        self._lock = asyncio.Lock()

    def _get_pricing(self, model: str) -> Dict[str, float]:
        for key in MODEL_PRICING:
            if key in model.lower():
                return MODEL_PRICING[key]
        return MODEL_PRICING["default"]

    async def track(self, component: str, model: str, tokens: int) -> float:
        """
        Ghi nhận chi phí. Dùng tokens (tổng) vì Agent hiện chỉ trả tokens_used.
        Ước lượng: 40% input, 60% output (tỷ lệ phổ biến RAG pipeline).
        """
        pricing = self._get_pricing(model)
        input_tokens = int(tokens * 0.4)
        output_tokens = tokens - input_tokens
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

        record = CostRecord(component=component, model=model, tokens=tokens, cost_usd=cost)

        async with self._lock:
            self.records.append(record)
            if self.budget_usd and self.total_cost > self.budget_usd:
                if not getattr(self, "_warned_budget", False):
                    logger.warning(
                        f"💸 CẢNH BÁO: Vượt ngân sách! ${self.total_cost:.4f} / ${self.budget_usd:.2f}. "
                        "Pipeline tiếp tục chạy để ghi nhận kết quả các cases đã hoàn thành."
                    )
                    self._warned_budget = True
        return cost

    @property
    def total_cost(self) -> float:
        return sum(r.cost_usd for r in self.records)

    @property
    def total_tokens(self) -> int:
        return sum(r.tokens for r in self.records)

    def breakdown_by_component(self) -> Dict[str, Any]:
        result = {}
        for r in self.records:
            if r.component not in result:
                result[r.component] = {"tokens": 0, "cost_usd": 0.0, "calls": 0}
            result[r.component]["tokens"] += r.tokens
            result[r.component]["cost_usd"] += r.cost_usd
            result[r.component]["calls"] += 1
        return result

    def breakdown_by_model(self) -> Dict[str, Any]:
        result = {}
        for r in self.records:
            if r.model not in result:
                result[r.model] = {"tokens": 0, "cost_usd": 0.0, "calls": 0}
            result[r.model]["tokens"] += r.tokens
            result[r.model]["cost_usd"] += r.cost_usd
            result[r.model]["calls"] += 1
        return result

    def generate_report(self, total_cases: int = 0) -> Dict[str, Any]:
        """
        Xuất cost report cho summary.json.
        total_cases: số test case thực tế để tính avg_cost_per_eval chính xác.
        Không dùng len(self.records) vì mỗi case tạo nhiều records (1 agent + N judges).
        """
        n = max(total_cases, 1)
        return {
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost, 6),
            "avg_cost_per_eval": round(self.total_cost / n, 6),
            "by_component": {
                k: {**v, "cost_usd": round(v["cost_usd"], 6)}
                for k, v in self.breakdown_by_component().items()
            },
            "by_model": {
                k: {**v, "cost_usd": round(v["cost_usd"], 6)}
                for k, v in self.breakdown_by_model().items()
            },
            "budget_usd": self.budget_usd,
            "budget_usage_pct": round(self.total_cost / self.budget_usd * 100, 2) if self.budget_usd else None,
        }

    def optimization_suggestions(self) -> List[str]:
        """Đề xuất giảm 30%+ chi phí eval."""
        suggestions = []
        by_model = self.breakdown_by_model()

        # Nếu dùng model đắt → gợi ý tiered judging
        expensive = [m for m in by_model if ("gpt-4o" in m and "mini" not in m)]
        if expensive:
            suggestions.append(
                "💡 TIERED JUDGING: Dùng GPT-4o-mini cho easy/medium cases, "
                "GPT-4o chỉ cho hard/adversarial → tiết kiệm ~40% chi phí Judge."
            )
        suggestions.append(
            "💡 EARLY TERMINATION: 2 Judge đồng ý (score lệch ≤ 0.5) → skip Judge thứ 3 → tiết kiệm ~20%."
        )
        suggestions.append(
            "💡 BATCH API: Dùng OpenAI Batch API (giảm 50% giá) cho eval không cần real-time."
        )
        suggestions.append(
            "💡 RESPONSE CACHE: Cache Agent response cho câu hỏi trùng → tiết kiệm ~15% token Agent."
        )
        return suggestions


# ═══════════════════════════════════════════════════════════════
#  BenchmarkRunner — Engine chính
# ═══════════════════════════════════════════════════════════════

class BenchmarkRunner:
    """
    Production-grade async benchmark runner.

    5 patterns:
      1. Header-Aware Wait     — đọc header retry-after từ 429
      2. Client-side Rate Limit — Semaphore concurrency limit
      3. Fallback Routing       — chuyển model dự phòng khi primary quá tải
      4. Circuit Breaker        — ngắt mạch khi lỗi liên tiếp
      5. Tenacity Retry         — decorator retry, không for/try tay

    Interface compatibility:
      - Agent.query(question) → {"answer", "contexts", "metadata": {"model", "tokens_used"}}
      - Evaluator.score(case, response) → {"faithfulness", "relevancy", "retrieval": {"hit_rate", "mrr"}}
      - Judge.evaluate_multi_judge(q, a, gt) → {"final_score", "agreement_rate", "individual_scores"}
    """

    def __init__(
        self,
        agent,
        evaluator,
        judge,
        max_concurrent: int = 5,
        budget_usd: Optional[float] = None,
        circuit_failure_threshold: int = 5,
        circuit_recovery_timeout: float = 30.0,
    ):
        self.agent = agent
        self.evaluator = evaluator
        self.judge = judge

        # Pattern 2: Semaphore
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent

        # Pattern 4: Circuit Breaker — tách riêng Agent/Judge
        # Lý do: Judge lỗi không nên block Agent và ngược lại
        self.agent_circuit = CircuitBreaker(
            failure_threshold=circuit_failure_threshold,
            recovery_timeout=circuit_recovery_timeout,
        )
        self.judge_circuit = CircuitBreaker(
            failure_threshold=circuit_failure_threshold,
            recovery_timeout=circuit_recovery_timeout,
        )

        # Cost & performance tracking
        self.cost_tracker = CostTracker(budget_usd=budget_usd)
        self._stage_timings: List[Dict[str, float]] = []
        self._errors: List[Dict[str, str]] = []
        self._retry_count: int = 0
        self._fallback_count: int = 0
        self._pipeline_time: float = 0.0

    # ── Pattern 5: Tenacity decorator cho từng component ──

    async def _call_agent(self, question: str) -> Dict:
        """
        Gọi Agent với Pattern 1 + 4 + 5.
        Tenacity xử lý retry tự động. Circuit breaker kiểm tra trước.
        """
        # Pattern 4: kiểm tra circuit của Agent
        await self.agent_circuit.before_call()

        # Flag tránh gọi on_failure() 2 lần nếu RetryError handler đã gọi rồi
        _failure_recorded = False

        try:
            # Pattern 5: tenacity — chỉ retry lỗi tạm thời (429, 5xx, connection)
            @retry(
                retry=retry_if_exception(_is_retryable_error),
                wait=wait_random_exponential(min=1, max=60),
                stop=stop_after_attempt(3),
                before_sleep=before_sleep_log(logger, logging.WARNING),
            )
            async def _inner():
                return await self.agent.query(question)

            result = await _inner()
            await self.agent_circuit.on_success()
            return result

        except RetryError as e:
            _failure_recorded = True
            await self.agent_circuit.on_failure()
            self._retry_count += 1

            original_error = e.last_attempt.exception()

            # Pattern 1: đọc header retry-after → thử thêm 1 lần
            if original_error:
                header_used = await header_aware_sleep(original_error)
                if header_used:
                    try:
                        result = await self.agent.query(question)
                        await self.agent_circuit.on_success()  # Bug 1: phải reset circuit
                        return result
                    except Exception:
                        pass  # tiếp tục xuống fallback

            # Pattern 3: Fallback routing
            if hasattr(self.agent, "query_with_model"):
                fallback = _get_fallback_model(getattr(self.agent, "model", "gpt-4o"))
                if fallback:
                    logger.info(f"🔄 Fallback Agent → {fallback}")
                    self._fallback_count += 1
                    try:
                        result = await self.agent.query_with_model(question, fallback)
                        await self.agent_circuit.on_success()  # Bug 1: phải reset circuit
                        return result
                    except Exception:
                        pass  # fallback cũng fail → raise bên dưới

            raise original_error or e

        except Exception as e:
            # Bug 2: chỉ gọi on_failure nếu RetryError handler chưa gọi
            if not _failure_recorded:
                await self.agent_circuit.on_failure()
            raise

    async def _call_judge(self, question: str, answer: str, ground_truth: str) -> Dict:
        """Gọi Judge với Pattern 1 + 4 + 5. Circuit Breaker tách riêng khỏi Agent."""
        await self.judge_circuit.before_call()

        _failure_recorded = False

        try:
            @retry(
                retry=retry_if_exception(_is_retryable_error),
                wait=wait_random_exponential(min=1, max=60),
                stop=stop_after_attempt(3),
                before_sleep=before_sleep_log(logger, logging.WARNING),
            )
            async def _inner():
                return await self.judge.evaluate_multi_judge(question, answer, ground_truth)

            result = await _inner()
            await self.judge_circuit.on_success()
            return result

        except RetryError as e:
            _failure_recorded = True
            await self.judge_circuit.on_failure()
            self._retry_count += 1

            original_error = e.last_attempt.exception()
            if original_error:
                header_used = await header_aware_sleep(original_error)
                if header_used:
                    try:
                        result = await self.judge.evaluate_multi_judge(question, answer, ground_truth)
                        await self.judge_circuit.on_success()  # Bug 1: phải reset circuit
                        return result
                    except Exception:
                        pass

            # Pattern 3: Fallback judge
            if hasattr(self.judge, "evaluate_fallback"):
                logger.info("🔄 Fallback Judge → model dự phòng")
                self._fallback_count += 1
                try:
                    result = await self.judge.evaluate_fallback(question, answer, ground_truth)
                    await self.judge_circuit.on_success()  # Bug 1: phải reset circuit
                    return result
                except Exception:
                    pass

            raise original_error or e

        except Exception as e:
            # Bug 2: chỉ gọi on_failure nếu chưa gọi trong RetryError handler
            if not _failure_recorded:
                await self.judge_circuit.on_failure()
            raise

    async def run_single_test(self, test_case: Dict) -> Dict:
        """
        Chạy 1 test case qua 3 stage, đo timing + cost từng stage.
        Tương thích hoàn toàn với interface hiện tại:
          - Agent trả {"metadata": {"tokens_used": int, "model": str}}
          - Judge trả {"individual_scores": {"gpt-4o": {...}, "gemini-2.5-flash": {...}}}
        """
        timings = {}
        total_start = time.perf_counter()

        try:
            # ── Stage 1: Agent ──
            t0 = time.perf_counter()
            response = await self._call_agent(test_case["question"])
            timings["agent_call"] = round(time.perf_counter() - t0, 4)

            # Cost tracking — đọc tokens_used từ Agent (interface hiện tại)
            meta = response.get("metadata", {})
            agent_tokens = meta.get("tokens_used", 0)
            agent_model = meta.get("model", "unknown")
            await self.cost_tracker.track("agent", agent_model, agent_tokens)

            # ── Stage 2: RAGAS / Evaluator ──
            t0 = time.perf_counter()
            ragas_scores = await self.evaluator.score(test_case, response)
            timings["ragas_eval"] = round(time.perf_counter() - t0, 4)

            # ── Stage 3: Multi-Judge ──
            t0 = time.perf_counter()
            judge_result = await self._call_judge(
                test_case["question"],
                response["answer"],
                test_case["expected_answer"],
            )
            timings["judge_eval"] = round(time.perf_counter() - t0, 4)

            # Cost tracking — đọc individual_scores từ Judge (interface hiện tại)
            # Mỗi model trong individual_scores = 1 lần gọi API
            individual = judge_result.get("individual_scores", {})
            for model_name in individual:
                # Judge hiện tại không trả token count → ước lượng ~200 tokens/lần judge
                judge_tokens = judge_result.get("tokens_per_model", {}).get(model_name, 200)
                await self.cost_tracker.track(f"judge_{model_name}", model_name, judge_tokens)

            # ── Kết quả ──
            timings["total"] = round(time.perf_counter() - total_start, 4)
            self._stage_timings.append(timings)

            return {
                "test_case": test_case["question"],
                "agent_response": response["answer"],
                "latency": timings["total"],
                "timing_breakdown": timings,
                "ragas": ragas_scores,
                "judge": judge_result,
                "status": "fail" if judge_result["final_score"] < 3 else "pass",
            }

        except CircuitBreakerOpen as e:
            logger.error(f"🔴 Circuit OPEN — skip: {test_case['question'][:50]}")
            timings["total"] = round(time.perf_counter() - total_start, 4)
            return self._error_result(test_case, timings, str(e))

        except Exception as e:
            logger.error(f"❌ Lỗi case '{test_case['question'][:50]}': {e}")
            timings["total"] = round(time.perf_counter() - total_start, 4)
            self._errors.append({
                "question": test_case["question"][:100],
                "error": f"{type(e).__name__}: {e}",
            })
            return self._error_result(test_case, timings, f"{type(e).__name__}: {e}")

    def _error_result(self, test_case: Dict, timings: Dict, error_msg: str) -> Dict:
        """Tạo kết quả cho case bị lỗi — giữ cùng schema với case thành công."""
        return {
            "test_case": test_case["question"],
            "agent_response": "",
            "latency": timings.get("total", 0),
            "timing_breakdown": timings,
            "ragas": {
                "faithfulness": 0, "relevancy": 0,
                "retrieval": {"hit_rate": 0, "mrr": 0},
            },
            "judge": {"final_score": 0, "agreement_rate": 0, "individual_scores": {}},
            "status": "error",
            "error": error_msg,
        }

    async def run_all(self, dataset: List[Dict]) -> List[Dict]:
        """
        Chạy benchmark toàn bộ dataset.
        Pattern 2: Semaphore giới hạn concurrency — max_concurrent truyền vào __init__.
        Dùng tqdm progress bar hiển thị tiến trình real-time.
        """
        pipeline_start = time.perf_counter()

        async def _limited_run(idx: int, case: Dict) -> tuple:
            """Wrap với Semaphore + giữ index để duy trì thứ tự kết quả."""
            async with self.semaphore:
                result = await self.run_single_test(case)
                return idx, result

        # Tạo tasks cho tất cả cases
        tasks = [_limited_run(i, case) for i, case in enumerate(dataset)]

        # Chạy với tqdm progress bar — dùng as_completed để hiển thị real-time
        indexed_results = []
        for coro in async_tqdm(
            asyncio.as_completed(tasks),
            total=len(tasks),
            desc="🚀 Benchmark",
            unit="case",
        ):
            idx, result = await coro
            indexed_results.append((idx, result))

        # Sắp xếp lại theo thứ tự ban đầu
        indexed_results.sort(key=lambda x: x[0])
        results = [r for _, r in indexed_results]

        self._pipeline_time = round(time.perf_counter() - pipeline_start, 2)

        # In summary nhanh
        passed = sum(1 for r in results if r["status"] == "pass")
        failed = sum(1 for r in results if r["status"] == "fail")
        errors = sum(1 for r in results if r["status"] == "error")
        print(f"\n📊 Xong trong {self._pipeline_time}s | ✅ Pass: {passed} | ❌ Fail: {failed} | ⚠️ Error: {errors}")
        print(f"💰 Tổng chi phí: ${self.cost_tracker.total_cost:.4f} | Tokens: {self.cost_tracker.total_tokens:,}")

        return results

    def generate_performance_report(self, total_cases: int) -> Dict[str, Any]:
        """
        Xuất performance report đầy đủ cho summary.json.
        Gồm: timing breakdown, cost breakdown, optimization suggestions.
        """
        # Timing analysis
        avg_timings = {}
        bottleneck = "N/A"
        if self._stage_timings:
            for key in ["agent_call", "ragas_eval", "judge_eval", "total"]:
                values = [t.get(key, 0) for t in self._stage_timings]
                avg_timings[f"avg_{key}"] = round(sum(values) / len(values), 4)

            stage_avgs = {k: v for k, v in avg_timings.items() if k != "avg_total"}
            if stage_avgs:
                bottleneck = max(stage_avgs, key=stage_avgs.get).replace("avg_", "")

        return {
            "timing": {
                "total_pipeline_seconds": self._pipeline_time,
                "avg_time_per_case": round(self._pipeline_time / max(total_cases, 1), 2),
                "stage_averages": avg_timings,
                "bottleneck_stage": bottleneck,
                "meets_sla": self._pipeline_time < 120,  # < 2 phút SLA
            },
            "cost": self.cost_tracker.generate_report(total_cases),
            "reliability": {
                "total_cases": total_cases,
                "errors": len(self._errors),
                "error_rate_pct": round(len(self._errors) / max(total_cases, 1) * 100, 2),
                "retries": self._retry_count,
                "fallbacks": self._fallback_count,
                "circuit_breaker_status": {
                    "agent": self.agent_circuit.status,
                    "judge": self.judge_circuit.status,
                },
                "error_details": self._errors[:10],  # Top 10 lỗi
            },
            "runner_config": {
                "max_concurrent": self.max_concurrent,
                "budget_usd": self.cost_tracker.budget_usd,
                "circuit_failure_threshold": self.agent_circuit.failure_threshold,
                "circuit_recovery_timeout": self.agent_circuit.recovery_timeout,
            },
            "optimization_suggestions": self.cost_tracker.optimization_suggestions(),
        }


# ═══════════════════════════════════════════════════════════════
#  PATTERN 3: Fallback routes (helper)
# ═══════════════════════════════════════════════════════════════

FALLBACK_ROUTES = {
    "gpt-4o":            "gpt-4o-mini",
    "gemini-2.5-flash":  "gemini-2.0-flash",
    "gpt-4o-mini":       None,
    "gemini-2.0-flash":  None,
}


def _get_fallback_model(current_model: str) -> Optional[str]:
    """Tra bảng routing để tìm model dự phòng."""
    for key, fallback in FALLBACK_ROUTES.items():
        if key in current_model.lower():
            return fallback
    return None