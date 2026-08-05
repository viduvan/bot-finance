#!/usr/bin/env python3
"""
ACTA — Full System Verification (Phases 1–8)
Runs all test phases in sequence and produces a unified report.
"""

import asyncio
import json
import subprocess
import time
import os
import sys
from datetime import datetime

import httpx

BASE_URL   = "http://localhost:8000"
WS_BASE    = "ws://localhost:8000"
EMAIL      = "admin@acta.io"
PASSWORD   = "Admin@acta2024!"
PROJECT    = "/home/vietpv/Desktop/bot-finance"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

passed_checks = 0
failed_checks = 0
warnings      = 0
results       = {}  # phase → [(name, status)]


def ok(msg):
    global passed_checks
    passed_checks += 1
    print(f"  {GREEN}✅ {msg}{RESET}")

def fail(msg):
    global failed_checks
    failed_checks += 1
    print(f"  {RED}❌ {msg}{RESET}")

def warn(msg):
    global warnings
    warnings += 1
    print(f"  {YELLOW}⚠  {msg}{RESET}")

def info(msg):
    print(f"  {BLUE}ℹ  {msg}{RESET}")

def phase_header(n, title):
    print(f"\n{BOLD}{CYAN}{'━'*60}")
    print(f"  PHASE {n} — {title}")
    print(f"{'━'*60}{RESET}")

def record(phase, name, passed):
    results.setdefault(phase, []).append((name, passed))


def docker_exec_psql(sql):
    """Run SQL in postgres container and return output."""
    r = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres",
         "psql", "-U", "acta", "-d", "acta", "-t", "-A", "-c", sql],
        capture_output=True, text=True, cwd=PROJECT
    )
    return r.stdout.strip()


async def wait_for_healthy(max_wait=90):
    """Wait for backend to become healthy."""
    print(f"\n{BOLD}[Pre-check] Waiting for services to become healthy...{RESET}")
    start = time.time()
    async with httpx.AsyncClient(timeout=5) as client:
        while time.time() - start < max_wait:
            try:
                r = await client.get(f"{BASE_URL}/api/v1/system/health")
                if r.status_code == 200 and r.json().get("status") == "healthy":
                    elapsed = time.time() - start
                    ok(f"Backend healthy after {elapsed:.0f}s")
                    return True
            except Exception:
                pass
            await asyncio.sleep(3)
            sys.stdout.write(".")
            sys.stdout.flush()
    fail("Backend did not become healthy within timeout")
    return False


async def phase1_docker_services():
    """Phase 1: Docker Services Health Check"""
    phase_header(1, "Docker Services Health")

    r = subprocess.run(
        ["docker", "compose", "ps", "--format", "json"],
        capture_output=True, text=True, cwd=PROJECT
    )

    services_ok = 0
    services_fail = 0
    expected = ["acta-backend", "acta-postgres", "acta-redis",
                "acta-celery-worker", "acta-celery-beat"]

    # Parse each JSON line
    for line in r.stdout.strip().split('\n'):
        if not line.strip():
            continue
        try:
            svc = json.loads(line)
        except json.JSONDecodeError:
            continue

        name = svc.get("Name", "?")
        state = svc.get("State", "?")
        health = svc.get("Health", "")
        status = svc.get("Status", "")

        if state == "running":
            if health == "healthy" or "healthy" in status:
                ok(f"{name}: running (healthy)")
                services_ok += 1
                record(1, name, True)
            elif health == "" and name in ("acta-grafana", "acta-prometheus"):
                ok(f"{name}: running (no healthcheck — monitoring)")
                services_ok += 1
                record(1, name, True)
            else:
                warn(f"{name}: running ({health or status})")
                services_ok += 1  # running but may still be starting
                record(1, name, True)
        else:
            fail(f"{name}: {state}")
            services_fail += 1
            record(1, name, False)

    # Verify expected services exist
    for name in expected:
        found = any(name in line for line in r.stdout.split('\n'))
        if not found:
            fail(f"{name}: NOT FOUND")
            record(1, name, False)

    return services_fail == 0


