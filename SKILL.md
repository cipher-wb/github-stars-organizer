---
name: github-stars-organizer
description: 整理用户自己的 GitHub Stars 和 Lists。当用户要求整理、清理、重新分类或归档 GitHub star，把未分类的收藏加入 List，或诊断 GitHub Lists 分类体系时使用。通过 Playwright 复用本地 GitHub 登录态，先生成快照和方案，再在用户明确批准后创建、删除 List 或修改归类。不用于整理他人账号、未获授权的 GitHub 数据，或未经确认直接执行写操作。
---

# GitHub Stars Organizer

通过 Playwright 整理 GitHub 星标收藏。GitHub Lists 没有公开写 API；本 Skill 使用 GitHub 网页表单端点创建、删除 List 和更新归类。

## 强制安全规则

1. 未获用户明确的“执行”指令前，禁止运行 `gh_apply.py`。
2. 删除 List 是破坏性操作。即使不会取消 star，也必须对删除清单获得第二次明确确认。
3. 用户未确认的仓库禁止写入 `plan.json`。可以批量建议，不得代替用户决定归属。
4. 每次写操作前，先简短说明即将改动的 List 和仓库数量。
5. 不得输出、上传、提交或复制 `gh_profile/` 内的 cookie 和登录数据。

## 运行约定

- 从 Skill 元数据中已知的 `SKILL.md` 路径解析 Skill 根目录，记为 `SKILL_ROOT`。运行脚本时始终使用绝对路径：`python3 "$SKILL_ROOT/scripts/<script>.py"`。
- 使用 `mktemp -d "${TMPDIR:-/tmp}/github-stars-organizer.XXXXXX"` 创建独立工作目录，不要将登录态和计划写入 Skill 目录或用户仓库。
- 结构化用户输入工具可用时可用它呈现模式选项；不可用时直接提出一个简短、明确的文本问题。不得依赖 Claude Code 专属的 `AskUserQuestion`。
- 登录需要 macOS 本地图形环境弹出 Chromium，由用户手动完成密码和 2FA。

## 前置检查

1. 获取用户自己的 GitHub 用户名。当本机 `gh auth status` 可读取当前账号时，可先将该账号作为候选并让用户确认；无法确定时再询问，禁止猜测。
2. 检查 Playwright：

   ```bash
   python3 -c "from playwright.sync_api import sync_playwright"
   ```

3. 缺失时告知用户将安装本 Skill 的运行依赖，然后执行：

   ```bash
   python3 -m pip install -r "$SKILL_ROOT/requirements.txt"
   python3 -m playwright install chromium
   ```

## 工作流

### 1. 登录

运行有头 Chromium，等待用户手动登录：

```bash
python3 "$SKILL_ROOT/scripts/gh_login.py" \
  --profile "$WORKDIR/gh_profile" \
  --user "$GITHUB_LOGIN"
```

等待 `LOGIN_OK user=<login>`。提醒用户在弹出窗口内登录，不要关闭窗口。如检测到的账号与期望用户名不同，停止并让用户决定是否继续。

### 2. 生成快照

```bash
python3 "$SKILL_ROOT/scripts/gh_snapshot.py" \
  --profile "$WORKDIR/gh_profile" \
  --user "$GITHUB_LOGIN" \
  --out "$WORKDIR/snapshot.json"
```

读取 `snapshot.json`：

- `lists`：现有 List 及成员。
- `all_repos`：全部 star，包含描述、语言、topics 和 star 数。
- `uncategorized`：尚未进入任何 List 的仓库。

### 3. 诊断并选择模式

先汇报 star 总数、List 数、未分类数，以及重复、命名不一致、错别字或低价值“垃圾桶”分类。然后必须让用户选择：

- **只补未分类（推荐）**：保留所有现有 List，只处理 `uncategorized`。
- **全部重新分类**：重建分类体系，包含删除 List 的破坏性操作。
- **仅微调**：调整或合并少量 List，再补齐未分类项。

### 4. 生成并批准方案

- 只补未分类：依据每个仓库的描述和 topics 建议现有 List，分批呈现，让用户确认或改派。
- 全部重新分类：按用途场景设计新体系，List 名最多 32 个字符，同时列出待删除 List。获得方案批准后，对删除清单再做一次单独确认。
- 仅微调：按具体变更分组呈现，明确哪些变更会通过“新建 + 重新归类 + 删除旧 List”实现。

仅将已确认项写入 `$WORKDIR/plan.json`。向用户复述最终计划和影响数量，然后暂停，直到用户明确说“执行”或同等含义的指令。

### 5. 执行并核对

只有在获得最终执行批准后才能运行：

```bash
python3 "$SKILL_ROOT/scripts/gh_apply.py" \
  --profile "$WORKDIR/gh_profile" \
  --user "$GITHUB_LOGIN" \
  --plan "$WORKDIR/plan.json" \
  --result "$WORKDIR/result.json" \
  --confirm APPLY
```

如计划含删除，必须在用户完成第二次确认后追加：

```bash
--confirm-delete DELETE-LISTS
```

`gh_apply.py` 按“删除 → 创建 → 归类”执行。读取 `result.json`，汇报成功数、失败数和失败清单，并让用户在 GitHub stars 页面刷新验收。不得在 `failed` 非空时宣称全部成功。

### 6. 安全收尾

说明 `$WORKDIR/gh_profile` 含 GitHub cookie。用户验收后，先询问是否删除工作目录；获得同意后再删除。不要在未确认时清理，否则用户无法复查计划和结果。

## `plan.json` 格式

```json
{
  "delete_lists": ["old-slug-1", "old-slug-2"],
  "create_lists": [
    {"name": "AI 写作", "desc": "写作工具与模型"}
  ],
  "assignments": [
    {"repo": "owner/name", "list": "AI 写作"},
    {"repo": "owner/other", "lists": ["分类 A", "分类 B"]}
  ]
}
```

- 各段均可选。
- `delete_lists` 使用 slug 列表；字符串 `"ALL"` 仅能在用户明确批准全量删除时使用。
- `assignments` 中的 `list` 或 `lists` 使用 List 显示名。归类是覆盖式的：传入的列表必须包含该仓库最终应保留的所有 List。

## 分类原则

- 按用途场景分类，不要只按语言或 star 数分类。
- 沿用用户已有命名习惯，List 名不超过 32 个字符。
- 将大量低价值同类项收纳到独立分类，保持主分类清晰。
- 执行后核对每个 List 数量和 `failed` 列表，不以脚本退出码代替业务验收。

## 故障排查

遇到 406、422、selector 超时、分页不全或 GitHub 页面改版时，读取 `references/github-lists-internals.md`。仅在出现这些问题时加载该参考文件。
