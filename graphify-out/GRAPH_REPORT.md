# Graph Report - .  (2026-08-04)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 2372 nodes · 4246 edges · 153 communities (134 shown, 19 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 425 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `dfb59a20`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- exceptions.py
- Base
- auth.py
- IndicatorEngine
- dependencies
- TradingFlowTest
- analysis_tasks.py
- risk/engine.py
- TradeProposal
- enums.py
- TestIndicatorEngine
- v1/market.py
- ProposalRepository
- TestRiskGate
- base_agent.py
- ProposalBuilder
- test_indicators.py
- BinanceWebSocketManager
- TestDataValidator
- MarketDataService
- TestProposalStateMachine
- decode_token
- BinanceRestClient
- DashboardPage.tsx
- dependencies.py
- MarketDataRepository
- orchestrator.py
- ai_chat.py
- AnalysisOrchestrator
- DailyLossTracker
- asyncio
- DataValidator
- compilerOptions
- ProposalExpirationService
- TestSignalAggregator
- TestEMAPullbackStrategy
- AgentOutput
- FeeSlippageEstimator
- RiskRewardCalculator
- TestDailyLossTracker
- TestPositionSizer
- TestSLTPCalculator
- PaperExecutionService
- TestApprovalTokenSecurity
- TestProposalBuilder
- api.ts
- MarketRegimeOutput
- schemas/market.py
- TestApprovalTokenManager
- compilerOptions
- TestEncryptionSecurity
- MarketPage.tsx
- execution.py
- ApprovalTokenManager
- ProposalService
- NotificationService
- make_candle
- features/engine.py
- BaseAgent
- execution/service.py
- ConnectionManager
- TelegramService
- TestPaperFillSimulator
- TestPaperPositionManager
- TestPaperPnLTracker
- react
- main.py
- models/audit.py
- features.py
- Settings
- TestPriceDriftGuard
- TestProposalExpirationService
- TestExchangeFilter
- RiskAnalysisAgent
- notifications.py
- PaperFillSimulator
- PaperPnLTracker
- PaperPositionManager
- GeminiService
- CandlestickChart.tsx
- AnalysisPage.tsx
- market_data/service.py
- EMAPullbackStrategy
- orders.py
- FeatureEngine
- volatility.py
- ._record_version
- StrategyRegistry
- conftest.py
- make_trending_candles
- volume.py
- SignalResult
- .make_book
- env.py
- AggregatedSignal
- system.py
- record_audit
- BaseStrategy
- I18nContext.tsx
- TestExtractJson
- config.py
- logging.py
- .compute
- ProposalCard.tsx
- .check
- phase1_api_test.sh
- rate_limit.py
- notification_service.py
- AuditPage.tsx
- error_handler.py
- UUID
- .apply
- sign_approval_context
- fixture
- Permission
- tsconfig.json
- ApprovalDecision
- ApprovalTokenStatus
- AuditAction
- LiquidityStatus
- PositionStatus
- Recommendation
- core/__init__.py
- database/__init__.py
- app/__init__.py
- scheduler/__init__.py
- .test_no_signal_empty_features
- test_paper_trading.py
- backup_database.sh
- start.sh
- stop.sh
- acta-backend

## God Nodes (most connected - your core abstractions)
1. `Base` - 40 edges
2. `ProposalRepository` - 39 edges
3. `TimestampMixin` - 37 edges
4. `BaseAgent` - 34 edges
5. `UUIDPrimaryKeyMixin` - 32 edges
6. `ACTAError` - 31 edges
7. `IndicatorEngine` - 31 edges
8. `User` - 29 edges
9. `ApprovalTokenManager` - 29 edges
10. `DailyLossTracker` - 29 edges

## Surprising Connections (you probably didn't know these)
- `AgentOutput` --uses--> `LLMClient`  [INFERRED]
  apps/backend/app/agents/base_agent.py → apps/backend/app/agents/llm_client.py
- `AgentOutput` --uses--> `LLMResponse`  [INFERRED]
  apps/backend/app/agents/base_agent.py → apps/backend/app/agents/llm_client.py
- `MarketRegimeAgent` --uses--> `AgentOutput`  [INFERRED]
  apps/backend/app/agents/market_regime_agent.py → apps/backend/app/agents/base_agent.py
- `MarketRegimeOutput` --uses--> `AgentOutput`  [INFERRED]
  apps/backend/app/agents/market_regime_agent.py → apps/backend/app/agents/base_agent.py
- `OrderFlowAgent` --uses--> `AgentOutput`  [INFERRED]
  apps/backend/app/agents/order_flow_agent.py → apps/backend/app/agents/base_agent.py

## Import Cycles
- None detected.

## Communities (153 total, 19 thin omitted)

### Community 0 - "exceptions.py"
Cohesion: 0.04
Nodes (45): ACTAError, AgentOutputValidationError, AgentTimeoutError, ApprovalTokenInvalidError, ApprovalTokenUsedError, BinanceConnectionError, ConfigurationError, ConflictError (+37 more)

### Community 1 - "Base"
Cohesion: 0.09
Nodes (47): Base, SQLAlchemy base model with common columns., Base class for all SQLAlchemy models., Mixin that adds created_at and updated_at columns., Mixin that adds a UUID primary key., TimestampMixin, UUIDPrimaryKeyMixin, ApprovalToken (+39 more)

### Community 2 - "auth.py"
Cohesion: 0.07
Nodes (53): get_current_user(), login(), LoginRequest, LoginResponse, logout(), MFASetupResponse, MFAVerifyRequest, AsyncSession (+45 more)

