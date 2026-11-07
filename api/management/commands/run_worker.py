"""
python manage.py run_worker

The analysis worker: loads both models once, reports a heartbeat for
/api/health/, then runs queued jobs (api/jobs.py) until stopped.

Jobs run in FORGEGUARD_MAX_CONCURRENT_INFERENCES threads (default 1) inside
this process, which is separate from the web server: an out-of-memory crash
kills one worker, never the site. Thread workers are used because Huey's
process workers are not available on Windows.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger("forgeguard.worker")


class Command(BaseCommand):
    help = "Run the ForgeGuard analysis worker."

    def add_arguments(self, parser):
        parser.add_argument("--no-warmup", action="store_true", help="Load models on the first job instead")

    def handle(self, *args, **options):
        from api import jobs
        from api.warmup import warmup

        if jobs.huey.immediate:
            self.stderr.write("The queue is in immediate mode (tests); nothing to consume.")
            return

        if not options["no_warmup"]:
            warmup()
        jobs.start_heartbeat()

        workers = max(1, settings.FORGEGUARD_MAX_CONCURRENT_INFERENCES)
        logger.info("Worker starting: backend=%s, threads=%d, max queue=%d",
                    settings.FORGEGUARD_QUEUE_BACKEND, workers, settings.FORGEGUARD_MAX_QUEUE)
        consumer = jobs.huey.create_consumer(workers=workers, worker_type="thread", periodic=True)
        consumer.run()
