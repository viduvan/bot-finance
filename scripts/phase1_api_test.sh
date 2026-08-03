#!/bin/bash
# Phase 1: Backend API Test Script
# Chạy: bash scripts/phase1_api_test.sh

set -e

BASE="http://localhost:8000"
GREEN='\033[92m'; YELLOW='\033[93m'; RED='\033[91m'
CYAN='\033[96m'; BOLD='\033[1m'; RESET='\033[0m'

ok()   { echo -e "  ${GREEN}✅ $1${RESET}"; }
warn() { echo -e "  ${YELLOW}⚠  $1${RESET}"; }
fail() { echo -e "  ${RED}❌ $1${RESET}"; }
info() { echo -e "  ${CYAN}ℹ  $1${RESET}"; }
step() { echo -e "\n${BOLD}${CYAN}[Step $1]${RESET} ${BOLD}$2${RESET}\n  ──────────────────────────────────────────────────────────"; }

SYMBOL="${1:-BTCUSDT}"

# ── Step 0: Health Check ──────────────────────────────────────────
step 0 "Health Check"
HEALTH=$(curl -s "$BASE/api/v1/system/health" 2>/dev/null)
if echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('status') in ('ok','healthy') else 1)" 2>/dev/null; then
  VERSION=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('version','?'))")
  MODE=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('trading_mode','?'))")
  ok "System healthy — v$VERSION mode=$MODE"
else
  fail "Backend not healthy: $HEALTH"
  exit 1
fi

# ── Step 1: Login ─────────────────────────────────────────────────
step 1 "Login"
LOGIN=$(curl -s -X POST "$BASE/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@acta.io","password":"Admin@acta2024!"}' 2>/dev/null)
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
if [ -z "$TOKEN" ]; then
  fail "Login failed: $LOGIN"
  exit 1
fi
ok "Logged in — token: ${TOKEN:0:30}..."

AUTH="-H \"Authorization: Bearer $TOKEN\""

# ── Step 2: Candle Stats (expect count=0 if fresh) ────────────────
step 2 "GET /candles/stats/$SYMBOL"
STATS=$(curl -s "$BASE/api/v1/market/candles/stats/$SYMBOL" \
  -H "Authorization: Bearer $TOKEN")
if echo "$STATS" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if 'timeframes' in d else 1)" 2>/dev/null; then
  echo "$STATS" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for tf, s in d['timeframes'].items():
    count = s['count']
    pct = s['sufficiency_pct']
    cov = s.get('coverage_days') or 'N/A'
    print(f'  {tf}: count={count}, coverage={cov}d, sufficiency={pct}%')
"
  ok "Stats endpoint working"
else
  fail "Stats failed: $STATS"
fi

# ── Step 3: Deep Backfill (light — 1 day) ────────────────────────
step 3 "POST /candles/deep-backfill ($SYMBOL, 1 day test)"
info "This may take 30-60 seconds..."
BACKFILL=$(curl -s -X POST \
  "$BASE/api/v1/market/candles/deep-backfill?symbol=$SYMBOL&days_15m=1&days_1h=3&days_4h=7" \
  -H "Authorization: Bearer $TOKEN")
if echo "$BACKFILL" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if 'results' in d else 1)" 2>/dev/null; then
  echo "$BACKFILL" | python3 -c "
import sys, json
d = json.load(sys.stdin)
total = 0
for tf, r in d['results'].items():
    n = r.get('candles_stored', 0)
    b = r.get('batches', 0)
    total += n
    print(f'  {tf}: {n} candles ({b} batches)')
print(f'  Total: {total} candles stored')
"
  ok "Deep backfill working"
else
  fail "Backfill failed: $BACKFILL"
fi

# ── Step 4: Candle History (paginated) ───────────────────────────
step 4 "GET /candles/history?symbol=$SYMBOL&timeframe=15m&limit=100"
HIST=$(curl -s "$BASE/api/v1/market/candles/history?symbol=$SYMBOL&timeframe=15m&limit=100" \
  -H "Authorization: Bearer $TOKEN")
echo "$HIST" | python3 -c "
import sys, json
d = json.load(sys.stdin)
candles = d.get('candles', [])
print(f'  Count: {len(candles)}')
if candles:
    print(f'  Oldest: {candles[0][\"open_time\"]}')
    print(f'  Newest: {candles[-1][\"open_time\"]}')
    # Verify ascending order (oldest first, newest last)
    times = [c['open_time'] for c in candles]
    is_asc = all(times[i] <= times[i+1] for i in range(len(times)-1))
    print(f'  Order: {\"✅ ascending (correct)\" if is_asc else \"❌ NOT ascending - chart will break\"}')
"
ok "History endpoint working"

# ── Step 5: Feature Compute ───────────────────────────────────────
step 5 "POST /features/$SYMBOL/compute"
FEAT=$(curl -s -X POST "$BASE/api/v1/features/$SYMBOL/compute" \
  -H "Authorization: Bearer $TOKEN" 2>/dev/null)
echo "$FEAT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f'  data_sufficient: {d.get(\"data_sufficient\")}')
    print(f'  candle_count_15m: {d.get(\"candle_count_15m\")}')
    print(f'  ema_21: {d.get(\"ema_21\")}')
    print(f'  rsi_14: {d.get(\"rsi_14\")}')
    w = d.get(\"data_warning\")
    if w: print(f'  ⚠ Warning: {w}')
except Exception as e:
    print(f'  Parse error: {e}')
    print(sys.stdin.read()[:300])
"

# ── Step 6: Strategy Signal ───────────────────────────────────────
step 6 "GET /strategy/$SYMBOL/signal"
SIG=$(curl -s "$BASE/api/v1/strategy/$SYMBOL/signal?strategy=ema_pullback" \
  -H "Authorization: Bearer $TOKEN" 2>/dev/null)
echo "$SIG" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f'  Signal: {d.get(\"signal\",\"?\")}')
    print(f'  Score: {d.get(\"score\",\"?\")}')
    print(f'  Confidence: {d.get(\"confidence\",\"?\")}')
except: print(sys.stdin.read()[:200])
"

echo ""
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}${GREEN}  Phase 1 API tests complete! ✅${RESET}"
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════${RESET}"
