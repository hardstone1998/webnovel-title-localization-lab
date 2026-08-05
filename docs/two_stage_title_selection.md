# 两阶段英文剧名生成与选优

## 功能概览

该工作流读取一条中文网文记录，依次完成：

1. 生成 12 个英文候选剧名：
   - `source_title`：根据中文原始剧名生成 4 个；
   - `synopsis`：根据故事简介生成 4 个；
   - `market_localized`：结合全部上下文，按英语网文市场习惯生成 4 个。
2. 对冻结的 12 个候选执行八维评分、加权复算、严重违规排除和确定性排名。
3. 输出候选集 JSON、排名结果 JSON 和可阅读的 Markdown 报告。

生成和排名使用两个独立制品。更换评分方法时，可以直接复用候选集，不必重新生成剧名。

## 输入要求

输入文件是 UTF-8 JSON 对象，必须包含：

| 字段 | 含义 |
| --- | --- |
| `sample_id` | 稳定的样本标识符 |
| `source_title` | 非空中文原始剧名 |
| `source_language` | `zh` 或以 `zh` 开头的语言代码 |
| `target_language` | `en` 或以 `en` 开头的语言代码 |
| `genre` | 作品类型 |
| `genre_zh` | 原始中文作品类型；生成与评分阶段均传给模型 |
| `synopsis` | 非空故事简介 |

可直接使用公开合成示例：`data/examples/sample_title_case.json`。

## 运行方式

安装开发环境：

```powershell
uv sync --extra dev
```

使用不联网的确定性适配器：

```powershell
title-localization `
  --input data/examples/sample_title_case.json `
  --config configs/title_selection.default.json `
  --output-dir artifacts/example-run `
  --adapter deterministic
```

也可以不依赖控制台入口：

```powershell
python -m app `
  --input data/examples/sample_title_case.json `
  --config configs/title_selection.default.json `
  --output-dir artifacts/example-run
```

## FastAPI 调用方式

安装依赖后，可在项目根目录启动同步 API 服务：

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

服务提供 `GET /healthz`、`GET /readyz`、`GET /docs` 和 `POST /v1/title-localizations`。
请求中的 `source` 必须包含本节输入要求的全部字段，包括 `genre_zh`；该字段会同时传递给生成与评分阶段的模型提示。`config_profile` 仅支持 `default` 或 `deepseek`，API 固定使用服务端受控的 `openai-compatible` 模型，不能传入 `adapter`。至少一个受控 profile 配置了有效模型和凭证时，`/readyz` 才返回就绪；该检查不会调用远端模型。

```powershell
$body = @{
  source = @{
    sample_id = "api_example_001"
    source_title = "开局觉醒神级签到系统"
    source_language = "zh"
    target_language = "en"
    genre = "system_fantasy"
    genre_zh = "系统玄幻"
    synopsis = "A cultivator gains a check-in system after being expelled from his sect."
  }
  config_profile = "default"
} | ConvertTo-Json -Depth 4

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/v1/title-localizations `
  -ContentType "application/json" `
  -Body $body
