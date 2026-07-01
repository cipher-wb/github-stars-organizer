---
name: github-stars-organizer
description: 交互式整理 GitHub Stars 收藏到 List 分类库。当用户想整理/重新分类自己的 GitHub star、给 star 归类到 List、清理杂乱的收藏夹、或把没放进任何 List 的仓库归类时使用。全程"先问后做"：抓取现状并诊断→询问「全部重新分类」还是「只补未归类」→对未归类仓库逐条建议→必须经用户明确同意，才用浏览器自动化在 GitHub 建 List/删 List/归类。触发词：整理github star、star分类、收藏太乱、给star归类、重新分类stars、star分类库、star归档。需要本地能弹出浏览器让用户登录 GitHub。
---

# GitHub Stars Organizer

用浏览器自动化整理 GitHub 星标收藏。GitHub 的 Lists 没有公开写 API，本 skill 通过驱动
网页表单端点完成建 List / 删 List / 归类，全部操作**必须先经用户同意**。

## ⛔ 交互铁律（最高优先级，不可违背）

1. **未经用户明确同意，绝不运行 `gh_apply.py`**（它会真实改动用户的 GitHub）。
2. **删除现有 List 是破坏性操作**（虽不影响 star 本身），必须单独、显式二次确认。
3. **未归类的仓库，必须让用户决定归属**——可批量建议，但不确认不落库，绝不自作主张。
4. 每一步动手前用一句话说清"接下来要做什么、影响什么"。

## 前置检查

- 需要**本地能弹出浏览器**的环境（登录 GitHub 要用户手动过账号密码/2FA）。
- 确认 Playwright 就绪：`python3 -c "from playwright.sync_api import sync_playwright"`；
  缺则 `pip install playwright && python3 -m playwright install chromium`。
- 拿到用户的 GitHub 用户名（`<login>`）；不知道就先问。

## 工作目录

在临时目录（scratchpad）下建工作区，存放：`gh_profile/`（浏览器登录态）、
`snapshot.json`、`plan.json`、`result.json`。脚本在本 skill 的 `scripts/` 下。

## 工作流

### 步骤 1 · 登录
后台运行，弹出浏览器让用户登录：
```
python3 scripts/gh_login.py --profile <workdir>/gh_profile --user <login>
```
等待输出 `LOGIN_OK user=<login>`。提醒用户：在弹出的窗口里登录、别关窗口、别用日常浏览器。

### 步骤 2 · 抓现状
```
python3 scripts/gh_snapshot.py --profile <workdir>/gh_profile --user <login> --out <workdir>/snapshot.json
```
读 `snapshot.json`：`lists`（现有分类+成员）、`all_repos`（全量 star，带 desc/lang/topics）、
`uncategorized`（没进任何 List 的仓库，带完整信息供归类判断）。

### 步骤 3 · 诊断 + 询问模式（必做）
先向用户汇报现状：多少 star、多少 List、多少未归类、现有分类有无明显问题
（重复/垃圾桶类/命名不一/错别字）。
然后**用 AskUserQuestion 询问模式**（这是用户强诉求，必问）：
- **只补未归类**（推荐，非破坏性）：保留现有 List，只把 `uncategorized` 归进去。
- **全部重新分类**（破坏性）：推倒现有 List，按新体系重建。
- **仅微调**：改名/合并个别 List + 补未归类。

### 步骤 4 · 生成方案 + 逐项确认（必做，禁止跳过）
- **只补未归类**：为每个 `uncategorized` 仓库按其 desc/topics 建议归入某个现有 List，
  用表格/分批 AskUserQuestion 呈现，让用户**逐条确认或改派**。用户没确认的仓库不写进 plan。
- **全部重新分类**：参考现有命名习惯 + star 内容，设计新分类体系（按用途场景，List 名 ≤32 字），
  连同"删除哪些旧 List"一起呈现，**逐类或整体获得用户批准**后才定案。删除需二次确认。
- 定案后写 `plan.json`（格式见下）。**把最终 plan 复述给用户，得到"执行"指令再进下一步**。

### 步骤 5 · 执行 + 核对
```
python3 scripts/gh_apply.py --profile <workdir>/gh_profile --user <login> --plan <workdir>/plan.json --result <workdir>/result.json
```
按 删→建→归类 顺序执行，末尾打印各 List 数量核对。读 `result.json` 汇报战果
（成功/失败数、失败清单）。建议用户去 stars 页刷新验收。

### 步骤 6 · 安全收尾
提醒：`gh_profile/` 目录含用户的 GitHub 登录 cookie。用户验收无误后，
**主动提出删除该目录**以保护账号，经同意后 `rm -rf <workdir>/gh_profile`。

## plan.json 格式

各段都可选，按 删→建→归类 执行。归类为覆盖式（传该 repo 应归属的全部 List）。
```json
{
  "delete_lists": ["旧slug1", "旧slug2"],
  "create_lists": [{"name": "AI网文·小说创作", "desc": "写小说的工具与模型"}],
  "assignments": [
    {"repo": "owner/name", "list": "AI网文·小说创作"},
    {"repo": "owner/other", "lists": ["分类A", "分类B"]}
  ]
}
```
- `delete_lists` 传 slug 列表，或字符串 `"ALL"` 删除所有现有 List（仅"全部重新分类"用，需二次确认）。
- `assignments` 的 `list`/`lists` 用 List 显示名；`gh_apply.py` 会自动映射到 List id。
  只补未归类时，只需列出 `uncategorized` 里用户确认过的仓库。

## 分类建议原则

- **按用途场景**分（贴合用户实际怎么用），而非单纯按语言/star 数。
- List 名简洁、`≤32 字`，沿用用户已有的命名习惯。
- 把大量低价值同类项（如几十星的练手 demo）打包成单独一类，保持主分类清爽。
- 数量核对：归类后各 List 成员总数应覆盖预期仓库，`fail=0` 才算干净。

## 出问题时

脚本报错（406 / 422 / selector 超时 / 分页抓不全）时，读
`references/github-lists-internals.md` —— 内含全部端点、令牌机制、DOM selector 与
错误码对照，据此定位并修补脚本。GitHub 改版导致 selector 失效时也查它。
