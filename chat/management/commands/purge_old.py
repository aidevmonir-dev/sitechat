from django.core.management.base import BaseCommand

from chat.views import purge_old


class Command(BaseCommand):
    help = "Delete conversations older than RETENTION_DAYS. Safe to run from cron."

    def handle(self, *args, **options):
        self.stdout.write(f"Deleted {purge_old()} rows from old conversations.")
