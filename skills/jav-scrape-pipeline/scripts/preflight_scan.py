#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from datetime import datetime


def load_toml_like(path: Path) -> dict:
    m = {}
    if not path.exists():
        return m
    in_norm = False
    for raw in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        s = raw.strip()
        if not s or s.startswith('#'):
            continue
        if s.startswith('['):
            in_norm = s.lower() == '[normalize]'
            continue
        if in_norm and '=' in s:
            k, v = s.split('=', 1)
            k = k.strip().strip('"').strip("'").lower()
            v = v.strip().strip('"').strip("'").upper()
            if k and v:
                m[k] = v
    return m


def ts():
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def norm_key(s: str) -> str:
    return re.sub(r'\s+', '', s).lower()


def extract_candidates(text: str) -> list[str]:
    t = text.upper()
    out = []
    # 标准：字母>=2 + 数字>=3
    out += re.findall(r'\b([A-Z]{2,8}-\d{3,6})\b', t)
    out += [x.replace('_', '-') for x in re.findall(r'\b([A-Z]{2,8}_\d{3,6})\b', t)]
    # 非标准：ABC00123 / ABC123 -> ABC-123
    for p, n in re.findall(r'\b([A-Z]{2,8})(\d{3,6})\b', t):
        out.append(f'{p}-{int(n)}')
    # 兼容少量 2 位数字（低优先）
    for p, n in re.findall(r'\b([A-Z]{2,8})[-_ ]?(\d{2})\b', t):
        out.append(f'{p}-{int(n)}')
    seen = set(); ans = []
    for x in out:
        if x not in seen:
            seen.add(x); ans.append(x)
    return ans


def score_candidate(raw_name: str, candidate: str, all_candidates: list[str], source: str) -> tuple[float, list[str]]:
    reasons = []
    score = 0.0
    m = re.match(r'^([A-Z]{2,8})-(\d{2,6})$', candidate)
    if not m:
        return 0.0, ['格式无效']

    prefix, num = m.group(1), m.group(2)

    # 结构判定：字母+数字，不依赖固定前缀白名单
    score += 35
    reasons.append('字母+数字结构成立')

    if len(prefix) >= 3:
        score += 12
        reasons.append('英文连续>2')
    else:
        score += 4
        reasons.append('英文连续=2(可疑但可用)')

    if len(num) >= 3:
        score += 20
        reasons.append('数字连续>=3')
    else:
        score += 6
        reasons.append('数字连续=2')

    if source == 'experience':
        score += 25
        reasons.append('经验集命中')
    elif source == 'dir':
        score += 15
        reasons.append('目录名命中')
    else:
        score += 5
        reasons.append('文件名命中')

    noise = len(re.findall(r'[@#\[\]\(\)]', raw_name))
    if noise == 0:
        score += 8
        reasons.append('噪声低')
    elif noise <= 3:
        score += 3
        reasons.append('噪声中')
    else:
        score -= 8
        reasons.append('噪声高')

    if len(all_candidates) == 1:
        score += 8
        reasons.append('候选唯一')
    else:
        score -= min(10, (len(all_candidates) - 1) * 3)
        reasons.append(f'候选冲突{len(all_candidates)}')

    return max(0.0, min(100.0, score)), reasons


def process_one_dir(d: Path, exts: set[str], min_size: int, ex: dict) -> dict | None:
    vids = [f for f in d.iterdir() if f.is_file() and f.suffix.lower() in exts and f.stat().st_size >= min_size]
    if not vids:
        return None

    if list(d.glob('*.nfo')):
        return None

    raw = f"{d.name} {' '.join(v.stem for v in vids)}"
    key = norm_key(raw)

    candidates = []
    candidate_sources = {}

    for ek, ev in ex.items():
        if ek in key:
            candidates.append(ev)
            candidate_sources[ev] = 'experience'

    for c in extract_candidates(d.name):
        candidates.append(c)
        candidate_sources.setdefault(c, 'dir')

    for c in extract_candidates(raw):
        candidates.append(c)
        candidate_sources.setdefault(c, 'raw')

    seen = set(); cands = []
    for c in candidates:
        c = c.upper()
        if c not in seen:
            seen.add(c); cands.append(c)

    if not cands:
        return {
            'dir': str(d),
            'videos': [str(v) for v in vids],
            'video_count': len(vids),
            'raw': raw,
            'candidates': [],
            'recommended_query': None,
            'confidence': 0.0,
            'reasons': ['未提取到番号'],
            'action': 'skip',
        }

    scored = []
    for c in cands:
        s, rs = score_candidate(raw, c, cands, candidate_sources.get(c, 'raw'))
        scored.append((s, c, rs, candidate_sources.get(c, 'raw')))
    scored.sort(key=lambda x: x[0], reverse=True)
    score, best, reasons, src = scored[0]

    # 给 Agent 的候选材料：目录名、主视频名、经验命中、推荐词
    video_names = [v.stem for v in vids]
    rec = {
        'dir': str(d),
        'videos': [str(v) for v in vids],
        'video_count': len(vids),
        'raw': raw,
        'directory_name': d.name,
        'main_video_names': video_names,
        'candidates': cands,
        'candidate_sources': candidate_sources,
        'chosen_number': best,
        'chosen_source': src,
        'recommended_query': best,
        'confidence': score,
        'reasons': reasons,
        'action': 'proceed' if score >= 55 else 'skip',
    }
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--roots', required=True, help='逗号分隔目录；通常传一组目录，少数情况只传一个')
    ap.add_argument('--video-extensions', default='.mp4,.mkv,.avi,.mov,.m2ts,.ts')
    ap.add_argument('--min-size-mb', type=int, default=300)
    ap.add_argument('--experience', default='memory/scrape_experience.toml')
    ap.add_argument('--output', default='plans/')
    args = ap.parse_args()

    ex = load_toml_like(Path(args.experience))
    exts = {x.strip().lower() for x in args.video_extensions.split(',') if x.strip()}
    min_size = args.min_size_mb * 1024 * 1024

    tasks, skipped = [], []

    for root in [Path(x.strip()) for x in args.roots.split(',') if x.strip()]:
        if not root.exists():
            skipped.append({'root': str(root), 'reason': '路径不存在'})
            continue

        # 一组目录：root 自身 + 子目录；单目录场景也兼容
        dirs = [root] + [p for p in root.rglob('*') if p.is_dir()]
        for d in dirs:
            rec = process_one_dir(d, exts, min_size, ex)
            if not rec:
                continue
            if rec['action'] == 'proceed':
                tasks.append(rec)
            else:
                skipped.append({'dir': str(d), 'reason': f"低置信度({rec['confidence']})", 'detail': rec})

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'scrape_preflight_{ts()}.json'
    payload = {'tasks': tasks, 'skipped': skipped, 'summary': {'tasks': len(tasks), 'skipped': len(skipped)}}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out))
    print(json.dumps(payload['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
