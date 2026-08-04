#!/usr/bin/env python3
"""
Phase 6: WebSocket Realtime Test
- /api/v1/ws/market  — price stream từ Binance
- /api/v1/ws/events  — system events (proposals, orders, positions)
- Test: connect, auth, receive messages, ping/pong, disconnect
"""

import asyncio
import json
import time
import httpx
import websockets
from datetime import datetime

BASE_URL   = "http://localhost:8000"
WS_BASE    = "ws://localhost:8000"
EMAIL      = "admin@acta.io"
PASSWORD   = "Admin@acta2024!"

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


async def get_token() -> str:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        r = await client.post("/api/v1/auth/login",
            json={"email": EMAIL, "password": PASSWORD})
        return r.json()["access_token"]


async def test_market_ws(token: str) -> dict:
    """Test /api/v1/ws/market endpoint."""
    url = f"{WS_BASE}/api/v1/ws/market?token={token}"
    results = {
        "connected": False,
        "received_msgs": [],
        "ping_pong": False,
        "subscribe_ack": False,
        "ticker_received": False,
        "kline_received": False,
        "disconnect_clean": False,
        "errors": [],
    }

    try:
        async with websockets.connect(url, open_timeout=10) as ws:
            results["connected"] = True
            ok("market_ws: Connected ✓")

            # Collect messages for 15s or until we get enough
            deadline = time.time() + 15
            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    msg = json.loads(raw)
                    results["received_msgs"].append(msg)
                    mtype = msg.get("type", "")

                    if mtype == "connected":
                        ok(f"  Received: connected — '{msg.get('message','')}'")
                    elif mtype == "ticker":
                        if not results["ticker_received"]:
                            results["ticker_received"] = True
                            ok(f"  Ticker: {msg.get('symbol')} price={msg.get('price')} vol={msg.get('volume')}")
                    elif mtype == "kline":
                        if not results["kline_received"]:
                            results["kline_received"] = True
                            ok(f"  Kline: {msg.get('symbol')} tf={msg.get('timeframe')} close={msg.get('close')}")
                    elif mtype == "ping":
                        info(f"  Server ping received → sending pong")
                        await ws.send(json.dumps({"type": "pong"}))
                    elif mtype == "pong":
                        results["ping_pong"] = True
                        ok(f"  Ping/Pong ✓")
                    else:
                        info(f"  Msg: {mtype} — {str(msg)[:80]}")

                    # Send ping after first message
                    if len(results["received_msgs"]) == 1:
                        await ws.send(json.dumps({"type": "ping"}))

                    # Send subscribe after 2nd message
                    if len(results["received_msgs"]) == 2:
                        await ws.send(json.dumps({
                            "type": "subscribe",
                            "symbols": ["BTCUSDT", "ETHUSDT"]
                        }))

                    # Subscribe ack
                    if mtype == "subscribed":
                        results["subscribe_ack"] = True
                        ok(f"  Subscribe ACK: symbols={msg.get('symbols')}")

                    # Break early if we have enough data
                    if (results["ping_pong"] and results["ticker_received"]
                            and len(results["received_msgs"]) >= 3):
                        break

                except asyncio.TimeoutError:
                    # No message in 5s — send ping to keep alive
                    await ws.send(json.dumps({"type": "ping"}))

            # Clean disconnect
            await ws.close()
            results["disconnect_clean"] = True

    except websockets.exceptions.InvalidStatusCode as e:
        results["errors"].append(f"HTTP {e.status_code}: {e}")
        fail(f"market_ws connection rejected: {e}")
    except Exception as e:
        results["errors"].append(str(e))
        fail(f"market_ws error: {e}")

    return results


