import json
import os

def validate_lab():
    print("🔍 Đang kiểm tra định dạng bài nộp...")

    required_files = [
        "reports/summary.json",
        "reports/benchmark_results.json",
        "analysis/failure_analysis.md"
    ]

    # 1. Kiểm tra sự tồn tại của tất cả file
    missing = []
    for f in required_files:
        if os.path.exists(f):
            print(f"✅ Tìm thấy: {f}")
        else:
            print(f"❌ Thiếu file: {f}")
            missing.append(f)

    if missing:
        print(f"\n❌ Thiếu {len(missing)} file. Hãy bổ sung trước khi nộp bài.")
        return

    # 2. Kiểm tra nội dung summary.json
    try:
        with open("reports/summary.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ File reports/summary.json không phải JSON hợp lệ: {e}")
        return

    # Check if using v1/v2 structure or flat structure
    if "v1" in data or "v2" in data:
        print("ℹ️  Phát hiện format Multi-version (V1/V2).")
        # Regression mode - use v2 or v1
        version_data = data.get("v2") or data.get("v1")
        if not version_data:
            print("❌ File summary.json thiếu dữ liệu v1 hoặc v2.")
            return
        if "metrics" not in version_data or "metadata" not in version_data:
            print("❌ File summary.json thiếu trường 'metrics' hoặc 'metadata' trong v1/v2.")
            return
        metrics = version_data["metrics"]
        metadata = version_data["metadata"]
    else:
        # Flat structure
        if "metrics" not in data or "metadata" not in data:
            print("❌ File summary.json thiếu trường 'metrics' hoặc 'metadata'.")
            return
        metrics = data["metrics"]
        metadata = data["metadata"]

    print(f"\n--- Thống kê nhanh ---")
    print(f"Tổng số cases: {metadata.get('total', 'N/A')}")
    print(f"Điểm trung bình: {metrics.get('avg_score', 0):.2f}")

    # EXPERT CHECKS
    has_retrieval = "hit_rate" in metrics
    if has_retrieval:
        print(f"✅ Đã tìm thấy Retrieval Metrics (Hit Rate: {metrics['hit_rate']*100:.1f}%)")
    else:
        print(f"⚠️ CẢNH BÁO: Thiếu Retrieval Metrics (hit_rate).")

    has_multi_judge = "agreement_rate" in metrics
    if has_multi_judge:
        print(f"✅ Đã tìm thấy Multi-Judge Metrics (Agreement Rate: {metrics['agreement_rate']*100:.1f}%)")
    else:
        print(f"⚠️ CẢNH BÁO: Thiếu Multi-Judge Metrics (agreement_rate).")

    if metadata.get("version"):
        print(f"✅ Đã tìm thấy thông tin phiên bản Agent: {metadata['version']}")
    
    # Check regression mode
    if "regression" in data:
        print(f"✅ Đã tìm thấy Regression Analysis (V1 vs V2)")
        print(f"   Decision: {data['regression'].get('decision', 'N/A')}")

    print("\n🚀 Bài lab đã sẵn sàng để chấm điểm!")

if __name__ == "__main__":
    validate_lab()
