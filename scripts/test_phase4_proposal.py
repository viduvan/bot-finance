#!/usr/bin/env python3
"""
Phase 4: Proposal Lifecycle Test
- Inject proposal trực tiếp vào DB (bypass volume gate)
- Test API: list → get → approve-token → approve → execute
- Test positions API sau khi execute
"""

import asyncio
import sys
import json
import subprocess
from datetime import UTC, datetime, timedelta
import httpx

BASE_URL = "http://localhost:8000"
EMAIL = "admin@acta.io"
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


def run_psql(sql: str) -> str:
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres",
         "psql", "-U", "acta", "-d", "acta", "-c", sql],
        capture_output=True, text=True,
        cwd="/home/vietpv/Desktop/bot-finance"
    )
    return result.stdout + result.stderr


async def main():
    print(f"\n{BOLD}{'='*60}")
    print("PHASE 4 — PROPOSAL LIFECYCLE TEST")
    print(f"{'='*60}{RESET}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    proposal_id = None

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:

        # ── Step 01: Health ───────────────────────────────────────────
        step(1, "Health Check")
        r = await client.get("/api/v1/system/health")
        d = r.json()
        if d.get("status") == "healthy":
            ok(f"Backend healthy — mode={d.get('trading_mode')} v={d.get('version')}")
        else:
            fail(f"Backend unhealthy: {d}")
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

        # ── Step 03: BTC Price ────────────────────────────────────────
        step(3, "Get Current BTC Price")
        r = await client.get("/api/v1/market/ticker/BTCUSDT", headers=headers)
        if r.status_code == 200:
            current_price = float(r.json().get("last_price", 63000))
            ok(f"BTC price: ${current_price:,.2f}")
        else:
            current_price = 63000.0
            warn(f"Ticker unavailable, using ${current_price:,.2f}")

        # ── Step 04: Inject Proposal into DB ──────────────────────────
        step(4, "Inject PENDING Proposal into DB (bypass volume gate)")

        entry = current_price
        sl    = round(entry * 0.985, 2)
        tp1   = round(entry * 1.03, 2)
        qty   = round(500 / entry, 6)
        rr    = round((tp1 - entry) / (entry - sl), 2)
        expires = (datetime.now(UTC) + timedelta(hours=4)).isoformat()

        sql = f"""
INSERT INTO trade_proposals (
    id, symbol, market, recommendation, status,
    current_price, entry_zone_min, entry_zone_max,
    suggested_order_type, suggested_price, suggested_quantity,
    stop_loss_price, take_profit_prices,
    estimated_risk_amount, estimated_profit_amount,
    risk_reward_ratio, confidence,
    supporting_reasons, risk_warnings, critic_objections,
    agent_consensus, environment, version,
    expires_at
) VALUES (
    gen_random_uuid(),
    'BTCUSDT', 'SPOT', 'BUY', 'PENDING_REVIEW',
    {entry}, {round(entry*0.998,2)}, {round(entry*1.002,2)},
    'LIMIT', {entry}, {qty},
    {sl}, '{{"tp1": {tp1}}}',
    {round(qty*(entry-sl),4)}, {round(qty*(tp1-entry),4)},
    {rr}, 0.75,
    '["EMA bearish stack signal reversal", "Price near VWAP support", "MACD bullish cross forming"]',
    '["Low volume environment - exercise caution"]',
    '[]',
    '{{"market_regime": 0.6, "technical": 0.7, "order_flow": 0.4}}',
    'PAPER', 1,
    '{expires}'
) RETURNING id::text;
"""
        result = run_psql(sql)
        # Parse the returned UUID from output
        proposal_id = None
        for line in result.split('\n'):
            line = line.strip()
            if len(line) == 36 and line.count('-') == 4:
                proposal_id = line
                break

        if proposal_id:
            ok(f"Proposal created in DB:")
            info(f"  id        = {proposal_id[:8]}...")
            info(f"  symbol    = BTCUSDT")
            info(f"  recommend = BUY  status = PENDING")
            info(f"  price     = ${entry:,.2f}")
            info(f"  stop_loss = ${sl:,.2f}  (-1.5%)")
            info(f"  take_prof = ${tp1:,.2f}  (+3.0%)")
            info(f"  qty       = {qty} BTC  (≈ $500)")
            info(f"  R:R ratio = {rr}")
        else:
            fail(f"DB insert failed: {result}")
            return

        await asyncio.sleep(1)

        # ── Step 05: List Proposals ───────────────────────────────────
        step(5, "List Proposals via GET /api/v1/proposals")
        r = await client.get("/api/v1/proposals?limit=20", headers=headers)
        if r.status_code != 200:
            fail(f"List proposals: {r.status_code} {r.text[:100]}")
        else:
            data = r.json()
            all_p = data.get("proposals", [])
            pending = [p for p in all_p if p.get("status") == "PENDING"]
            ok(f"Response: total={data.get('total',0)}, returned={len(all_p)}, PENDING={len(pending)}")
            if pending:
                p0 = pending[0]
                info(f"  First PENDING: id={str(p0.get('id',''))[:8]}... rec={p0.get('recommendation')}")

        # ── Step 06: Active Proposals ─────────────────────────────────
        step(6, "GET /api/v1/proposals/active")
        r = await client.get("/api/v1/proposals/active", headers=headers)
        if r.status_code == 200:
            active = r.json()
            active_list = active.get("proposals", [])
            ok(f"Active proposals: {len(active_list)}")
        else:
            warn(f"Active: {r.status_code} — {r.text[:100]}")

        # ── Step 07: Get Single Proposal ──────────────────────────────
        step(7, f"GET /api/v1/proposals/{proposal_id[:8]}...")
        r = await client.get(f"/api/v1/proposals/{proposal_id}", headers=headers)
        if r.status_code == 200:
            p = r.json()
            ok(f"Proposal detail:")
            info(f"  status         : {p.get('status')}")
            info(f"  recommendation : {p.get('recommendation')}")
            info(f"  suggested_price: {p.get('suggested_price')}")
            info(f"  stop_loss_price: {p.get('stop_loss_price')}")
            info(f"  take_profit    : {p.get('take_profit_prices')}")
            info(f"  suggested_qty  : {p.get('suggested_quantity')}")
            info(f"  risk_reward    : {p.get('risk_reward_ratio')}")
            info(f"  confidence     : {p.get('confidence')}")
            info(f"  environment    : {p.get('environment')}")
        else:
            fail(f"Get proposal: {r.status_code} {r.text[:200]}")

        # ── Step 08: Approval Token ───────────────────────────────────
        step(8, "POST /api/v1/proposals/{id}/approval-token")
        r = await client.post(
            f"/api/v1/proposals/{proposal_id}/approval-token",
            headers=headers
        )
        approval_token = None
        if r.status_code in (200, 201):
            tok_data = r.json()
            approval_token = (
                tok_data.get("token") or
                tok_data.get("approval_token") or
                tok_data.get("code")
            )
            ok(f"Token: {str(approval_token)[:20]}..." if approval_token else "Token field not found in response")
            if not approval_token:
                info(f"  Response keys: {list(tok_data.keys())}")
        else:
            warn(f"Approval token: {r.status_code} — {r.text[:200]}")

        # ── Step 09: Approve ──────────────────────────────────────────
        step(9, "POST /api/v1/proposals/{id}/approve")
        approve_body = {
            "current_price": str(current_price),
        }
        if approval_token:
            approve_body["token"] = str(approval_token)

        r = await client.post(
            f"/api/v1/proposals/{proposal_id}/approve",
            headers=headers,
            json=approve_body
        )
        if r.status_code in (200, 201):
            result_data = r.json()
            ok(f"Approved! New status: {result_data.get('status')}")
        else:
            fail(f"Approve: {r.status_code} — {r.text[:400]}")

        # ── Step 10: Verify Approved Status ───────────────────────────
        step(10, "Verify Proposal Status = APPROVED")
        r = await client.get(f"/api/v1/proposals/{proposal_id}", headers=headers)
        if r.status_code == 200:
            status = r.json().get("status")
            if status == "APPROVED":
                ok("Status = APPROVED ✓")
            else:
                warn(f"Status = {status} (expected APPROVED)")
        else:
            fail(f"Verify status failed: {r.text[:100]}")

        # ── Step 11: Execute ──────────────────────────────────────────
        step(11, "POST /api/v1/execution/{id}/execute  (PAPER mode)")
        r = await client.post(
            f"/api/v1/execution/{proposal_id}/execute",
            headers=headers,
            json={"current_price": str(current_price)},
            timeout=30
        )
        if r.status_code in (200, 201):
            result_data = r.json()
            ok(f"Trade executed in PAPER mode!")
            info(f"  order_id    : {str(result_data.get('order_id',''))[:12]}...")
            info(f"  status      : {result_data.get('status')}")
            info(f"  filled_qty  : {result_data.get('filled_quantity')}")
            info(f"  fill_price  : {result_data.get('average_fill_price')}")
            info(f"  total_cost  : {result_data.get('total_cost')}")
        else:
            fail(f"Execute: {r.status_code} — {r.text[:400]}")

        # ── Step 12: Positions ────────────────────────────────────────
        step(12, "GET /api/v1/positions — Verify Position Created")
        await asyncio.sleep(1)
        r = await client.get("/api/v1/positions", headers=headers)
        if r.status_code == 200:
            pos_data = r.json()
            positions = pos_data.get("positions", [])
            open_pos  = [p for p in positions if p.get("status") == "OPEN"]
            ok(f"Total positions: {len(positions)}, OPEN: {len(open_pos)}")
            for p in open_pos[:3]:
                info(f"  symbol={p.get('symbol')} side={p.get('side')} qty={p.get('quantity')} entry={p.get('entry_price')}")
        else:
            fail(f"Positions: {r.status_code} — {r.text[:100]}")

        # ── Step 13: P&L Summary ──────────────────────────────────────
        step(13, "GET /api/v1/positions/summary/pnl")
        r = await client.get("/api/v1/positions/summary/pnl", headers=headers)
        if r.status_code == 200:
            pnl = r.json()
            ok(f"P&L Summary:")
            info(f"  open_positions    : {pnl.get('open_positions_count')}")
            info(f"  total_unrealized  : {pnl.get('total_unrealized_pnl')}")
            info(f"  total_value       : {pnl.get('total_position_value')}")
            info(f"  win_rate          : {pnl.get('win_rate')}")
        else:
            warn(f"P&L: {r.status_code} — {r.text[:100]}")

        # ── Step 14: Orders ───────────────────────────────────────────
        step(14, "GET /api/v1/orders — Verify Orders Created")
        r = await client.get("/api/v1/orders?limit=10", headers=headers)
        if r.status_code == 200:
            orders_data = r.json()
            orders = orders_data.get("orders", [])
            ok(f"Total orders: {len(orders)}")
            for o in orders[:3]:
                info(f"  symbol={o.get('symbol')} side={o.get('side')} status={o.get('status')} qty={o.get('quantity')} price={o.get('price')}")
        else:
            fail(f"Orders: {r.status_code} — {r.text[:100]}")

        # ── Summary ───────────────────────────────────────────────────
        print(f"\n{BOLD}{'='*60}")
        print("PHASE 4 COMPLETE")
        print(f"{'='*60}{RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
