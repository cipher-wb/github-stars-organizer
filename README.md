# GitHub Stars Organizer for Codex

一个面向 **OpenAI Codex** 的 Agent Skill：读取你的 GitHub Stars 和 Lists，诊断收藏体系，生成分类方案，并在你确认后通过浏览器自动化执行。

> 这不是“一键把你的收藏夹炸成渣”工具。任何写操作都要先给出方案、再获得确认；删除 List 还需要第二次确认。

## 能做什么

- 抓取全部 Stars、现有 Lists 和未分类仓库。
- 识别重复、命名不一致、错别字和低价值“垃圾桶”分类。
- 按用途场景建议归类，而不是粗暴地只看编程语言。
- 支持“只补未分类”、“全部重新分类”和“仅微调”三种模式。
- 执行后输出成功、失败与 List 数量核对结果。

## 它如何工作

GitHub 目前没有用于创建、删除和分配 Stars Lists 的公开写 API。本 Skill 使用 Playwright 打开本地 Chromium，由你手动完成 GitHub 登录和 2FA，然后在该登录会话中调用 GitHub 网页表单端点。

工作流是：

```text
登录 → 快照 → 诊断 → 选择模式 → 批准方案 → 执行 → 核对
```

## 环境要求

- macOS 或其他可弹出本地浏览器的图形环境。
- Python 3.10 或更高版本。
- OpenAI Codex 桌面端、CLI 或 IDE 扩展。
- Playwright 和 Chromium。

## 安装到 Codex

Codex 的用户级 Skill 目录是 `~/.agents/skills`。克隆后安装依赖：

```bash
git clone https://github.com/cipher-wb/github-stars-organizer.git \
  ~/.agents/skills/github-stars-organizer

python3 -m pip install -r \
  ~/.agents/skills/github-stars-organizer/requirements.txt

python3 -m playwright install chromium
```

Codex 通常会自动检测新 Skill。如果当前会话没有显示，重启 Codex 后再试。

如果你下载的是 `github-stars-organizer.skill`，它是一个 ZIP 格式的可分发包，可直接解压到用户级 Skill 目录：

```bash
mkdir -p ~/.agents/skills
unzip github-stars-organizer.skill -d ~/.agents/skills
python3 -m pip install -r \
  ~/.agents/skills/github-stars-organizer/requirements.txt
python3 -m playwright install chromium
```

### 已经克隆了仓库？

Codex 支持跟随符号链接。可将仓库链接到用户级 Skill 目录：

```bash
mkdir -p ~/.agents/skills
ln -s /absolute/path/to/github-stars-organizer \
  ~/.agents/skills/github-stars-organizer
```

这样更新仓库后，Codex 读取到的也是最新版本。

## 用法

可显式调用：

```text
$github-stars-organizer 整理一下我的 GitHub Stars
```

也可直接说：

- “我的 GitHub star 太乱了，帮我分类。”
- “把还没进 List 的 star 整理一下。”
- “诊断一下我的 GitHub Lists，先别改。”

Codex 会先读取现状并给出方案。只有你明确批准最终 `plan.json` 并要求执行后，它才会运行写操作。

## 安全设计

- `gh_apply.py` 必须收到 `--confirm APPLY` 才会执行。
- 计划包含删除时，还必须收到 `--confirm-delete DELETE-LISTS`。
- 登录 cookie 保存在本机临时工作目录的 `gh_profile/` 中，不写入仓库；仓库的 `.gitignore` 也额外排除了该目录名。
- Skill 要求在用户验收后再询问是否删除登录态。
- 脚本不需要 GitHub Personal Access Token，也不会要求你把密码交给 Codex。

## 仓库结构

```text
github-stars-organizer/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   └── github-lists-internals.md
├── scripts/
│   ├── gh_login.py
│   ├── gh_snapshot.py
│   └── gh_apply.py
├── requirements.txt
└── github-stars-organizer.skill
```

`SKILL.md` 是 Codex 实际加载的工作流。`agents/openai.yaml` 提供桌面端展示信息和默认调用提示。`references/` 只在 GitHub 改版或脚本报错时供 Codex 按需读取。

## 已知限制

- 这是对 GitHub 网页端点和 DOM 结构的自动化，GitHub 改版后可能需要更新 selector 或表单字段。
- 必须使用拥有目标 Stars 的本人 GitHub 账号登录。
- 无图形界面的远程环境无法完成首次手动登录。
- GitHub 的限流、人机验证或 DOM 变更可能使快照或写入失败。

## 验证开发版

```bash
python3 ~/.agents/skills/skill-creator/scripts/quick_validate.py .
python3 -m compileall -q scripts
python3 scripts/gh_login.py --help
python3 scripts/gh_snapshot.py --help
python3 scripts/gh_apply.py --help
```

## License

[MIT](LICENSE)
