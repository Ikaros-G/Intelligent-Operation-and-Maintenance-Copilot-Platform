from pathlib import Path

from evaluation.run_ragas import load_dataset


def test_ragas_dataset_contains_required_rag_fields():
    rows = load_dataset(Path("evaluation/dataset.jsonl"))

    assert len(rows) >= 3
    assert all(row["retrieved_contexts"] for row in rows)
    assert all(row["reference"] for row in rows)
