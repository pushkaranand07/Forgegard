"""
python manage.py worker_status

Exit 0 if a worker has reported a heartbeat recently, 1 otherwise. Used as the
worker container's health check in docker-compose.
"""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Exit 0 when a worker heartbeat is fresh."

    def add_arguments(self, parser):
        parser.add_argument("--max-age", type=float, default=30.0, help="Seconds (default 30)")

    def handle(self, *args, **options):
        from api import jobs

        beat = jobs.read_heartbeat()
        if not beat:
            raise CommandError("no worker heartbeat")
        age = time.time() - beat["ts"]
        if age > options["max_age"]:
            raise CommandError(f"last worker heartbeat {age:.0f}s ago")
        self.stdout.write(f"worker alive (pid {beat['pid']}, {age:.1f}s ago, device {beat['device']})")
