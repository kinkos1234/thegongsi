#!/usr/bin/env python3
"""Benchmark runner — queries.yml 전체 실행 → recall/precision 계산.

사용법:
    python bench/runner.py
    python bench/runner.py --category supply_chain
    python bench/runner.py --skip-dynamic

결과: bench_results/YYYY-MM-DD-HHmm.json
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(ROOT / "backend" / ".env")


def _recall_precision(expected: list[str], returned: list[str]) -> tuple[float, float]:
    if not expected:
        return 0.0, 0.0
    exp_set, ret_set = set(expected), set(returned)
    true_pos = len(exp_set & ret_set)
    recall = true_pos / len(exp_set) if exp_set else 0.0
    precision = true_pos / len(ret_set) if ret_set else 0.0
    return recall, precision


async def run_query(q: dict) -> dict:
    """Q&A 엔드포인트 동일 경로로 실행."""
    from app.services.graph.qa import ask
    result = await ask(q["question"])

    # rows에서 ticker/person 추출.
    # Neo4j는 flat dict 반환 ({'p.name_ko': ..., 'c.ticker': ...}).
    # 키 이름으로 분류: ticker/corp_code 포함 → ticker, name_ko/person 포함 → person.
    returned_tickers = []
    returned_persons = []
    for row in result.get("rows", []):
        for k, v in row.items():
            lk = k.lower()
            if v is None:
                continue
            # nested dict 대응
            if isinstance(v, dict):
                if v.get("ticker"):
                    returned_tickers.append(str(v["ticker"]))
                if v.get("name_ko") and "person" in lk:
                    returned_persons.append(str(v["name_ko"]))
                continue
            # flat value
            sval = str(v)
            if ("ticker" in lk or lk.endswith("_ticker")) and sval.isdigit():
                returned_tickers.append(sval)
            elif "person" in lk or "leader" in lk or "name" == lk or lk.startswith("p."):
                # p.name_ko → person
                if "name" in lk or lk.endswith(".name_ko") or lk == "person":
                    returned_persons.append(sval)
            elif "company" in lk or "c.name_ko" in lk:
                # company name — 회사 기대값과도 문자열 매칭용으로 ticker가 아니면 패스
                pass

    # 보조: name_ko를 기대 ticker로 매핑하기 위해 answer 문자열에서 이름 매칭
    # (governance 질문은 ticker가 아니라 회사명으로 반환되는 경우 많음)
    answer_text = (result.get("answer") or "") + " ".join(
        str(v) for row in result.get("rows", []) for v in row.values()
    )

    exp = q.get("expected", {})
    expected_tickers = exp.get("tickers", [])
    expected_persons = exp.get("persons", [])

    # ticker가 answer/rows 문자열 내에 포함되어도 매칭으로 인정 (lenient)
    for t in expected_tickers:
        if t in answer_text and t not in returned_tickers:
            returned_tickers.append(t)
    for p in expected_persons:
        if p in answer_text and p not in returned_persons:
            returned_persons.append(p)

    r_t, p_t = _recall_precision(expected_tickers, returned_tickers)
    r_p, p_p = _recall_precision(expected_persons, returned_persons)

    is_person = bool(expected_persons)
    recall, precision = (r_p, p_p) if is_person else (r_t, p_t)

    min_r = q.get("min_recall", 0.0)
    min_p = q.get("min_precision", 0.0)
    passed = recall >= min_r and precision >= min_p

    return {
        "id": q["id"],
        "category": q["category"],
        "recall": round(recall, 2),
        "precision": round(precision, 2),
        "min_recall": min_r,
        "min_precision": min_p,
        "passed": passed,
        "cypher": result.get("cypher", ""),
    }


async def main():
    import yaml
    with open(ROOT / "bench" / "queries.yml") as f:
        spec = yaml.safe_load(f)

    skip_dynamic = "--skip-dynamic" in sys.argv
    category_filter = None
    if "--category" in sys.argv:
        category_filter = sys.argv[sys.argv.index("--category") + 1]

    today = datetime.now().date().isoformat()
    results = []
    for q in spec["queries"]:
        if q.get("skip_until") and today < q["skip_until"]:
            continue
        if skip_dynamic and q.get("dynamic"):
            continue
        if category_filter and q["category"] != category_filter:
            continue
        try:
            r = await run_query(q)
        except Exception as e:
            r = {"id": q["id"], "error": str(e), "passed": False}
        results.append(r)
        mark = "✓" if r.get("passed") else "✗"
        print(f"{mark} {r['id']:30s} r={r.get('recall', '-'):<4} p={r.get('precision', '-'):<4}")

    pass_rate = sum(1 for r in results if r.get("passed")) / len(results) if results else 0
    out = {
        "timestamp": datetime.utcnow().isoformat(),
        "total": len(results),
        "passed": sum(1 for r in results if r.get("passed")),
        "pass_rate": round(pass_rate, 3),
        "avg_recall": round(sum(r.get("recall", 0) for r in results) / len(results) if results else 0, 3),
        "avg_precision": round(sum(r.get("precision", 0) for r in results) / len(results) if results else 0, 3),
        "results": results,
    }

    results_dir = ROOT / "bench_results"
    results_dir.mkdir(exist_ok=True)
    out_path = results_dir / f"{datetime.now().strftime('%Y-%m-%d-%H%M')}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\n총 {out['passed']}/{out['total']} pass ({out['pass_rate']*100:.0f}%), "
          f"recall={out['avg_recall']}, precision={out['avg_precision']}")
    print(f"→ {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
