# jav-scrape-pipeline Skill

## 中文说明

### 依赖服务

本仓库仍基于 `metatube-sdk-go` 提供能力，该服务整合了大量刮削与图片下载功能。

- 关联仓库（remote）：`https://github.com/metatube-community/metatube-sdk-go.git`
- 本地路径：`/home/base/javmanager/repo/metatube-sdk-go`

### 技能定位

本技能将原本主要由 Jellyfin 调用的 metatube 服务，转变为可由 Agent 直接调用的自动化流程。

你只需提供一个模糊路径地址，后续流程（例如：识别番号、选择刮削策略、多结果处理与合并）都由 Agent 自动接管，无需人工干预。

### 工作流程能力

- 从模糊路径自动识别目标内容
- 自动判断番号与元数据来源
- 在多候选刮削结果中自动选择或合并
- 自动处理图片下载与元数据落地
- 输出智能合并后的最终刮削结果

---

## English

### Service Dependency

This repository still relies on `metatube-sdk-go`, which integrates large-scale scraping and artwork/image downloading capabilities.

- Upstream remote: `https://github.com/metatube-community/metatube-sdk-go.git`
- Local path: `/home/base/javmanager/repo/metatube-sdk-go`

### Skill Purpose

This skill turns the metatube service (originally consumed mainly by Jellyfin) into an Agent-driven workflow.

You only provide a fuzzy path input. The Agent then handles title/code identification, scraping strategy decisions, multi-candidate handling, and result merging automatically with no manual operation.

### Pipeline Capabilities

- Detect target media from fuzzy path inputs
- Identify code/metadata sources automatically
- Select and/or merge multiple scraping candidates
- Download images and materialize metadata automatically
- Produce an intelligently merged final scraping output

## Structure

```text
skills/
  jav-scrape-pipeline/
```
