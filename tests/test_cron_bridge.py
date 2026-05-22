from myagent.agent.runtime.cron_bridge import AgentCronBridge
from myagent.bus import MessageBus
from myagent.cron.types import CronJob, CronPayload, CronSchedule


async def test_cron_bridge_routes_system_jobs_as_agent_messages() -> None:
    bus = MessageBus()
    bridge = AgentCronBridge(bus)
    job = CronJob(
        id="job-1",
        name="memory-maintenance",
        schedule=CronSchedule(kind="every", every=86400),
        payload=CronPayload(
            message="Please consolidate pending memory proposals with memory_consolidate.",
            job_type="system",
        ),
    )

    await bridge.on_job(job)

    inbound = await bus.consume_inbound()
    assert inbound.channel == "scheduler"
    assert inbound.chat_id == "job-1"
    assert inbound.sender_id == "cron"
    assert inbound.metadata == {"job_name": "memory-maintenance", "source": "cron"}
    assert "memory_consolidate" in inbound.content


async def test_cron_bridge_preserves_user_job_route() -> None:
    bus = MessageBus()
    bridge = AgentCronBridge(bus)
    job = CronJob(
        id="job-2",
        name="drink-water",
        schedule=CronSchedule(kind="every", every=1200),
        payload=CronPayload(
            message="Tell the user to drink water.",
            channel="cli",
            chat_id="default",
        ),
    )

    await bridge.on_job(job)

    inbound = await bus.consume_inbound()
    assert inbound.channel == "cli"
    assert inbound.chat_id == "default"
    assert "Tell the user to drink water." in inbound.content
