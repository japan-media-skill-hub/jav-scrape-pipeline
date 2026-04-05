#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime


def ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def api_get(base: str, token: str, path: str):
    req = urllib.request.Request(base.rstrip("/") + path)
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def short_title(s: str, n: int = 30) -> str:
    s = (s or "").strip().replace("\n", " ")
    return s[:n]


def to_candidate_view(rs: list[dict]) -> list[dict]:
    out = []
    for i, r in enumerate(rs, 1):
        out.append(
            {
                "idx": i,
                "id": r.get("id"),
                "number": r.get("number"),
                "provider": r.get("provider"),
                "title30": short_title(r.get("title", ""), 30),
                "actors": r.get("actors") or [],
            }
        )
    return out


def print_candidates_stdio(dir_path: str, query: str, candidates: list[dict]):
    print(f"\n=== DIR: {dir_path}")
    print(f"QUERY: {query}")
    if not candidates:
        print("(no search results)")
        return
    for c in candidates:
        print(
            f"[{c['idx']:02d}] provider={c.get('provider')} | number={c.get('number')} | "
            f"id={c.get('id')} | title30={c.get('title30')} | actors={','.join(c.get('actors') or [])}"
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preflight", required=True)
    ap.add_argument("--metatube", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--output", default="plans/")
    ap.add_argument(
        "--print-candidates",
        action="store_true",
        help="将精简候选打印到标准输出，供 Agent 决策",
    )
    args = ap.parse_args()

    pre = json.loads(Path(args.preflight).read_text(encoding="utf-8"))
    plan = {"items": [], "skipped": [], "summary": {}}

    for t in pre.get("tasks", []):
        # query 由 Agent 最终确认后写入 approved_query；否则回退 recommended_query
        query = (
            t.get("approved_query")
            or t.get("recommended_query")
            or t.get("chosen_number")
        )
        if not query:
            plan["skipped"].append({"dir": t.get("dir"), "reason": "缺少query"})
            continue

        q = urllib.parse.quote(query)
        try:
            s = api_get(args.metatube, args.token, f"/v1/movies/search?q={q}")
            rs = s.get("data") or []
            candidates = to_candidate_view(rs)

            # 将 search 结果原样落盘，供后续脚本做校验；同时保存精简候选
            search_file = None
            if rs:
                search_file = Path(t["dir"]) / "search.json"
                search_file.write_text(
                    json.dumps(rs, ensure_ascii=False, indent=2), encoding="utf-8"
                )

            if args.print_candidates:
                print_candidates_stdio(t["dir"], query, candidates)

            plan["items"].append(
                {
                    "dir": t["dir"],
                    "videos": t.get("videos", []),
                    "video_count": t.get("video_count", 0),
                    "query": query,
                    "recommended_query": t.get("recommended_query"),
                    "approved_query": t.get("approved_query"),
                    "search_results_file": str(search_file) if search_file else None,
                    "search_results": rs,
                    "search_candidates": candidates,
                    "preflight": t,
                    "trace": [
                        {
                            "stage": "preflight",
                            "query_source": "approved_query"
                            if t.get("approved_query")
                            else "recommended_query",
                        }
                    ],
                }
            )
        except Exception as e:
            plan["skipped"].append(
                {"dir": t.get("dir"), "reason": f"API失败: {e}", "query": query}
            )

    plan["summary"] = {"items": len(plan["items"]), "skipped": len(plan["skipped"])}
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"scrape_query_{ts()}.json"
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out))
    print(json.dumps(plan["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
