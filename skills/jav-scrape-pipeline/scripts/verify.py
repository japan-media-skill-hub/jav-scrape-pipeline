#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

VALID_IMAGE_KEYWORDS = ('poster', 'cover', 'fanart', 'backdrop', 'thumb', 'logo', 'clearart', 'banner', 'disc', 'keyart')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True, help='要验证的目录')
    ap.add_argument('--report', required=False, help='可选：执行结果json')
    args = ap.parse_args()

    d = Path(args.dir)
    result = {
        'dir': str(d),
        'ok': True,
        'checks': {},
        'issues': [],
    }

    nfos = list(d.glob('*.nfo'))
    result['checks']['nfo_count'] = len(nfos)
    if len(nfos) != 1:
        result['ok'] = False
        result['issues'].append(f'nfo数量异常: {len(nfos)}')

    imgs = [p.name.lower() for p in d.iterdir() if p.is_file() and p.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff'}]
    good_imgs = [x for x in imgs if any(k in x for k in VALID_IMAGE_KEYWORDS)]
    result['checks']['image_count'] = len(imgs)
    result['checks']['good_image_count'] = len(good_imgs)
    if not good_imgs:
        result['ok'] = False
        result['issues'].append('未找到clean白名单图片')

    if args.report:
        rp = Path(args.report)
        if rp.exists():
            data = json.loads(rp.read_text(encoding='utf-8'))
            result['checks']['report_done'] = len(data.get('done', []))
            result['checks']['report_failed'] = len(data.get('failed', []))

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
