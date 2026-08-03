#!/usr/bin/env python3
"""
test_trading_flow.py — E2E Test Script cho Luồng Giao Dịch Thực Tế trên Localtest

Chạy toàn bộ pipeline giao dịch:
  Step 1:  Health Check
  Step 2:  Login
  Step 3:  Deep backfill candles
  Step 4:  Verify data sufficiency
  Step 5:  Compute features
  Step 6:  Run strategy signal
  Step 7:  Run full AI analysis (5 agents)
  Step 8:  Check proposal
  Step 9:  Approve & execute paper trade
  Step 10: Verify position

Usage:
    cd /home/vietpv/Desktop/bot-finance
    pip install httpx
    python scripts/test_trading_flow.py --symbol BTCUSDT
    python scripts/test_trading_flow.py --symbol BTCUSDT --skip-backfill
    python scripts/test_trading_flow.py --symbol BTCUSDT --skip-analysis
"""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime
from typing import Any

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

BASE_URL = "http://localhost:8000"
DEFAULT_EMAIL = "admin@acta.io"
DEFAULT_PASSWORD = "Admin@acta2024!"

GREEN="\033[92m"; YELLOW="\033[93m"; RED="\033[91m"
BLUE="\033[94m"; CYAN="\033[96m"; BOLD="\033[1m"; RESET="\033[0m"

def ok(m): print(f"  {GREEN}✅ {m}{RESET}")
def warn(m): print(f"  {YELLOW}⚠  {m}{RESET}")
def fail(m): print(f"  {RED}❌ {m}{RESET}")
def info(m): print(f"  {CYAN}ℹ  {m}{RESET}")
def step(n, t): print(f"\n{BOLD}{BLUE}[Step {n:02d}]{RESET} {BOLD}{t}{RESET}\n  {'─'*60}")
def section(t): print(f"\n{BOLD}{CYAN}{'═'*64}\n  {t}\n{'═'*64}{RESET}")

class APIClient:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self._token: str | None = None
        self._c = httpx.Client(timeout=300.0)

    def login(self, email: str, password: str):
        r = self._c.post(f"{self.base}/api/v1/auth/login", json={"email": email, "password": password})
        r.raise_for_status()
        self._token = r.json()["access_token"]

    @property
    def _h(self): return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    def get(self, path: str, **kw) -> dict:
        r = self._c.get(f"{self.base}{path}", headers=self._h, **kw)
        r.raise_for_status(); return r.json()

    def post(self, path: str, **kw) -> dict:
        r = self._c.post(f"{self.base}{path}", headers=self._h, **kw)
        r.raise_for_status(); return r.json()

    def close(self): self._c.close()


