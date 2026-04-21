import argparse
import json
import re
from pathlib import Path
from typing import Iterable


SECTION_HEADER_RE = re.compile(r"^===\s*(.*?)\s*===\s*$")
HR_SUBSECTION_RE = re.compile(r"^(\d+\.\d+)\s+(.+?)(?::)?$")
WHITESPACE_RE = re.compile(r"\s+")

SOURCE_SLUGS = {
    "access_control_sop.txt": "access",
    "hr_leave_policy.txt": "hr",
    "it_helpdesk_faq.txt": "helpdesk",
    "policy_refund_v4.txt": "refund",
    "sla_p1_2026.txt": "sla",
}

SECTION_SLUGS = {
    "access_control_sop.txt": {
        "Section 1: Phạm vi và mục đích": "scope",
        "Section 2: Phân cấp quyền truy cập": "level",
        "Section 3: Quy trình yêu cầu cấp quyền": "process",
        "Section 4: Escalation khi cần thay đổi quyền hệ thống": "escalation",
        "Section 5: Thu hồi quyền truy cập": "revoke",
        "Section 6: Audit và review định kỳ": "audit",
    },
    "hr_leave_policy.txt": {
        "Phần 1.1: Nghỉ phép năm": "annual_leave",
        "Phần 1.2: Nghỉ ốm": "sick_leave",
        "Phần 1.3: Nghỉ thai sản": "maternity",
        "Phần 2: Quy trình xin nghỉ phép": "leave_process",
        "Phần 3: Chính sách làm thêm giờ": "overtime",
        "Phần 4: Remote work policy": "remote",
    },
    "it_helpdesk_faq.txt": {
        "Section 1: Tài khoản và mật khẩu": "pwd",
        "Section 2: VPN và kết nối từ xa": "vpn",
        "Section 3: Phần mềm và license": "software",
        "Section 4: Thiết bị và phần cứng": "hardware",
        "Section 5: Email và lịch": "email",
    },
    "policy_refund_v4.txt": {
        "Điều 1: Phạm vi áp dụng": "scope",
        "Điều 2: Điều kiện được hoàn tiền": "condition",
        "Điều 3: Điều kiện áp dụng và ngoại lệ": "exception",
        "Điều 4: Quy trình xử lý yêu cầu hoàn tiền": "process",
        "Điều 5: Hình thức hoàn tiền": "method",
        "Điều 6: Liên hệ và hỗ trợ": "contact",
    },
    "sla_p1_2026.txt": {
        "Phần 1: Định nghĩa mức độ ưu tiên": "definition",
        "Phần 2: SLA theo mức độ ưu tiên": "targets",
        "Phần 3: Quy trình xử lý sự cố P1": "p1_process",
        "Phần 4: Công cụ và kênh liên lạc": "channels",
        "Phần 5: Lịch sử phiên bản": "changelog",
    },
}

EXCLUDED_SECTIONS = {
    "access_control_sop.txt": {"Section 7: Công cụ liên quan"},
    "hr_leave_policy.txt": {"Phần 5: Liên hệ HR"},
    "it_helpdesk_faq.txt": {"Section 6: Liên hệ IT Helpdesk"},
    "policy_refund_v4.txt": {"Điều 6: Liên hệ và hỗ trợ"},
    "sla_p1_2026.txt": {"Phần 4: Công cụ và kênh liên lạc"},
}

HR_SUBSECTION_TITLES = {
    "1.1": "Phần 1.1: Nghỉ phép năm",
    "1.2": "Phần 1.2: Nghỉ ốm",
    "1.3": "Phần 1.3: Nghỉ thai sản",
}


def normalize_text(lines: Iterable[str]) -> str:
    return WHITESPACE_RE.sub(" ", " ".join(line.strip() for line in lines if line.strip())).strip()


def fallback_slug(section_title: str) -> str:
    slug = section_title.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_") or "section"


def split_hr_leave_sections(section_lines: list[str]) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    current_code: str | None = None
    current_lines: list[str] = []

    for raw_line in section_lines:
        match = HR_SUBSECTION_RE.match(raw_line.strip())
        if match and match.group(1) in HR_SUBSECTION_TITLES:
            if current_code and current_lines:
                sections.append((HR_SUBSECTION_TITLES[current_code], current_lines))
            current_code = match.group(1)
            current_lines = []
            continue

        if current_code:
            current_lines.append(raw_line)

    if current_code and current_lines:
        sections.append((HR_SUBSECTION_TITLES[current_code], current_lines))

    return sections


def chunk_document(path: Path) -> list[dict]:
    source_name = path.name
    source_slug = SOURCE_SLUGS.get(source_name, path.stem)
    section_slug_map = SECTION_SLUGS.get(source_name, {})
    excluded_sections = EXCLUDED_SECTIONS.get(source_name, set())

    sections: list[tuple[str, list[str]]] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = SECTION_HEADER_RE.match(raw_line.strip())
        if match:
            if current_title and current_lines:
                sections.append((current_title, current_lines))
            current_title = match.group(1)
            current_lines = []
            continue

        if current_title:
            current_lines.append(raw_line)

    if current_title and current_lines:
        sections.append((current_title, current_lines))

    expanded_sections: list[tuple[str, list[str]]] = []
    for section_title, section_lines in sections:
        if section_title in excluded_sections:
            continue
        if source_name == "hr_leave_policy.txt" and section_title == "Phần 1: Các loại nghỉ phép":
            expanded_sections.extend(split_hr_leave_sections(section_lines))
            continue
        expanded_sections.append((section_title, section_lines))

    chunks = []
    for index, (section_title, section_lines) in enumerate(expanded_sections, start=1):
        text = normalize_text(section_lines)
        if not text:
            continue

        section_slug = section_slug_map.get(section_title, fallback_slug(section_title))
        chunk = {
            "id": f"{source_slug}_{section_slug}_{index:02d}",
            "source": source_name,
            "section": section_title,
            "text": text,
        }
        chunks.append(chunk)

    return chunks


def build_corpus(docs_dir: Path) -> list[dict]:
    chunks: list[dict] = []
    for path in sorted(docs_dir.glob("*.txt")):
        chunks.extend(chunk_document(path))
    return chunks


def write_jsonl(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build data/corpus.jsonl from text docs.")
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=Path(__file__).with_name("docs"),
        help="Directory containing source .txt documents.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("corpus.jsonl"),
        help="Output JSONL path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_corpus(args.docs_dir)
    write_jsonl(rows, args.output)
    print(f"Wrote {len(rows)} chunks to {args.output}")


if __name__ == "__main__":
    main()