### Community 3 - "IndicatorEngine"
Cohesion: 0.08
Nodes (30): _candles_to_df(), IndicatorEngine, Any, Decimal, Technical Indicator Engine. Computes OHLCV-based indicators using pandas-ta.…, Get the most recent EMA values for all periods. Returns dict: {'ema_9': value,…, Compute Relative Strength Index. Args: candles: list of OHLCV dicts period: RSI…, Get the most recent RSI value. (+22 more)

### Community 4 - "dependencies"
Cohesion: 0.04
Nodes (46): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema, dependencies, axios, lightweight-charts (+38 more)

### Community 5 - "TradingFlowTest"
Cohesion: 0.10
Nodes (23): backfill_gaps_task(), cleanup_old_data_task(), initial_load_task(), task, Các tác vụ Celery (Celery tasks) để đồng bộ dữ liệu thị trường. Các tác vụ được…, Xóa dữ liệu nến cũ hơn N ngày. Chạy hàng ngày qua Celery Beat., Tải dữ liệu lịch sử ban đầu cho một cặp giao dịch. Được gọi thủ công hoặc trong…, Chạy một hàm bất đồng bộ trong một event loop mới (dành cho Celery workers đồng… (+15 more)

### Community 6 - "analysis_tasks.py"
Cohesion: 0.06
Nodes (37): get_analysis_history(), get_analysis_task_status(), CurrentUser, DBSession, get, post, Analysis API endpoints — trigger and retrieve analysis results., Manually trigger an analysis run for a symbol (async via Celery). Returns the… (+29 more)

### Community 7 - "risk/engine.py"
Cohesion: 0.09
Nodes (27): Any, Risk Engine — Orchestration layer for all risk management components. This is…, Full risk assessment for a trade proposal. Args: context: Must include: symbol,…, Complete risk assessment result for a proposed trade., Convert to JSON-serializable dict., Orchestrates all risk management logic for a trade proposal. Usage: engine =…, RiskAssessment, RiskEngine (+19 more)

### Community 8 - "TradeProposal"
Cohesion: 0.09
Nodes (27): AgentOutput, AgentRun, AgentWorkflow, Agent workflow, run, and output models., Tracks one complete analysis workflow (all agents for one symbol)., Individual agent execution within a workflow., Structured output from an agent run., Order (+19 more)

### Community 9 - "enums.py"
Cohesion: 0.11
Nodes (37): AgentName, AgentRunStatus, AgentWorkflowStatus, AnalysisTriggerType, BacktestStatus, CloseReason, CriticVerdict, DataSource (+29 more)

### Community 10 - "TestIndicatorEngine"
Cohesion: 0.05
Nodes (19): In a strong uptrend, EMA9 should be above EMA21., In a strong uptrend, EMA21 should be above EMA50., All RSI values should be between 0 and 100., In a strong uptrend, RSI should be above 50., RSI < 30 should be classified as OVERSOLD., RSI > 70 should be classified as OVERBOUGHT., RSI 30-70 should be classified as NEUTRAL., MACD should return macd, signal, and histogram series. (+11 more)

### Community 11 - "v1/market.py"
Cohesion: 0.14
Nodes (33): backfill_gaps(), check_data_quality(), deep_backfill_candles(), fetch_candles(), get_candle_stats(), get_candles(), get_candles_history(), get_exchange_info() (+25 more)

### Community 12 - "ProposalRepository"
Cohesion: 0.13
Nodes (32): approve_proposal(), ApproveRequest, cancel_proposal(), edit_proposal(), EditRequest, get_proposal(), issue_approval_token(), list_active_proposals() (+24 more)

### Community 13 - "TestRiskGate"
Cohesion: 0.09
Nodes (18): Tests for RiskGate — 15 blocking conditions. All conditions must pass for a…, Build a passing risk context (all conditions satisfied)., All conditions satisfied → trade allowed., Daily loss exceeding max blocks the trade., Exceeding max open positions blocks the trade., Signal score below minimum blocks the trade., R/R ratio below minimum blocks the trade., Spread above max bps blocks the trade. (+10 more)

### Community 14 - "base_agent.py"
Cohesion: 0.09
Nodes (18): ABC, Base Agent — abstract class for all ACTA analysis agents. Each agent: 1.…, GeminiProvider, LLMClient, LLMProviderError, LLMResponse, OllamaProvider, OpenAIProvider (+10 more)

### Community 15 - "ProposalBuilder"
Cohesion: 0.06
Nodes (30): Approval Token Manager — one-time-use HMAC-signed tokens for trade approval.…, ProposalBuilder, Any, Decimal, Proposal Builder — constructs TradeProposal dicts from AnalysisResult. Takes…, Safely convert a value to Decimal., Builds a trade proposal dict from an analysis result. The result dict can be…, Build a proposal from analysis result. Args: analysis_result: Full… (+22 more)

### Community 16 - "test_indicators.py"
Cohesion: 0.10
Nodes (23): MarketStructure, Market structure analysis. Identifies key support/resistance levels, trend…, Identifies market structure from OHLCV data. Provides: - Trend direction…, OrderBookFeatures, Decimal, Order book feature computation. Computes bid/ask imbalance, spread metrics, and…, Detect if any single level represents > threshold of total volume. A 'wall' is…, Computes order book depth features. Inputs: bid/ask depth data from Binance… (+15 more)

### Community 17 - "BinanceWebSocketManager"
Cohesion: 0.08
Nodes (17): BinanceWebSocketManager, Any, Đăng ký callback cho các bản cập nhật nến (kline)., Đăng ký callback cho các bản cập nhật giá (ticker)., Đăng ký một client WebSocket frontend để nhận dữ liệu phát sóng (broadcast)., Hủy đăng ký một client WebSocket frontend., Lấy số giây trôi qua kể từ tin nhắn cuối cùng cho một cặp tiền., Kết nối WebSocket, lắng nghe tin nhắn và tự động kết nối lại. (+9 more)

### Community 18 - "TestDataValidator"
Cohesion: 0.08
Nodes (17): Khối lượng bằng 0 phải đưa ra cảnh báo., Khung thời gian không xác định vẫn phải trả về kết quả kèm cảnh báo., Không có dữ liệu phải được báo cáo là cũ (stale)., Dữ liệu gần đây không được coi là cũ., Dữ liệu cũ phải được báo cáo là stale., Không có nến phải trả về một khoảng trống lớn., Dữ liệu đầy đủ không được có khoảng trống nào., Các bài kiểm tra cho việc xác thực dữ liệu thị trường. (+9 more)

### Community 19 - "MarketDataService"
Cohesion: 0.08
Nodes (17): MarketDataService, datetime, Tải dữ liệu lịch sử sâu cho tất cả các timeframe. Fetch nhiều batch 1000 nến…, Lấy dữ liệu nến từ cơ sở dữ liệu., Lấy giá mới nhất từ Binance REST API., Trả về thống kê số lượng nến cho mỗi timeframe (dùng cho dashboard). Trả về…, Lấy nến cho chart với lazy loading theo thời gian. Dùng để load thêm nến khi…, Tạo một ảnh chụp nhanh thị trường mới và lưu vào cơ sở dữ liệu. (+9 more)

### Community 20 - "TestProposalStateMachine"
Cohesion: 0.07
Nodes (15): DRAFT → APPROVED skipping review is NOT allowed., get_allowed_transitions() returns list of valid next states., Tests for the strict proposal state machine. Valid transitions: DRAFT →…, DRAFT → PENDING_REVIEW is valid., PENDING_REVIEW → APPROVED is valid., PENDING_REVIEW → REJECTED is valid., PENDING_REVIEW → RECONFIRM_REQUIRED is valid., RECONFIRM_REQUIRED → PENDING_REVIEW is valid (user reconfirms). (+7 more)

### Community 21 - "decode_token"
Cohesion: 0.08
Nodes (22): events_websocket(), websocket, WebSocket endpoint for real-time proposal + system events. Frontend connects…, Real-time event stream: proposals, analysis, orders, positions. Auth: pass JWT…, market_websocket(), websocket, Endpoint WebSocket cho luồng dữ liệu thị trường trực tiếp tới frontend.…, Endpoint WebSocket cho dữ liệu thị trường thời gian thực. Frontend kết nối qua:… (+14 more)

### Community 22 - "BinanceRestClient"
Cohesion: 0.10
Nodes (15): BinanceRestClient, AsyncClient, datetime, Lấy dữ liệu nến OHLCV. Trả về danh sách các dict nến với key chuẩn hóa. Weight:…, Lấy giá hiện tại cho một cặp giao dịch. Weight: 2., Lấy thống kê ticker trong 24h qua. Weight: 2., Lấy giá bid/ask tốt nhất cho một cặp giao dịch. Weight: 2., Lấy độ sâu sổ lệnh. Weight: 5 cho limit=20, 10 cho 50, 50 cho 500. (+7 more)

### Community 23 - "DashboardPage.tsx"
Cohesion: 0.12
Nodes (20): useT(), AnalysisControlPanel(), AnalysisResultCard(), DashboardView(), formatDuration(), formatVol(), LiveTickerBar(), MiniCandleChart() (+12 more)

### Community 24 - "dependencies.py"
Cohesion: 0.20
Nodes (13): User roles for RBAC authorization., UserRole, AuthenticationError, AuthorizationError, Invalid credentials or expired token., User lacks required permissions., JWT or approval token has expired., TokenExpiredError (+5 more)

### Community 25 - "MarketDataRepository"
Cohesion: 0.09
Nodes (15): MarketDataRepository, AsyncSession, datetime, Lấy cây nến gần nhất cho một cặp giao dịch/khung thời gian., Đếm số lượng nến trong một khoảng thời gian., Xóa các nến cũ hơn một thời điểm nhất định., Đếm số lượng nến hiện có trong DB cho mỗi timeframe. Trả về dict: {'15m': 500,…, Lấy thời gian nến cũ nhất và mới nhất trong DB. Trả về dict: {'oldest':… (+7 more)

### Community 26 - "orchestrator.py"
Cohesion: 0.11
Nodes (15): Analysis Orchestrator — coordinates the full multi-agent analysis workflow.…, Signal Aggregator — weighted consensus from all agent outputs. Combines outputs…, Aggregates agent signals using weighted consensus. Weights (from…, SignalAggregator, AgentOutput, Any, field_validator, Technical Agent — pattern recognition and indicator-based signal analysis.… (+7 more)

### Community 27 - "ai_chat.py"
Cohesion: 0.12
Nodes (25): ai_status(), chat(), ChatRequest, ChatResponse, _detect_and_call_tools(), _extract_symbol(), Any, BaseModel (+17 more)

### Community 28 - "AnalysisOrchestrator"
Cohesion: 0.11
Nodes (16): AnalysisOrchestrator, AnalysisResult, Any, Run the full analysis pipeline for a symbol. Returns AnalysisResult regardless…, Internal pipeline execution., Complete output of the analysis orchestrator., Convert to JSON-serializable dict for DB storage., Orchestrates the full multi-agent analysis pipeline. Usage: orchestrator =… (+8 more)

### Community 29 - "DailyLossTracker"
Cohesion: 0.13
Nodes (13): AsyncSession, DailyLossTracker, Decimal, Daily Loss Tracker — tracks intraday PnL losses per symbol. Supports two…, Reset daily loss counter for a symbol (call at start of new day)., Reset all daily loss counters., Get raw accumulated loss amount., Redis key for daily loss counter. (+5 more)

### Community 30 - "asyncio"
Cohesion: 0.14
Nodes (22): Quản lý kết nối Binance WebSocket. Quản lý các kết nối liên tục (persistent…, AsyncClient, Tests for health check and system API., Health check should return 200 with system status., Should reject invalid password., Should reject login for non-existent user., Should reject short passwords (minimum 12 chars)., Config endpoint should return non-sensitive configuration. (+14 more)

### Community 31 - "DataValidator"
Cohesion: 0.17
Nodes (9): DataValidator, datetime, Kiểm tra xem dữ liệu có bị cũ/đóng băng không., Tìm những khoảng thời gian trống cần gọi REST API để điền đầy dữ liệu. Trả về…, Kiểm tra dữ liệu thị trường xem có vấn đề về chất lượng không., Kiểm tra danh sách nến và trả về báo cáo chất lượng. Trả về: dict có chứa các…, AsyncSession, fixture (+1 more)

### Community 32 - "compilerOptions"
Cohesion: 0.08
Nodes (23): compilerOptions, allowArbitraryExtensions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection (+15 more)

### Community 33 - "ProposalExpirationService"
Cohesion: 0.11
Nodes (13): ProposalExpirationService, Proposal Expiration Service — detect and process expired proposals. Proposals…, Detects expired proposals and processes expiration logic., Check if a proposal has passed its expiration time. Args: proposal: Dict with…, Return seconds remaining until expiry. Returns 0 if already expired., Get human-readable expiry status for a proposal., ProposalStateMachine, Proposal State Machine — strict transition enforcement. States: DRAFT →… (+5 more)

### Community 34 - "TestSignalAggregator"
Cohesion: 0.12
Nodes (12): fixture, Tests for signal aggregation and consensus scoring., All bullish signals should produce LONG direction., All bearish signals should produce SHORT direction., Contradicting signals should produce NO_SIGNAL., Bullish consensus should have positive score., 100% agent agreement should give high agreement_pct., is_actionable should be False for weak consensus. (+4 more)

### Community 35 - "TestEMAPullbackStrategy"
Cohesion: 0.15
Nodes (11): Tests for EMA Pullback strategy signal generation., Create feature dict that strongly satisfies LONG conditions., Bullish features should produce LONG signal above threshold., Bearish features should produce SHORT signal above threshold., SL hint for LONG should be below entry price., TP hint for LONG should be above entry price., Adding 4h trend confirmation should increase score., EMA21 < EMA50 in a supposed long setup should lower score. (+3 more)

### Community 36 - "AgentOutput"
Cohesion: 0.13
Nodes (13): AgentOutput, BaseModel, Base output model that all agent outputs inherit from., CriticAgent, CriticOutput, AgentOutput, Any, field_validator (+5 more)

### Community 37 - "FeeSlippageEstimator"
Cohesion: 0.10
Nodes (13): FeeSlippageEstimator, Decimal, Estimates trading costs: exchange fees + market slippage. Fee model: Binance…, Estimate single-side trade cost. Args: notional: Order notional value (qty ×…, Estimate round-trip (open + close) total cost., Tests for fee and slippage cost estimation., Binance maker fee = 0.1% of notional., Binance taker fee = 0.1% (same for standard tier). (+5 more)

### Community 38 - "RiskRewardCalculator"
Cohesion: 0.11
Nodes (12): Decimal, Calculate R/R ratio. R/R = |take_profit - entry| / |entry - stop_loss| Args:…, Check if R/R ratio meets the minimum required., Computes risk/reward ratio for a trade setup., RiskRewardCalculator, Phase 3: Risk Engine Tests (TDD — written BEFORE implementation). Tests cover…, Tests for risk/reward ratio calculation., Classic 2:1 R/R for LONG. (+4 more)

### Community 39 - "TestDailyLossTracker"
Cohesion: 0.09
Nodes (10): fixture, Tests for daily loss tracking. Uses an in-memory mock — Redis integration…, Fresh tracker should have zero daily loss., Recording losses should accumulate., Profitable trades should not increase daily loss counter., Daily reset should clear accumulated losses., exceeds_limit() returns True when loss > limit., exceeds_limit() returns False when loss < limit. (+2 more)

### Community 40 - "TestPositionSizer"
Cohesion: 0.09
Nodes (12): LONG position with SL above entry should raise ValueError., SHORT position with SL below entry should raise ValueError., Risk % above 5% (safety cap) should raise ValueError., Negative account balance should raise ValueError., Result must include notional_value = quantity × entry_price., Position notional must not exceed max_position_pct of balance (default 20%)., Tests for position sizing using the fixed-risk formula. Formula: position_size…, Standard LONG position: $500,000 account, 1% risk, $100 stop distance. (+4 more)

### Community 41 - "TestSLTPCalculator"
Cohesion: 0.09
Nodes (12): Tests for stop-loss and take-profit calculation., ATR-based SL for LONG: entry - (atr_multiplier × ATR)., ATR-based SL for SHORT: entry + (atr_multiplier × ATR)., TP for LONG at 2:1 R/R., TP for SHORT at 2:1 R/R., Stop loss must always be below entry for LONG., Stop loss must always be above entry for SHORT., Take profit must always be above entry for LONG. (+4 more)

### Community 42 - "PaperExecutionService"
Cohesion: 0.15
Nodes (12): PaperExecutionService, Synchronous paper execution service for unit testing. For production (DB…, Tests for execution flow: APPROVED proposal → simulated fill → position., Return a factory for mock APPROVED proposals., execute() should return a dict with order details., A successfully filled order should create an open position., BUY recommendation should open LONG position., SELL recommendation should open SHORT position. (+4 more)

### Community 43 - "TestApprovalTokenSecurity"
Cohesion: 0.10
Nodes (11): Removing stop-loss after token issuance invalidates the token., Token with zero TTL should be rejected., Completely malformed tokens are rejected cleanly., Tokens from different secrets must not cross-validate., Two different tokens should have different fingerprints., Same token cannot be used twice (replay protection)., Token with modified signature is rejected., Token issued to user-1 cannot be used by user-2. (+3 more)

### Community 44 - "TestProposalBuilder"
Cohesion: 0.14
Nodes (11): Tests for building proposals from analysis results., build() should return a dict with required fields., LONG signal should map to BUY recommendation., SHORT signal should map to SELL recommendation., Proposal must include SL, TP, R/R, fees from risk assessment., New proposal should start in DRAFT status., Proposal must have an expiration timestamp., Should raise ValueError if proceed_to_proposal is False. (+3 more)

### Community 45 - "api.ts"
Cohesion: 0.11
Nodes (17): PnLChart(), Props, OrdersPage(), api, AppNotification, LoginResponse, notificationsApi, Order (+9 more)

### Community 46 - "MarketRegimeOutput"
Cohesion: 0.13
Nodes (10): MarketRegimeAgent, MarketRegimeOutput, AgentOutput, Any, field_validator, Market Regime Agent — classifies the current market environment. Analyzes…, Output from the Market Regime Agent., Analyzes macro market regime from multi-timeframe features. (+2 more)

### Community 47 - "schemas/market.py"
Cohesion: 0.09
Nodes (27): CandleListResponse, CandleQueryParams, CandleResponse, DataQualityReport, MarketSnapshotResponse, OrderBookLevel, OrderBookResponse, BaseModel (+19 more)

### Community 48 - "TestApprovalTokenManager"
Cohesion: 0.14
Nodes (10): Tests for one-time approval token lifecycle., Issued token should be a non-empty string., A freshly issued token should be valid., Token issued for user-1 should fail for user-2., Token should be invalid after being consumed., Token should be invalid after expiry time., Token should be invalid if proposal price changes after issuance., Two proposals should produce different tokens. (+2 more)

### Community 49 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, noEmit, noFallthroughCasesInSwitch (+11 more)

### Community 50 - "TestEncryptionSecurity"
Cohesion: 0.18
Nodes (11): decrypt_value(), encrypt_value(), _get_fernet(), Get or create Fernet encryption instance., Encrypt a sensitive value (e.g., API key) for database storage., Decrypt a stored sensitive value., Encrypted value must decrypt to original., API key must not appear as substring in its ciphertext. (+3 more)

### Community 51 - "MarketPage.tsx"
Cohesion: 0.12
Nodes (11): DataCoverage(), Props, TfStats, EBState, ErrorBoundary, formatVolume(), MarketPage(), Props (+3 more)

### Community 52 - "execution.py"
Cohesion: 0.21
Nodes (17): execute_proposal(), get_pnl_summary(), get_position(), list_positions(), list_trade_results(), CurrentUser, DBSession, get (+9 more)

### Community 53 - "ApprovalTokenManager"
Cohesion: 0.18
Nodes (10): ApprovalTokenManager, Any, Mark token as used (one-time-use enforcement)., Decode token payload without validating signature (for inspection)., Compute HMAC-SHA256 signature., Compute a hash of the security-critical proposal fields. Any change to price,…, Compute a fingerprint for one-time-use tracking., Issues and validates one-time approval tokens. Uses HMAC-SHA256 signed tokens… (+2 more)

### Community 54 - "ProposalService"
Cohesion: 0.14
Nodes (10): ProposalService, Any, AsyncSession, Decimal, Approve a proposal for execution. Validates: token, user, price drift. On price…, Edit a proposal (triggers RECONFIRM_REQUIRED for security-critical fields).…, Convert proposal ORM object to dict for token/API use., Orchestrates all proposal lifecycle operations. (+2 more)

### Community 55 - "NotificationService"
Cohesion: 0.15
Nodes (10): NotificationService, AsyncSession, Notify about a filled order., Notify about a risk limit being exceeded., Notify about a system error., Notify about Binance WebSocket disconnection., Multi-channel notification dispatcher., Send notification to dashboard and optionally Telegram. Always saves to DB (for… (+2 more)

### Community 56 - "make_candle"
Cohesion: 0.11
Nodes (11): make_candle(), make_flat_candles(), With too few candles, most indicators should return None., Volume SMA should be computed when candles >= 20., Relative volume = 1 when current volume equals average., Volume spike detected when current > 2× average., Majority green candles → bullish pressure bias., VWAP should be computed when at least 2 candles. (+3 more)

### Community 57 - "features/engine.py"
Cohesion: 0.12
Nodes (10): AsyncSession, Feature Engine — Orchestration layer for all feature computation. Pulls candle…, FeatureRepository, AsyncSession, datetime, Repository for TechnicalFeature records., Insert a new feature record., Get the most recent feature record for a symbol/timeframe. (+2 more)

### Community 58 - "BaseAgent"
Cohesion: 0.17
Nodes (10): BaseAgent, Any, Augment prompt with format correction instruction on retry., Abstract base class for all analysis agents. Subclasses must implement: - name:…, Unique agent identifier., System instruction that defines the agent's role., Build the user-facing prompt from market context and features., Parse and validate LLM response text into a typed output model. (+2 more)

### Community 59 - "execution/service.py"
Cohesion: 0.17
Nodes (12): ExecuteRequest, BaseModel, PaperExecutionServiceAsync, Any, Decimal, Paper Execution Service — orchestrates APPROVED proposal → simulated fill →…, Async paper execution service with DB persistence. Used in the API and Celery…, Execute proposal and persist order + position to DB. Args: proposal_dict:… (+4 more)

### Community 60 - "ConnectionManager"
Cohesion: 0.15
Nodes (9): ConnectionManager, Any, WebSocket, WebSocket connection manager — broadcast to multiple frontend clients. Provides…, Manages WebSocket connections and broadcast logic., Accept and register a new WebSocket connection., Remove a disconnected WebSocket., Broadcast an event to all connected clients. Silently removes clients that fail… (+1 more)

### Community 61 - "TelegramService"
Cohesion: 0.16
Nodes (8): AsyncClient, Send order execution notification., Send a system alert notification., Close the HTTP client., Sends notifications via Telegram Bot API. Uses httpx directly instead of…, Send a text message to the configured chat. Returns True if sent successfully,…, Send a formatted trade proposal notification., TelegramService

### Community 62 - "TestPaperFillSimulator"
Cohesion: 0.12
Nodes (9): Zero or negative quantity should raise ValueError., Tests for simulated order fill logic., MARKET order fills immediately at current market price (zero slippage)., MARKET BUY order fill price includes slippage (slightly above market)., LIMIT BUY fills when current price <= limit price., LIMIT BUY does NOT fill when current price > limit price., LIMIT SELL fills when current price >= limit price., Fee = notional × fee_rate (with zero slippage for exact calculation). (+1 more)

### Community 63 - "TestPaperPositionManager"
Cohesion: 0.12
Nodes (9): Tests for paper position tracking., Opening a LONG position returns position dict., Unrealized PnL for LONG should be positive when price rises., Unrealized PnL for LONG should be negative when price falls., Unrealized PnL for SHORT should be positive when price falls., Closing a position should return a TradeResult dict., Net PnL = gross PnL - entry fee - exit fee., Stop loss hit should close position at stop price. (+1 more)

### Community 64 - "TestPaperPnLTracker"
Cohesion: 0.12
Nodes (9): Tests for aggregated PnL tracking (realized + unrealized)., Fresh tracker should have zero values., Recording a winning trade increases realized PnL., Recording a losing trade decreases realized PnL., Win rate = winning_trades / total_trades × 100., Max drawdown should track the largest cumulative loss., total_pnl = realized_pnl + unrealized_pnl., Profit factor = gross_wins / abs(gross_losses). (+1 more)

### Community 65 - "react"
Cohesion: 0.23
Nodes (12): App(), ProtectedRoute(), PublicRoute(), DashboardPage(), LoginPage(), authApi, createEventsWebSocket(), LoginRequest (+4 more)

### Community 66 - "main.py"
Cohesion: 0.20
Nodes (14): Register rate limiter on the FastAPI app., register_rate_limiter(), Configure structured logging for the application. - Development: colored,…, setup_logging(), close_db(), init_db(), Initialize database connection (called on startup)., Close database connections (called on shutdown). (+6 more)

### Community 67 - "models/audit.py"
Cohesion: 0.15
Nodes (12): list_audit_logs(), CurrentUser, DBSession, get, Audit log API endpoints — view audit trail., List audit log entries (newest first). Admin only., Audit log helper — fire-and-forget helper for recording audit events. Usage:…, AuditLog (+4 more)

### Community 68 - "features.py"
Cohesion: 0.22
Nodes (14): compute_features(), get_latest_features(), get_strategy_signal(), list_strategies(), CurrentUser, DBSession, get, post (+6 more)

### Community 69 - "Settings"
Cohesion: 0.15
Nodes (9): Any, field_validator, Parse comma-separated or JSON array fallback chain into list., Ensure system defaults to PAPER mode for safety., Check if system is in live trading mode., Return appropriate Binance base URL based on testnet setting., Application settings loaded from environment variables., Settings (+1 more)

### Community 70 - "TestPriceDriftGuard"
Cohesion: 0.11
Nodes (9): fixture, Phase 5: Proposal + Approval System Tests (TDD — written BEFORE…, Tests for price drift detection requiring re-confirmation., Price within threshold should NOT trigger reconfirmation., Price drift above threshold MUST trigger reconfirmation., Downward drift above threshold also triggers reconfirmation., Result should include the actual drift in basis points., Identical price should not require reconfirmation. (+1 more)

### Community 71 - "TestProposalExpirationService"
Cohesion: 0.13
Nodes (8): Tests for proposal expiration detection., Proposal past expiration time should be detected as expired., Proposal with future expiration should not be expired., seconds_until_expiry() should be positive for active proposals., seconds_until_expiry() should return 0 for expired proposals., REJECTED proposals should not be re-expired., EXECUTED proposals should not be re-expired., TestProposalExpirationService

### Community 72 - "TestExchangeFilter"
Cohesion: 0.19
Nodes (8): Tests for Binance exchange filter enforcement. LOT_SIZE: quantity must be…, Quantity must be rounded down to nearest step_size., Price must be rounded to nearest tick_size., Quantity below min_qty should raise ValueError., Quantity above max_qty should raise ValueError., Notional below min_notional should raise ValueError., Valid order should pass all filters., TestExchangeFilter

### Community 73 - "RiskAnalysisAgent"
Cohesion: 0.16
Nodes (8): AgentOutput, Any, field_validator, Risk Analysis Agent — assesses trade-specific risk factors. Given a potential…, Output from the Risk Analysis Agent., Evaluates risk profile of a proposed trade setup., RiskAnalysisAgent, RiskAnalysisOutput

### Community 74 - "notifications.py"
Cohesion: 0.23
Nodes (13): list_notifications(), mark_all_read(), mark_read(), CurrentUser, DBSession, get, post, Notification API endpoints — list, mark read, unread count. (+5 more)

### Community 75 - "PaperFillSimulator"
Cohesion: 0.27
Nodes (8): PaperFillSimulator, Any, Decimal, Paper Fill Simulator — simulates order fills for paper trading. Rules: MARKET…, Limit order: fills only when market crosses limit price., Simulates exchange order fills for paper trading environment., Simulate an order fill attempt. Args: order_type: 'MARKET' or 'LIMIT'…, Market order: fills immediately with slippage.

### Community 76 - "PaperPnLTracker"
Cohesion: 0.18
Nodes (8): PaperPnLTracker, Any, Decimal, Paper PnL Tracker — aggregates realized and unrealized P&L. Tracks: - Total…, Compute and return the full P&L summary., Aggregates all P&L metrics for paper trading performance. Usage: tracker =…, Record a completed trade result. Args: net_pnl: Net realized P&L (after fees) —…, Update the current unrealized P&L from open positions.

### Community 77 - "PaperPositionManager"
Cohesion: 0.23
Nodes (8): PaperPositionManager, Any, Decimal, Paper Position Manager — tracks open and closed paper positions. Handles: -…, Close a position and compute realized P&L. Args: position: Open position dict…, Manages paper trading positions with P&L computation. All values are Decimal…, Create and return a new open position. Args: symbol: Trading pair e.g.…, Compute unrealized PnL at a given market price. LONG: (current - entry) × qty…

### Community 78 - "GeminiService"
Cohesion: 0.19
Nodes (7): GeminiService, Any, Gemini AI Service — wraps google-genai SDK for ACTA. Provides: - Connection…, Build a prompt enriched with tool data context., Centralized Gemini AI service for chat and analysis., Return current Gemini API configuration status., Send a chat message with tool-calling context. The tools_context provides pre-…

### Community 79 - "CandlestickChart.tsx"
Cohesion: 0.23
Nodes (12): CandlestickChart(), candleToChart(), candleToVolume(), computeEMA(), dedup(), formatPrice(), formatTime(), OHLCTooltip (+4 more)

### Community 80 - "AnalysisPage.tsx"
Cohesion: 0.17
Nodes (9): AnalysisPage(), formatIndicatorValue(), IndicatorsTab(), Props, analysisApi, AnalysisWorkflow, featuresApi, strategyApi (+1 more)

### Community 81 - "market_data/service.py"
Cohesion: 0.13
Nodes (12): Application constants. Centralized constants that are NOT configurable (unlike…, Market data is too old to be trusted., StaleDataError, Binance REST API client. Client HTTP bất đồng bộ cho Binance REST API với: -…, Dịch vụ kiểm tra chất lượng dữ liệu (Data validation service). Phát hiện các…, Dịch vụ dữ liệu thị trường — Lớp điều phối (orchestration layer). Phối hợp giữa…, Any, Trình tạo ảnh chụp nhanh thị trường (Market snapshot builder). Tạo các ảnh chụp… (+4 more)

### Community 82 - "EMAPullbackStrategy"
Cohesion: 0.23
Nodes (7): EMAPullbackStrategy, Decimal, Score LONG setup conditions., Score SHORT setup conditions (mirror of long logic)., Safely extract a Decimal value from a feature dict., Rule-based EMA Pullback strategy. Consumes pre-computed feature dicts from the…, Evaluate strategy across all timeframes. Args: features_15m: feature dict for…

### Community 83 - "orders.py"
Cohesion: 0.27
Nodes (10): get_order(), list_orders(), CurrentUser, DBSession, get, Order, Orders API endpoints — view orders and fills., List orders with their fills (newest first). (+2 more)

### Community 84 - "FeatureEngine"
Cohesion: 0.25
Nodes (7): FeatureEngine, Any, Retrieve the most recent feature set from DB., Load candles from DB and convert to feature-ready dicts., Run all feature modules on a single timeframe., Orchestrates feature computation across all modules. Usage: engine =…, Compute all features for a symbol and persist to DB. Args: symbol: trading pair…

### Community 85 - "volatility.py"
Cohesion: 0.18
Nodes (6): Decimal, Volatility feature computation. ATR-based volatility classification, Bollinger…, Classify candle type based on body-to-range ratio., Compute all volatility features for the most recent candle. Returns: dict with…, Classify volatility regime from ATR as % of price., Compute annualized historical volatility from log returns. Standard close-to-…

### Community 86 - "._record_version"
Cohesion: 0.20
Nodes (7): Any, Transition proposal to a new status via state machine., Expire all proposals past their expiration time. Returns list of expired IDs., Recursively convert non-JSON-serializable types to safe equivalents., Record a version snapshot for audit trail., Create a new proposal in DRAFT status., _sanitize_for_json()

### Community 87 - "StrategyRegistry"
Cohesion: 0.20
Nodes (6): Registry mapping strategy names to instances. Allows the analysis pipeline to…, Register a strategy under a given name., Retrieve a strategy by name., Evaluate a named strategy with multi-timeframe features., Return list of registered strategy names., StrategyRegistry

### Community 88 - "conftest.py"
Cohesion: 0.24
Nodes (10): client(), db_session(), event_loop(), AsyncClient, AsyncSession, fixture, Test configuration and fixtures., Create event loop for async tests. (+2 more)

### Community 89 - "make_trending_candles"
Cohesion: 0.20
Nodes (6): make_downtrend_candles(), make_trending_candles(), Steadily rising candles should produce BULLISH trend., Swing highs should be found in enough data., SMA50 should be computed with 60 candles., Generate n candles with a steady uptrend.

### Community 90 - "volume.py"
Cohesion: 0.24
Nodes (6): Decimal, Volume feature computation. Computes volume-based features used by agents to…, Estimate buy/sell pressure from candle body direction. Green candles (close >…, Compute all volume features for the most recent candle. Args: candles: list of…, Compute VWAP using typical price × volume., _to_decimal()

### Community 92 - "SignalResult"
Cohesion: 0.27
Nodes (7): EMA Pullback Strategy — Rule-based signal generation. This strategy identifies…, Output from strategy evaluation., SignalResult, Strategy registry — manage and dispatch trading strategies., Interface that all strategies must implement., Strategy, Protocol

### Community 93 - ".make_book"
Cohesion: 0.20
Nodes (5): Create a synthetic order book., Spread should be correctly computed., Equal bid/ask quantity → neutral pressure., More bid volume → buy pressure., More ask volume → sell pressure.

### Community 94 - "env.py"
Cohesion: 0.31
Nodes (8): do_run_migrations(), Alembic env.py for async migrations., Run migrations in 'offline' mode., Run migrations with a connection., Run migrations in 'online' mode with async engine., run_async_migrations(), run_migrations_offline(), run_migrations_online()

### Community 95 - "AggregatedSignal"
Cohesion: 0.22
Nodes (5): AggregatedSignal, Any, Result of the signal aggregation process., True if consensus is strong enough to warrant a proposal., Compute weighted consensus signal. Returns direction LONG / SHORT / NO_SIGNAL…

### Community 96 - "system.py"
Cohesion: 0.28
Nodes (8): get_config(), get_license(), get_status(), get, System API: health check, configuration, and status., Return license and LLM integration info., Return non-sensitive system configuration. NEVER exposes API keys, secrets, or…, System status including dynamic service connectivity checks.

### Community 97 - "record_audit"
Cohesion: 0.17
Nodes (7): Any, AsyncSession, Request, Append an audit log entry. Silently swallows errors to avoid breaking main flow., record_audit(), AsyncSession, List active proposals (DRAFT, PENDING_REVIEW, RECONFIRM_REQUIRED).

### Community 98 - "BaseStrategy"
Cohesion: 0.25
Nodes (6): BaseStrategy, ABC, Base strategy interface., Abstract base class for all trading strategies., Strategy name identifier., Evaluate features and return a trade signal.

### Community 99 - "I18nContext.tsx"
Cohesion: 0.36
Nodes (7): I18nContext, I18nContextValue, I18nProvider(), LangToggle(), Lang, TranslationKey, translations

### Community 100 - "TestExtractJson"
Cohesion: 0.36
Nodes (3): Extract JSON object from LLM response that may contain markdown or extra text., Tests for BaseAgent.extract_json helper., TestExtractJson

### Community 101 - "config.py"
Cohesion: 0.36
Nodes (6): Environment, Enum, str, Application configuration using Pydantic Settings. All config is loaded from…, TradingMode, Telegram bot service for sending notifications. Telegram is used ONLY for…

### Community 102 - "logging.py"
Cohesion: 0.29
Nodes (7): get_logger(), Any, Structured JSON logging configuration using structlog. All logs include:…, Get a structured logger with optional initial context. Usage: logger =…, Remove sensitive values from log output. Any key containing 'secret',…, _secret_filter(), BoundLogger

### Community 103 - ".compute"
Cohesion: 0.25
Nodes (4): Find swing high points (local maxima)., Find swing low points (local minima)., Determine trend from swing structure. BULLISH: Higher Highs + Higher Lows…, Compute market structure features. Args: candles: OHLCV candle list (at least…

### Community 104 - "ProposalCard.tsx"
Cohesion: 0.29
Nodes (7): ProposalCard(), Props, REC_COLORS, STATUS_COLORS, executionApi, Proposal, proposalsApi

### Community 105 - ".check"
Cohesion: 0.29
Nodes (4): Any, Compute a 0-100 risk score. Higher = riskier. Considers: daily loss, spread,…, Classify a block reason for Prometheus label (short form)., Evaluate all risk conditions. Args: context: Dict containing all values needed…

### Community 106 - "phase1_api_test.sh"
Cohesion: 0.48
Nodes (5): fail(), info(), ok(), phase1_api_test.sh script, step()

### Community 107 - "rate_limit.py"
Cohesion: 0.33
Nodes (5): _key_func(), FastAPI, Request, Rate limiting middleware using slowapi. Protects API from abuse with…, Rate limit key: use real IP or forwarded IP.

### Community 108 - "notification_service.py"
Cohesion: 0.33
Nodes (5): NotificationChannel, NotificationEventType, Notification delivery channel., Notification event types., Notification service: dispatches notifications to multiple channels. Supports:…

### Community 109 - "AuditPage.tsx"
Cohesion: 0.33
Nodes (5): ACTION_COLORS, ACTION_LABELS, AuditPage(), auditApi, AuditLogEntry

### Community 110 - "error_handler.py"
Cohesion: 0.50
Nodes (4): FastAPI, Global error handler middleware. Catches all exceptions and returns consistent…, Register all global exception handlers on the FastAPI app., register_error_handlers()

### Community 111 - "UUID"
Cohesion: 0.40
Nodes (3): Record a human decision on a proposal., Get a proposal by ID., UUID

### Community 112 - ".apply"
Cohesion: 0.50
Nodes (3): Decimal, Apply all exchange filters to a proposed order. Args: quantity: Proposed order…, Floor value to the nearest multiple of step.

### Community 113 - "sign_approval_context"
Cohesion: 0.50
Nodes (4): Create an HMAC signature for the approval context. This proves the approval is…, Verify the HMAC signature of an approval context., sign_approval_context(), verify_approval_signature()

## Knowledge Gaps
- **87 isolated node(s):** `acta-backend`, `$schema`, `oxc`, `react/rules-of-hooks`, `warn` (+82 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ProposalRepository` connect `ProposalRepository` to `Base`, `ProposalExpirationService`, `record_audit`, `ai_chat.py`, `TradeProposal`, `PaperExecutionService`, `ProposalBuilder`, `UUID`, `execution.py`, `ProposalService`, `._record_version`, `execution/service.py`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `DailyLossTracker` connect `DailyLossTracker` to `FeeSlippageEstimator`, `RiskRewardCalculator`, `TestDailyLossTracker`, `risk/engine.py`, `TestExchangeFilter`, `TestPositionSizer`, `TestSLTPCalculator`, `TestRiskGate`, `orchestrator.py`, `AnalysisOrchestrator`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Why does `MarketDataService` connect `MarketDataService` to `TradingFlowTest`, `v1/market.py`, `market_data/service.py`, `BinanceRestClient`, `MarketDataRepository`, `DataValidator`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Are the 23 inferred relationships involving `Base` (e.g. with `AgentOutput` and `AgentRun`) actually correct?**
  _`Base` has 23 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `ProposalRepository` (e.g. with `ChatRequest` and `ChatResponse`) actually correct?**
  _`ProposalRepository` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `TimestampMixin` (e.g. with `AgentOutput` and `AgentRun`) actually correct?**
  _`TimestampMixin` has 23 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `BaseAgent` (e.g. with `LLMClient` and `LLMResponse`) actually correct?**
  _`BaseAgent` has 17 INFERRED edges - model-reasoned connections that need verification._