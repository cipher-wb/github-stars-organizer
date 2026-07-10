#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""执行分类计划：删 List / 建 List / 归类 repo。全部走 GitHub 表单端点。

用法:
  python3 gh_apply.py --profile <目录> --user <登录名> --plan plan.json \
    [--result result.json] --confirm APPLY [--confirm-delete DELETE-LISTS]

plan.json 结构（各段都可选，按 删→建→归类 顺序执行）:
  {
    "delete_lists": ["slug1","slug2"]  或  "ALL"（删所有现有 List）,
    "create_lists": [{"name":"分类名(≤32字)", "desc":"描述"}],
    "assignments":  [{"repo":"owner/name", "list":"分类名"}]
        # 也支持 "lists":["A","B"] 归入多个；可选 "repo_id" 加速
  }
归类为覆盖式：同一 repo 传其应归属的全部 List。需先 gh_login.py 登录同一 --profile。
关键：所有写请求必须带 header X-Requested-With: XMLHttpRequest（缺则 406）；
     归类令牌必须取自该 repo 的 GET /{repo}/lists 面板（用别处令牌会 422）。
"""
import sys, os, json, time, argparse
from playwright.sync_api import sync_playwright


def log(m): print(m, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--user", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--result", default=None)
    ap.add_argument("--confirm", default=None,
                    help="写操作确认口令；必须精确为 APPLY")
    ap.add_argument("--confirm-delete", default=None,
                    help="删除 List 二次确认口令；必须精确为 DELETE-LISTS")
    args = ap.parse_args()
    U = args.user
    plan = json.load(open(args.plan))
    if args.confirm != "APPLY":
        ap.error("拒绝执行：未提供 --confirm APPLY")
    if plan.get("delete_lists") and args.confirm_delete != "DELETE-LISTS":
        ap.error("拒绝删除 List：计划包含 delete_lists，但未提供 "
                 "--confirm-delete DELETE-LISTS")
    STARS = f"https://github.com/{U}?tab=stars"

    def load_stars(page):
        page.goto(STARS, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_selector("div.col-12.d-block", timeout=20000)
        page.wait_for_timeout(1000)

    def get_slugs(page):
        return page.evaluate("""(U) => {
            const s=new Set();
            document.querySelectorAll(`a[href*="/stars/${U}/lists/"]`).forEach(a=>{
                const m=a.getAttribute('href').split('/lists/')[1];
                if(m && !m.includes('/') && !m.includes('?')) s.add(m);});
            return [...s];
        }""", U)

    def delete_list(page, slug):
        return page.evaluate("""async ({U,slug}) => {
            const resp=await fetch(`/stars/${U}/lists/`+slug,{headers:{'X-Requested-With':'XMLHttpRequest'}});
            const txt=await resp.text(); const doc=new DOMParser().parseFromString(txt,'text/html');
            const di=doc.querySelector('input[name=_method][value=delete]');
            if(!di) return {ok:false,status:-1,err:'no-del-form'};
            const tok=di.closest('form').querySelector('input[name=authenticity_token]').value;
            const fd=new FormData(); fd.append('_method','delete'); fd.append('authenticity_token',tok);
            const r=await fetch(`/stars/${U}/lists/`+slug,{method:'POST',body:fd,redirect:'manual',
                headers:{'X-Requested-With':'XMLHttpRequest'}});
            return {ok:[0,200,302].includes(r.status), status:r.status};
        }""", {"U":U,"slug":slug})

    def create_list(page, name, desc):
        return page.evaluate("""async ({U,name,desc}) => {
            const f=document.querySelector(`form[action="/stars/${U}/lists"]`);
            if(!f) return {ok:false,status:-1,err:'no-create-form'};
            const tok=f.querySelector('input[name=authenticity_token]').value;
            const fd=new FormData(); fd.append('user_list[name]',name);
            fd.append('user_list[description]',desc||''); fd.append('user_list[private]','0');
            fd.append('authenticity_token',tok);
            const r=await fetch(`/stars/${U}/lists`,{method:'POST',body:fd,redirect:'manual',
                headers:{'X-Requested-With':'XMLHttpRequest'}});
            return {ok:[0,200,302].includes(r.status), status:r.status};
        }""", {"U":U,"name":name,"desc":desc})

    def get_name_to_id(page, probe):
        return page.evaluate("""async (repo) => {
            const r=await fetch('/'+repo+'/lists',{headers:{'X-Requested-With':'XMLHttpRequest'}});
            const txt=await r.text(); const doc=new DOMParser().parseFromString(txt,'text/html');
            const m={};
            doc.querySelectorAll('button.ActionListContent[data-value]').forEach(b=>{
                m[b.textContent.trim()]=b.getAttribute('data-value');});
            return m;
        }""", probe)

    def assign(page, repo, list_ids, repo_id=None):
        return page.evaluate("""async ({repo,listids,rid}) => {
            const g=await fetch('/'+repo+'/lists',{headers:{'X-Requested-With':'XMLHttpRequest'}});
            if(g.status!==200) return {ok:false,status:g.status,err:'get-fail'};
            const txt=await g.text(); const doc=new DOMParser().parseFromString(txt,'text/html');
            const tokEl=doc.querySelector('input[name=authenticity_token]');
            if(!tokEl) return {ok:false,status:-1,err:'no-token'};
            const ridEl=doc.querySelector('input[name=repository_id]');
            const useRid = rid || (ridEl?ridEl.value:null);
            const fd=new FormData(); fd.append('_method','put'); fd.append('repository_id',useRid);
            fd.append('context','user_list_menu'); fd.append('user_list_menu_dirty','1');
            fd.append('authenticity_token',tokEl.value);
            listids.forEach(id => fd.append('list_ids[]', id));
            const r=await fetch('/'+repo+'/lists',{method:'POST',body:fd,redirect:'manual',
                headers:{'X-Requested-With':'XMLHttpRequest'}});
            return {ok:r.status===200, status:r.status};
        }""", {"repo":repo,"listids":[str(i) for i in list_ids],"rid":str(repo_id) if repo_id else None})

    result = {"deleted": [], "created": [], "assigned": [], "failed": []}
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            args.profile, headless=True, no_viewport=True,
            args=["--disable-blink-features=AutomationControlled"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        load_stars(page)
        probe = page.locator("div.col-12.d-block").first.locator(
            'form[action$="/star"], form[action$="/unstar"]').first.get_attribute("action").strip("/").rsplit("/",1)[0]
        log(f"probe repo = {probe}")

        # ===== 删 =====
        dl = plan.get("delete_lists")
        if dl:
            slugs = get_slugs(page) if dl == "ALL" else list(dl)
            log(f"===== 删除 {len(slugs)} 个 List =====")
            for s in slugs:
                try:
                    r = delete_list(page, s); log(f"  删 {s}: {r}")
                    (result["deleted"] if r.get("ok") else result["failed"]).append([s, r])
                except Exception as e:
                    result["failed"].append([s, str(e)]); log(f"  删 {s} ERR {e}")
                time.sleep(0.2)

        # ===== 建 =====
        cl = plan.get("create_lists") or []
        if cl:
            log(f"===== 建 {len(cl)} 个 List =====")
            for item in cl:
                load_stars(page)
                try:
                    r = create_list(page, item["name"], item.get("desc",""))
                    log(f"  建 {item['name']}: {r}")
                    (result["created"] if r.get("ok") else result["failed"]).append([item["name"], r])
                except Exception as e:
                    result["failed"].append([item["name"], str(e)]); log(f"  建 {item['name']} ERR {e}")
                time.sleep(0.25)

        # ===== 归类 =====
        asg = plan.get("assignments") or []
        if asg:
            load_stars(page)
            name_to_id = get_name_to_id(page, probe)
            log(f"===== 归类 {len(asg)} 个 repo =====（现有 List {len(name_to_id)} 个）")
            for i, a in enumerate(asg, 1):
                repo = a["repo"]
                names = a.get("lists") or ([a["list"]] if a.get("list") else [])
                ids = [name_to_id[n] for n in names if n in name_to_id]
                miss = [n for n in names if n not in name_to_id]
                if not ids:
                    result["failed"].append([repo, f"no-list-id names={names} miss={miss}"])
                    log(f"  [{i}/{len(asg)}] SKIP {repo} 找不到 List {miss}"); continue
                try:
                    r = assign(page, repo, ids, a.get("repo_id"))
                    if r.get("ok"): result["assigned"].append(repo)
                    else:
                        result["failed"].append([repo, r]); log(f"  [{i}/{len(asg)}] FAIL {repo}: {r}")
                except Exception as e:
                    result["failed"].append([repo, str(e)]); log(f"  [{i}/{len(asg)}] ERR {repo}: {e}")
                if i % 20 == 0:
                    log(f"  ...进度 {i}/{len(asg)} ok={len(result['assigned'])} fail={len(result['failed'])}")
                time.sleep(0.18)

        # ===== 核对 =====
        load_stars(page)
        counts = page.evaluate("""(U) => {
            const out=[];
            document.querySelectorAll(`a[href*="/stars/${U}/lists/"]`).forEach(a=>{
                const t=a.textContent.replace(/\\s+/g,' ').trim(); if(t) out.push(t);});
            return [...new Set(out)];
        }""", U)
        log("===== 核对各 List =====")
        for c in counts: log(f"    {c}")
        ctx.close()

    log(f"\n汇总: 删={len(result['deleted'])} 建={len(result['created'])} "
        f"归类={len(result['assigned'])} 失败={len(result['failed'])}")
    if result["failed"]:
        for f in result["failed"]: log(f"  FAIL {f}")
    if args.result:
        json.dump(result, open(args.result,"w"), ensure_ascii=False, indent=1)
    print("APPLY_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
