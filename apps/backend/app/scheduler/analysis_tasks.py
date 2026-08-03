"""Analysis Celery tasks — scheduled and manual-trigger analysis runs.

Tasks:
  - run_scheduled_analysis: Runs for all configured symbols every 15min
  - run_analysis_for_symbol: Single-symbol analysis (manual trigger)
"""

from __future__ import annotations

import asyncio

import structlog

from app.scheduler.worker import celery_app

logger = structlog.get_logger(__name__)


def _run_async(coro):
    """Bridge synchronous Celery task to async code."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _analyze_symbol(symbol: str) -> dict:
    """Run full analysis pipeline for one symbol and persist results."""
    from app.database.session import async_session_factory
    from app.agents.orchestrator import AnalysisOrchestrator
    from app.repositories.agent_repo import AgentWorkflowRepository

    async with async_session_factory() as db:
        repo = AgentWorkflowRepository(db)
        workflow = await repo.create_workflow(symbol=symbol, trigger_type="SCHEDULED")

        try:
            orchestrator = AnalysisOrchestrator(db)
            result = await orchestrator.analyze(symbol)
            result_dict = result.to_dict()

            # Save individual agent run records
            for agent_name in ["market_regime", "technical", "order_flow", "risk_analysis", "critic"]:
                agent_out = result_dict.get(agent_name)
                if agent_out and isinstance(agent_out, dict):
                    await repo.save_agent_run(
                        workflow_id=str(workflow.id),
                        agent_name=agent_name,
                        output_dict=agent_out,
                        status="SUCCESS",
                    )

            await repo.complete_workflow(
                workflow=workflow,
                success=result.success,
                analysis_result_dict=result_dict,
                error_message=result.error,
            )
            await db.commit()

            # Telegram notification if proceeding to proposal
            if result.proceed_to_proposal:
                await _notify_proposal_ready(symbol, result_dict)

            logger.info(
                "analysis_task_complete",
                symbol=symbol,
                success=result.success,
                direction=result.final_direction,
                proceed=result.proceed_to_proposal,
            )
            return result_dict

        except Exception as e:
            await repo.complete_workflow(
                workflow=workflow,
                success=False,
                analysis_result_dict={},
                error_message=str(e),
            )
            await db.commit()
            raise


async def _notify_proposal_ready(symbol: str, result: dict) -> None:
    """Send Telegram notification when analysis recommends a proposal."""
    from app.config import settings
    if not settings.telegram_enabled:
        return

    direction = result.get("final_direction", "UNKNOWN")
    score = result.get("consensus_score", 0)
    critic = result.get("critic", {}) or {}
    summary = critic.get("summary", "Analysis complete")

    message = (
        f"🔔 *ACTA Analysis Alert*\n"
        f"Symbol: `{symbol}`\n"
        f"Direction: *{direction}*\n"
        f"Consensus: {score:.1f}/100\n"
        f"Summary: {summary}\n\n"
        f"_Review and approve in the dashboard._"
    )

    try:
        import httpx
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(url, json={
                "chat_id": settings.telegram_chat_id,
                "text": message,
                "parse_mode": "Markdown",
            })
        logger.info("telegram_notification_sent", symbol=symbol)
    except Exception as e:
        logger.warning("telegram_notification_failed", error=str(e))


@celery_app.task(
    name="app.scheduler.analysis_tasks.run_scheduled_analysis",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def run_scheduled_analysis(self) -> dict:
    """Run analysis for all configured trading symbols every 15 minutes."""
    from app.config import settings
    symbols = settings.trading_symbols
    logger.info("scheduled_analysis_start", symbols=symbols)

    results = {}
    for symbol in symbols:
        try:
            result = _run_async(_analyze_symbol(symbol))
            results[symbol] = {"status": "success", "direction": result.get("final_direction")}
        except Exception as e:
            logger.error("scheduled_analysis_symbol_failed", symbol=symbol, error=str(e))
            results[symbol] = {"status": "error", "error": str(e)}

    return {"symbols_processed": len(symbols), "results": results}


@celery_app.task(
    name="app.scheduler.analysis_tasks.run_analysis_for_symbol",
    bind=True,
    max_retries=1,
)
def run_analysis_for_symbol(self, symbol: str) -> dict:
    """Manual trigger: run full analysis for a specific symbol."""
    logger.info("manual_analysis_start", symbol=symbol)
    try:
        result = _run_async(_analyze_symbol(symbol))
        return {"status": "success", "symbol": symbol, **result}
    except Exception as e:
        logger.error("manual_analysis_failed", symbol=symbol, error=str(e))
        self.retry(exc=e)
