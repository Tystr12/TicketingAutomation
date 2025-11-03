# api/views.py (or wherever your viewset is)
from django.db.models import Q, Case, When, Value, IntegerField
from rest_framework import viewsets
from .models import Ticket
from .serializers import TicketSerializer

class TicketViewSet(viewsets.ModelViewSet):
    serializer_class = TicketSerializer

    def get_queryset(self):
        qs = Ticket.objects.all()

        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(description__icontains=q) |
                Q(category__icontains=q) |
                Q(status__icontains=q)
            )

        status_param = (self.request.query_params.get("status") or "").strip()
        status_key = status_param.lower()
        if status_key in {"open", "closed"}:
            qs = qs.filter(status__iexact=status_param)  # case-insensitive exact


        category = (self.request.query_params.get("category") or "").strip()
        if category:
            qs = qs.filter(category__icontains=category)

        ordering = (self.request.query_params.get("ordering") or "-created_at").strip()

        # Logical priority ordering (if priority is text)
        if ordering == "priority":
            prio_order = Case(
                When(priority="high", then=Value(1)),
                When(priority="medium", then=Value(2)),
                When(priority="low", then=Value(3)),
                default=Value(99),
                output_field=IntegerField(),
            )
            qs = qs.annotate(_p=prio_order).order_by("_p", "-created_at")
        elif ordering in {"created_at", "-created_at"}:
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by("-created_at")

        return qs
