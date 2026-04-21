import argparse
import json
import sys
from collections import Counter
from pathlib import Path


ALLOWED_TOP_LEVEL_KEYS = {
    "id",
    "question",
    "expected_answer",
    "context",
    "expected_retrieval_ids",
    "metadata",
}

REQUIRED_TOP_LEVEL_KEYS = {
    "id",
    "question",
    "expected_answer",
    "expected_retrieval_ids",
    "metadata",
}

ALLOWED_METADATA_KEYS = {"difficulty", "type", "source_doc", "tags"}
REQUIRED_METADATA_KEYS = {"difficulty", "type"}
ALLOWED_DIFFICULTIES = {"easy", "medium", "hard", "adversarial"}
ALLOWED_TYPES = {
    "fact-check",
    "reasoning",
    "multi-turn",
    "out-of-context",
    "ambiguous",
    "conflict",
    "prompt-injection",
    "goal-hijacking",
}


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} is not valid JSON: {exc}") from exc
    return rows


def load_corpus_ids(path: Path) -> set[str]:
    ids = set()
    for row in load_jsonl(path):
        chunk_id = row.get("id")
        if isinstance(chunk_id, str) and chunk_id:
            ids.add(chunk_id)
    return ids


def expect_string(case: dict, key: str, errors: list[str], prefix: str) -> None:
    value = case.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{prefix}: field '{key}' must be a non-empty string")


def validate_metadata(metadata: object, errors: list[str], prefix: str) -> dict | None:
    if not isinstance(metadata, dict):
        errors.append(f"{prefix}: field 'metadata' must be an object")
        return None

    missing = REQUIRED_METADATA_KEYS - metadata.keys()
    extra = metadata.keys() - ALLOWED_METADATA_KEYS
    if missing:
        errors.append(f"{prefix}: metadata missing keys: {sorted(missing)}")
    if extra:
        errors.append(f"{prefix}: metadata has unexpected keys: {sorted(extra)}")

    difficulty = metadata.get("difficulty")
    case_type = metadata.get("type")
    if difficulty not in ALLOWED_DIFFICULTIES:
        errors.append(f"{prefix}: metadata.difficulty must be one of {sorted(ALLOWED_DIFFICULTIES)}")
    if case_type not in ALLOWED_TYPES:
        errors.append(f"{prefix}: metadata.type must be one of {sorted(ALLOWED_TYPES)}")

    tags = metadata.get("tags")
    if tags is not None:
        if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
            errors.append(f"{prefix}: metadata.tags must be a list of non-empty strings")
        elif len(tags) != len(set(tags)):
            errors.append(f"{prefix}: metadata.tags must not contain duplicates")

    source_doc = metadata.get("source_doc")
    if source_doc is not None and (not isinstance(source_doc, str) or not source_doc.strip()):
        errors.append(f"{prefix}: metadata.source_doc must be a non-empty string when present")

    return metadata


def validate_expected_ids(
    case: dict,
    corpus_ids: set[str],
    errors: list[str],
    prefix: str,
    case_type: str | None,
) -> None:
    expected_ids = case.get("expected_retrieval_ids")
    if not isinstance(expected_ids, list):
        errors.append(f"{prefix}: field 'expected_retrieval_ids' must be an array")
        return

    if any(not isinstance(item, str) or not item.strip() for item in expected_ids):
        errors.append(f"{prefix}: expected_retrieval_ids must contain only non-empty strings")
        return

    if len(expected_ids) != len(set(expected_ids)):
        errors.append(f"{prefix}: expected_retrieval_ids must not contain duplicates")

    if case_type == "out-of-context":
        if expected_ids:
            errors.append(f"{prefix}: out-of-context cases must use an empty expected_retrieval_ids array")
        return

    if not expected_ids:
        errors.append(f"{prefix}: expected_retrieval_ids cannot be empty unless metadata.type is 'out-of-context'")
        return

    missing_ids = [chunk_id for chunk_id in expected_ids if chunk_id not in corpus_ids]
    if missing_ids:
        errors.append(f"{prefix}: expected_retrieval_ids not found in corpus: {missing_ids}")


def validate_case(case: object, line_number: int, corpus_ids: set[str], seen_ids: set[str]) -> list[str]:
    prefix = f"line {line_number}"
    errors: list[str] = []

    if not isinstance(case, dict):
        return [f"{prefix}: case must be a JSON object"]

    missing = REQUIRED_TOP_LEVEL_KEYS - case.keys()
    extra = case.keys() - ALLOWED_TOP_LEVEL_KEYS
    if missing:
        errors.append(f"{prefix}: missing required keys: {sorted(missing)}")
    if extra:
        errors.append(f"{prefix}: unexpected keys: {sorted(extra)}")

    expect_string(case, "id", errors, prefix)
    expect_string(case, "question", errors, prefix)
    expect_string(case, "expected_answer", errors, prefix)
    if "context" in case and case["context"] is not None and not isinstance(case["context"], str):
        errors.append(f"{prefix}: field 'context' must be a string when present")

    case_id = case.get("id")
    if isinstance(case_id, str) and case_id:
        if case_id in seen_ids:
            errors.append(f"{prefix}: duplicate case id '{case_id}'")
        seen_ids.add(case_id)

    metadata = validate_metadata(case.get("metadata"), errors, prefix)
    case_type = metadata.get("type") if metadata else None
    validate_expected_ids(case, corpus_ids, errors, prefix, case_type)

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate data/golden_set.jsonl against corpus ids.")
    parser.add_argument(
        "--golden-set",
        type=Path,
        default=Path(__file__).with_name("golden_set.jsonl"),
        help="Path to the golden set JSONL file.",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path(__file__).with_name("corpus.jsonl"),
        help="Path to the corpus JSONL file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        corpus_ids = load_corpus_ids(args.corpus)
        cases = load_jsonl(args.golden_set)
    except (FileNotFoundError, ValueError) as exc:
        print(f"❌ {exc}")
        return 1

    all_errors: list[str] = []
    seen_ids: set[str] = set()
    type_counter: Counter[str] = Counter()

    with args.golden_set.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            case = json.loads(line)
            all_errors.extend(validate_case(case, line_number, corpus_ids, seen_ids))
            metadata = case.get("metadata", {})
            case_type = metadata.get("type") if isinstance(metadata, dict) else None
            if isinstance(case_type, str):
                type_counter[case_type] += 1

    if all_errors:
        print("❌ Golden set validation failed:")
        for error in all_errors:
            print(f"- {error}")
        print(f"\nFound {len(all_errors)} error(s) in {args.golden_set}")
        return 1

    print(f"✅ Golden set is valid: {len(cases)} case(s)")
    print(f"✅ Corpus ids loaded: {len(corpus_ids)} chunk(s)")
    if type_counter:
        print("\nCase type distribution:")
        for case_type, count in sorted(type_counter.items()):
            print(f"- {case_type}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())