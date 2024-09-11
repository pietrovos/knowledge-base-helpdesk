import logging

from app.services import ingestion
from app.worker.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(name="system.ping")
def ping() -> str:
    return "pong"


@celery_app.task(bind=True, name="ingest.process_version", max_retries=ingestion.MAX_ATTEMPTS - 1)
def process_version_task(self, version_id: int) -> None:
    try:
        ingestion.process_version(version_id)
    except ingestion.PermanentIngestError as e:
        ingestion.mark_failed(version_id, str(e))
    except ingestion.TransientIngestError as e:
        if self.request.retries >= self.max_retries:
            ingestion.mark_failed(
                version_id, f"{e} (gave up after {self.request.retries + 1} attempts)"
            )
            return
        delay = ingestion.backoff_seconds(self.request.retries)
        ingestion.mark_retrying(version_id, str(e), delay)
        raise self.retry(exc=e, countdown=delay) from e
    except Exception as e:
        log.exception("unexpected ingestion failure for version %s", version_id)
        ingestion.mark_failed(version_id, f"Unexpected error: {e}")
