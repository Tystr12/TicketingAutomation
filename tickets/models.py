from django.db import models

class Ticket(models.Model):
    title = models.CharField(max_length=400)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    priority = models.IntegerField(default=3)  # 1: High, 2: Medium, 3: Low
    status = models.CharField(max_length=50, default='Open')
    category = models.CharField(max_length=100, blank=True, null=True)
    is_duplicate = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.status})"