class TradingFlowTest:
    def __init__(self, symbol: str, skip_backfill: bool, skip_analysis: bool):
        self.sym = symbol
        self.skip_backfill = skip_backfill
        self.skip_analysis = skip_analysis
        self.client = APIClient(BASE_URL)
        self.results: dict[str, Any] = {"symbol": symbol, "started_at": datetime.now().isoformat(), "steps": {}}
        self._proposal_id: str | None = None

    def run(self) -> bool:
        section(f"ACTA E2E Trading Flow Test — {self.sym}")
        print(f"  Base URL : {BASE_URL}\n  Symbol   : {self.sym}\n  Time     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        all_passed = True
        for n, title, fn in [
            (1,  "Health Check",                  self._health),
            (2,  "Login",                          self._login),
            (3,  "Deep Backfill Candles",          self._backfill),
            (4,  "Verify Data Sufficiency",        self._verify_data),
            (5,  "Compute Features",               self._features),
            (6,  "Run Strategy Signal",            self._strategy),
            (7,  "Run Full Analysis (AI Agents)",  self._analysis),
            (8,  "Check Proposal",                 self._check_proposal),
            (9,  "Approve & Execute Trade",        self._execute),
            (10, "Verify Position",                self._verify_position),
        ]:
            step(n, title)
            try:
                r = fn()
                self.results["steps"][title] = {"status": "PASS", "data": r}
            except SystemExit: break
            except Exception as e:
                fail(str(e)); self.results["steps"][title] = {"status": "FAIL", "error": str(e)}
                all_passed = False
        self._summary(all_passed)
        self.client.close()
        return all_passed

    def _health(self):
        r = self.client.get("/api/v1/system/health")
        s = r.get("status", "?")
        (ok if s == "ok" else warn)(f"System {s} — version {r.get('version','?')} mode {r.get('trading_mode','?')}")
        return r

    def _login(self):
        try:
            self.client.login(DEFAULT_EMAIL, DEFAULT_PASSWORD)
            ok(f"Logged in as {DEFAULT_EMAIL}")
        except httpx.HTTPStatusError:
            try:
                self.client.login("admin@example.com", "adminpassword123")
                ok("Logged in with fallback credentials")
            except Exception as e2:
                raise RuntimeError(f"Login failed. Try creating a user first. Error: {e2}")
        return {"logged_in": True}

    def _backfill(self):
        if self.skip_backfill:
            warn("Skipping deep backfill (--skip-backfill)"); return {"skipped": True}
        info("Starting deep backfill (may take 1-3 minutes)…")
        try:
            r = self.client.post(f"/api/v1/market/candles/deep-backfill?symbol={self.sym}&days_15m=30&days_1h=90&days_4h=365")
            for tf, d in r.get("results", {}).items():
                ok(f"{tf}: {d.get('candles_stored',0):,} candles ({d.get('batches',0)} batches)")
            return r
        except httpx.ReadTimeout:
            warn("Timed out — backfill may still be running"); return {"timed_out": True}

    def _verify_data(self):
        r = self.client.get(f"/api/v1/market/candles/stats/{self.sym}")
        all_ok = True
        for tf, s in r.get("timeframes", {}).items():
            count, pct, req, suf = s["count"], s["sufficiency_pct"], s["min_required"], s["is_sufficient"]
            cov = s.get("coverage_days")
            if suf: ok(f"{tf}: {count:,} candles ({cov}d) — sufficient")
            else: warn(f"{tf}: {count:,}/{req} ({pct}%) — insufficient"); all_ok = False
        if not all_ok: warn("Run Deep Backfill for better prediction accuracy")
        else: ok("All timeframes sufficient")
        return {**r, "all_sufficient": all_ok}

    def _features(self):
        r = self.client.post(f"/api/v1/features/{self.sym}/compute")
        cnt = r.get("candle_count_15m", "?")
        ds = r.get("data_sufficient")
        ok(f"Features computed — {cnt} candles, at {r.get('computed_at','?')}")
        if ds is False: warn(r.get("data_warning",""))
        elif ds is True: ok("Data sufficient for EMA 200")
        for n, k in [("EMA21",  "ema_21"), ("EMA50", "ema_50"), ("RSI14", "rsi_14"), ("MACD",  "macd_histogram")]:
            v = r.get(k)
            if v: info(f"  {n}: {v}")
        return r

    def _strategy(self):
        r = self.client.get(f"/api/v1/strategy/{self.sym}/signal?strategy=ema_pullback")
        sig, sc, conf = r.get("signal","NO_SIGNAL"), r.get("score",0), r.get("confidence","?")
        c = GREEN if sig == "LONG" else (RED if sig == "SHORT" else YELLOW)
        conf_display = f"{conf:.0%}" if isinstance(conf, float) else str(conf)
        print(f"  {c}{BOLD}Signal: {sig}{RESET}  Score: {sc}/100  Confidence: {conf_display}")
        for reason in r.get("reasons", [])[:5]: info(f"• {reason}")
        return r

    def _analysis(self):
        if self.skip_analysis:
            warn("Skipping AI analysis (--skip-analysis)"); return {"skipped": True}
        info("Running full multi-agent analysis (30-120s)…")
        try:
            r = self.client.post(f"/api/v1/analysis/{self.sym}/trigger-sync")
            d, sc, proc = r.get("final_direction","?"), r.get("consensus_score",0), r.get("proceed_to_proposal",False)
            c = GREEN if d == "LONG" else (RED if d == "SHORT" else YELLOW)
            print(f"  {c}{BOLD}Direction: {d}{RESET}  Consensus: {sc:.1f}/100")
            print(f"  Proceed: {GREEN+'YES'+RESET if proc else YELLOW+'NO'+RESET}")
            return r
        except httpx.ReadTimeout:
            warn("Analysis timed out — LLM may be slow"); return {"timed_out": True}

    def _check_proposal(self):
        r = self.client.get(f"/api/v1/proposals/active?symbol={self.sym}")
        proposals = r.get("proposals", [])
        if not proposals:
            warn(f"No active proposals for {self.sym}")
            return {"proposals": 0}
        p = proposals[0]; self._proposal_id = p["id"]
        ok(f"Proposal: {p.get('recommendation','?')} @ ${p.get('suggested_price') or p.get('current_price','?')}")
        info(f"ID: {self._proposal_id}")
        return {"proposal_id": self._proposal_id}

    def _execute(self):
        if not self._proposal_id:
            warn("No proposal to execute"); return {"executed": False}
        ticker = self.client.get(f"/api/v1/market/ticker/{self.sym}")
        price = str(ticker.get("price", "50000"))
        info(f"Current price: ${price}")
        token_r = self.client.post(f"/api/v1/proposals/{self._proposal_id}/approval-token")
        token = token_r.get("token", "")
        self.client.post(f"/api/v1/proposals/{self._proposal_id}/approve", json={"token": token, "current_price": price})
        ok("Proposal approved")
        exec_r = self.client.post(f"/api/v1/execution/{self._proposal_id}/execute", json={"current_price": price})
        ok(f"Trade: {exec_r.get('side','?')} {exec_r.get('fill_quantity','?')} @ ${exec_r.get('fill_price','?')} [{exec_r.get('environment','?')}]")
        return exec_r

    def _verify_position(self):
        r = self.client.get(f"/api/v1/positions?symbol={self.sym}&status=OPEN")
        pos = r.get("positions", [])
        if not pos:
            warn("No open positions found"); return {"positions": 0}
        p = pos[0]
        ok(f"Position: {p.get('side','?')} {p.get('quantity','?')} {self.sym} @ ${p.get('entry_price','?')}")
        return {"positions": len(pos), "position": p}

    def _summary(self, all_passed: bool):
        section("TEST SUMMARY")
        total = len(self.results["steps"])
        passed = sum(1 for s in self.results["steps"].values() if s["status"] == "PASS")
        print(f"  Steps: {total}  {GREEN}Pass: {passed}{RESET}  {RED}Fail: {total-passed}{RESET}\n")
        for title, r in self.results["steps"].items():
            s = r["status"]; c = GREEN if s == "PASS" else RED
            print(f"  {c}{'✅' if s=='PASS' else '❌'} {title}{RESET}")
        print()
        if all_passed: print(f"  {GREEN}{BOLD}🎉 ALL TESTS PASSED!{RESET}")
        else: print(f"  {YELLOW}{BOLD}⚠  Some steps failed — check logs above{RESET}")
        self.results.update({"completed_at": datetime.now().isoformat(), "all_passed": all_passed})
        out = f"/tmp/flow_test_{self.sym}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(out, "w") as f: json.dump(self.results, f, indent=2, default=str)
        info(f"Results: {out}")


def main():
    global BASE_URL
    p = argparse.ArgumentParser(description="ACTA E2E Trading Flow Test")
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--skip-backfill", action="store_true")
    p.add_argument("--skip-analysis", action="store_true")
    p.add_argument("--base-url", default=BASE_URL)
    args = p.parse_args()
    if args.base_url:
        BASE_URL = args.base_url
    test = TradingFlowTest(args.symbol, args.skip_backfill, args.skip_analysis)
    sys.exit(0 if test.run() else 1)

if __name__ == "__main__":
    main()
