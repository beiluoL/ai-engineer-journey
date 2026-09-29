"""任务集抽象、自动评分与多模型排行。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .autoeval import AutoEvalScore, aggregate_scores, evaluate_answer
from .evalset import infer_topic


@dataclass(frozen=True)
class BenchmarkTask:
    task_id: str
    prompt: str
    reference: str
    keywords: tuple[str, ...] = ()
    topic: str = "general"


class Benchmark:
    def __init__(self, name: str, tasks: list[BenchmarkTask]) -> None:
        if not tasks:
            raise ValueError("Benchmark 至少需要一个任务")
        ids = [task.task_id for task in tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("task_id 必须唯一")
        self.name = name
        self.tasks = list(tasks)

    def evaluate(self, model_name: str, predictor: Callable[[str], str]) -> dict:
        details = []
        scores: list[AutoEvalScore] = []
        for task in self.tasks:
            answer = predictor(task.prompt)
            score = evaluate_answer(answer, task.reference, list(task.keywords) or None)
            scores.append(score)
            details.append({
                "task_id": task.task_id,
                "topic": task.topic,
                "answer": answer,
                **score.to_dict(),
            })
        return {
            "benchmark": self.name,
            "model": model_name,
            "n_tasks": len(self.tasks),
            **aggregate_scores(scores),
            "details": details,
        }

    def compare(self, predictors: dict[str, Callable[[str], str]]) -> list[dict]:
        rows = [self.evaluate(name, predictor) for name, predictor in predictors.items()]
        rows.sort(key=lambda row: (-row["total"], row["model"]))
        for rank, row in enumerate(rows, 1):
            row["rank"] = rank
        return rows


def tasks_from_records(records: list[dict], keyword_map: "dict[str, list[str]] | None" = None) -> list[BenchmarkTask]:
    tasks = []
    for index, record in enumerate(records):
        prompt = (record.get("instruction") or "").strip()
        keys = tuple((keyword_map or {}).get(prompt, ()))
        tasks.append(BenchmarkTask(
            task_id=f"java-{index + 1:03d}", prompt=prompt,
            reference=(record.get("output") or "").strip(), keywords=keys,
            topic=record.get("topic") or infer_topic(record),
        ))
    return tasks


__all__ = ["Benchmark", "BenchmarkTask", "tasks_from_records"]
