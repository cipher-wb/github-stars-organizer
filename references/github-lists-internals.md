# GitHub Stars Lists 技术内幕

GitHub 的「星标列表 Lists」**没有公开写 API**（REST/GraphQL 均不支持创建/删除/归类），
只能驱动网页表单端点。以下是逆向出的全部机制，脚本失效时照此调试。

## 目录
- 端点一览
- 两个致命关卡
- 关键 DOM selector
- 全量 star 的获取
- 常见错误码对照

## 端点一览

| 操作 | 请求 | 关键字段 |
|---|---|---|
| 建 List | `POST /stars/{user}/lists` | `user_list[name]`(≤32字) `user_list[description]` `user_list[private]=0` `authenticity_token` |
| 删 List | `POST /stars/{user}/lists/{slug}` | `_method=delete` `authenticity_token`（取自该 List 页面删除表单） |
| 归类 | `POST /{owner}/{repo}/lists` | `_method=put` `repository_id` `context=user_list_menu` `user_list_menu_dirty=1` `authenticity_token` `list_ids[]`（可多值，**覆盖式**） |
| 读归类面板 | `GET /{owner}/{repo}/lists` | 返回含专属 `authenticity_token`、`repository_id`、全部 List 的 `button.ActionListContent[data-value=<listid>]`（`aria-selected=true` 表当前归属） |

归类是**覆盖式**：`list_ids[]` 传该 repo 应归属的全部 List id（不是增量）。传空则移出所有 List。

## 两个致命关卡

1. **所有写请求必须带 header `X-Requested-With: XMLHttpRequest`**，否则 `406 Not Acceptable`（响应体为空）。
2. **归类的 `authenticity_token` 必须取自该 repo 的 `GET /{owner}/{repo}/lists` 面板**；
   用建 List 表单或其他页面的 token 会 `422 Unprocessable`。建 List / 删 List 的 token 则各取自对应表单。

提交用页面内原生 `fetch` + `FormData`（multipart），最贴近真人，GitHub 不拦。

## 关键 DOM selector

- repo 卡片：`div.col-12.d-block`
- repo 的 star 表单（拿 full_name）：`form[action$="/star"]` 或 `form[action$="/unstar"]`，action 去掉 `/star` 即 `owner/repo`
- repo_id：卡片内 `[data-repository-id]`
- star 下拉触发：`button[id$="-starred-button"]`（点开懒加载 `dialog[id$="-starred-dialog"]`）
- List 选项：`button.ActionListContent[data-value]`（`data-value`=list id，`textContent`=名字，`aria-selected`=当前是否归属）
- 建 List 表单：`form[action="/stars/{user}/lists"]`（页面初始 DOM 即存在，但不可见——用 `querySelector` 取，勿用等待可见的 `wait_for_selector`）
- List 成员分页：`/stars/{user}/lists/{slug}?page=N`，逐页翻直到无 `div.col-12.d-block`

## 全量 star 的获取

用 GitHub 公开 API：`GET https://api.github.com/users/{user}/starred?per_page=100&page=N`，
逐页直到返回空或不足 100。每项的 `id` 即 `repository_id`，`full_name` 即 `owner/repo`。
未认证限流 60 次/小时，足够快照使用。

⚠️ 个人 profile 的 `?tab=stars` **网页分页不可靠**（`&page=N` 常返回第一页），勿用它抓全量，只用它抓 List 成员。

## 常见错误码对照

| 现象 | 原因 | 处理 |
|---|---|---|
| 406（体空） | 缺 `X-Requested-With: XMLHttpRequest` | 补 header |
| 422 | 归类 token 来源错误 / 缺 `user_list_menu_dirty` | token 改取自 repo 面板 |
| status 0 (opaqueredirect) / 302 | `redirect:'manual'` 下删/建成功的正常表现 | 视为成功 |
| 归类返回 200 + JSON | 归类成功（`{"didStar":...}`） | 视为成功 |
| `wait_for_selector` 超时 | 等的是不可见的表单，或用了 `networkidle`（GitHub 长轮询永不 idle） | 改等 `div.col-12.d-block`；表单用 `querySelector` |
