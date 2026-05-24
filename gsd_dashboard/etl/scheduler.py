"""
ETL Scheduler — runs as a separate Fly.io Machine (cron worker).

Do NOT run this inside the Streamlit process.
Long-running operations would block session threads.

Usage:
    python -m etl.scheduler
or via Fly.io:
    [processes]
    etl = "python -m etl.scheduler"
"""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

log = logging.getLogger("etl.scheduler")


def main() -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from etl.sheets_sync import sync_issue_log, sync_stakeholders, sync_standards
    from etl.kpi_calculator import calculate_and_snapshot_kpis

    scheduler = BlockingScheduler(timezone="Asia/Beirut")

    # Hourly syncs (jitter ±60s to avoid thundering-herd on Google API)
    scheduler.add_job(
        sync_issue_log, "interval", hours=1, id="sync_issues",
        jitter=60, misfire_grace_time=120,
    )
    scheduler.add_job(
        sync_stakeholders, "interval", hours=1, id="sync_stakeholders",
        jitter=60, misfire_grace_time=120,
    )

    # Daily at 06:00 and 07:00 Beirut time
    scheduler.add_job(
        sync_standards,              "cron", hour=6,  minute=0, id="sync_standards",
        misfire_grace_time=600,
    )
    scheduler.add_job(
        calculate_and_snapshot_kpis, "cron", hour=7,  minute=0, id="kpi_snapshot",
        misfire_grace_time=600,
    )

    log.info("ETL scheduler starting. Jobs: %s", [j.id for j in scheduler.get_jobs()])
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("ETL scheduler stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
