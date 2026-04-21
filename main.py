"""
main.py — Orchestrator chính
- Chạy Benchmark V1 (MainAgent) vs V2 (MainAgentV2)
- Dùng RetrievalEvaluator thật (Task D) tích hợp vào summary
- Dùng LLMJudge thật (Task C: GPT-4o + Gemini 2.5 Flash)
- Performance Report từ BenchmarkRunner (Task E)
- Regression Gate tự động (Task F)
"""

import asyncio
import json
import os
import time
from engine.runner import BenchmarkRunner
from engine.retrieval_eval import RetrievalEvaluator
from engine.llm_judge import LLMJudge
from agent.main_agent import MainAgent, MainAgentV2

# ── Placeholder: RAGAS Evaluator (Task D sẽ thay thế nếu cần) ─────────────
class ExpertEvaluator:
    async def score(self, case, resp):
        return {
            "faithfulness": 0.9,
            "relevancy": 0.8,
            "retrieval": {
                "hit_rate": 1.0,
                "mrr": 0.5,
            },
        }
# ─────────────────────────────────────────────────────────────────────────


async def run_retrieval_eval(agent, dataset: list, top_k: int = 5) -> dict:
    """Chạy Retrieval Evaluation thật và trả về aggregated metrics."""
    evaluator = RetrievalEvaluator()
    return await evaluator.evaluate_batch(dataset, agent=agent, top_k=top_k)


