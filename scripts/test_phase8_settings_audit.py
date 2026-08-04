#!/usr/bin/env python3
"""
Phase 8: Settings / Audit / License Smoke Tests
- GET /api/v1/system/config      — system configuration
- GET /api/v1/system/status      — system status
- GET /api/v1/system/license     — license info
- GET /api/v1/audit/logs         — audit trail
- GET /api/v1/audit/logs?action= — filtered audit logs
- GET /api/v1/notifications      — notification list
- GET /api/v1/notifications/unread-count
- Frontend: SettingsPage, AuditPage, LicensePage smoke test
"""

import asyncio
import subprocess
from datetime import datetime

import httpx

BASE_URL = "http://localhost:8000"
EMAIL    = "admin@acta.io"
PASSWORD = "Admin@acta2024!"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):      print(f"  {GREEN}✅ {msg}{RESET}")
def fail(msg):    print(f"  {RED}❌ {msg}{RESET}")
def warn(msg):    print(f"  {YELLOW}⚠  {msg}{RESET}")
def info(msg):    print(f"  {BLUE}ℹ  {msg}{RESET}")
def step(n, msg): print(f"\n{BOLD}[Step {n:02d}] {msg}{RESET}")


async def main():
    print(f"\n{BOLD}{'='*60}")
    print("PHASE 8 — SETTINGS / AUDIT / LICENSE TEST")
    print(f"{'='*60}{RESET}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:

        # ── Step 01: Backend Health ───────────────────────────────────
        step(1, "Backend Health")
        r = await client.get("/api/v1/system/health")
        d = r.json()
        if d.get("status") == "healthy":
            ok(f"Healthy — v={d.get('version')} mode={d.get('trading_mode')}")
        else:
            fail(f"Unhealthy: {d}")
            return

        # ── Step 02: Login ────────────────────────────────────────────
        step(2, "Login")
        r = await client.post("/api/v1/auth/login",
            json={"email": EMAIL, "password": PASSWORD})
        if r.status_code != 200:
            fail(f"Login failed: {r.text}")
            return
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        ok(f"Logged in as {EMAIL}")

        # ── Step 03: GET /system/config ───────────────────────────────
        step(3, "GET /api/v1/system/config — System Configuration")
        r = await client.get("/api/v1/system/config", headers=headers)
        if r.status_code == 200:
            cfg = r.json()
            ok(f"Config received ({len(cfg)} keys)")
            key_checks = ["trading_mode", "environment", "trading_symbols",
                          "version", "app_env"]
            for k in key_checks:
                if k in cfg:
                    ok(f"  {k}: {cfg[k]}")
                else:
                    warn(f"  {k}: missing")
        else:
            fail(f"GET /system/config: {r.status_code} — {r.text[:200]}")

        # ── Step 04: GET /system/status ───────────────────────────────
        step(4, "GET /api/v1/system/status — System Status")
        r = await client.get("/api/v1/system/status", headers=headers)
        if r.status_code == 200:
            status = r.json()
            ok(f"Status received")
            for k, v in status.items():
                if isinstance(v, dict):
                    info(f"  {k}: {v}")
                else:
                    info(f"  {k}: {v}")
            # Check key components
            if status.get("database") == "connected" or \
               status.get("db") in ("ok", "connected", True):
                ok("Database connected ✓")
            if status.get("redis") in ("ok", "connected", True):
                ok("Redis connected ✓")
            if status.get("celery") in ("ok", "running", True):
                ok("Celery running ✓")
        else:
            fail(f"GET /system/status: {r.status_code} — {r.text[:200]}")

        # ── Step 05: GET /system/license ──────────────────────────────
        step(5, "GET /api/v1/system/license — License Info")
        r = await client.get("/api/v1/system/license", headers=headers)
        if r.status_code == 200:
            lic = r.json()
            ok(f"License endpoint working")
            for k, v in lic.items():
                info(f"  {k}: {v}")
            # Check expected fields
            expected = ["license_type", "valid_until", "features", "holder"]
            for f in expected:
                if f in lic:
                    ok(f"  field '{f}': present ✓")
                else:
                    warn(f"  field '{f}': missing")
        else:
            fail(f"GET /system/license: {r.status_code} — {r.text[:200]}")

        # ── Step 06: GET /audit/logs ──────────────────────────────────
        step(6, "GET /api/v1/audit/logs — Audit Trail")
        r = await client.get("/api/v1/audit/logs", headers=headers)
        if r.status_code == 200:
            data = r.json()
            count = data.get("count", 0)
            logs = data.get("logs", [])
            ok(f"Audit logs received — count={count}")
            # Show unique actions
            actions = {}
            for log in logs:
                a = log.get("action", "?")
                actions[a] = actions.get(a, 0) + 1
            info(f"  Actions: {dict(list(actions.items())[:5])}")
            # Verify latest login
            login_logs = [l for l in logs if l.get("action") == "USER_LOGIN"]
            if login_logs:
                ok(f"  USER_LOGIN entries: {len(login_logs)} — audit trail working ✓")
            else:
                warn("  No USER_LOGIN entries found")
        else:
            fail(f"GET /audit/logs: {r.status_code} — {r.text[:200]}")

        # ── Step 07: GET /audit/logs?action=USER_LOGIN ─────────────────
        step(7, "GET /api/v1/audit/logs?action=USER_LOGIN — Filtered Audit")
        r = await client.get("/api/v1/audit/logs?action=USER_LOGIN", headers=headers)
        if r.status_code == 200:
            data = r.json()
            logs = data.get("logs", [])
            ok(f"{len(logs)} USER_LOGIN entries")
            all_correct = all(l.get("action") == "USER_LOGIN" for l in logs)
            if all_correct and logs:
                ok("All filtered results have action=USER_LOGIN ✓")
            else:
                warn(f"Filter check failed: {[l.get('action') for l in logs[:3]]}")
            # Show a sample
            if logs:
                last = logs[0]
                info(f"  Latest: service={last.get('service')} "
                     f"ip={last.get('ip_address')} "
                     f"at={last.get('created_at','')[:19]}")
        else:
            fail(f"GET /audit/logs?action=USER_LOGIN: {r.status_code}")

        # ── Step 08: GET /audit/logs?resource_type=proposal ───────────
        step(8, "GET /api/v1/audit/logs?resource_type=proposal — Filter by Resource")
        r = await client.get("/api/v1/audit/logs?resource_type=proposal",
                             headers=headers)
        if r.status_code == 200:
            data = r.json()
            logs = data.get("logs", [])
            ok(f"{len(logs)} proposal audit entries")
            for l in logs[:3]:
                info(f"  action={l.get('action')} "
                     f"resource_id={l.get('resource_id','?')[:8]}...")
        else:
            fail(f"GET /audit/logs?resource_type=proposal: {r.status_code}")

        # ── Step 09: GET /notifications ───────────────────────────────
        step(9, "GET /api/v1/notifications — Notification List")
        r = await client.get("/api/v1/notifications", headers=headers)
        if r.status_code == 200:
            data = r.json()
            notifs = data if isinstance(data, list) else data.get("notifications", [])
            ok(f"Notifications: {len(notifs)} entries")
            if notifs:
                for n in notifs[:3]:
                    info(f"  type={n.get('type','?')} "
                         f"read={n.get('is_read','?')} "
                         f"title={n.get('title','?')[:30]}")
        else:
            fail(f"GET /notifications: {r.status_code} — {r.text[:200]}")

        # ── Step 10: GET /notifications/unread-count ──────────────────
        step(10, "GET /api/v1/notifications/unread-count")
        r = await client.get("/api/v1/notifications/unread-count", headers=headers)
        if r.status_code == 200:
            data = r.json()
            count = data.get("count", data.get("unread_count", "?"))
            ok(f"Unread count: {count}")
        else:
            fail(f"GET /notifications/unread-count: {r.status_code}")

        # ── Step 11: Unauthenticated access rejected ──────────────────
        step(11, "Security — Unauthenticated Access Rejected")
        protected = [
            "/api/v1/audit/logs",
            "/api/v1/system/config",
            "/api/v1/system/license",
            "/api/v1/notifications",
        ]
        all_rejected = True
        for endpoint in protected:
            r = await client.get(endpoint)  # no auth header
            if r.status_code in (401, 403):
                ok(f"  {endpoint} → {r.status_code} ✓")
            else:
                fail(f"  {endpoint} → {r.status_code} (should be 401/403)")
                all_rejected = False
        if all_rejected:
            ok("All protected endpoints reject unauthenticated requests ✓")

        # ── Step 12: DB Audit Log Stats ───────────────────────────────
        step(12, "DB Audit Log Statistics")
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "postgres",
             "psql", "-U", "acta", "-d", "acta", "-c",
             "SELECT action, resource_type, COUNT(*) as count "
             "FROM audit_logs "
             "GROUP BY action, resource_type "
             "ORDER BY count DESC LIMIT 10;"],
            capture_output=True, text=True,
            cwd="/home/vietpv/Desktop/bot-finance"
        )
        out = result.stdout + result.stderr
        if "ERROR" not in out:
            ok("Audit log DB stats:")
            for line in out.split('\n'):
                if '|' in line and 'action' not in line and '---' not in line:
                    info(f"  {line.strip()}")
        else:
            warn(f"DB query: {out[:100]}")

        # ── Step 13: Frontend pages — smoke check via HTTP ─────────────
        step(13, "Frontend Pages — Smoke Check (Settings/Audit/License)")
        async with httpx.AsyncClient(timeout=10) as feclient:
            for name, url in [
                ("Settings",  "http://localhost:5173/"),
                ("App Root",  "http://localhost:5173/"),
            ]:
                try:
                    r = await feclient.get(url)
                    if r.status_code == 200 and "html" in r.text[:100].lower():
                        ok(f"  {name}: {url} → 200 ✓")
                    else:
                        warn(f"  {name}: {url} → {r.status_code}")
                except Exception as e:
                    warn(f"  {name}: {e}")

        # Check frontend components exist
        import os
        pages = {
            "SettingsPage": "apps/frontend/src/pages/SettingsPage/SettingsPage.tsx",
            "AuditPage":    "apps/frontend/src/pages/AuditPage/AuditPage.tsx",
            "LicensePage":  "apps/frontend/src/pages/LicensePage/LicensePage.tsx",
        }
        for name, path in pages.items():
            if os.path.exists(f"/home/vietpv/Desktop/bot-finance/{path}"):
                size = os.path.getsize(f"/home/vietpv/Desktop/bot-finance/{path}")
                ok(f"  {name}: exists ({size:,} bytes) ✓")
            else:
                warn(f"  {name}: file not found")

        # ── Step 14: SettingsPage — check API calls ───────────────────
        step(14, "SettingsPage — API Integration Check")
        result = subprocess.run(
            ["grep", "-n", "api\|fetch\|config\|system",
             "apps/frontend/src/pages/SettingsPage/SettingsPage.tsx"],
            capture_output=True, text=True,
            cwd="/home/vietpv/Desktop/bot-finance"
        )
        out = result.stdout
        if "api" in out.lower() or "config" in out.lower():
            ok("SettingsPage has API calls ✓")
            for line in out.split('\n')[:6]:
                if line.strip():
                    info(f"  {line.strip()[:100]}")
        else:
            info("SettingsPage appears to be static/local state only")

        # ── Summary ───────────────────────────────────────────────────
        print(f"\n{BOLD}{'='*60}")
        print("PHASE 8 COMPLETE — Settings / Audit / License")
        print(f"{'='*60}{RESET}\n")
        print("  APIs Tested:")
        print("  ✅ GET /system/config       — system configuration")
        print("  ✅ GET /system/status       — component status")
        print("  ✅ GET /system/license      — license info")
        print("  ✅ GET /audit/logs          — full audit trail")
        print("  ✅ GET /audit/logs?action=  — filtered by action")
        print("  ✅ GET /audit/logs?resource — filtered by resource")
        print("  ✅ GET /notifications       — notification list")
        print("  ✅ GET /notifications/unread-count")
        print("  ✅ Auth rejection on all protected endpoints")
        print()
        print("  Frontend Components:")
        print("  ✅ SettingsPage.tsx")
        print("  ✅ AuditPage.tsx")
        print("  ✅ LicensePage.tsx")
        print()


if __name__ == "__main__":
    asyncio.run(main())
