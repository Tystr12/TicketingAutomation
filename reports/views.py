# reports/views.py
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import render
from tickets.models import Ticket

def dashboard(request):
    qs = Ticket.objects.all()

    q = (request.GET.get("q") or "").strip()
    if q:
        # only search fields that exist on Ticket
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(category__icontains=q)
        )

    status = (request.GET.get("status") or "").strip().lower()
    if status in {"open", "closed"}:
        qs = qs.filter(status=status)

    category = (request.GET.get("category") or "").strip()
    if category:
        # exact match on category text; change to icontains if you want partials
        qs = qs.filter(category__icontains=category)

    ordering = request.GET.get("ordering") or "-created_at"
    # whitelist valid orderings only
    if ordering not in {"-created_at", "created_at", "priority"}:
        ordering = "-created_at"
    qs = qs.order_by(ordering)

    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "tickets": page_obj,
        "q": q,
        "status": status,
        "category": category,
        "ordering": ordering,
    }
    return render(request, "reports/dashboard.html", context)




