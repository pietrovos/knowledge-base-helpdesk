import contextlib

from celery import Celery
from celery.signals import worker_ready

from app.config import get_settings

settings = get_settings()

celery_app = Celery("supportlens", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_always_eager=settings.celery_eager,
    task_eager_propagates=False,
    imports=["app.worker.tasks"],
)


HEARTBEAT_KEY = "worker:heartbeat"


@worker_ready.connect
def _start_heartbeat(**_) -> None:
    """Publish liveness to Redis so the API can tell users when background work is stalled."""
    import threading
    import time

    from app.services.resilience import get_redis

    def beat() -> None:
        while True:
            with contextlib.suppress(Exception):
                get_redis().set(HEARTBEAT_KEY, str(time.time()), ex=30)
            time.sleep(10)

    threading.Thread(target=beat, daemon=True, name="heartbeat").start()