```

该接口会同步等待真实模型完成，不创建 API 专用制品目录。成功时仅返回最终选择、应用程序复算的权威总分和其余候选剧名：

```json
{
  "selected": {
    "candidate_id": "cand_...",
    "title": "Every Check-In Makes Me Stronger",
    "score": 87.5
  },
  "unselected_titles": ["...", "..."]
}
```

响应不再包含 `candidate_set`、`ranking_result` 或 Markdown `report`。模型配置、凭证或上游调用不可用时，接口返回 HTTP 502 的结构化错误而不输出兜底候选或评分；若全部候选都不合格，则返回 `NO_ELIGIBLE_WINNER` 的 HTTP 422 错误。每次生成、评分和最终选择都会输出含 `X-Request-ID` 的 INFO 日志摘要；日志不会写入 API Key、Authorization header、完整提示词、简介或评分理由。首版没有认证、限流、批量任务或持久化结果；请仅在受信网络或受保护的部署环境中使用。

## 八个评分维度

每个维度使用 1–10 整数分。默认权重如下：

| 维度 | 权重 | 评估内容 |
| --- | ---: | --- |
| `semantic_fidelity` | 20 | 与源内容和故事前提是否一致 |
| `natural_english` | 15 | 英文表达是否自然 |
| `genre_tone_fit` | 10 | 是否正确体现类型和基调 |
| `target_market_fit` | 10 | 是否符合目标英语市场习惯 |
| `reader_appeal` | 15 | 是否具有清晰且不过度夸大的吸引力 |
| `memorability_distinctiveness` | 10 | 是否易记且有辨识度 |
| `clarity_concision` | 10 | 是否清晰、简洁并可作为正式剧名 |
| `integrity_safety` | 10 | 是否避免虚构、剧透和误导性标题党 |

模型会给出各项分数、加权贡献和总分。应用程序使用十进制运算独立复算，复算结果才是排名依据。模型计算差异会保留在制品中用于审计。

## 排名与严重违规

存在严重级别 `SEMANTIC_MISMATCH`、`ENTITY_ERROR`、`GENRE_MISMATCH` 或 `HOOK_INVENTED` 的候选不具备胜出资格。

合格候选依次按以下字段排名：

1. 加权总分；
2. 语义忠实度；
3. 诚信安全性；
4. 英文自然度；
5. 候选 ID。

如果全部候选均不合格，仍会输出可审计的排名制品，但结果为 `no_eligible_winner`，CLI 返回非零退出码。

## 输出制品

输出目录包含：

- `candidate_set.json`：12 个候选、4/4/4 策略来源、模型与提示词元数据、源记录指纹；
- `ranking_result.json`：八维得分、模型与程序计算、违规项、资格、完整排名和胜出者；
- `report.md`：面向人工阅读的排名及评分报告；
- `run_error.json`：发生校验或供应商错误时的机器可读诊断。

文件通过临时文件加原子重命名发布。报告只读取已完成制品，不会再次调用模型。

## 模型适配器

### `deterministic`

使用固定合成候选和基于内容的确定性评分，不访问网络，适用于测试、演示和复现。

### `openai-compatible`

使用配置中的 `base_url`、`model` 和 `timeout_seconds` 发起结构化 JSON 请求。凭证只从 `api_key_env` 指定的环境变量读取；默认变量为：

```powershell
$env:TITLE_LOCALIZATION_API_KEY = "<your-key>"
```

凭证不会写入配置、制品或错误报告。

### 使用 DeepSeek API Key

项目提供 `configs/title_selection.deepseek.json` 预设，通过同一个
`openai-compatible` 适配器访问 DeepSeek。先在当前 PowerShell 会话中设置
API Key：

```powershell
$env:DEEPSEEK_API_KEY = "<your-deepseek-api-key>"
```

然后运行完整的候选生成与评分流程：

```powershell
title-localization `
  --input data/examples/sample_title_case.json `
  --config configs/title_selection.deepseek.json `
  --output-dir artifacts/deepseek-example-run `
  --adapter openai-compatible
```

环境变量只对当前 PowerShell 进程及其子进程有效。使用完毕后可以清除：

```powershell
Remove-Item Env:DEEPSEEK_API_KEY
```

不要把真实 Key 写入 JSON 配置、源代码、生成制品或提交到仓库的脚本。
配置文件只保存环境变量名 `DEEPSEEK_API_KEY`。如果变量未设置，程序会在
访问网络前返回 `PROVIDER_CREDENTIAL_MISSING`，并指出缺失的变量名。

该预设当前使用 `deepseek-v4-flash`，基础地址为
`https://api.deepseek.com`。模型名称属于外部供应商配置，可能随时间变化；
运行前可查看 [DeepSeek 官方模型与价格列表](https://api-docs.deepseek.com/quick_start/pricing)。
若要使用其他受支持且具有 JSON Output 能力的模型，复制预设后只修改
`provider.model`，不要添加 API Key 字段：

```powershell
Copy-Item `
  configs/title_selection.deepseek.json `
  configs/title_selection.deepseek.custom.json
```

DeepSeek 的 JSON Output 要求提示词明确要求 JSON。本项目的候选生成和评分
提示词已经包含该要求，并由适配器设置
`response_format={"type":"json_object"}`。如果供应商返回空内容、截断内容或
无效 JSON，程序会按现有供应商响应错误处理，不会发布不完整结果。

## 失败与退出码

| 退出码 | 含义 |
| ---: | --- |
| `0` | 成功选出一个英文剧名 |
| `2` | 输入、配置、模型响应或供应商交互失败 |
| `4` | 完成评分，但没有任何合格候选 |

生成阶段无法凑齐 4/4/4 候选时不会发布不完整候选集；评分响应遗漏候选、改变剧名或缺少维度时会在有限重试后失败。
