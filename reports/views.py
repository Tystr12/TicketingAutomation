# reports/views.py
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from tickets.models import Ticket, TicketEvent
import random

def priority_label(priority):
    labels = {
        0: "CRITICAL",
        1: "HIGH",
        2: "MEDIUM",
        3: "LOW",
    }
    return labels.get(priority, "UNKNOWN")

def status_label(status):
    return str(status).upper()

def dashboard(request):
    qs = Ticket.objects.all()

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(category__icontains=q)
        )

    status = (request.GET.get("status") or "").strip().lower()
    if status in {"open", "waiting_user", "closed"}:
        qs = qs.filter(status=status)

    category = (request.GET.get("category") or "").strip()
    if category:
        qs = qs.filter(category__icontains=category)

    ordering = request.GET.get("ordering") or "-created_at"

    if ordering not in {"-created_at", "created_at", "priority"}:
        ordering = "-created_at"

    qs = qs.order_by(ordering)

    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    selected_ticket = None
    selected_ticket_id = request.GET.get("selected")

    if selected_ticket_id:
        selected_ticket = Ticket.objects.filter(id=selected_ticket_id).first()

    context = {
        "tickets": page_obj,
        "q": q,
        "status": status,
        "category": category,
        "ordering": ordering,
        "selected_ticket": selected_ticket,
        "selected_ticket_id": selected_ticket_id,
    }

    return render(request, "reports/dashboard.html", context)


@require_POST
def ticket_action(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    action = request.POST.get("action")

    if action == "close":
        old_status = ticket.status
        ticket.status = "closed"
        ticket.save()

        TicketEvent.objects.create(
            ticket=ticket,
            event_type="status_changed",
            message=f"Status changed (!CLOSED)\nPrevious status: !{status_label(old_status)}"
        )

    elif action == "reopen":
        old_status = ticket.status
        ticket.status = "open"
        ticket.save()

        TicketEvent.objects.create(
            ticket=ticket,
            event_type="status_changed",
            message=f"Status changed (!OPEN)\nPrevious status: !{status_label(old_status)}"
        )

    elif action == "duplicate":
        ticket.is_duplicate = True
        ticket.save()

        TicketEvent.objects.create(
            ticket=ticket,
            event_type="marked_duplicate",
            message="Duplicate changed (!DUPLICATE)\nTicket was marked as a duplicate."
        )

    elif action == "not_duplicate":
        ticket.is_duplicate = False
        ticket.save()

        TicketEvent.objects.create(
            ticket=ticket,
            event_type="unmarked_duplicate",
            message="Duplicate changed (!NOT_DUPLICATE)\nTicket was unmarked as duplicate."
        )

    elif action == "increase_priority":
        old_priority = ticket.priority
        ticket.priority = max(0, ticket.priority - 1)
        ticket.save()

        TicketEvent.objects.create(
            ticket=ticket,
            event_type="priority_changed",
            message=(
                f"Priority changed (!{priority_label(ticket.priority)})\n"
                f"Previous priority: !{priority_label(old_priority)}"
            )
        )

    elif action == "decrease_priority":
        old_priority = ticket.priority
        ticket.priority = min(3, ticket.priority + 1)
        ticket.save()

        TicketEvent.objects.create(
            ticket=ticket,
            event_type="priority_changed",
            message=(
                f"Priority changed (!{priority_label(ticket.priority)})\n"
                f"Previous priority: !{priority_label(old_priority)}"
            )
        )

    return redirect(f"/reports/dashboard/?selected={ticket.id}")

@require_POST
def send_reply(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    reply_template = request.POST.get("reply_template")
    custom_message = (request.POST.get("custom_message") or "").strip()

    replies = {
        "restart_pc": "Hi, please restart your PC and check if the issue is still happening.",
        "reconnect_monitor": "Hi, please unplug the monitor power cable for 30 seconds, plug it back in, and check that the display cable is firmly connected.",
        "send_screenshot": "Hi, could you please send a screenshot of the error message you are seeing?",
        "test_vpn": "Hi, please disconnect from VPN, reconnect again, and test if the issue continues.",
        "restart_printer": "Hi, please restart the printer and check whether other users are affected as well.",
        "more_info": "Hi, could you please provide more information about the issue, including when it started and whether it affects only you or multiple users?",
    }

    reply_message = custom_message or replies.get(reply_template)

    if reply_message:
        TicketEvent.objects.create(
            ticket=ticket,
            event_type="message_sent",
            message=f"Reply sent (!USER)\n{reply_message}"
        )

        old_status = ticket.status
        ticket.status = "waiting_user"
        ticket.save()

        TicketEvent.objects.create(
            ticket=ticket,
            event_type="status_changed",
            message=f"Status changed (!WAITING_USER)\nPrevious status: !{status_label(old_status)}"
        )

    return redirect(f"/reports/dashboard/?selected={ticket.id}")

@require_POST
def simulate_user_reply(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    possible_replies = [
        "I tried that, but the issue is still happening.",
        "That fixed it, thank you!",
        "It works now after restarting.",
        "I am still getting the same error message.",
        "I cannot test right now, but I will try later.",
        "This also affects my colleague.",
        "I sent a screenshot of the error.",
    ]

    reply = random.choice(possible_replies)

    TicketEvent.objects.create(
        ticket=ticket,
        event_type="user_reply",
        message=f"User replied (!USER)\n{reply}"
    )

    old_status = ticket.status
    ticket.status = "open"
    ticket.save()

    TicketEvent.objects.create(
        ticket=ticket,
        event_type="status_changed",
        message=f"Status changed (!OPEN)\nPrevious status: !{status_label(old_status)}"
    )

    return redirect(f"/reports/dashboard/?selected={ticket.id}")