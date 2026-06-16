# reports/views.py
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from tickets.models import Ticket, TicketEvent, GameState
import random
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone


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

def add_score(points, reason):
    game = GameState.get_state()
    game.score += points
    game.save()
    return game


def user_confirmed_fixed(ticket):
    """
    Returns True if the latest user reply sounds like the issue is fixed.
    """
    latest_user_reply = ticket.events.filter(event_type="user_reply").first()

    if not latest_user_reply:
        return False

    text = latest_user_reply.message.lower()

    positive_phrases = [
        "fixed it",
        "works now",
        "it works",
        "thank you",
        "thanks",
        "resolved",
        "working now",
    ]

    return any(phrase in text for phrase in positive_phrases)

def process_incoming_tickets(request):
    game = GameState.get_state()

    if not game.simulation_running:
        return JsonResponse({
            "created": False,
            "simulation_running": False,
        })

    created_ticket = None

    # 25% chance every time this endpoint is called
    if random.random() < 0.25:
        created_ticket = create_random_ticket()

    return JsonResponse({
        "created": created_ticket is not None,
        "ticket_id": created_ticket.id if created_ticket else None,
        "ticket_number": created_ticket.ticket_number if created_ticket else None,
        "title": created_ticket.title if created_ticket else None,
        "priority": created_ticket.priority if created_ticket else None,
        "simulation_running": True,
    })


def create_random_ticket():
    ticket_templates = [
        {
            "title": "User cannot log in",
            "description": "User reports that they cannot log in after changing their password.",
            "priority": 2,
            "category": "Password",
        },
        {
            "title": "VPN keeps disconnecting",
            "description": "User says VPN disconnects every few minutes while working from home.",
            "priority": 2,
            "category": "Network",
        },
        {
            "title": "Printer queue is stuck",
            "description": "Print jobs are stuck in the queue and several users are affected.",
            "priority": 2,
            "category": "Printer",
        },
        {
            "title": "Monitor has no signal",
            "description": "User says their monitor is black even though the computer is turned on.",
            "priority": 3,
            "category": "PC peripheral",
        },
        {
            "title": "Outlook will not open",
            "description": "User reports that Outlook crashes immediately after starting.",
            "priority": 2,
            "category": "M365",
        },
        {
            "title": "Internet is down in building 3",
            "description": "Multiple users report no network connection in building 3.",
            "priority": 1,
            "category": "Internet and Networks",
        },
        {
            "title": "Medical testing server is unreachable",
            "description": "Several users report that the medical testing server cannot be reached.",
            "priority": 0,
            "category": "Medical",
        },
        {
            "title": "Keyboard not working",
            "description": "User says their keyboard stopped working after docking their laptop.",
            "priority": 3,
            "category": "PC peripheral",
        },
        {
            "title": "Teams microphone not detected",
            "description": "User says Microsoft Teams cannot detect their headset microphone.",
            "priority": 3,
            "category": "M365",
        },
        {
            "title": "Shared drive missing",
            "description": "User says the department shared drive is no longer visible.",
            "priority": 2,
            "category": "Access",
        },
        {
    "title": "Account locked after too many login attempts",
    "description": "User reports that their account is locked after entering the wrong password several times.",
    "priority": 2,
    "category": "Password",
},
{
    "title": "Shared mailbox missing in Outlook",
    "description": "User says the department mailbox disappeared from Outlook this morning.",
    "priority": 2,
    "category": "M365",
},
{
    "title": "Possible phishing email reported",
    "description": "User received a suspicious email with a link asking them to verify their account.",
    "priority": 1,
    "category": "Security",
},
{
    "title": "Laptop battery drains very quickly",
    "description": "User says their laptop battery goes from full to empty in less than one hour.",
    "priority": 3,
    "category": "Hardware",
},
{
    "title": "Cannot access patient system",
    "description": "User gets an access denied message when opening the patient system.",
    "priority": 1,
    "category": "Access",
},
{
    "title": "Several users cannot access shared drive",
    "description": "Multiple users in the same department report that the shared drive is unavailable.",
    "priority": 1,
    "category": "Shared drive",
},
    ]

    template = random.choice(ticket_templates)

    ticket = Ticket.objects.create(
        title=template["title"],
        description=template["description"],
        priority=template["priority"],
        category=template["category"],
        status=Ticket.STATUS_OPEN,
    )

    TicketEvent.objects.create(
        ticket=ticket,
        event_type="created",
        message="Ticket created (!NEW)\nTicket was automatically generated by the simulator."
    )

    return ticket