async def run_benchmark_with_results(agent, agent_version: str, dataset: list):
    """Chạy full benchmark cho 1 agent version."""
    print(f"🚀 Khởi động Benchmark cho {agent_version}...")

    # Dùng LLMJudge thật (GPT-4o + Gemini 2.5 Flash) thay vì placeholder
    runner = BenchmarkRunner(
        agent=agent,
        evaluator=ExpertEvaluator(),
        judge=LLMJudge(),
        max_concurrent=5,
        budget_usd=5.0,
        circuit_failure_threshold=5,
        circuit_recovery_timeout=30.0,
    )
    results = await runner.run_all(dataset)

    total = len(results)

    # Retrieval metrics thực từ RetrievalEvaluator
    retrieval_eval = await run_retrieval_eval(agent, dataset)

    # Performance report từ Runner (Task E)
    perf_report = runner.generate_performance_report(total)

    summary = {
        "metadata": {
            "version": agent_version,
            "total": total,
            "passed": sum(1 for r in results if r["status"] == "pass"),
            "failed": sum(1 for r in results if r["status"] == "fail"),
            "errors": sum(1 for r in results if r["status"] == "error"),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "metrics": {
            "avg_score": sum(r["judge"]["final_score"] for r in results) / total,
            "hit_rate": retrieval_eval.get("avg_hit_rate", 0.0),
            "mrr": retrieval_eval.get("avg_mrr", 0.0),
            "precision_at_k": retrieval_eval.get("avg_precision_at_k", 0.0),
            "ndcg_at_k": retrieval_eval.get("avg_ndcg_at_k", 0.0),
            "agreement_rate": sum(r["judge"]["agreement_rate"] for r in results) / total,
            "avg_latency": sum(r["latency"] for r in results) / total,
        },
        "retrieval_analysis": {
            "total_eval_cases": retrieval_eval.get("total_cases", 0),
            "failure_cases": retrieval_eval.get("failure_cases_count", 0),
            "failure_rate": retrieval_eval.get("failure_rate", 0.0),
            "quality_note": retrieval_eval.get("retrieval_quality_note", ""),
        },
        "performance": perf_report,
    }
    return results, summary


async def main():
    if not os.path.exists("data/golden_set_A.jsonl"):
        print("❌ Thiếu data/golden_set.jsonl. Hãy chạy 'python data/synthetic_gen.py' trước.")
        return  

    with open("data/golden_set_A.jsonl", "r", encoding="utf-8") as f:
        dataset = [json.loads(line) for line in f if line.strip()]

    if not dataset:
        print("❌ File data/golden_set.jsonl rỗng. Hãy tạo ít nhất 1 test case.")
        return

    print(f"📂 Loaded {len(dataset)} test cases.\n")

    # ── V1 Benchmark ──
    v1_agent = MainAgent()
    v1_results, v1_summary = await run_benchmark_with_results(
        v1_agent, "Agent_V1_Base", dataset
    )

    # ── V2 Benchmark ──
    v2_agent = MainAgentV2()
    v2_results, v2_summary = await run_benchmark_with_results(
        v2_agent, "Agent_V2_Optimized", dataset
    )

    if not v1_summary or not v2_summary:
        print("❌ Không thể chạy Benchmark.")
        return

    # ── Regression Gate (Task F hook) ──────────────────────────────────
    print("\n" + "=" * 60)
    print("📊 KẾT QUẢ SO SÁNH (REGRESSION)")
    print("=" * 60)
    m1 = v1_summary["metrics"]
    m2 = v2_summary["metrics"]

    delta_score    = m2["avg_score"]    - m1["avg_score"]
    delta_hitrate  = m2["hit_rate"]     - m1["hit_rate"]

    print(f"{'Metric':<25} {'V1':>8} {'V2':>8} {'Delta':>10}")
    print("-" * 55)
    for key in ["avg_score", "hit_rate", "mrr", "agreement_rate", "avg_latency"]:
        v1_val = m1.get(key, 0)
        v2_val = m2.get(key, 0)
        delta  = v2_val - v1_val
        sign   = "+" if delta >= 0 else ""
        print(f"{key:<25} {v1_val:>8.3f} {v2_val:>8.3f} {sign}{delta:>9.3f}")

    print("\n🔍 Retrieval Quality Note (V2):", v2_summary["retrieval_analysis"]["quality_note"])

    # ── Performance Report (Task E) ──
    perf = v2_summary.get("performance", {})
    timing = perf.get("timing", {})
    cost = perf.get("cost", {})
    reliability = perf.get("reliability", {})

    print(f"\n⏱️  PERFORMANCE")
    print(f"  Pipeline: {timing.get('total_pipeline_seconds', 0)}s | Avg/case: {timing.get('avg_time_per_case', 0)}s")
    print(f"  Bottleneck: {timing.get('bottleneck_stage', 'N/A')}")
    print(f"  SLA < 2 phút: {'✅ ĐẠT' if timing.get('meets_sla') else '❌ KHÔNG ĐẠT'}")

    print(f"\n💰 CHI PHÍ")
    print(f"  Tổng: ${cost.get('total_cost_usd', 0):.4f} | Tokens: {cost.get('total_tokens', 0):,}")
    print(f"  Avg/eval: ${cost.get('avg_cost_per_eval', 0):.6f}")
    by_component = cost.get("by_component", {})
    for comp, data in by_component.items():
        print(f"    · {comp}: {data['tokens']:,} tokens (${data['cost_usd']:.6f})")

    print(f"\n🛡️  RELIABILITY")
    print(f"  Errors: {reliability.get('errors', 0)} ({reliability.get('error_rate_pct', 0)}%)")
    print(f"  Retries: {reliability.get('retries', 0)} | Fallbacks: {reliability.get('fallbacks', 0)}")
    cb_status = reliability.get('circuit_breaker_status', {})
    if isinstance(cb_status, dict):
        print(f"  Circuit Breaker: Agent={cb_status.get('agent', 'N/A')}, Judge={cb_status.get('judge', 'N/A')}")
    else:
        print(f"  Circuit Breaker: {cb_status}")

    # Optimization suggestions
    suggestions = perf.get("optimization_suggestions", [])
    if suggestions:
        print(f"\n🔧 ĐỀ XUẤT TỐI ƯU (giảm 30%+ chi phí)")
        for s in suggestions:
            print(f"  {s}")

    # ── Release Gate Decision ──
    print("\n" + "=" * 60)
    print("🚦 RELEASE GATE")
    print("=" * 60)
    blocked = False
    if delta_score < 0:
        print(f"❌ BLOCK: avg_score giảm ({delta_score:+.3f})")
        blocked = True
    if delta_hitrate < -0.05:
        print(f"❌ BLOCK: hit_rate giảm > 5% ({delta_hitrate:+.3%})")
        blocked = True
    if m2["agreement_rate"] < 0.7:
        print(f"⚠️  WARNING: agreement_rate thấp ({m2['agreement_rate']:.2%})")

    if not blocked:
        print("✅ QUYẾT ĐỊNH: CHẤP NHẬN BẢN CẬP NHẬT (APPROVE)")
    else:
        print("❌ QUYẾT ĐỊNH: TỪ CHỐI (BLOCK RELEASE)")

    # ── Save reports ──
    os.makedirs("reports", exist_ok=True)

    final_summary = {
        "v1": v1_summary,
        "v2": v2_summary,
        "regression": {
            "delta_avg_score": round(delta_score, 4),
            "delta_hit_rate": round(delta_hitrate, 4),
            "decision": "APPROVE" if not blocked else "BLOCK",
        },
    }

    with open("reports/summary.json", "w", encoding="utf-8") as f:
        json.dump(final_summary, f, ensure_ascii=False, indent=2)
    with open("reports/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump({"v1": v1_results, "v2": v2_results}, f, ensure_ascii=False, indent=2)

    print("\n✅ Reports đã lưu vào reports/summary.json và reports/benchmark_results.json")


if __name__ == "__main__":
    asyncio.run(main())
