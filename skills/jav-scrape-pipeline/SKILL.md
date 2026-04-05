---
name: jav-scrape-pipeline
description: 综合刮削流水线。对多个目录做“候选识别→metatube 搜索→候选精简展示→Agent 仅做 number/provider 优先级决策→脚本生成 provider 计划→执行抓取合并落盘→验证”。
---

# JAV 综合刮削 Skill

## 目标

对多个目录中的“未刮削大视频”执行全流程处理，并降低大模型逐字读 JSON 的不稳定风险：

1. preflight 扫描候选
2. scrape_query_provider 拉 metatube 搜索结果
3. **脚本提取精简候选字段并打印到 stdio**（仅供 Agent 决策）
4. Agent 主要决策两件事：
   - 每个目录的最终 `number`
   - provider priority 顺序
   - （可选）是否强制补充标签/类型（由 Agent 基于目录名/文件名语义判断）
5. provider_scrape_plan.py 根据 `scrape_query_*.json + decisions.json` 生成计划
6. execute_provider_scrape_plan 才执行抓取/合并/图片/NFO

---

## 精简候选字段（用于决策）

从 `search_results` 仅提取这几个字段：

- `id`
- `number`
- `provider`
- `title`（截前 30 字符）
- `actors`

Agent 不需要逐字通读整份 `search_results`。

---

## 推荐流程

### 1) preflight

```bash
.venv/bin/python active_skills/jav-scrape-pipeline/scripts/preflight_scan.py \
  --roots "/path/A,/path/B" \
  --video-extensions ".mp4,.mkv,.avi,.mov,.m2ts,.ts" \
  --min-size-mb 300 \
  --experience "memory/scrape_experience.toml" \
  --output "plans/"
```

输出：`plans/scrape_preflight_*.json`

### 2) scrape_query_provider（打印精简候选）

```bash
.venv/bin/python active_skills/jav-scrape-pipeline/scripts/scrape_query_provider.py \
  --preflight "plans/scrape_preflight_*.json" \
  --metatube "http://192.168.3.110:8090" \
  --token "123456" \
  --print-candidates \
  --output "plans/"
```

输出：`plans/scrape_query_*.json`

说明：
- 脚本仍保存完整 `search_results`
- 同时生成 `search_candidates`（精简字段）并可直接打印到终端

### Agent 决策风格（重要）

- 不依赖脚本规则判断“是否无码/中文字幕”，由 Agent 自主判断
- 决策依据应包含：`directory_name`、`main_video_names`、`raw`（来自 preflight）
- 当目录名或文件名包含 `-U`、`-C`、`uncensored`、`无码`、`中文`、`中字`、`CHS`、`C字幕` 等语义线索时，Agent 可主动在 decisions 中写入强制标签/类型
- 即使抓取源未返回这些标签，执行阶段也会按 decision 强制合并并写入 NFO

### 3) Agent 决策文件（decisions.json）

Agent 仅输出决策，不手写 provider_scrape_plan：

```json
{
  "items": [
    {
      "dir": "/path/to/dir",
      "number": "EBOD-968",
      "provider_priority": ["JavBus", "JAV321", "DUGA"],
      "uncensored": true,
      "force_tags": ["无码", "Uncensored"],
      "force_genres": ["无码"]
    }
  ]
}
```

说明：
- `uncensored=true` 会自动补充 `force_tags=["无码","Uncensored"]` 与 `force_genres=["无码"]`
- 也可只写 `force_tags/force_genres`（不写 `uncensored`）
- 这些强制标签会在执行阶段合并进 metadata，并写入 NFO（即便抓取源未返回）

### 4) provider_scrape_plan（脚本生成，带校验）

```bash
.venv/bin/python active_skills/jav-scrape-pipeline/scripts/provider_scrape_plan.py \
  --query-plan "plans/scrape_query_*.json" \
  --decisions "plans/decisions_*.json" \
  --output "plans/"
```

规则：
- `number` 优先用 decisions；缺失时回退 query-plan
- provider 必须来自该目录 `search_results` 的 provider 池
- decisions 未写全的 provider 会自动追加到末尾，避免漏抓
- `force_tags/force_genres/uncensored` 会透传到执行计划 `metadata_overrides`

输出：`plans/provider_scrape_plan_*.json`

### 5) execute_provider_scrape_plan

```bash
.venv/bin/python active_skills/jav-scrape-pipeline/scripts/execute_provider_scrape_plan.py \
  --plan "plans/provider_scrape_plan_*.json" \
  --metatube "http://192.168.3.110:8090" \
  --token "123456" \
  --rename-pattern "number2"
```

---

## 约束与边界

- `scrape_query_provider`：只查搜索，不做 metadata 合并
- `provider_scrape_plan`：只生成计划，不抓取
- `execute_provider_scrape_plan`：才进行抓取/合并/图片/NFO
- 计划文件统一放 `plans/`
- 多视频目录执行前自动联动 `video-renamer`

---

## 图片策略

- 当前执行器已支持 **metatube proxy 优先链路**（用于规避源站 403）
- 失败不回滚，写入 trace
- 文件名保持 clean 白名单：`poster/thumb/fanart/backdrop/fanart-xx`
