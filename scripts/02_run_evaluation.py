"""运行问答系统对比评测并生成报告。"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import get_settings  # noqa: E402
from src.evaluation.evaluator import Evaluator  # noqa: E402
from src.kg.graph_client_factory import get_graph_db_display_name  # noqa: E402
from src.qa.kg_qa_engine import KGQAEngine  # noqa: E402
from src.qa.llm_qa_engine import LLMQAEngine  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="KG / KG+LLM 问答对比评测")
    p.add_argument(
        "--skip-llm",
        action="store_true",
        help="仅评测 KG-only（跳过 LLM API，秒级完成）",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=None,
        help="LLM 并发请求数（默认读取配置 eval_llm_workers）",
    )
    p.add_argument(
        "--no-fast-llm",
        action="store_true",
        help="关闭评测快速模式（更长上下文与回复，更慢）",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    test_path = ROOT / "data" / "evaluation" / "qa_test_set.json"
    output_dir = ROOT / "data" / "evaluation" / "reports"

    workers = args.workers if args.workers is not None else settings.eval_llm_workers
    fast_llm = settings.eval_llm_fast and not args.no_fast_llm

    kg_engine = KGQAEngine()
    llm_engine = LLMQAEngine(kg_engine)

    try:
        evaluator = Evaluator(test_path, graph_database=get_graph_db_display_name(settings))
        mode = settings.graph_mode
        print(f"开始评测（图谱: {mode}，题量: {len(evaluator.test_set)}）")
        if args.skip_llm:
            print("模式: 仅 KG-only（--skip-llm）")
        else:
            print(f"模式: KG-only + KG+LLM（并发 {workers}，fast_llm={fast_llm}）")
            if not settings.llm_enabled or not settings.llm_api_key:
                print("警告: LLM 未启用或未配置 API Key，KG+LLM 将回退为 KG-only 结果")

        t0 = time.perf_counter()
        report = evaluator.run_comparison(
            kg_engine,
            llm_engine,
            output_dir,
            skip_llm=args.skip_llm,
            llm_workers=workers,
            fast_llm=fast_llm,
        )
        total_elapsed = time.perf_counter() - t0

        kg = report["metrics"]["kg_only"]
        llm = report["metrics"]["kg_llm"]
        print("\n===== 评测完成 =====")
        print(f"总耗时: {total_elapsed:.1f}s")
        print(
            f"纯知识图谱  命中率: {kg['hit_rate']:.2%}  "
            f"关键词召回: {kg['avg_keyword_recall']:.2%}  "
            f"耗时: {kg.get('elapsed_seconds', '—')}s"
        )
        if not args.skip_llm:
            print(
                f"图谱+大模型  命中率: {llm['hit_rate']:.2%}  "
                f"关键词召回: {llm['avg_keyword_recall']:.2%}  "
                f"耗时: {llm.get('elapsed_seconds', '—')}s"
            )
        print("\n报告已保存:")
        print(f"  JSON: {report['report_paths']['json']}")
        print(f"  Markdown: {report['report_paths']['markdown']}")
    finally:
        llm_engine.close()


if __name__ == "__main__":
    main()
