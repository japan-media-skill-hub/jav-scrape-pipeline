#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil, subprocess, urllib.request, urllib.parse, os
from pathlib import Path
from datetime import datetime

VIDEO_EXTS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".wmv",
    ".mov",
    ".flv",
    ".rmvb",
    ".rm",
    ".3gp",
    ".m4v",
    ".m2ts",
    ".ts",
    ".mpg",
}
MIN_SIZE_MB = 300


def ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def debug_enabled() -> bool:
    return os.environ.get("JAV_SCRAPE_DEBUG", "0").lower() in ("1", "true", "yes", "on")


def debug_log(tag: str, obj):
    if not debug_enabled():
        return
    try:
        print(f"[DEBUG] {tag}: {json.dumps(obj, ensure_ascii=False, indent=2)}")
    except Exception:
        print(f"[DEBUG] {tag}: {obj}")


def api_get(base: str, token: str, path: str):
    req = urllib.request.Request(base.rstrip("/") + path)
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def dl(url: str, dst: Path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        dst.write_bytes(r.read())


def ext(url: str) -> str:
    u = url.lower()
    if ".png" in u:
        return ".png"
    if ".webp" in u:
        return ".webp"
    return ".jpg"


def cleanup_old_plans():
    py = r"""
import time
from pathlib import Path
p = Path("plans")
p.mkdir(exist_ok=True)
count = 0
for f in p.iterdir():
    if f.is_file() and time.time() - f.stat().st_mtime > 864000:
        f.unlink(); count += 1
print(f"清理完成: 删除 {count} 个旧计划文件")
"""
    subprocess.check_call([".venv/bin/python", "-c", py])


def list_big_videos(folder: Path) -> list[Path]:
    min_bytes = MIN_SIZE_MB * 1024 * 1024
    return sorted(
        [
            f
            for f in folder.iterdir()
            if f.is_file()
            and f.suffix.lower() in VIDEO_EXTS
            and f.stat().st_size >= min_bytes
        ],
        key=lambda x: x.name,
    )


def run_video_renamer_for_dir(folder: Path, pattern: str = "number2") -> dict:
    cleanup_old_plans()
    subprocess.check_call(
        [
            ".venv/bin/python",
            "active_skills/video-renamer/scripts/plan_rename.py",
            "--root",
            str(folder.parent),
            "--pattern",
            pattern,
            "--output",
            "plans/",
            "--min-size",
            str(MIN_SIZE_MB),
            "--extensions",
            ",".join(sorted(VIDEO_EXTS)),
        ]
    )

    plans = sorted(
        Path("plans").glob("rename_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not plans:
        return {"renamed": False, "reason": "未生成rename计划"}

    ops = json.loads(plans[0].read_text(encoding="utf-8"))
    target_ops = [op for op in ops if Path(op.get("source", "")).parent == folder]
    if not target_ops:
        return {"renamed": False, "reason": "当前目录无需重命名"}

    fp = Path("plans") / f"rename_{ts()}_only_{folder.name}.json"
    fp.write_text(
        json.dumps(target_ops, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    cleanup_old_plans()
    subprocess.check_call(
        [
            ".venv/bin/python",
            "active_skills/video-renamer/scripts/execute_plan.py",
            "--plan",
            str(fp),
        ]
    )
    return {"renamed": True, "plan": str(fp), "ops": len(target_ops)}


def ensure_single_nfo(folder: Path, keep_nfo: Path) -> list[dict]:
    moved = []
    delete_dir = folder / ".delete"
    delete_dir.mkdir(parents=True, exist_ok=True)
    for n in folder.glob("*.nfo"):
        if n.resolve() == keep_nfo.resolve():
            continue
        dst = delete_dir / n.name
        i = 1
        while dst.exists():
            dst = delete_dir / f"{n.stem}.{i}{n.suffix}"
            i += 1
        shutil.move(str(n), str(dst))
        moved.append({"from": str(n), "to": str(dst)})
    return moved


def merge_metadata(chain: list[dict]) -> tuple[dict, list[dict]]:
    merged, trace = {}, []
    list_fields = {"actors", "genres", "preview_images"}

    # 单值：按 provider 优先级先到先得
    for it in chain:
        p = it["provider"]
        md = it.get("metadata") or {}
        for k, v in md.items():
            if k in list_fields or v in (None, "", []):
                continue
            if k not in merged or merged[k] in (None, "", []):
                merged[k] = v
                trace.append({"field": k, "provider": p, "op": "set", "value": v})

    # 数组：并集
    for it in chain:
        p = it["provider"]
        md = it.get("metadata") or {}
        for k in list_fields:
            vals = md.get(k) or []
            if not vals:
                continue
            merged.setdefault(k, [])
            before = list(merged[k])
            for v in vals:
                if v not in merged[k]:
                    merged[k].append(v)
            if before != merged[k]:
                trace.append(
                    {"field": k, "provider": p, "op": "union", "value": merged[k]}
                )

    return merged, trace


def merge_forced_labels(
    merged: dict, trace: list[dict], overrides: dict | None
) -> dict:
    overrides = overrides or {}

    def clean_list(values) -> list[str]:
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

    force_tags = clean_list(overrides.get("force_tags"))
    force_genres = clean_list(overrides.get("force_genres"))
    if not force_tags and not force_genres:
        return {"force_tags": [], "force_genres": []}

    merged.setdefault("tags", [])
    merged.setdefault("genres", [])
    merged["tags"] = clean_list(merged.get("tags"))
    merged["genres"] = clean_list(merged.get("genres"))

    for tag in force_tags:
        if tag not in merged["tags"]:
            merged["tags"].append(tag)
            trace.append(
                {"field": "tags", "provider": "decision", "op": "append", "value": tag}
            )

    for genre in force_genres:
        if genre not in merged["genres"]:
            merged["genres"].append(genre)
            trace.append(
                {
                    "field": "genres",
                    "provider": "decision",
                    "op": "append",
                    "value": genre,
                }
            )

    return {"force_tags": force_tags, "force_genres": force_genres}


def download_images(
    folder: Path,
    merged: dict,
    trace: list[dict],
    metatube_base: str,
    verbose: bool = False,
) -> tuple[list[str], list[dict], list[dict]]:
    saved = []
    attempted = []
    failed = []

    cover = merged.get("big_cover_url") or merged.get("cover_url")
    thumb = merged.get("big_thumb_url") or merged.get("thumb_url")
    previews = merged.get("preview_images") or []

    def metatube_proxy(url: str, role: str):
        provider = merged.get("provider") or "JavBus"
        number = merged.get("number") or merged.get("id") or ""
        if not provider or not number:
            return None
        q = urllib.parse.urlencode(
            {"url": url, "ratio": "-1", "pos": "1", "auto": "True", "quality": "100"}
        )
        full = f"{metatube_base}/v1/images/primary/{urllib.parse.quote(str(provider), safe='')}/{urllib.parse.quote(str(number), safe='')}?{q}"
        if verbose:
            print(f"[METATUBE_IMAGE] role={role} url={full}")
        return full

    tasks = []
    if cover:
        tasks.append(
            {"role": "poster", "url": cover, "file": folder / f"poster{ext(cover)}"}
        )
    if thumb:
        tasks.append(
            {"role": "thumb", "url": thumb, "file": folder / f"thumb{ext(thumb)}"}
        )
    if previews:
        first = previews[0]
        tasks.append(
            {"role": "fanart", "url": first, "file": folder / f"fanart{ext(first)}"}
        )
        tasks.append(
            {"role": "backdrop", "url": first, "file": folder / f"backdrop{ext(first)}"}
        )
        for i, u in enumerate(previews, 1):
            tasks.append(
                {
                    "role": f"fanart-{i:02d}",
                    "url": u,
                    "file": folder / f"fanart-{i:02d}{ext(u)}",
                }
            )

    for t in tasks:
        attempted.append({"role": t["role"], "url": t["url"], "file": str(t["file"])})
        try:
            proxy_url = metatube_proxy(t["url"], t["role"])
            if not proxy_url:
                raise RuntimeError("metatube proxy unavailable")
            trace.append(
                {
                    "image": t["role"],
                    "source": t["url"],
                    "proxy": proxy_url,
                    "file": str(t["file"]),
                    "status": "proxy_try",
                }
            )
            if verbose:
                print(f"[IMG_PROXY_TRY] role={t['role']} proxy={proxy_url}")
            dl(proxy_url, t["file"])
            saved.append(str(t["file"]))
            trace.append(
                {
                    "image": t["role"],
                    "source": t["url"],
                    "proxy": proxy_url,
                    "file": str(t["file"]),
                    "status": "ok",
                }
            )
            if verbose:
                print(
                    f"[IMG_PROXY_OK] role={t['role']} proxy={proxy_url} file={t['file']}"
                )
        except Exception as e:
            failed.append(
                {
                    "role": t["role"],
                    "url": t["url"],
                    "file": str(t["file"]),
                    "error": str(e),
                }
            )
            trace.append(
                {
                    "image": t["role"],
                    "source": t["url"],
                    "file": str(t["file"]),
                    "status": "failed",
                    "error": str(e),
                }
            )

    if previews:
        try:
            first_preview = folder / f"fanart{ext(previews[0])}"
            if first_preview.exists():
                poster_fallback = folder / f"poster{first_preview.suffix}"
                thumb_fallback = folder / f"thumb{first_preview.suffix}"
                if not poster_fallback.exists():
                    shutil.copyfile(first_preview, poster_fallback)
                    saved.append(str(poster_fallback))
                    trace.append(
                        {
                            "image": "poster",
                            "source": str(first_preview),
                            "file": str(poster_fallback),
                            "status": "fallback_from_preview",
                        }
                    )
                if not thumb_fallback.exists():
                    shutil.copyfile(first_preview, thumb_fallback)
                    saved.append(str(thumb_fallback))
                    trace.append(
                        {
                            "image": "thumb",
                            "source": str(first_preview),
                            "file": str(thumb_fallback),
                            "status": "fallback_from_preview",
                        }
                    )
        except Exception as e:
            failed.append(
                {
                    "role": "fallback_from_preview",
                    "url": "(local)",
                    "file": str(folder),
                    "error": str(e),
                }
            )

    return saved, attempted, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, help="provider_scrape_plan_*.json")
    ap.add_argument("--metatube", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--rename-pattern", default="number2")
    args = ap.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    result = {"done": [], "failed": []}
    trace_all = {"items": []}

    for it in plan.get("items", []):
        d = Path(it["dir"])
        try:
            d.mkdir(parents=True, exist_ok=True)
            number = it["number"]
            providers = sorted(
                it.get("providers", []), key=lambda x: int(x.get("priority", 9999))
            )

            videos = list_big_videos(d)
            rename_info = {"renamed": False, "reason": "single video or not needed"}
            if len(videos) > 1 and not all("-cd" in v.stem.lower() for v in videos):
                rename_info = run_video_renamer_for_dir(d, pattern=args.rename_pattern)
                videos = list_big_videos(d)

            provider_chain = []
            fetch_errors = []
            debug_log(
                "item_start",
                {"dir": str(d), "number": number, "providers_plan": providers},
            )
            for pv in providers:
                provider = pv["provider"]
                pri = int(pv.get("priority", 9999))
                try:
                    prov = urllib.parse.quote(provider, safe="")
                    pid = urllib.parse.quote(number, safe="")
                    data = api_get(
                        args.metatube, args.token, f"/v1/movies/{prov}/{pid}"
                    )
                    md = data.get("data") or {}
                    if md:
                        provider_chain.append(
                            {"provider": provider, "priority": pri, "metadata": md}
                        )
                        debug_log(
                            "metatube_fetch_ok",
                            {
                                "provider": provider,
                                "priority": pri,
                                "metadata_keys": list(md.keys()),
                                "metadata_sample": {
                                    k: md.get(k) for k in list(md.keys())[:20]
                                },
                            },
                        )
                    else:
                        fetch_errors.append(
                            {"provider": provider, "error": "empty metadata"}
                        )
                        debug_log(
                            "metatube_fetch_empty",
                            {"provider": provider, "priority": pri},
                        )
                except Exception as e:
                    fetch_errors.append({"provider": provider, "error": str(e)})
                    debug_log(
                        "metatube_fetch_error",
                        {"provider": provider, "priority": pri, "error": str(e)},
                    )

            if not provider_chain:
                raise RuntimeError(f"全部provider抓取失败: {fetch_errors}")

            merged, merge_trace = merge_metadata(provider_chain)
            debug_log(
                "merged_after_merge_metadata",
                {"keys": list(merged.keys()), "merged": merged, "trace": merge_trace},
            )

            # 兼容 metatube 返回的字段别名，避免 NFO 只剩空壳
            alias_fields = {
                "title": ["title"],
                "summary": ["summary", "plot"],
                "director": ["director"],
                "runtime": ["runtime"],
                "homepage": ["homepage"],
                "provider": ["provider"],
                "id": ["id"],
                "number": ["number", "num"],
                "release_date": ["release_date", "releasedate"],
                "score": ["score", "rating"],
                "maker": ["maker", "studio"],
                "label": ["label"],
                "thumb_url": ["thumb_url", "thumb"],
                "big_thumb_url": ["big_thumb_url", "bigthumb_url"],
                "cover_url": ["cover_url", "poster_url"],
                "big_cover_url": ["big_cover_url", "bigcover_url"],
                "preview_images": ["preview_images", "previews", "images"],
            }
            debug_log("before_alias_fields", {"merged": merged})
            for dst, srcs in alias_fields.items():
                if merged.get(dst) not in (None, "", [], {}):
                    continue
                for src in srcs:
                    val = None
                    for pc in provider_chain:
                        md = pc.get("metadata") or {}
                        if md.get(src) not in (None, "", []):
                            val = md.get(src)
                            break
                    if val not in (None, "", []):
                        merged[dst] = val
                        merge_trace.append(
                            {
                                "field": dst,
                                "op": "alias_fill",
                                "source_field": src,
                                "value": val,
                            }
                        )
                        debug_log("alias_fill", {"dst": dst, "src": src, "value": val})
                        break

            debug_log("after_alias_fields", {"merged": merged, "trace": merge_trace})

            # provider_chain 中的 preview_images 可能是字符串，也可能是数组，统一展开
            merged.setdefault("preview_images", [])
            if isinstance(merged["preview_images"], str):
                s = merged["preview_images"].strip()
                merged["preview_images"] = (
                    [x.strip() for x in s[1:-1].split(",") if x.strip()]
                    if s.startswith("{") and s.endswith("}")
                    else ([s] if s else [])
                )
            for pc in provider_chain:
                md = pc.get("metadata") or {}
                vals = md.get("preview_images") or []
                if isinstance(vals, str):
                    s = vals.strip()
                    vals = (
                        [x.strip() for x in s[1:-1].split(",") if x.strip()]
                        if s.startswith("{") and s.endswith("}")
                        else ([s] if s else [])
                    )
                for u in vals:
                    if u not in merged["preview_images"]:
                        merged["preview_images"].append(u)
                        merge_trace.append(
                            {
                                "field": "preview_images",
                                "provider": pc["provider"],
                                "op": "image_union_append",
                                "value": u,
                            }
                        )

            metadata_overrides = it.get("metadata_overrides") or {}
            forced_labels = merge_forced_labels(merged, merge_trace, metadata_overrides)

            # 让 create_nfo 同时拿到合并结果、轨迹和 provider_chain
            packed_meta = {
                "merged": merged,
                "trace": merge_trace,
                "provider_chain": provider_chain,
            }
            saved_images, image_attempts, image_failures = download_images(
                d, merged, merge_trace, args.metatube, verbose=debug_enabled()
            )

            if videos:
                main_video = sorted(
                    videos, key=lambda x: x.stat().st_size, reverse=True
                )[0]
                nfo = main_video.with_suffix(".nfo")
            else:
                nfo = d / "movie.nfo"

            merged_file = d / ".metatube.merged.json"
            merged_file.write_text(
                json.dumps(packed_meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            debug_log(
                "merged_file_written",
                json.loads(merged_file.read_text(encoding="utf-8")),
            )

            subprocess.check_call(
                [
                    ".venv/bin/python",
                    "active_skills/nfo-translator/scripts/create_nfo.py",
                    "--metadata-json",
                    str(merged_file),
                    "--output-nfo",
                    str(nfo),
                ]
            )

            moved = ensure_single_nfo(d, nfo)

            trace_all["items"].append(
                {
                    "dir": str(d),
                    "number": number,
                    "providers_plan": providers,
                    "provider_chain_fetched": provider_chain,
                    "packed_meta_keys": list(packed_meta.keys()),
                    "fetch_errors": fetch_errors,
                    "metadata_overrides": metadata_overrides,
                    "forced_labels": forced_labels,
                    "merge_trace": merge_trace,
                    "images": saved_images,
                    "image_attempts": image_attempts,
                    "image_failures": image_failures,
                    "nfo": str(nfo),
                }
            )

            result["done"].append(
                {
                    "dir": str(d),
                    "number": number,
                    "rename": rename_info,
                    "nfo": str(nfo),
                    "moved_old_nfos": moved,
                    "images": saved_images,
                    "image_attempts": image_attempts,
                    "image_failures": image_failures,
                    "fetch_errors": fetch_errors,
                    "metadata_overrides": metadata_overrides,
                    "forced_labels": forced_labels,
                    "merged_file": str(merged_file),
                }
            )
        except Exception as e:
            result["failed"].append(
                {"dir": str(d), "number": it.get("number"), "error": str(e)}
            )

    plan_path = Path(args.plan)
    trace_file = plan_path.with_name(
        f"execute_provider_scrape_plan_traceable_result_{ts()}.json"
    )
    result_file = plan_path.with_name(
        f"execute_provider_scrape_plan_{ts()}.result.json"
    )
    trace_file.write_text(
        json.dumps(trace_all, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    result_file.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(str(trace_file))
    print(str(result_file))
    print(
        json.dumps(
            {"done": len(result["done"]), "failed": len(result["failed"])},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
