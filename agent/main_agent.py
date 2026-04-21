"""
main_agent.py — Task D: RAG Agent thực tế
Member D (Backend Engineer)
- Thực hiện RAG pipeline: Load docs → Chunk → TF-IDF retrieval → LLM generation
- Trả về retrieved_ids cho Retrieval Evaluation
- Hai phiên bản V1 (baseline) và V2 (optimized prompt)
"""

import asyncio
import os
import re
import math
from typing import List, Dict, Any
from collections import Counter

from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
#  TF-IDF In-Memory Vector Store (không cần DB)
# ─────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    """Tách từ đơn giản: lowercase, bỏ ký tự đặc biệt."""
    return re.findall(r'\w+', text.lower())


class TFIDFStore:
    """Chunk documents và tính TF-IDF để retrieval."""

    def __init__(self, chunk_size: int = 300, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.chunks: List[Dict] = []   # {"id", "text", "source"}
        self.idf: Dict[str, float] = {}
        self._built = False

    # ── Build ──────────────────────────────────────────────────────────────
    def load_docs_from_dir(self, docs_dir: str) -> None:
        for fname in os.listdir(docs_dir):
            if not fname.endswith(".txt"):
                continue
            fpath = os.path.join(docs_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            doc_id = fname.replace(".txt", "")
            self._chunk_document(content, doc_id)
        self._build_idf()
        self._built = True

    def _chunk_document(self, text: str, doc_id: str) -> None:
        words = text.split()
        step = self.chunk_size - self.overlap
        for i, start in enumerate(range(0, len(words), max(step, 1))):
            chunk_words = words[start: start + self.chunk_size]
            if not chunk_words:
                break
            chunk_text = " ".join(chunk_words)
            chunk_id = f"{doc_id}_chunk{i:03d}"
            self.chunks.append({"id": chunk_id, "text": chunk_text, "source": doc_id})

    def _build_idf(self) -> None:
        N = len(self.chunks)
        df: Counter = Counter()
        for chunk in self.chunks:
            tokens = set(_tokenize(chunk["text"]))
            for t in tokens:
                df[t] += 1
        self.idf = {t: math.log((N + 1) / (freq + 1)) + 1 for t, freq in df.items()}

    # ── Query ─────────────────────────────────────────────────────────────
    def _tf(self, tokens: List[str]) -> Dict[str, float]:
        count = Counter(tokens)
        total = len(tokens) or 1
        return {t: c / total for t, c in count.items()}

    def _tfidf_vec(self, text: str) -> Dict[str, float]:
        tokens = _tokenize(text)
        tf = self._tf(tokens)
        return {t: tf_val * self.idf.get(t, 0) for t, tf_val in tf.items()}

    def _cosine(self, a: Dict[str, float], b: Dict[str, float]) -> float:
        common = set(a) & set(b)
        dot = sum(a[t] * b[t] for t in common)
        norm_a = math.sqrt(sum(v * v for v in a.values())) or 1e-9
        norm_b = math.sqrt(sum(v * v for v in b.values())) or 1e-9
        return dot / (norm_a * norm_b)

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        if not self._built:
            raise RuntimeError("Store chưa được build. Gọi load_docs_from_dir() trước.")
        q_vec = self._tfidf_vec(query)
        scores = [
            (chunk, self._cosine(q_vec, self._tfidf_vec(chunk["text"])))
            for chunk in self.chunks
        ]
        scores.sort(key=lambda x: x[1], reverse=True)
        return [{"id": c["id"], "text": c["text"], "source": c["source"], "score": s}
                for c, s in scores[:top_k]]


# ─────────────────────────────────────────────
#  Singleton store (load 1 lần duy nhất)
# ─────────────────────────────────────────────
_STORE: TFIDFStore | None = None
_DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "docs")


def _get_store() -> TFIDFStore:
    global _STORE
    if _STORE is None:
        _STORE = TFIDFStore(chunk_size=300, overlap=50)
        _STORE.load_docs_from_dir(os.path.abspath(_DOCS_DIR))
    return _STORE


# ─────────────────────────────────────────────
#  Agent V1 — Baseline (prompt ngắn gọn)
# ─────────────────────────────────────────────

class MainAgent:
    """
    Agent V1 — RAG Baseline.
    Retrieval: TF-IDF, top-5 chunks.
    Generation: GPT-4o-mini với system prompt đơn giản.
    """

    SYSTEM_PROMPT = (
        "Bạn là nhân viên hỗ trợ nội bộ. Chỉ dựa vào CONTEXT được cung cấp để trả lời. "
        "Nếu không tìm thấy thông tin trong context, trả lời: 'Tôi không có thông tin về vấn đề này.'"
        " Trả lời ngắn gọn, chính xác."
    )

    def __init__(self, model: str = "gpt-4o-mini", top_k: int = 5):
        self.name = "SupportAgent-v1"
        self.model = model
        self.top_k = top_k
        self._client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_API_KEY"))

    async def query(self, question: str) -> Dict[str, Any]:
        store = _get_store()

        # ── Retrieval ──────────────────────────────────────────────────────
        retrieved = store.search(question, top_k=self.top_k)
        context_text = "\n\n---\n".join(
            f"[{r['source']}] {r['text']}" for r in retrieved
        )
        retrieved_ids = [r["id"] for r in retrieved]

        # ── Generation ────────────────────────────────────────────────────
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"CONTEXT:\n{context_text}\n\nCÂU HỎI: {question}"},
        ]
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            max_tokens=512,
        )
        answer = response.choices[0].message.content.strip()
        usage = response.usage

        return {
            "answer": answer,
            "contexts": [r["text"] for r in retrieved],
            "retrieved_ids": retrieved_ids,
            "metadata": {
                "model": self.model,
                "tokens_used": usage.total_tokens if usage else 0,
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "sources": list({r["source"] for r in retrieved}),
                "version": self.name,
            },
        }