async def test_events_ws(token: str) -> dict:
    """Test /api/v1/ws/events endpoint."""
    url = f"{WS_BASE}/api/v1/ws/events?token={token}"
    results = {
        "connected": False,
        "connected_msg": False,
        "ping_pong": False,
        "received_msgs": [],
        "disconnect_clean": False,
        "errors": [],
    }

    try:
        async with websockets.connect(url, open_timeout=10) as ws:
            results["connected"] = True
            ok("events_ws: Connected ✓")

            deadline = time.time() + 12
            ping_sent = False

            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    msg = json.loads(raw)
                    results["received_msgs"].append(msg)
                    mtype = msg.get("type", "")

                    if mtype == "connected":
                        results["connected_msg"] = True
                        ok(f"  Received: connected — '{msg.get('message','')}'")
                        info(f"  user_id: {msg.get('user_id','?')}")

                    elif mtype in ("proposal_update", "analysis_complete",
                                   "order_filled", "position_update"):
                        ok(f"  Event: {mtype} — {str(msg)[:80]}")

                    elif mtype == "ping":
                        info(f"  Server ping → sending pong")
                        await ws.send(json.dumps({"type": "pong"}))

                    elif mtype == "pong":
                        results["ping_pong"] = True
                        ok("  Ping/Pong ✓")

                    else:
                        info(f"  Msg: {mtype}")

                    # Send ping after receiving connected
                    if mtype == "connected" and not ping_sent:
                        await ws.send(json.dumps({"type": "ping"}))
                        ping_sent = True

                    if results["ping_pong"] and results["connected_msg"]:
                        break

                except asyncio.TimeoutError:
                    if not ping_sent:
                        await ws.send(json.dumps({"type": "ping"}))
                        ping_sent = True

            await ws.close()
            results["disconnect_clean"] = True

    except websockets.exceptions.InvalidStatusCode as e:
        results["errors"].append(f"HTTP {e.status_code}: {e}")
        fail(f"events_ws connection rejected: {e}")
    except Exception as e:
        results["errors"].append(str(e))
        fail(f"events_ws error: {e}")

    return results


async def test_invalid_token_rejected():
    """Verify unauthenticated connections are rejected."""
    results = {"market_rejected": False, "events_rejected": False,
               "no_token_rejected": False}

    # Bad token and no token cases — websockets 15.x raises different exceptions
    REJECT_EXCEPTIONS = (
        websockets.exceptions.InvalidHandshake,
        websockets.exceptions.ConnectionClosedError,
        websockets.exceptions.ConnectionClosed,
        OSError,
    )
    # Handle version-specific exceptions
    for attr in ("RejectHandshake", "RejectConnection", "RedirectHandshake",
                 "InvalidStatusCode"):
        exc_cls = getattr(websockets.exceptions, attr, None)
        if exc_cls is not None:
            REJECT_EXCEPTIONS = REJECT_EXCEPTIONS + (exc_cls,)

    for endpoint, key in [("market", "market_rejected"), ("events", "events_rejected")]:
        url = f"{WS_BASE}/api/v1/ws/{endpoint}?token=invalid.jwt.token"
        try:
            async with websockets.connect(url, open_timeout=5) as ws:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=3)
                    warn(f"  {endpoint}: Got message with bad token: {msg[:50]}")
                except websockets.exceptions.ConnectionClosed as e:
                    results[key] = True
                    ok(f"  {endpoint}: Bad token rejected (code={e.code}) ✓")
        except REJECT_EXCEPTIONS as e:
            results[key] = True
            ok(f"  {endpoint}: Bad token rejected (HTTP 403) ✓")
        except Exception as e:
            if "403" in str(e) or "401" in str(e) or "rejected" in str(e).lower():
                results[key] = True
                ok(f"  {endpoint}: Bad token rejected ✓")
            else:
                warn(f"  {endpoint}: {e}")

    # No token
    url = f"{WS_BASE}/api/v1/ws/market"
    try:
        async with websockets.connect(url, open_timeout=5) as ws:
            try:
                await asyncio.wait_for(ws.recv(), timeout=3)
            except websockets.exceptions.ConnectionClosed as e:
                results["no_token_rejected"] = True
                ok(f"  No-token: rejected (code={e.code}) ✓")
    except REJECT_EXCEPTIONS as e:
        results["no_token_rejected"] = True
        ok("  No-token: rejected (HTTP 403) ✓")
    except Exception as e:
        if "403" in str(e) or "401" in str(e) or "rejected" in str(e).lower():
            results["no_token_rejected"] = True
            ok("  No-token: rejected ✓")
        else:
            warn(f"  No-token check: {e}")

    return results


async def test_concurrent_connections(token: str) -> bool:
    """Test multiple simultaneous WS connections."""
    url = f"{WS_BASE}/api/v1/ws/events?token={token}"
    conns = []
    ok_count = 0

    try:
        for i in range(3):
            try:
                ws = await websockets.connect(url, open_timeout=5)
                conns.append(ws)
                ok_count += 1
            except Exception as e:
                warn(f"  Connection {i+1} failed: {e}")

        if ok_count >= 2:
            ok(f"  {ok_count}/3 concurrent connections established ✓")
            return True
        else:
            warn(f"  Only {ok_count}/3 connections established")
            return False
    finally:
        for ws in conns:
            try:
                await ws.close()
            except Exception:
                pass


