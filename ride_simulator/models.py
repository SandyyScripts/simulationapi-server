from django.db import models
from django.utils import timezone
import datetime

class APIUsage(models.Model):
    request_count = models.IntegerField(default=0)
    first_request_timestamp = models.DateTimeField(default=timezone.now)

    def reset_if_necessary(self):
        now = timezone.now()
        if (now - self.first_request_timestamp).days > 15:
            self.request_count = 0
            self.first_request_timestamp = now
            self.save()

    def __str__(self):
        return f'{self.request_count} requests since {self.first_request_timestamp}'