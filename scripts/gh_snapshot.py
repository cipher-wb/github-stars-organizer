#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取 GitHub Stars 现状：全量 star + 现有 List + 每个 List 成员 + 未归类清单。

用法:
  python3 gh_snapshot.py --profile <目录> --user <登录名> [--out snapshot.json]

输出 JSON（stdout 或 --out）:
  {
    "user": "...",
    "lists":   [{"name","id","slug","count","members":["owner/repo",...]}],
    "all_repos":[{"full_name":"owner/repo","repo_id":"123"}],
    "uncategorized": ["owner/repo", ...]
  }
需先用 gh_login.py 在同一 --profile 目录登录。
"""
import sys, os, json, argparse, urllib.request
from playwright.sync_api import sync_playwright

XHR = {'X-Requested-With': 'XMLHttpRequest'}


def fetch_all_stars(page, user):
    """在浏览器上下文 fetch GitHub 公开 API 拿全量 star（走 chromium 网络栈，避开本机直连限制）。
    需先 page.goto 到 github.com 建立 origin。未认证限流 60/h，够快照用。"""
    return page.evaluate("""async (user) => {
        const out=[];
        for(let pg=1; pg<60; pg++){
            let r;
            try { r = await fetch(`https://api.github.com/users/${user}/starred?per_page=100&page=${pg}`,
                {headers:{'Accept':'application/vnd.github+json'}}); }
            catch(e){ break; }
            if(!r.ok) break;
            const data = await r.json();
            if(!data.length) break;
            for(const repo of data){
                out.push({full_name: repo.full_name, repo_id: String(repo.id),
                    desc: (repo.description||'').trim(), lang: repo.language,
                    topics: (repo.topics||[]).slice(0,8), stars: repo.stargazers_count});
            }
            if(data.length < 100) break;
        }
        return out;
    }""", user)

SCRAPE_PAGE = """(sel) => {
    return [...document.querySelectorAll('div.col-12.d-block')].map(c => {
        const f = c.querySelector('form[action$="/star"], form[action$="/unstar"]');
        const fn = f ? f.getAttribute('action').replace(/^\\//,'').replace(/\\/(un)?star$/,'') : null;
        const rb = c.querySelector('[data-repository-id]');
        const rid = rb ? rb.getAttribute('data-repository-id') : null;
        return {full_name: fn, repo_id: rid};
    }).filter(x => x.full_name);
}"""


def scrape_paginated(page, base_url):
    """翻页抓取 repo 卡片，直到空页。返回 [{full_name,repo_id}]。"""
    out, seen = [], set()
    for pg in range(1, 40):
        url = base_url + ("&" if "?" in base_url else "?") + f"page={pg}"
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        try:
            page.wait_for_selector("div.col-12.d-block", timeout=8000)
        except Exception:
            break
        page.wait_for_timeout(600)
        rows = page.evaluate(SCRAPE_PAGE)
        fresh = [r for r in rows if r["full_name"] not in seen]
        if not fresh:
            break
        for r in fresh:
            seen.add(r["full_name"]); out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--user", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    U = args.user

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            args.profile, headless=True, no_viewport=True,
            args=["--disable-blink-features=AutomationControlled"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # 先加载 stars 页，建立 github.com origin（供浏览器内 fetch API 使用）
        page.goto(f"https://github.com/{U}?tab=stars", timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(1200)

        # 1) 全量 star（含 repo_id）—— 浏览器内 fetch GitHub API，走 chromium 网络栈
        all_repos = fetch_all_stars(page, U)

        # 2) 现有 List：侧边栏 name+slug；GET /{probe}/lists 拿 name->id
        sidebar = page.evaluate("""(U) => {
            const out=[];
            document.querySelectorAll(`a[href*="/stars/${U}/lists/"]`).forEach(a=>{
                const slug=a.getAttribute('href').split('/lists/')[1];
                if(!slug || slug.includes('/') || slug.includes('?')) return;
                const name=(a.textContent||'').trim().split('\\n')[0].trim();
                out.push({name, slug});
            });
            return out;
        }""", U)
        # 去重 slug
        seen=set(); lists_meta=[]
        for s in sidebar:
            if s["slug"] in seen: continue
            seen.add(s["slug"]); lists_meta.append(s)

        name_to_id = {}
        if all_repos:
            probe = all_repos[0]["full_name"]
            name_to_id = page.evaluate("""async (repo) => {
                const r=await fetch('/'+repo+'/lists',{headers:{'X-Requested-With':'XMLHttpRequest'}});
                const txt=await r.text(); const doc=new DOMParser().parseFromString(txt,'text/html');
                const m={};
                doc.querySelectorAll('button.ActionListContent[data-value]').forEach(b=>{
                    m[b.textContent.trim()]=b.getAttribute('data-value');});
                return m;
            }""", probe)

        # 3) 每个 List 成员
        lists = []
        for lm in lists_meta:
            members = [r["full_name"] for r in
                       scrape_paginated(page, f"https://github.com/stars/{U}/lists/{lm['slug']}")]
            lists.append({
                "name": lm["name"],
                "id": name_to_id.get(lm["name"]),
                "slug": lm["slug"],
                "count": len(members),
                "members": members,
            })

        # 4) 未归类
        categorized = set()
        for l in lists:
            categorized.update(l["members"])
        # 未归类清单带完整信息（desc/lang/topics/stars），供 AI 直接判断归属
        uncategorized = [r for r in all_repos if r["full_name"] not in categorized]

        snap = {"user": U, "lists": lists, "all_repos": all_repos, "uncategorized": uncategorized}
        ctx.close()

    text = json.dumps(snap, ensure_ascii=False, indent=1)
    if args.out:
        open(args.out, "w").write(text)
        print(f"SNAPSHOT_OK repos={len(all_repos)} lists={len(lists)} "
              f"uncategorized={len(uncategorized)} -> {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
