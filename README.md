# github-stars-organizer

一个 [Claude Code](https://claude.ai/code) Skill —— **交互式整理 GitHub Stars 收藏到 List 分类库**。

## 这是什么

GitHub 的「星标列表 Lists」**没有公开写 API**（REST/GraphQL 都不支持创建/删除/归类），
没法用脚本直接归类收藏。本 skill 通过驱动网页表单端点，让 Claude Code 帮你：

- 抓取全部 star + 现有 List + 揪出没归类的仓库
- 按用途场景智能建议分类
- **全程先问后做**：你确认后才建 List / 删 List / 归类

## 特性

- 🔒 **先问后做**：任何写操作都要你明确同意，删 List 还需二次确认
- 🧠 **智能诊断**：识别重复 / 垃圾桶类 / 命名不一 / 错别字的 List
- 📦 **逐条确认**：未归类仓库按 desc/topics 建议归属，你拍板才落库
- ⚡ **无需写 API**：纯网页表单端点（Lists 本就无写 API），复用你的登录态

## 安装

克隆到 Claude Code 的 skills 目录：

```bash
git clone https://github.com/cipher-wb/github-stars-organizer ~/.claude/skills/github-stars-organizer
```

或下载 release 里的 `github-stars-organizer.skill` 直接安装。

依赖 Playwright（用于驱动浏览器登录 GitHub）：

```bash
pip install playwright && python3 -m playwright install chromium
```

## 用法

在 Claude Code 里说触发词即可自动调用：

- 「整理一下我的 github star」
- 「star 收藏太乱帮我分类」
- 「把没归类的 star 归归类」

工作流：**登录 → 抓现状 → 诊断 + 问模式 → 逐项确认 → 执行 → 核对**。

三种模式任选：**只补未归类**（非破坏性）/ **全部重新分类**（推倒重建）/ **仅微调**。

## 结构

```
SKILL.md                          工作流 + 交互铁律
references/
  github-lists-internals.md       端点 / 令牌 / 错误码内幕（GitHub 改版时照此修）
scripts/
  gh_login.py                     拉浏览器登录（持久化配置）
  gh_snapshot.py                  抓全量 star + 现有 List + 未归类清单
  gh_apply.py                     读 plan.json 执行 删 / 建 / 归类
```

## 技术内幕

GitHub Lists 的表单端点、`X-Requested-With` 关卡、归类令牌机制、DOM selector 与
错误码对照，全部记录在 [references/github-lists-internals.md](references/github-lists-internals.md)。
GitHub 改版导致脚本失效时，照此定位修补。

## 安全

- 登录用持久化浏览器配置（含 GitHub cookie），只存本地工作目录，**不会上传**。
- 用完建议删除该目录以保护账号。

## License

[MIT](LICENSE)
