"""
Test script để kiểm tra LLMJudge có hoạt động không:
1. Gọi cả 2 judge (OpenAI + Gemini) thật
2. Agreement rate
3. Tie-breaker (case lệch nhiều)
4. Position bias check
5. Cost summary
"""
import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()

from engine.llm_judge import LLMJudge


async def test_basic_multi_judge():
    print("\n" + "=" * 70)
    print("TEST 1: Multi-Judge trên 1 câu trả lời TỐT")
    print("=" * 70)
    judge = LLMJudge()

    question = "Làm thế nào để đổi mật khẩu trên hệ thống nội bộ?"
    answer = (
        "Để đổi mật khẩu, bạn vào menu 'Cài đặt tài khoản' → 'Bảo mật' → "
        "'Đổi mật khẩu'. Nhập mật khẩu cũ, sau đó nhập mật khẩu mới (tối thiểu "
        "8 ký tự, có chữ hoa, số và ký tự đặc biệt) và xác nhận. Hệ thống sẽ "
        "yêu cầu đăng nhập lại sau khi đổi thành công."
    )
    ground_truth = (
        "Vào Settings → Security → Change Password. Nhập mật khẩu cũ và mật khẩu "
        "mới (yêu cầu: >=8 ký tự, chữ hoa, số, ký tự đặc biệt). Sau khi đổi, "
        "phải đăng nhập lại."
    )

    result = await judge.evaluate_multi_judge(question, answer, ground_truth)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert "final_score" in result and "agreement_rate" in result, "Thiếu key bắt buộc"
    assert 1.0 <= result["final_score"] <= 5.0, "final_score không nằm trong 1-5"
    assert 0.0 <= result["agreement_rate"] <= 1.0, "agreement_rate không nằm trong 0-1"
    print("PASS: Multi-judge trả về đúng interface contract.")
    return judge


async def test_bad_answer(judge: LLMJudge):
    print("\n" + "=" * 70)
    print("TEST 2: Multi-Judge trên 1 câu trả lời SAI / HALLUCINATION")
    print("=" * 70)

    question = "Chính sách nghỉ phép năm của công ty là bao nhiêu ngày?"
    answer = "Công ty cho phép mỗi nhân viên nghỉ 365 ngày mỗi năm và không cần xin phép ai cả."
    ground_truth = "Mỗi nhân viên có 12 ngày nghỉ phép năm, cần xin phép quản lý trực tiếp."

    result = await judge.evaluate_multi_judge(question, answer, ground_truth)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert result["final_score"] <= 3.0, (
        f"Câu trả lời SAI rõ ràng nhưng final_score={result['final_score']} > 3.0 "
        "(judge có thể đang hoạt động không đúng)"
    )
    print("PASS: Judge phát hiện được câu trả lời sai.")


async def test_position_bias(judge: LLMJudge):
    print("\n" + "=" * 70)
    print("TEST 3: Position Bias check")
    print("=" * 70)

    question = "Tổng giám đốc công ty tên gì?"
    response_a = "Tổng giám đốc công ty là ông Nguyễn Văn A, nhậm chức từ 2020."
    response_b = "TGĐ tên gì đó, tôi không chắc lắm."

    result = await judge.check_position_bias(question, response_a, response_b)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert "has_position_bias" in result, "Thiếu key has_position_bias"
    print("PASS: Position bias check chạy được.")


async def test_cost_summary(judge: LLMJudge):
    print("\n" + "=" * 70)
    print("TEST 4: Cost Summary")
    print("=" * 70)
    summary = judge.get_cost_summary()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    assert summary["total_cost_usd"] >= 0
    assert summary["tokens"]["openai"]["input"] > 0, "OpenAI input tokens = 0 → chưa gọi API thật!"
    assert summary["tokens"]["gemini"]["input"] > 0, "Gemini input tokens = 0 → chưa gọi API thật!"
    print("PASS: Có tracking token của CẢ 2 model → đã gọi API thật.")


async def main():
    if not os.getenv("OPEN_AI_API_KEY"):
        print("ERROR: Thiếu OPEN_AI_API_KEY trong .env")
        return
    if not os.getenv("GEMINI_API_KEY"):
        print("ERROR: Thiếu GEMINI_API_KEY trong .env")
        return

    try:
        judge = await test_basic_multi_judge()
        await test_bad_answer(judge)
        await test_position_bias(judge)
        await test_cost_summary(judge)
        print("\n" + "=" * 70)
        print("TAT CA TEST DA PASS - LLMJudge hoat dong dung.")
        print("=" * 70)
    except AssertionError as e:
        print(f"\nFAIL: {e}")
    except Exception as e:
        print(f"\nERROR (unhandled): {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
