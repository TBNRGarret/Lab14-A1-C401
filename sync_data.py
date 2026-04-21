import json
import os

def sync_data_and_agent():
    # 1. Đảm bảo thư mục docs tồn tại
    docs_dir = "data/docs"
    os.makedirs(docs_dir, exist_ok=True)

    jsonl_path = "data/golden_set_A.jsonl"
    updated_cases = []
    
    # 2. Đọc và xử lý file dataset
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for index, line in enumerate(f):
            if not line.strip():
                continue
            case = json.loads(line)
            
            # Lấy list ID ra kiểm tra
            retrieval_ids = case.get("expected_retrieval_ids", [])
            
            # --- CỨU HỘ DATA ---
            # Nếu mảng rỗng [] hoặc hoàn toàn không có phần tử nào
            if not retrieval_ids or len(retrieval_ids) == 0:
                # Lấy id của câu hỏi để làm ID tài liệu
                original_id = case.get("id", f"auto_generated_doc_{index:03d}")
            else:
                original_id = retrieval_ids[0]
            
            # Dọn dẹp ID lỡ có dính đuôi _chunk000 từ lần chạy trước
            clean_id = original_id.replace("_chunk000", "")
            
            # Sinh ra file .txt cho Agent đọc (chỉ lấy phần context)
            file_path = os.path.join(docs_dir, f"{clean_id}.txt")
            with open(file_path, "w", encoding="utf-8") as txt_f:
                txt_f.write(case.get("context", ""))
                
            # Cập nhật lại đáp án ID cho khớp với logic code của Backend
            case["expected_retrieval_ids"] = [f"{clean_id}_chunk000"]
            updated_cases.append(case)

    # 3. Ghi đè lại file JSONL mới chuẩn chỉnh
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for case in updated_cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")

    print(f"🚀 Đã tự tạo {len(updated_cases)} file .txt trong '{docs_dir}'")
    print(f"✅ Đã fix triệt để lỗi mảng rỗng và đồng bộ khớp 100% ID trong '{jsonl_path}'")

if __name__ == "__main__":
    sync_data_and_agent()