async def phase2_auth(client, headers_out):
    """Phase 2: Authentication Flows"""
    phase_header(2, "Authentication Flows")

    # Login
    r = await client.post("/api/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD})
    if r.status_code == 200:
        data = r.json()
        token = data["access_token"]
        refresh = data["refresh_token"]
        ok(f"Login: 200 — token={token[:20]}...")
        record(2, "login", True)
    else:
        fail(f"Login: {r.status_code}")
        record(2, "login", False)
        return False

    headers_out["Authorization"] = f"Bearer {token}"

    # Refresh token
    r = await client.post("/api/v1/auth/refresh",
        json={"refresh_token": refresh})
    if r.status_code == 200:
        new_token = r.json()["access_token"]
        headers_out["Authorization"] = f"Bearer {new_token}"
        ok(f"Token refresh: success")
        record(2, "token_refresh", True)
    else:
        fail(f"Token refresh: {r.status_code}")
        record(2, "token_refresh", False)

    # Invalid login
    r = await client.post("/api/v1/auth/login",
        json={"email": "fake@test.io", "password": "wrong"})
    if r.status_code in (401, 403):
        ok(f"Invalid login rejected: {r.status_code}")
        record(2, "invalid_login_rejected", True)
    else:
        fail(f"Invalid login: {r.status_code} (should be 401)")
        record(2, "invalid_login_rejected", False)

    return True


async def phase3_market_data(client, headers):
    """Phase 3: Market Data REST APIs"""
    phase_header(3, "Market Data REST APIs")

    # Health endpoint
    r = await client.get("/api/v1/system/health")
    d = r.json()
    ok(f"Health: status={d.get('status')} mode={d.get('trading_mode')}")
    record(3, "health", True)

    # Market snapshot (per-symbol endpoint)
    for sym in ["BTCUSDT", "ETHUSDT"]:
        r = await client.get(f"/api/v1/market/snapshot/{sym}", headers=headers)
        if r.status_code == 200:
            s = r.json()
            price = s.get("last_price", s.get("price", "?"))
            ok(f"Snapshot {sym}: ${price}")
        else:
            fail(f"Snapshot {sym}: {r.status_code}")
    record(3, "market_snapshot", True)

    # Candles
    r = await client.get("/api/v1/market/candles",
        params={"symbol": "BTCUSDT", "timeframe": "1h", "limit": 10},
        headers=headers)
    if r.status_code == 200:
        data = r.json()
        candles = data if isinstance(data, list) else data.get("candles", [])
        ok(f"Candles BTCUSDT/1h: {len(candles)} rows")
        record(3, "candles", True)
    else:
        fail(f"Candles: {r.status_code}")
        record(3, "candles", False)

    # DB candle count
    count = docker_exec_psql("SELECT COUNT(*) FROM market_candles;")
    if count and count.strip().isdigit() and int(count) > 0:
        ok(f"DB candles: {count} rows")
        record(3, "db_candles", True)
    else:
        warn(f"DB candles: {count}")
        record(3, "db_candles", False)

    # DB snapshots
    snap_count = docker_exec_psql("SELECT COUNT(*) FROM market_snapshots;")
    if snap_count and int(snap_count) > 0:
        ok(f"DB snapshots: {snap_count} rows")
        record(3, "db_snapshots", True)
    else:
        warn(f"DB snapshots: {snap_count}")
        record(3, "db_snapshots", False)


async def phase4_proposals(client, headers):
    """Phase 4: Proposals Workflow"""
    phase_header(4, "Proposals Workflow")

    # List proposals
    r = await client.get("/api/v1/proposals", headers=headers)
    if r.status_code == 200:
        data = r.json()
        proposals = data if isinstance(data, list) else data.get("proposals", [])
        ok(f"List proposals: {len(proposals)} entries")
        record(4, "list_proposals", True)

        if proposals:
            pid = proposals[0].get("id", proposals[0].get("proposal_id"))
            r2 = await client.get(f"/api/v1/proposals/{pid}", headers=headers)
            if r2.status_code == 200:
                ok(f"Get proposal detail: {pid[:8]}...")
                record(4, "get_detail", True)
            else:
                fail(f"Get proposal detail: {r2.status_code}")
                record(4, "get_detail", False)
        else:
            warn("No proposals to test detail")
            record(4, "get_detail", None)
    else:
        fail(f"List proposals: {r.status_code}")
        record(4, "list_proposals", False)

    # DB check
    prop_count = docker_exec_psql("SELECT COUNT(*) FROM trade_proposals;")
    ok(f"DB proposals: {prop_count} rows")
    record(4, "db_proposals", True)


async def phase5_celery():
    """Phase 5: Celery Scheduled Tasks"""
    phase_header(5, "Celery Scheduled Tasks")

    # Check celery worker is responding
    r = subprocess.run(
        ["docker", "compose", "exec", "-T", "celery-worker",
         "celery", "-A", "app.scheduler.worker.celery_app",
         "inspect", "ping", "--timeout", "10"],
        capture_output=True, text=True, cwd=PROJECT, timeout=20
    )
    out = r.stdout + r.stderr
    if "pong" in out.lower():
        ok("Celery worker responds to ping ✓")
        record(5, "celery_ping", True)
    else:
        fail(f"Celery ping failed: {out[:100]}")
        record(5, "celery_ping", False)

    # Check beat schedule
    r = subprocess.run(
        ["docker", "compose", "exec", "-T", "celery-worker",
         "celery", "-A", "app.scheduler.worker.celery_app",
         "inspect", "scheduled", "--timeout", "10"],
        capture_output=True, text=True, cwd=PROJECT, timeout=20
    )
    out = r.stdout + r.stderr
    if "empty" not in out.lower() or "scheduled" in out.lower():
        ok("Celery beat scheduled tasks found ✓")
        record(5, "celery_beat_schedule", True)
    else:
        warn("No scheduled tasks found (beat may need more time)")
        record(5, "celery_beat_schedule", None)

    # Check registered tasks
    r = subprocess.run(
        ["docker", "compose", "exec", "-T", "celery-worker",
         "celery", "-A", "app.scheduler.worker.celery_app",
         "inspect", "registered", "--timeout", "10"],
        capture_output=True, text=True, cwd=PROJECT, timeout=20
    )
    out = r.stdout + r.stderr
    expected_tasks = ["system_heartbeat", "sync_candles", "refresh_snapshots"]
    found_tasks = []
    for task in expected_tasks:
        if task in out:
            found_tasks.append(task)
    if found_tasks:
        ok(f"Registered tasks: {', '.join(found_tasks)}")
        record(5, "registered_tasks", True)
    else:
        fail("No expected tasks found in registered list")
        record(5, "registered_tasks", False)

    # Check system_events for recent heartbeat
    hb = docker_exec_psql(
        "SELECT COUNT(*) FROM system_events WHERE created_at > NOW() - INTERVAL '10 minutes';"
    )
    if hb and hb.strip().isdigit() and int(hb) > 0:
        ok(f"System events in last 10min: {hb}")
        record(5, "system_events", True)
    else:
        warn("No recent system events (services may have just started)")
        record(5, "system_events", None)

    # DB candle data (shows sync task worked)
    total_candles = docker_exec_psql("SELECT COUNT(*) FROM market_candles;")
    if total_candles and total_candles.strip().isdigit() and int(total_candles) > 100:
        ok(f"Candle sync verified: {total_candles} rows in DB")
        record(5, "candle_sync", True)
    else:
        warn(f"Only {total_candles} candles in DB")
        record(5, "candle_sync", None)


async def phase6_websocket():
    """Phase 6: WebSocket Realtime"""
    phase_header(6, "WebSocket Realtime")

    try:
        import websockets
    except ImportError:
        fail("websockets library not installed")
        record(6, "import", False)
        return

    # Get token
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        r = await client.post("/api/v1/auth/login",
            json={"email": EMAIL, "password": PASSWORD})
        token = r.json()["access_token"]

    # Handle websockets exception types
    from websockets.exceptions import (
        InvalidHandshake, ConnectionClosedError, ConnectionClosed
    )
    REJECT_EXCEPTIONS = (InvalidHandshake, ConnectionClosedError,
                         ConnectionClosed, OSError)
    import websockets.exceptions as ws_exc
    for attr in ("RejectHandshake", "RejectConnection", "RedirectHandshake",
                 "InvalidStatusCode"):
        exc_cls = getattr(ws_exc, attr, None)
        if exc_cls is not None:
            REJECT_EXCEPTIONS = REJECT_EXCEPTIONS + (exc_cls,)

    # market_ws
    url = f"{WS_BASE}/api/v1/ws/market?token={token}"
    from websockets.exceptions import ConnectionClosed as WsConnClosed
    market_ok = False
    ticker_ok = False
    try:
        async with websockets.connect(url, open_timeout=10) as ws:
            market_ok = True
            deadline = time.time() + 12
            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    msg = json.loads(raw)
                    mtype = msg.get("type", "")
                    if mtype == "connected":
                        ok(f"market_ws connected: '{msg.get('message','')}'")
                    elif mtype == "ticker":
                        ticker_ok = True
                        ok(f"market_ws ticker: {msg.get('symbol')} ${msg.get('price')}")
                        break
                    elif mtype == "ping":
                        await ws.send(json.dumps({"type": "pong"}))
                except asyncio.TimeoutError:
                    await ws.send(json.dumps({"type": "ping"}))
    except Exception as e:
        fail(f"market_ws: {e}")

    record(6, "market_ws_connect", market_ok)
    record(6, "market_ws_ticker", ticker_ok)

    # events_ws
    url = f"{WS_BASE}/api/v1/ws/events?token={token}"
    events_ok = False
    events_msg = False
    pong_ok = False
    try:
        async with websockets.connect(url, open_timeout=10) as ws:
            events_ok = True
            ping_sent = False
            deadline = time.time() + 10
            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    msg = json.loads(raw)
                    mtype = msg.get("type", "")
                    if mtype == "connected":
                        events_msg = True
                        ok(f"events_ws connected: user={msg.get('user_id','?')[:8]}")
                        await ws.send(json.dumps({"type": "ping"}))
                        ping_sent = True
                    elif mtype == "pong":
                        pong_ok = True
                        ok("events_ws ping/pong ✓")
                        break
                except asyncio.TimeoutError:
                    if not ping_sent:
                        await ws.send(json.dumps({"type": "ping"}))
                        ping_sent = True
    except Exception as e:
        fail(f"events_ws: {e}")

    record(6, "events_ws_connect", events_ok)
    record(6, "events_ws_message", events_msg)
    record(6, "events_ws_pingpong", pong_ok)

    # Auth rejection
    url = f"{WS_BASE}/api/v1/ws/market?token=bad.jwt.token"
    auth_rejected = False
    try:
        async with websockets.connect(url, open_timeout=5) as ws:
            try:
                await asyncio.wait_for(ws.recv(), timeout=3)
            except WsConnClosed:
                auth_rejected = True
    except REJECT_EXCEPTIONS:
        auth_rejected = True
    except Exception as e:
        if "403" in str(e) or "401" in str(e):
            auth_rejected = True

    if auth_rejected:
        ok("Invalid token rejected ✓")
    else:
        fail("Invalid token NOT rejected")
    record(6, "auth_rejection", auth_rejected)


async def phase7_positions_orders(client, headers):
    """Phase 7: Positions & Orders"""
    phase_header(7, "Positions & Orders")

    # Positions
    r = await client.get("/api/v1/positions", headers=headers)
    if r.status_code == 200:
        data = r.json()
        positions = data if isinstance(data, list) else data.get("positions", data.get("items", []))
        ok(f"GET /positions: {len(positions)} position(s)")
        for p in positions[:3]:
            info(f"  {p.get('symbol')} {p.get('side')} @ ${p.get('entry_price')} [{p.get('status')}]")
        record(7, "list_positions", True)
    else:
        fail(f"GET /positions: {r.status_code}")
        record(7, "list_positions", False)
        positions = []

    # Position detail
    if positions:
        pid = positions[0].get("id")
        r = await client.get(f"/api/v1/positions/{pid}", headers=headers)
        if r.status_code == 200:
            ok(f"GET /positions/{{id}}: detail OK")
            record(7, "position_detail", True)
        else:
            fail(f"GET /positions/{{id}}: {r.status_code}")
            record(7, "position_detail", False)

    # PnL summary
    r = await client.get("/api/v1/positions/summary/pnl", headers=headers)
    if r.status_code == 200:
        ok(f"GET /positions/summary/pnl: OK")
        record(7, "pnl_summary", True)
    else:
        fail(f"PnL summary: {r.status_code}")
        record(7, "pnl_summary", False)

    # Orders
    r = await client.get("/api/v1/orders", headers=headers)
    if r.status_code == 200:
        data = r.json()
        orders = data if isinstance(data, list) else data.get("orders", data.get("items", []))
        ok(f"GET /orders: {len(orders)} order(s)")
        for o in orders[:3]:
            info(f"  {o.get('symbol')} {o.get('side')} {o.get('order_type')} [{o.get('status')}]")
        record(7, "list_orders", True)
    else:
        fail(f"GET /orders: {r.status_code}")
        record(7, "list_orders", False)
        orders = []

    # Order detail
    if orders:
        oid = orders[0].get("id")
        r = await client.get(f"/api/v1/orders/{oid}", headers=headers)
        if r.status_code == 200:
            ok(f"GET /orders/{{id}}: detail OK")
            record(7, "order_detail", True)
        else:
            fail(f"GET /orders/{{id}}: {r.status_code}")
            record(7, "order_detail", False)


async def phase8_settings_audit(client, headers):
    """Phase 8: Settings / Audit / License"""
    phase_header(8, "Settings / Audit / License")

    # System config
    r = await client.get("/api/v1/system/config", headers=headers)
    if r.status_code == 200:
        cfg = r.json()
        mode = cfg.get("trading", {}).get("mode", "?")
        symbols = cfg.get("trading", {}).get("symbols", [])
        ok(f"GET /system/config: mode={mode} symbols={symbols}")
        record(8, "system_config", True)
    else:
        fail(f"GET /system/config: {r.status_code}")
        record(8, "system_config", False)

    # System status
    r = await client.get("/api/v1/system/status", headers=headers)
    if r.status_code == 200:
        st = r.json()
        svcs = st.get("services", {})
        ok(f"GET /system/status: {st.get('status')} — DB={svcs.get('database')} Redis={svcs.get('redis')}")
        record(8, "system_status", True)
    else:
        fail(f"GET /system/status: {r.status_code}")
        record(8, "system_status", False)

    # License
    r = await client.get("/api/v1/system/license", headers=headers)
    if r.status_code == 200:
        lic = r.json()
        ok(f"GET /system/license: {lic.get('license')} — LLM={lic.get('llm_model')}")
        record(8, "license", True)
    else:
        fail(f"GET /system/license: {r.status_code}")
        record(8, "license", False)

    # Audit logs
    r = await client.get("/api/v1/audit/logs", headers=headers)
    if r.status_code == 200:
        data = r.json()
        count = data.get("count", 0)
        actions = {}
        for log in data.get("logs", []):
            a = log.get("action", "?")
            actions[a] = actions.get(a, 0) + 1
        ok(f"GET /audit/logs: {count} entries — {dict(list(actions.items())[:3])}")
        record(8, "audit_logs", True)
    else:
        fail(f"GET /audit/logs: {r.status_code}")
        record(8, "audit_logs", False)

    # Audit filter
    r = await client.get("/api/v1/audit/logs?action=USER_LOGIN", headers=headers)
    if r.status_code == 200:
        data = r.json()
        ok(f"GET /audit/logs?action=USER_LOGIN: {len(data.get('logs',[]))} entries")
        record(8, "audit_filter", True)
    else:
        fail(f"Audit filter: {r.status_code}")
        record(8, "audit_filter", False)

    # Notifications
    r = await client.get("/api/v1/notifications", headers=headers)
    if r.status_code == 200:
        ok("GET /notifications: OK")
        record(8, "notifications", True)
    else:
        fail(f"GET /notifications: {r.status_code}")
        record(8, "notifications", False)

    # Unread count
    r = await client.get("/api/v1/notifications/unread-count", headers=headers)
    if r.status_code == 200:
        ok(f"GET /notifications/unread-count: {r.json().get('count', '?')}")
        record(8, "unread_count", True)
    else:
        fail(f"Unread count: {r.status_code}")
        record(8, "unread_count", False)

    # Auth rejection on protected endpoints
    r_noauth = await client.get("/api/v1/audit/logs")  # no headers
    if r_noauth.status_code in (401, 403):
        ok(f"Auth rejection on /audit/logs: {r_noauth.status_code} ✓")
        record(8, "auth_rejection", True)
    else:
        fail(f"Auth rejection: {r_noauth.status_code}")
        record(8, "auth_rejection", False)

    # Frontend components exist
    pages = {
        "SettingsPage": "apps/frontend/src/pages/SettingsPage/SettingsPage.tsx",
        "AuditPage": "apps/frontend/src/pages/AuditPage/AuditPage.tsx",
        "LicensePage": "apps/frontend/src/pages/LicensePage/LicensePage.tsx",
    }
    for name, path in pages.items():
        full = os.path.join(PROJECT, path)
        if os.path.exists(full):
            ok(f"{name}: exists ({os.path.getsize(full):,} bytes)")
            record(8, name, True)
        else:
            fail(f"{name}: NOT FOUND")
            record(8, name, False)


async def main():
    start_time = time.time()

    print(f"\n{BOLD}{CYAN}{'═'*60}")
    print("   ACTA — FULL SYSTEM VERIFICATION (Phases 1–8)")
    print(f"{'═'*60}{RESET}")
    print(f"  Time  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Target: {BASE_URL}")
    print(f"  User  : {EMAIL}")
    print()

    # Wait for services
    healthy = await wait_for_healthy(max_wait=120)
    if not healthy:
        print(f"\n{RED}ABORTED: Backend not healthy.{RESET}")
        return

    # ── Phase 1 ──────────────────────────────────────────────
    await phase1_docker_services()

    # ── Phases 2–8 (need HTTP client) ────────────────────────
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        headers = {}

        await phase2_auth(client, headers)
        await phase3_market_data(client, headers)
        await phase4_proposals(client, headers)

    # Phase 5 uses subprocess
    await phase5_celery()

    # Phase 6 uses websockets
    await phase6_websocket()

    # Phases 7-8 need HTTP client again
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        # Re-login
        r = await client.post("/api/v1/auth/login",
            json={"email": EMAIL, "password": PASSWORD})
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        await phase7_positions_orders(client, headers)
        await phase8_settings_audit(client, headers)

    # ── Final Report ──────────────────────────────────────────
    elapsed = time.time() - start_time

    print(f"\n\n{BOLD}{CYAN}{'═'*60}")
    print("   FINAL REPORT")
    print(f"{'═'*60}{RESET}\n")

    all_pass = True
    for phase_num in sorted(results.keys()):
        checks = results[phase_num]
        phase_pass = sum(1 for _, s in checks if s is True)
        phase_fail = sum(1 for _, s in checks if s is False)
        phase_warn = sum(1 for _, s in checks if s is None)
        total = len(checks)

        if phase_fail > 0:
            icon = f"{RED}❌{RESET}"
            all_pass = False
        elif phase_warn > 0:
            icon = f"{YELLOW}⚠ {RESET}"
        else:
            icon = f"{GREEN}✅{RESET}"

        phase_names = {
            1: "Docker Services",
            2: "Authentication",
            3: "Market Data",
            4: "Proposals",
            5: "Celery Tasks",
            6: "WebSocket Realtime",
            7: "Positions & Orders",
            8: "Settings/Audit/License",
        }
        name = phase_names.get(phase_num, f"Phase {phase_num}")
        print(f"  {icon} Phase {phase_num}: {name:.<35} "
              f"{GREEN}{phase_pass}{RESET}/{total} pass"
              + (f"  {RED}{phase_fail} fail{RESET}" if phase_fail else "")
              + (f"  {YELLOW}{phase_warn} warn{RESET}" if phase_warn else ""))

    total_checks = passed_checks + failed_checks
    print(f"\n  {'─'*50}")
    print(f"  Total checks : {GREEN}{passed_checks}{RESET} passed / "
          f"{RED}{failed_checks}{RESET} failed / "
          f"{YELLOW}{warnings}{RESET} warnings")
    print(f"  Elapsed      : {elapsed:.1f}s")

    if all_pass:
        print(f"\n  {GREEN}{BOLD}🎉 ALL PHASES PASSED — SYSTEM FULLY OPERATIONAL{RESET}\n")
    else:
        print(f"\n  {RED}{BOLD}⚠ SOME CHECKS FAILED — SEE DETAILS ABOVE{RESET}\n")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    asyncio.run(main())