# ─────────────────────────────────────────────
#  Agent V2 — Optimized (prompt nâng cao + top7)
# ─────────────────────────────────────────────

class MainAgentV2(MainAgent):
    """
    Agent V2 — Cải tiến:
    - System prompt đầy đủ hơn (chain-of-thought ngắn, citation yêu cầu).
    - top_k = 7 để coverage rộng hơn.
    - Temperature thấp hơn = 0.1 cho độ ổn định.
    """

    SYSTEM_PROMPT = (
        "Bạn là nhân viên hỗ trợ nội bộ chuyên nghiệp. "
        "NHIỆM VỤ: Trả lời CÂU HỎI dựa trên CONTEXT bên dưới. "
        "QUY TẮC:\n"
        "1. Chỉ sử dụng thông tin từ CONTEXT, không suy đoán.\n"
        "2. Trích dẫn nguồn tài liệu trong ngoặc vuông, ví dụ: [hr_leave_policy].\n"
        "3. Nếu context có thông tin mâu thuẫn, hãy nêu rõ sự mâu thuẫn.\n"
        "4. Nếu không có đủ thông tin, trả lời: 'Tôi không có thông tin về vấn đề này.'\n"
        "5. Không bịa đặt số liệu, ngày tháng, hay tên người.\n"
        "Trả lời rõ ràng, chuyên nghiệp, đúng trọng tâm."
    )

    def __init__(self, model: str = "gpt-4o-mini", top_k: int = 7):
        super().__init__(model=model, top_k=top_k)
        self.name = "SupportAgent-v2"

    async def query(self, question: str) -> Dict[str, Any]:
        store = _get_store()

        retrieved = store.search(question, top_k=self.top_k)
        context_text = "\n\n---\n".join(
            f"[{r['source']}] {r['text']}" for r in retrieved
        )
        retrieved_ids = [r["id"] for r in retrieved]

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"CONTEXT:\n{context_text}\n\nCÂU HỎI: {question}"},
        ]
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.1,
            max_tokens=512,
        )
        answer = response.choices[0].message.content.strip()
        usage = response.usage

        return {
            "answer": answer,
            "contexts": [r["text"] for r in retrieved],
            "retrieved_ids": retrieved_ids,
            "metadata": {
                "model": self.model,
                "tokens_used": usage.total_tokens if usage else 0,
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "sources": list({r["source"] for r in retrieved}),
                "version": self.name,
            },
        }


# ─────────────────────────────────────────────
#  Smoke test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    async def _test():
        agent_v1 = MainAgent()
        agent_v2 = MainAgentV2()

        question = "Làm thế nào để đổi mật khẩu khi quên?"
        print("=== V1 ===")
        r1 = await agent_v1.query(question)
        print("Answer:", r1["answer"][:200])
        print("Retrieved IDs:", r1["retrieved_ids"])

        print("\n=== V2 ===")
        r2 = await agent_v2.query(question)
        print("Answer:", r2["answer"][:200])
        print("Retrieved IDs:", r2["retrieved_ids"])

    asyncio.run(_test())