async def main():
    print(f"\n{BOLD}{'='*60}")
    print("PHASE 6 — WEBSOCKET REALTIME TEST")
    print(f"{'='*60}{RESET}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # ── Login ────────────────────────────────────────────────────
    step(1, "Login & Get JWT Token")
    try:
        token = await get_token()
        ok(f"Token obtained: {token[:20]}...")
    except Exception as e:
        fail(f"Login failed: {e}")
        return

    # ── Step 02: market_ws ────────────────────────────────────────
    step(2, "ws://localhost:8000/api/v1/ws/market  (price stream)")
    info("Connecting to market WebSocket... (up to 15s)")
    market_result = await test_market_ws(token)

    print(f"\n  {BOLD}Market WS Summary:{RESET}")
    checks = [
        ("connected",        "WebSocket connected"),
        ("ping_pong",        "Ping/Pong working"),
        ("subscribe_ack",    "Subscribe command ACK"),
        ("ticker_received",  "Ticker message received"),
        ("kline_received",   "Kline message received"),
        ("disconnect_clean", "Clean disconnect"),
    ]
    for key, label in checks:
        val = market_result.get(key, False)
        (ok if val else warn)(f"{label}: {'✓' if val else 'not received yet'}")

    total_msgs = len(market_result["received_msgs"])
    info(f"Total messages received: {total_msgs}")
    if market_result["errors"]:
        for e in market_result["errors"]:
            fail(f"Error: {e}")

    # ── Step 03: events_ws ────────────────────────────────────────
    step(3, "ws://localhost:8000/api/v1/ws/events  (event stream)")
    info("Connecting to events WebSocket... (up to 12s)")
    events_result = await test_events_ws(token)

    print(f"\n  {BOLD}Events WS Summary:{RESET}")
    checks = [
        ("connected",        "WebSocket connected"),
        ("connected_msg",    "'connected' message received"),
        ("ping_pong",        "Ping/Pong working"),
        ("disconnect_clean", "Clean disconnect"),
    ]
    for key, label in checks:
        val = events_result.get(key, False)
        (ok if val else warn)(f"{label}: {'✓' if val else 'not received yet'}")

    total_msgs = len(events_result["received_msgs"])
    info(f"Total messages received: {total_msgs}")
    if events_result["errors"]:
        for e in events_result["errors"]:
            fail(f"Error: {e}")

    # ── Step 04: Auth Rejection ───────────────────────────────────
    step(4, "Security — Invalid Token Rejected")
    auth_result = await test_invalid_token_rejected()
    if all(auth_result.values()):
        ok("All invalid token cases rejected correctly ✓")
    else:
        for k, v in auth_result.items():
            (ok if v else warn)(f"  {k}: {'✓' if v else 'not rejected'}")

    # ── Step 05: Concurrent Connections ──────────────────────────
    step(5, "Concurrent WebSocket Connections (3x events_ws)")
    concurrent_ok = await test_concurrent_connections(token)
    if concurrent_ok:
        ok("Multiple concurrent connections supported ✓")

    # ── Step 06: Backend WS logs ──────────────────────────────────
    step(6, "Backend WebSocket Logs")
    import subprocess
    result = subprocess.run(
        ["docker", "compose", "logs", "backend", "--tail=20"],
        capture_output=True, text=True,
        cwd="/home/vietpv/Desktop/bot-finance"
    )
    logs = result.stdout + result.stderr
    ws_events = [l for l in logs.split('\n') if 'ws_client' in l or 'events_ws' in l]
    if ws_events:
        ok(f"WS events in backend logs ({len(ws_events)}):")
        for l in ws_events[-5:]:
            info(f"  {l.strip()[:100]}")
    else:
        warn("No WS events in recent backend logs")

    # ── Summary ───────────────────────────────────────────────────
    print(f"\n{BOLD}{'='*60}")
    print("PHASE 6 SUMMARY")
    print(f"{'='*60}{RESET}\n")

    m = market_result
    e = events_result

    rows = [
        ("market_ws connect",     m["connected"]),
        ("market_ws ping/pong",   m["ping_pong"]),
        ("market_ws ticker",      m["ticker_received"]),
        ("market_ws kline",       m["kline_received"]),
        ("events_ws connect",     e["connected"]),
        ("events_ws connected msg", e["connected_msg"]),
        ("events_ws ping/pong",   e["ping_pong"]),
        ("auth rejection",        all(auth_result.values())),
        ("concurrent conns",      concurrent_ok),
    ]
    passed = sum(1 for _, v in rows if v)
    total  = len(rows)

    for label, passed_flag in rows:
        sym = "✅" if passed_flag else "⚠ "
        print(f"  {sym} {label}")

    print(f"\n  Score: {passed}/{total} checks passed")
    print()


if __name__ == "__main__":
    asyncio.run(main())
