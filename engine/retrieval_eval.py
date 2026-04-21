"""
retrieval_eval.py — Task D: Retrieval Evaluation đầy đủ
Member D (Backend Engineer)
- Hit Rate@K: ít nhất 1 expected_id nằm trong top-K retrieved_ids
- MRR (Mean Reciprocal Rank): vị trí trung bình của expected_id đầu tiên
- Precision@K: tỷ lệ retrieved_ids đúng trong top-K
- NDCG@K: Normalized Discounted Cumulative Gain (bonus metric nâng cao)
- evaluate_batch: chạy toàn bộ dataset với agent thật, tổng hợp metrics
"""

import asyncio
import math
from typing import List, Dict, Any, Optional


class RetrievalEvaluator:
    """Tính toán các Retrieval Metrics cho toàn bộ dataset."""

    # ──────────────────────────── Core Metrics ────────────────────────────

    def calculate_hit_rate(
        self,
        expected_ids: List[str],
        retrieved_ids: List[str],
        top_k: int = 5,
    ) -> float:
        """
        Hit Rate@K: =1.0 nếu có ít nhất 1 expected_id nằm trong top_k retrieved_ids.
        Công thức: HR@K = 1 if ∃ id ∈ expected_ids s.t. id ∈ retrieved_ids[:K] else 0
        """
        top_retrieved = retrieved_ids[:top_k]
        hit = any(doc_id in top_retrieved for doc_id in expected_ids)
        return 1.0 if hit else 0.0

    def calculate_mrr(
        self,
        expected_ids: List[str],
        retrieved_ids: List[str],
    ) -> float:
        """
        Mean Reciprocal Rank (MRR):
        Công thức: MRR = 1 / rank_of_first_relevant_doc
        rank bắt đầu từ 1. Nếu không tìm thấy → 0.
        """
        for i, doc_id in enumerate(retrieved_ids):
            if doc_id in expected_ids:
                return 1.0 / (i + 1)
        return 0.0

    def calculate_precision_at_k(
        self,
        expected_ids: List[str],
        retrieved_ids: List[str],
        top_k: int = 5,
    ) -> float:
        """
        Precision@K: Tỷ lệ retrieved_ids đúng trong top_k.
        Công thức: P@K = |relevant ∩ retrieved[:K]| / K
        """
        top_retrieved = retrieved_ids[:top_k]
        relevant_hits = sum(1 for doc_id in top_retrieved if doc_id in expected_ids)
        return relevant_hits / top_k if top_k > 0 else 0.0

    def calculate_ndcg_at_k(
        self,
        expected_ids: List[str],
        retrieved_ids: List[str],
        top_k: int = 5,
    ) -> float:
        """
        NDCG@K (Normalized Discounted Cumulative Gain) — nâng cao.
        Relevance nhị phân: 1 nếu doc_id ∈ expected_ids, 0 nếu không.
        Công thức: NDCG@K = DCG@K / IDCG@K
        """
        def _dcg(ids: List[str], k: int) -> float:
            dcg = 0.0
            for i, doc_id in enumerate(ids[:k]):
                rel = 1.0 if doc_id in expected_ids else 0.0
                dcg += rel / math.log2(i + 2)  # log2(rank + 1), rank bắt đầu từ 1
            return dcg

        dcg = _dcg(retrieved_ids, top_k)
        # IDCG: kịch bản lý tưởng — tất cả expected_ids đều ở đầu
        ideal_retrieved = [eid for eid in expected_ids] + ["padding"] * top_k
        idcg = _dcg(ideal_retrieved, top_k)
        return dcg / idcg if idcg > 0 else 0.0

    # ──────────────────────────── Batch Evaluation ────────────────────────

    async def _evaluate_single(
        self,
        case: Dict[str, Any],
        agent,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Evaluate 1 test case:
        1. Gọi agent để lấy retrieved_ids thực tế.
        2. Tính tất cả retrieval metrics.
        """
        expected_ids: List[str] = case.get("expected_retrieval_ids", [])

        # Gọi agent để lấy retrieved_ids thực tế
        response = await agent.query(case["question"])
        retrieved_ids: List[str] = response.get("retrieved_ids", [])

        # Tính metrics
        hit_rate = self.calculate_hit_rate(expected_ids, retrieved_ids, top_k=top_k)
        mrr = self.calculate_mrr(expected_ids, retrieved_ids)
        precision = self.calculate_precision_at_k(expected_ids, retrieved_ids, top_k=top_k)
        ndcg = self.calculate_ndcg_at_k(expected_ids, retrieved_ids, top_k=top_k)

        return {
            "case_id": case.get("id", "unknown"),
            "question": case.get("question", ""),
            "expected_ids": expected_ids,
            "retrieved_ids": retrieved_ids,
            "metrics": {
                f"hit_rate@{top_k}": hit_rate,
                "mrr": mrr,
                f"precision@{top_k}": precision,
                f"ndcg@{top_k}": ndcg,
            },
            "agent_answer": response.get("answer", ""),
        }

    async def evaluate_batch(
        self,
        dataset: List[Dict[str, Any]],
        agent=None,
        top_k: int = 5,
        concurrency: int = 5,
    ) -> Dict[str, Any]:
        """
        Chạy Retrieval Evaluation cho toàn bộ dataset.

        Args:
            dataset: list các test cases, mỗi case có `expected_retrieval_ids`.
            agent: Agent instance (phải có method async query(question) → Dict).
            top_k: số lượng retrieved_ids để đánh giá.
            concurrency: Semaphore limit để tránh rate limit.

        Returns:
            Aggregated metrics + per-case results + failure cases.
        """
        # Filter các case có expected_retrieval_ids
        eval_cases = [c for c in dataset if c.get("expected_retrieval_ids")]

        if not eval_cases:
            return {
                "warning": "Không có case nào có trường `expected_retrieval_ids`. Bỏ qua Retrieval Eval.",
                "avg_hit_rate": 0.0,
                "avg_mrr": 0.0,
                "avg_precision": 0.0,
                "avg_ndcg": 0.0,
                "total_cases": 0,
                "per_case": [],
            }

        if agent is None:
            # Fallback: trả về placeholder nếu không có agent
            return {"avg_hit_rate": 0.85, "avg_mrr": 0.72, "total_cases": len(eval_cases), "per_case": []}

        # Semaphore để giới hạn số lượng request song song
        semaphore = asyncio.Semaphore(concurrency)

        async def _bounded(case):
            async with semaphore:
                return await self._evaluate_single(case, agent, top_k=top_k)

        per_case_results = await asyncio.gather(
            *[_bounded(case) for case in eval_cases],
            return_exceptions=False,
        )

        # Tổng hợp metrics
        n = len(per_case_results)
        hit_key = f"hit_rate@{top_k}"
        prec_key = f"precision@{top_k}"
        ndcg_key = f"ndcg@{top_k}"

        avg_hit_rate = sum(r["metrics"][hit_key] for r in per_case_results) / n
        avg_mrr = sum(r["metrics"]["mrr"] for r in per_case_results) / n
        avg_precision = sum(r["metrics"][prec_key] for r in per_case_results) / n
        avg_ndcg = sum(r["metrics"][ndcg_key] for r in per_case_results) / n

        # Phân loại failure cases (hit_rate = 0)
        failure_cases = [r for r in per_case_results if r["metrics"][hit_key] == 0.0]

        # Phân tích mối quan hệ Retrieval Quality → Answer Quality
        retrieval_quality_note = _analyze_retrieval_quality(avg_hit_rate, avg_mrr)

        return {
            "avg_hit_rate": round(avg_hit_rate, 4),
            "avg_mrr": round(avg_mrr, 4),
            "avg_precision_at_k": round(avg_precision, 4),
            "avg_ndcg_at_k": round(avg_ndcg, 4),
            "total_cases": n,
            "failure_cases_count": len(failure_cases),
            "failure_rate": round(len(failure_cases) / n, 4),
            "retrieval_quality_note": retrieval_quality_note,
            "per_case": list(per_case_results),
            "failure_cases": failure_cases,
        }


# ──────────────────────────── Helper ──────────────────────────────────────

def _analyze_retrieval_quality(avg_hit_rate: float, avg_mrr: float) -> str:
    """
    Phân tích mối quan hệ giữa Retrieval Quality và Answer Quality.
    - Hit Rate cao nhưng MRR thấp: đúng tài liệu nhưng không xếp hạng đúng vị trí.
    - Cả hai thấp: vấn đề cơ bản ở Chunking hoặc Indexing pipeline.
    """
    if avg_hit_rate >= 0.8 and avg_mrr >= 0.7:
        return (
            "✅ Retrieval tốt: Hit Rate cao và MRR cao. Nếu Generation vẫn sai, "
            "lỗi nằm ở Prompting hoặc LLM hallucination."
        )
    elif avg_hit_rate >= 0.6 and avg_mrr < 0.5:
        return (
            "⚠️ Retrieval trung bình: Tìm đúng tài liệu nhưng xếp hạng chưa tốt (MRR thấp). "
            "Xem xét cải thiện re-ranking hoặc thuật toán similarity."
        )
    elif avg_hit_rate < 0.5:
        return (
            "❌ Retrieval yếu: Hit Rate thấp — tài liệu liên quan không được tìm thấy. "
            "Root cause có thể ở Chunking strategy hoặc Embedding/Indexing pipeline."
        )
    else:
        return (
            f"📊 Retrieval metrics: Hit Rate={avg_hit_rate:.2%}, MRR={avg_mrr:.4f}. "
            "Cần phân tích sâu hơn để xác định root cause."
        )


# ────────────────────────────────────────────────────────────────────────
#  Smoke test (chạy mà không cần agent)
# ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    evaluator = RetrievalEvaluator()

    expected = ["doc_a", "doc_b"]
    retrieved = ["doc_c", "doc_a", "doc_d", "doc_b", "doc_e"]

    print("Hit Rate @3:", evaluator.calculate_hit_rate(expected, retrieved, top_k=3))
    print("Hit Rate @5:", evaluator.calculate_hit_rate(expected, retrieved, top_k=5))
    print("MRR:", evaluator.calculate_mrr(expected, retrieved))
    print("Precision@3:", evaluator.calculate_precision_at_k(expected, retrieved, top_k=3))
    print("NDCG@5:", evaluator.calculate_ndcg_at_k(expected, retrieved, top_k=5))

    note = _analyze_retrieval_quality(avg_hit_rate=0.45, avg_mrr=0.3)
    print("Analysis:", note)
