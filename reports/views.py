from django.core.paginator import Paginator
from django.shortcuts import render
from django.db.models import Q
from tickets.models import Ticket


def dashboard(request):
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    category = request.GET.get('category', '')
    ordering = request.GET.get('ordering', '-created_at')

    qs = Ticket.objects.all()

    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(created_by__username__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    if category:
        qs = qs.filter(category=category)
    

    qs = qs.order_by(ordering)
    paginator = Paginator(qs, 10)  # Show 10 tickets per page
    page = request.GET.get('page')
    tickets = paginator.get_page(page)

    return render(request, 'reports/dashboard.html', {
        'tickets': tickets, 
        'q': q,
        'status': status,
        'category': category,
        'ordering': ordering,
    })





