# SDG Usage Guide

Tài liệu này mô tả cách dùng các script trong thư mục `data/` để tạo corpus, sinh Golden Dataset và validate dữ liệu trước khi chạy benchmark.

---

## 1. Chuẩn bị tài liệu nguồn

Đặt các file `.txt` vào thư mục `data/docs/`.

Hiện tại repo đang dùng các file sau:
- `data/docs/access_control_sop.txt`
- `data/docs/hr_leave_policy.txt`
- `data/docs/it_helpdesk_faq.txt`
- `data/docs/policy_refund_v4.txt`
- `data/docs/sla_p1_2026.txt`

---

## 2. Tạo corpus từ tài liệu nguồn

Script:

```bash
python data/build_corpus.py
```

Kết quả:
- Tạo hoặc ghi đè file `data/corpus.jsonl`
- Mỗi dòng là 1 chunk có các trường:
  - `id`
  - `source`
  - `section`
  - `text`

Nếu muốn ghi ra file khác:

```bash
python data/build_corpus.py --output /tmp/corpus.jsonl
```

Nếu muốn đổi thư mục tài liệu đầu vào:

```bash
python data/build_corpus.py --docs-dir data/docs --output /tmp/corpus.jsonl
```

---

## 3. Sinh Golden Dataset từ corpus

Script:

```bash
python data/synthetic_gen.py
```

Kết quả:
- Tạo hoặc ghi đè file `data/golden_set.jsonl`
- Script đọc trực tiếp từ `data/corpus.jsonl`
- Script hiện sinh tự động các nhóm case:
  - `fact-check`
  - `reasoning`
  - `ambiguous`
  - `out-of-context`
  - `prompt-injection`
  - `goal-hijacking`
  - `conflict`

Nếu muốn ghi ra file khác:

```bash
python data/synthetic_gen.py --output /tmp/golden_set.jsonl
```

Nếu muốn dùng corpus khác:

```bash
python data/synthetic_gen.py --corpus /tmp/corpus.jsonl --output /tmp/golden_set.jsonl
```

---

## 4. Validate Golden Dataset

Script:

```bash
python data/validate_golden_set.py
```

Script này kiểm tra:
- File JSONL có parse được hay không
- Mỗi case có đủ field bắt buộc hay không
- `metadata.type` và `metadata.difficulty` có hợp lệ hay không
- `id` của case có bị trùng hay không
- `expected_retrieval_ids` có tồn tại trong `data/corpus.jsonl` hay không
- Case `out-of-context` có dùng mảng retrieval rỗng hay không

Nếu muốn validate file khác:

```bash
python data/validate_golden_set.py --golden-set /tmp/golden_set.jsonl --corpus data/corpus.jsonl
```

---

## 5. Quy trình chạy chuẩn

Chạy theo đúng thứ tự này:

```bash
python data/build_corpus.py
python data/synthetic_gen.py
python data/validate_golden_set.py
```

Nếu mọi thứ hợp lệ, bạn sẽ có:
- `data/corpus.jsonl`
- `data/golden_set.jsonl`

Lúc đó mới nên chạy benchmark bằng `main.py`.

---

## 6. Kiểm tra nhanh đầu ra

Đếm số chunk trong corpus:

```bash
wc -l data/corpus.jsonl
```

Đếm số test case trong golden set:

```bash
wc -l data/golden_set.jsonl
```

Xem vài dòng đầu của file:

```bash
sed -n '1,5p' data/corpus.jsonl
sed -n '1,5p' data/golden_set.jsonl
```

---

## 7. Khi nào cần chạy lại

Bạn nên chạy lại `build_corpus.py` khi:
- Có thay đổi trong `data/docs/`
- Có thêm tài liệu nguồn mới
- Bạn muốn cập nhật lại `id` và `text` chunk theo tài liệu mới

Bạn nên chạy lại `synthetic_gen.py` khi:
- Corpus thay đổi
- Bạn thay logic sinh test case
- Bạn muốn refresh toàn bộ Golden Dataset

Bạn nên chạy lại `validate_golden_set.py` khi:
- Có chỉnh sửa thủ công trong `data/golden_set.jsonl`
- Có thay đổi schema hoặc corpus
- Trước khi chạy benchmark hoặc nộp bài

---

## 8. Các file liên quan

- `data/build_corpus.py`: tạo `corpus.jsonl` từ `data/docs/`
- `data/corpus.jsonl`: corpus retrieval có gắn chunk id
- `data/synthetic_gen.py`: sinh Golden Dataset từ corpus
- `data/golden_set.jsonl`: bộ test case dùng cho benchmark
- `data/validate_golden_set.py`: validate chất lượng và tính nhất quán của golden set
- `data/golden_case.schema.json`: schema chuẩn của 1 test case
- `data/SDG_PLAYBOOK.md`: playbook thiết kế SDG và QC gate
