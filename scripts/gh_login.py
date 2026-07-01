#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""拉起有头 Chromium（持久化配置），等用户手动登录 GitHub。

用法:
  python3 gh_login.py --profile <持久化目录> [--user <期望登录名>] [--timeout 600]

检测到 GitHub 的 logged_in=yes cookie 即视为成功，打印 `LOGIN_OK user=<login>`。
持久化目录保存登录态，后续 gh_snapshot.py / gh_apply.py 复用同一目录即免登。
"""
import sys, time, os, argparse
from playwright.sync_api import sync_playwright


def logged_in(ctx):
    try:
        for c in ctx.cookies():
            if c.get("name") == "logged_in" and c.get("value") == "yes":
                return True
    except Exception:
        pass
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True, help="浏览器持久化目录（保存登录态）")
    ap.add_argument("--user", default=None, help="期望登录的 GitHub 用户名（可选，仅校验提示）")
    ap.add_argument("--timeout", type=int, default=600, help="等待登录最长秒数")
    args = ap.parse_args()
    os.makedirs(args.profile, exist_ok=True)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            args.profile, headless=False, no_viewport=True,
            args=["--no-first-run", "--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        if logged_in(ctx):
            print("LOGIN_OK_ALREADY", flush=True)
            ctx.close(); return 0
        try:
            page.goto("https://github.com/login", timeout=60000)
        except Exception as e:
            print("NAV_WARN", e, flush=True)
        print("WAITING_LOGIN  (浏览器窗口已弹出，请登录 GitHub)", flush=True)
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            if logged_in(ctx):
                who = None
                try:
                    page.goto("https://github.com/settings/profile", timeout=30000)
                    who = page.locator('meta[name="octolytics-actor-login"]').get_attribute("content")
                except Exception:
                    pass
                print(f"LOGIN_OK user={who}", flush=True)
                if args.user and who and who != args.user:
                    print(f"WARN 登录者 {who} 与期望 {args.user} 不一致", flush=True)
                ctx.close(); return 0
            time.sleep(3)
        print("LOGIN_TIMEOUT", flush=True)
        ctx.close(); return 1


if __name__ == "__main__":
    sys.exit(main())
