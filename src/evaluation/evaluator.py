"""问答系统评测：对比 KG-only 与 KG+LLM 模式。"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import logging

import jieba


@dataclass
class EvalMetrics:
    mode: str
    total: int
    hit_count: int
    hit_rate: float
    avg_keyword_recall: float
    avg_response_length: float
    elapsed_seconds: float = 0.0


class Evaluator:
    """基于关键词召回与命中率的轻量评测。"""

    def __init__(self, test_set_path: Path, graph_database: str = "Neo4j 5.26") -> None:
        with test_set_path.open(encoding="utf-8") as f:
            self.test_set = json.load(f)
        self.graph_database = graph_database
        jieba.initialize()
        jieba.setLogLevel(logging.INFO)

    @staticmethod
    @lru_cache(maxsize=1024)
    def _tokenize_cached(text: str) -> frozenset[str]:
        words = {w.strip() for w in jieba.cut(text) if len(w.strip()) > 1}
        return frozenset(words)

    @classmethod
    def _keyword_recall(cls, expected: str, actual: str) -> float:
        expected_tokens = cls._tokenize_cached(expected)
        if not expected_tokens:
            return 1.0 if expected in actual else 0.0
        actual_tokens = cls._tokenize_cached(actual)
        hit = len(expected_tokens & actual_tokens)
        return hit / len(expected_tokens)

    @classmethod
    def _is_hit(cls, expected: str, actual: str) -> bool:
        if expected in actual:
            return True
        return cls._keyword_recall(expected, actual) >= 0.5

    @staticmethod
    def _accumulate_metrics(
        expected: str, actual: str, hit_count: int, recalls: list[float], lengths: list[int]
    ) -> int:
        if Evaluator._is_hit(expected, actual):
            hit_count += 1
        recalls.append(Evaluator._keyword_recall(expected, actual))
        lengths.append(len(actual))
        return hit_count

    @staticmethod
    def _finalize_metrics(
        mode_name: str, total: int, hit_count: int, recalls: list[float], lengths: list[int], elapsed: float
    ) -> EvalMetrics:
        return EvalMetrics(
            mode=mode_name,
            total=total,
            hit_count=hit_count,
            hit_rate=round(hit_count / total, 4) if total else 0.0,
            avg_keyword_recall=round(sum(recalls) / total, 4) if total else 0.0,
            avg_response_length=round(sum(lengths) / total, 2) if total else 0.0,
            elapsed_seconds=round(elapsed, 2),
        )

    @staticmethod
    def _batch_llm_answers(llm_engine, questions: list[str], workers: int, fast: bool) -> list:
        n = len(questions)
        results: list = [None] * n
        workers = max(1, min(workers, n))

        if workers == 1:
            for i, q in enumerate(questions):
                results[i] = llm_engine.answer(q, fast=fast)
            return results

        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_map = {
                pool.submit(llm_engine.answer, q, fast=fast): i for i, q in enumerate(questions)
            }
            done = 0
            for fut in as_completed(future_map):
                idx = future_map[fut]
                results[idx] = fut.result()
                done += 1
                if done % 5 == 0 or done == n:
                    print(f"  [KG+LLM] 已完成 {done}/{n}")

        return results

    def run_comparison(
        self,
        kg_engine,
        llm_engine,
        output_dir: Path,
        *,
        skip_llm: bool = False,
        llm_workers: int = 6,
        fast_llm: bool = True,
    ) -> dict:
        """单次遍历测试集，避免重复调用 answer（原实现约 4× 题量）。"""
        questions = [item["question"] for item in self.test_set]
        total = len(questions)

        print(f"评测 {total} 题（KG-only）…")
        t0 = time.perf_counter()
        kg_results = []
        for i, q in enumerate(questions, 1):
            kg_results.append(kg_engine.answer(q))
            if i % 10 == 0 or i == total:
                print(f"  [KG-only] {i}/{total}")
        kg_elapsed = time.perf_counter() - t0

        llm_elapsed = 0.0
        if skip_llm:
            print("跳过 KG+LLM（--skip-llm）")
            llm_results = kg_results
        else:
            print(f"评测 {total} 题（KG+LLM，并发 {llm_workers}，fast={fast_llm}）…")
            t1 = time.perf_counter()
            llm_results = self._batch_llm_answers(
                llm_engine, questions, workers=llm_workers, fast=fast_llm
            )
            llm_elapsed = time.perf_counter() - t1

        kg_hit, kg_recalls, kg_lengths = 0, [], []
        llm_hit, llm_recalls, llm_lengths = 0, [], []
        details = []

        for item, kg_ans, llm_ans in zip(self.test_set, kg_results, llm_results):
            expected = item["expected_answer"]
            kg_text = kg_ans.answer
            llm_text = llm_ans.answer

            kg_hit = self._accumulate_metrics(expected, kg_text, kg_hit, kg_recalls, kg_lengths)
            llm_hit = self._accumulate_metrics(expected, llm_text, llm_hit, llm_recalls, llm_lengths)

            details.append(
                {
                    "id": item["id"],
                    "question": item["question"],
                    "expected": expected,
                    "kg_answer": kg_text,
                    "llm_answer": llm_text,
                    "kg_hit": self._is_hit(expected, kg_text),
                    "llm_hit": self._is_hit(expected, llm_text),
                }
            )

        kg_metrics = self._finalize_metrics("kg_only", total, kg_hit, kg_recalls, kg_lengths, kg_elapsed)
        llm_mode = "kg_only_skipped" if skip_llm else "kg_llm"
        llm_metrics = self._finalize_metrics(llm_mode, total, llm_hit, llm_recalls, llm_lengths, llm_elapsed)

        report = {
            "generated_at": datetime.now().isoformat(),
            "domain": "中国先进人工智能技术",
            "graph_database": self.graph_database,
            "test_set_size": total,
            "eval_options": {
                "skip_llm": skip_llm,
                "llm_workers": llm_workers,
                "fast_llm": fast_llm,
            },
            "metrics": {
                "kg_only": asdict(kg_metrics),
                "kg_llm": asdict(llm_metrics),
            },
            "improvement": {
                "hit_rate_delta": round(llm_metrics.hit_rate - kg_metrics.hit_rate, 4),
                "keyword_recall_delta": round(
                    llm_metrics.avg_keyword_recall - kg_metrics.avg_keyword_recall, 4
                ),
            },
            "details": details,
        }

        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "evaluation_report.json"
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        md_path = output_dir / "evaluation_report.md"
        md_path.write_text(self._to_markdown(report), encoding="utf-8")

        report["report_paths"] = {"json": str(report_path), "markdown": str(md_path)}
        return report

    @staticmethod
    def _to_markdown(report: dict) -> str:
        kg = report["metrics"]["kg_only"]
        llm = report["metrics"]["kg_llm"]
        imp = report["improvement"]
        opts = report.get("eval_options", {})
        skip_llm = opts.get("skip_llm", False)

        lines = [
            "# 中国先进人工智能技术知识图谱问答系统评测报告",
            "",
            f"- 生成时间：{report['generated_at']}",
            f"- 领域：{report['domain']}",
            f"- 图数据库：{report['graph_database']}",
            f"- 测试集规模：{report['test_set_size']} 题",
            f"- KG-only 耗时：{kg.get('elapsed_seconds', '—')}s",
        ]
        if not skip_llm:
            lines.append(f"- KG+LLM 耗时：{llm.get('elapsed_seconds', '—')}s（workers={opts.get('llm_workers', '—')}）")
        else:
            lines.append("- KG+LLM：已跳过（--skip-llm）")

        lines.extend(
            [
                "",
                "## 对比实验结果",
                "",
                "| 模式 | 命中率 | 关键词召回 | 平均回答长度 | 耗时(s) |",
                "|------|--------|------------|--------------|---------|",
                f"| 纯知识图谱 (KG-only) | {kg['hit_rate']:.2%} | {kg['avg_keyword_recall']:.2%} | {kg['avg_response_length']} | {kg.get('elapsed_seconds', '—')} |",
            ]
        )
        if skip_llm:
            lines.append("| 图谱+大模型 (KG+LLM) | — | — | — | — |")
        else:
            lines.append(
                f"| 图谱+大模型 (KG+LLM) | {llm['hit_rate']:.2%} | {llm['avg_keyword_recall']:.2%} | {llm['avg_response_length']} | {llm.get('elapsed_seconds', '—')} |"
            )

        lines.extend(
            [
                "",
                "## 提升幅度",
                "",
                f"- 命中率提升：{imp['hit_rate_delta']:+.2%}",
                f"- 关键词召回提升：{imp['keyword_recall_delta']:+.2%}",
                "",
                "## 样例对比",
                "",
            ]
        )

        for d in report["details"][:5]:
            lines.extend(
                [
                    f"### {d['id']} {d['question']}",
                    f"- 期望：{d['expected']}",
                    f"- KG：{d['kg_answer']}",
                    f"- LLM：{d['llm_answer']}",
                    "",
                ]
            )

        return "\n".join(lines)