@require_POST
def toggle_simulation(request):
    game = GameState.get_state()
    game.simulation_running = not game.simulation_running
    game.save()

    return redirect("dashboard")

def create_simulated_user_reply(ticket):
    possible_replies = [
        "I tried that, but the issue is still happening.",
        "That fixed it, thank you!",
        "It works now after restarting.",
        "I am still getting the same error message.",
        "I cannot test right now, but I will try later.",
        "This also affects my colleague.",
        "I sent a screenshot of the error.",
        "The issue disappeared for a while, but now it is back.",
    ]

    reply = random.choice(possible_replies)

    TicketEvent.objects.create(
        ticket=ticket,
        event_type="user_reply",
        message=f"User replied (!USER)\n{reply}"
    )

    old_status = ticket.status
    ticket.status = Ticket.STATUS_OPEN
    ticket.user_reply_due_at = None
    ticket.is_waiting_for_simulated_reply = False
    ticket.save()

    TicketEvent.objects.create(
        ticket=ticket,
        event_type="status_changed",
        message=f"Status changed (!OPEN)\nPrevious status: !{status_label(old_status)}"
    )
    game = GameState.get_state()
    game.score += 10
    game.user_replies_received += 1
    game.save()

    TicketEvent.objects.create(
    ticket=ticket,
    event_type="score",
    message="Score changed (!+10)\nUser replied to the ticket."
    )

    return {
        "ticket_id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "reply": reply,
    }

def process_simulated_replies(request):
    game = GameState.get_state()

    if not game.simulation_running:
        return JsonResponse({
            "created_replies": 0,
            "simulation_running": False,
            "replies": [],
        })

    now = timezone.now()

    tickets_ready = Ticket.objects.filter(
        status=Ticket.STATUS_WAITING_USER,
        is_waiting_for_simulated_reply=True,
        user_reply_due_at__lte=now,
    )

    replies = []

    for ticket in tickets_ready:
        reply_data = create_simulated_user_reply(ticket)
        if reply_data:
            replies.append(reply_data)

    return JsonResponse({
        "created_replies": len(replies),
        "simulation_running": True,
        "replies": replies,
    })

def dashboard(request):
    qs = Ticket.objects.all()

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(category__icontains=q)
        )

    status = (request.GET.get("status") or "active").strip().lower()

    if status == "active":
        # Default view: tickets that still need attention
        qs = qs.exclude(status__in=[Ticket.STATUS_CLOSED, Ticket.STATUS_ESCALATED])

    elif status in {
        Ticket.STATUS_OPEN,
        Ticket.STATUS_WAITING_USER,
        Ticket.STATUS_CLOSED,
        Ticket.STATUS_ESCALATED,
    }:
        qs = qs.filter(status=status)

    elif status == "all":
        pass

    else:
        status = "active"
        qs = qs.exclude(status__in=[Ticket.STATUS_CLOSED, Ticket.STATUS_ESCALATED])

    category = (request.GET.get("category") or "").strip()
    if category:
        qs = qs.filter(category__icontains=category)

    ordering = request.GET.get("ordering") or "-updated_at"

    if ordering not in {"-updated_at", "-created_at", "created_at", "priority"}:
        ordering = "-updated_at"

    qs = qs.order_by(ordering)

    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    selected_ticket = None
    selected_ticket_id = request.GET.get("selected")
    game_state = GameState.get_state()
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
        "game_state": game_state,
    }

    return render(request, "reports/dashboard.html", context)

