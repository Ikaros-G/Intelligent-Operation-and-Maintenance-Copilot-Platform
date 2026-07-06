"""Run RAGAS collections metrics against the checked-in AIOps evaluation set."""

import argparse
import asyncio
import json
from pathlib import Path
from statistics import mean
from typing import Any

from app.config import config


def load_dataset(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    required = {"user_input", "response", "retrieved_contexts", "reference"}
    for index, row in enumerate(rows, 1):
        missing = required - row.keys()
        if missing:
            raise ValueError(f"第 {index} 条评测数据缺少字段: {sorted(missing)}")
    return rows


async def evaluate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from openai import AsyncOpenAI
    from ragas.embeddings.base import embedding_factory
    from ragas.llms import llm_factory
    from ragas.metrics.collections import AnswerRelevancy, ContextRecall, Faithfulness

    client = AsyncOpenAI(api_key=config.dashscope_api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    llm = llm_factory(config.rag_model, client=client)
    embeddings = embedding_factory("openai", model=config.dashscope_embedding_model, client=client)
    metrics = {
        "context_recall": ContextRecall(llm=llm),
        "answer_relevancy": AnswerRelevancy(llm=llm, embeddings=embeddings),
        "faithfulness": Faithfulness(llm=llm),
    }
    details = []
    for row in rows:
        scores = {
            "context_recall": (await metrics["context_recall"].ascore(user_input=row["user_input"], retrieved_contexts=row["retrieved_contexts"], reference=row["reference"])).value,
            "answer_relevancy": (await metrics["answer_relevancy"].ascore(user_input=row["user_input"], response=row["response"])).value,
            "faithfulness": (await metrics["faithfulness"].ascore(user_input=row["user_input"], response=row["response"], retrieved_contexts=row["retrieved_contexts"])).value,
        }
        details.append({"user_input": row["user_input"], "scores": scores})
    averages = {name: mean(item["scores"][name] for item in details) for name in metrics}
    return {"averages": averages, "samples": details}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("evaluation/dataset.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("evaluation/report.json"))
    args = parser.parse_args()
    report = await evaluate(load_dataset(args.dataset))
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["averages"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
