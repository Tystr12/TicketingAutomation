from django.db import models

from django.db import models


class Ticket(models.Model):
    PRIORITY_CRITICAL = 0
    PRIORITY_HIGH = 1
    PRIORITY_MEDIUM = 2
    PRIORITY_LOW = 3

    PRIORITY_CHOICES = [
        (PRIORITY_CRITICAL, "Critical"),
        (PRIORITY_HIGH, "High"),
        (PRIORITY_MEDIUM, "Medium"),
        (PRIORITY_LOW, "Low"),
    ]

    STATUS_OPEN = "open"
    STATUS_WAITING_USER = "waiting_user"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_WAITING_USER, "Waiting user"),
        (STATUS_CLOSED, "Closed"),
    ]

    title = models.CharField(max_length=400)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    priority = models.IntegerField(
        choices=PRIORITY_CHOICES,
        default=PRIORITY_LOW
    )

    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN
    )

    category = models.CharField(max_length=100, blank=True, null=True)
    is_duplicate = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def ticket_number(self):
        return f"INC-{self.id:06d}"

    def __str__(self):
        return f"{self.ticket_number} - {self.title} ({self.status})"

class TicketEvent(models.Model):
    EVENT_TYPES = [
        ("created", "Created"),
        ("status_changed", "Status changed"),
        ("priority_changed", "Priority changed"),
        ("marked_duplicate", "Marked duplicate"),
        ("unmarked_duplicate", "Unmarked duplicate"),
        ("message_sent", "Message sent"),
        ("user_reply", "User reply"),
        ("note", "Internal note"),
    ]

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="events"
    )

    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ticket.ticket_number} - {self.event_type}"