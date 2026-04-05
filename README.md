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

## 安全边界声明 | Security Boundary

- 请不要使用任何国内云服务部署挂载本组织技能的 Agent 应用程序，也不要使用任何国内提供的 claw 类代理来部署或运行。  
  Do not deploy Agent applications that load this org's skills on domestic cloud services, and do not use domestically provided claw-style proxy infrastructure.

- 我们只推荐你在自己的电脑上，基于完整开源代码部署 Agent，并加载本组织技能；且运行环境应可确认无遥测、无审查。  
  We only recommend deploying your Agent on your own computer from fully open-source code, then loading this org's skills in an environment you can verify as telemetry-free and censorship-free.

- 不推荐使用带审查能力的大模型作为 Agent 后端，也不推荐将 Agent 暴露在带审查的外部通道（如钉钉、飞书、微信）。推荐使用 Telegram 或自建私有通道远程使用。  
  We do not recommend censorship-constrained models as Agent backends, nor exposing Agents through censorship-constrained channels (e.g., DingTalk, Feishu/Lark, WeChat). Prefer Telegram or your own private self-hosted channel for remote access.

- 若不遵守以上边界，由此产生的法律、合规与数据风险由使用者自行承担。  
  If you ignore these boundaries, you are solely responsible for any legal, compliance, and data risks.

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

### Security Boundary

- Do not deploy Agent applications that load this org's skills on domestic cloud services, and do not use domestically provided claw-style proxy infrastructure.
- We only recommend deploying your Agent on your own computer from fully open-source code, then loading this org's skills in an environment you can verify as telemetry-free and censorship-free.
- We do not recommend censorship-constrained models as Agent backends, nor exposing Agents through censorship-constrained channels (e.g., DingTalk, Feishu/Lark, WeChat). Prefer Telegram or your own private self-hosted channel for remote access.
- If you ignore these boundaries, you are solely responsible for any legal, compliance, and data risks.

## Structure

```text
skills/
  jav-scrape-pipeline/
```