@require_POST
def ticket_action(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    action = request.POST.get("action")

    if action == "close":
        old_status = ticket.status
        ticket.status = Ticket.STATUS_CLOSED
        ticket.user_reply_due_at = None
        ticket.is_waiting_for_simulated_reply = False
        ticket.save()

        TicketEvent.objects.create(
            ticket=ticket,
            event_type="status_changed",
            message=f"Status changed (!CLOSED)\nPrevious status: !{status_label(old_status)}"
        )

        game = GameState.get_state()
        game.tickets_closed += 1

        if user_confirmed_fixed(ticket):
            game.score += 20
            score_message = "Score changed (!+20)\nTicket closed after user confirmed the issue was fixed."
        else:
            game.score -= 10
            score_message = "Score changed (!-10)\nTicket closed without user confirming the issue was fixed."

        game.save()

        TicketEvent.objects.create(
            ticket=ticket,
            event_type="score",
            message=score_message
        )

    elif action == "reopen":
        old_status = ticket.status
        ticket.status = Ticket.STATUS_OPEN
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

    elif action == "escalate_2nd_line":
        old_status = ticket.status
        ticket.status = Ticket.STATUS_ESCALATED
        ticket.user_reply_due_at = None
        ticket.is_waiting_for_simulated_reply = False
        ticket.save()

        TicketEvent.objects.create(
            ticket=ticket,
            event_type="status_changed",
            message=(
                f"Status changed (!ESCALATED)\n"
                f"Previous status: !{status_label(old_status)}\n"
                "Ticket escalated to 2nd line."
            )
        )

        add_score(8, "Escalated ticket to 2nd line")

        TicketEvent.objects.create(
            ticket=ticket,
            event_type="score",
            message="Score changed (!+8)\nTicket escalated to 2nd line."
        )

    return redirect(f"/reports/dashboard/?selected={ticket.id}")

@require_POST
def add_internal_note(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    note = (request.POST.get("internal_note") or "").strip()

    if note:
        TicketEvent.objects.create(
            ticket=ticket,
            event_type="note",
            message=f"Internal note (!NOTE)\n{note}"
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
        "closing_message": "Thanks for the feedback. We will be closing this ticket now. Please create a new ticket if the issue returns.",
    }

    reply_message = custom_message or replies.get(reply_template)

    if not reply_message:
        return redirect(f"/reports/dashboard/?selected={ticket.id}")

    TicketEvent.objects.create(
        ticket=ticket,
        event_type="message_sent",
        message=f"Reply sent (!USER)\n{reply_message}"
    )
    game = GameState.get_state()
    game.score += 5
    game.replies_sent += 1
    game.save()

    TicketEvent.objects.create(
    ticket=ticket,
    event_type="score",
    message="Score changed (!+5)\nReply sent to user."
    )

    old_status = ticket.status

    # Special final reply: send message, do NOT wait for user reply, close ticket
    if reply_template == "closing_message":
        ticket.status = Ticket.STATUS_CLOSED
        ticket.user_reply_due_at = None
        ticket.is_waiting_for_simulated_reply = False
        ticket.save()

        TicketEvent.objects.create(
            ticket=ticket,
            event_type="status_changed",
            message=(
                f"Status changed (!CLOSED)\n"
                f"Previous status: !{status_label(old_status)}"
            )
        )
        game = GameState.get_state()
        game.tickets_closed += 1

        if user_confirmed_fixed(ticket):
            game.score += 20
            score_message = "Score changed (!+20)\nTicket closed after user confirmed the issue was fixed."
        else:
            game.score -= 10
            score_message = "Score changed (!-10)\nTicket closed without user confirming the issue was fixed."

        game.save()

        TicketEvent.objects.create(
        ticket=ticket,
        event_type="score",
        message=score_message
        )

        return redirect(f"/reports/dashboard/?selected={ticket.id}")

    # Normal reply: send message, then wait for simulated user reply
    ticket.status = Ticket.STATUS_WAITING_USER

    delay_seconds = random.randint(20, 90)
    ticket.user_reply_due_at = timezone.now() + timedelta(seconds=delay_seconds)
    ticket.is_waiting_for_simulated_reply = True

    ticket.save()

    TicketEvent.objects.create(
        ticket=ticket,
        event_type="status_changed",
        message=(
            f"Status changed (!WAITING_USER)\n"
            f"Previous status: !{status_label(old_status)}\n"
            f"Simulated user reply expected in about {delay_seconds} seconds."
        )
    )

    return redirect(f"/reports/dashboard/?selected={ticket.id}")