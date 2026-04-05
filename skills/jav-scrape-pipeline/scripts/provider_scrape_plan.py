#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from datetime import datetime


def ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def normalize_decisions(decisions_raw: dict) -> dict[str, dict]:
    """
    统一为按 dir 索引:
    {
      "/path/dir": {
        "number": "EBOD-968",
        "provider_priority": ["JavBus", "JAV321"]
      }
    }
    """
    if "items" in decisions_raw and isinstance(decisions_raw["items"], list):
        out = {}
        for it in decisions_raw["items"]:
            d = it.get("dir")
            if not d:
                continue
            force_tags = it.get("force_tags") or it.get("tags") or []
            force_genres = it.get("force_genres") or it.get("genres") or []
            # 支持通过布尔开关快速补充无码语义标签
            if it.get("uncensored") is True:
                force_tags = list(force_tags) + ["无码", "Uncensored"]
                force_genres = list(force_genres) + ["无码"]
            out[d] = {
                "number": it.get("number") or it.get("query"),
                "provider_priority": it.get("provider_priority")
                or it.get("providers")
                or [],
                "force_tags": force_tags,
                "force_genres": force_genres,
            }
        return out
    return decisions_raw


def clean_str_list(values) -> list[str]:
    if not values:
        return []
    out = []
    seen = set()
    for v in values:
        s = str(v).strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def choose_number(item: dict, decision: dict | None) -> str | None:
    if decision and decision.get("number"):
        return decision["number"]
    return (
        item.get("approved_query")
        or item.get("query")
        or item.get("recommended_query")
        or (item.get("preflight") or {}).get("chosen_number")
    )


def provider_pool_from_search(item: dict) -> list[str]:
    seen = set()
    out = []
    for r in item.get("search_results", []) or []:
        p = r.get("provider")
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--query-plan", required=True, help="scrape_query_provider 输出文件"
    )
    ap.add_argument(
        "--decisions",
        required=True,
        help="Agent 决策文件(JSON): 指定每个dir的number与provider_priority",
    )
    ap.add_argument("--output", default="plans/")
    args = ap.parse_args()

    qp = json.loads(Path(args.query_plan).read_text(encoding="utf-8"))
    decisions_raw = json.loads(Path(args.decisions).read_text(encoding="utf-8"))
    decisions = normalize_decisions(decisions_raw)

    out = {"items": [], "skipped": [], "summary": {}}

    for item in qp.get("items", []):
        d = item.get("dir")
        dec = decisions.get(d)

        number = choose_number(item, dec)
        if not number:
            out["skipped"].append({"dir": d, "reason": "缺少number"})
            continue

        pool = provider_pool_from_search(item)
        if not pool:
            out["skipped"].append({"dir": d, "reason": "search_results 无 provider"})
            continue

        chosen_order = []
        if dec and dec.get("provider_priority"):
            # 允许 decisions 给 list[str] 或 list[{'provider':...}]
            for p in dec["provider_priority"]:
                name = p.get("provider") if isinstance(p, dict) else p
                if name in pool and name not in chosen_order:
                    chosen_order.append(name)

        # 决策里没写全，则把pool里剩余 provider 追加到末尾，防止漏抓
        for p in pool:
            if p not in chosen_order:
                chosen_order.append(p)

        providers = [
            {"provider": p, "priority": i + 1} for i, p in enumerate(chosen_order)
        ]
        force_tags = clean_str_list((dec or {}).get("force_tags"))
        force_genres = clean_str_list((dec or {}).get("force_genres"))

        out["items"].append(
            {
                "dir": d,
                "number": number,
                "providers": providers,
                "metadata_overrides": {
                    "force_tags": force_tags,
                    "force_genres": force_genres,
                },
                "videos": item.get("videos", []),
                "video_count": item.get("video_count", 0),
                "search_results_file": item.get("search_results_file"),
            }
        )

    out["summary"] = {"items": len(out["items"]), "skipped": len(out["skipped"])}

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    f = out_dir / f"provider_scrape_plan_{ts()}.json"
    f.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(f))
    print(json.dumps(out["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
