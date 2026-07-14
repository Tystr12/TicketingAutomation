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

# Probability (0.0-1.0) that any simulated reply becomes a funny/wacky reply.
# Can be overridden in tests by setting reports.views.FUNNY_REPLY_CHANCE = <value>
FUNNY_REPLY_CHANCE = 0.05


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


def get_ticket_issue_type(ticket):
    text = " ".join(filter(None, [ticket.category, ticket.title, ticket.description])).lower()

    issue_types = {
        "printer": ["printer", "print", "paper jam", "toner", "spooler"],
        "monitor": ["monitor", "display", "no signal", "screen", "black screen"],
        "password": ["password", "login", "sign in", "account locked", "locked"],
        "network": ["vpn", "internet", "network", "disconnect", "connection", "wifi"],
        "m365": ["outlook", "teams", "mailbox", "email", "office"],
        "access": ["shared drive", "access denied", "permission", "patient system", "shared mailbox"],
        "hardware": ["battery", "keyboard", "microphone", "headset", "laptop", "dock", "pc peripheral", "peripheral", "mouse", "trackpad", "printer"],
        "security": ["phishing", "suspicious", "malware", "link", "security"],
    }

    for issue_type, keywords in issue_types.items():
        if any(keyword in text for keyword in keywords):
            return issue_type

    return "general"


def evaluate_reply_quality(ticket, reply_message):
    reply = (reply_message or "").lower()
    issue_type = get_ticket_issue_type(ticket)

    if any(keyword in reply for keyword in [
        "location",
        "room number",
        "room",
        "floor",
        "where are you",
        "which room",
        "desk",
    ]):
        return {
            "score_change": 2,
            "user_reply": "I'm on the 4th floor in room 421. Please let me know if you need anything else.",
            "evaluation": "neutral",
        }

    if any(keyword in reply for keyword in [
        "send a new password",
        "password reset",
        "password reset link",
        "reset link",
        "reset your password",
    ]):
        return {
            "score_change": 10,
            "user_reply": "Thanks, I received the password reset link and will update my password now.",
            "evaluation": "good",
        }

    if any(keyword in reply for keyword in [
        "unlock account",
        "unlock your account",
        "unlocked your account",
    ]):
        return {
            "score_change": 10,
            "user_reply": "Thanks, I can sign in again now.",
            "evaluation": "good",
        }

    # Specific diagnostic/question handlers
    # If the agent asked whether multiple users are affected, reply accordingly
    if any(keyword in reply for keyword in [
        "affect multiple",
        "does this affect multiple",
        "affects multiple",
        "multiple users",
        "others affected",
        "only you",
        "only me",
    ]):
        context_text = " ".join(filter(None, [getattr(ticket, 'title', ''), getattr(ticket, 'description', '')])).lower()
        if any(w in context_text for w in ["multiple", "several", "many"]):
            return {
                "score_change": 2,
                "user_reply": "Multiple users are affected in our department.",
                "evaluation": "neutral",
            }
        else:
            return {
                "score_change": 2,
                "user_reply": "It's only me — no one else is affected.",
                "evaluation": "neutral",
            }

    # If agent asked for more information (time started, error details), provide sensible details
    if any(keyword in reply for keyword in [
        "more information",
        "when it started",
        "what time",
        "details",
        "additional information",
        "please provide more information",
    ]):
        # Try to echo an error fragment from the ticket description if present
        context_text = (getattr(ticket, 'description', '') or '').lower()
        sample_error = None
        for candidate in ["access denied", "error", "crash", "not working", "no signal"]:
            if candidate in context_text:
                sample_error = candidate
                break

        reply_text = "It started this morning around 09:15 and affects only me."
        if sample_error:
            reply_text = f"It started this morning around 09:15. Error observed: {sample_error}. It affects only me."

        return {
            "score_change": 2,
            "user_reply": reply_text,
            "evaluation": "neutral",
        }

    # If agent asked for a screenshot, indicate one was provided
    if "screenshot" in reply:
        return {
            "score_change": 2,
            "user_reply": "I've attached a screenshot of the error message.",
            "evaluation": "neutral",
        }

    rules = {
        "printer": {
            "good": ["printer", "print", "paper jam", "toner", "spooler", "restart printer", "print queue", "printer driver", "paper tray"],
            "neutral": ["restart", "reboot", "power cycle", "check cable", "check connection"],
            "wrong": ["monitor", "screen", "vpn", "password", "outlook", "email", "battery"],
        },
        "monitor": {
            "good": ["monitor", "display", "no signal", "screen", "brightness", "cable", "power on", "video cable"],
            "neutral": ["restart", "reboot", "power cycle", "check cable", "check connection"],
            "wrong": ["printer", "paper jam", "toner", "vpn", "password", "outlook"],
        },
        "password": {
            "good": [
                "password",
                "reset password",
                "password reset",
                "unlock account",
                "login",
                "account locked",
                "credentials",
                "reset link",
            ],
            "neutral": ["restart", "reboot", "check", "verify"],
            "wrong": ["printer", "monitor", "vpn", "outlook", "email"],
        },
        "network": {
            "good": ["vpn", "internet", "network", "disconnect", "connection", "wifi", "router", "dns"],
            "neutral": ["restart", "reboot", "power cycle", "check cable", "check connection"],
            "wrong": ["printer", "monitor", "password", "outlook", "email"],
        },
        "m365": {
            "good": ["outlook", "teams", "mailbox", "email", "office", "exchange", "microsoft 365"],
            "neutral": ["restart", "reboot", "sign in", "check account"],
            "wrong": ["printer", "monitor", "vpn", "password", "battery"],
        },
        "access": {
            "good": ["access", "shared drive", "permission", "patient system", "shared mailbox", "network drive"],
            "neutral": ["restart", "reboot", "check permissions", "verify access"],
            "wrong": ["printer", "monitor", "vpn", "password", "email"],
        },
        "hardware": {
            "good": [
                "battery", "keyboard", "microphone", "headset", "laptop", "dock", "hardware",
                "plug in", "plug it in", "unplug", "unplug and replug", "replug", "replace hardware",
                "replace the hardware", "replace the device", "replace your hardware", "replacement"
            ],
            "neutral": ["restart", "reboot", "power cycle", "check cable", "verify location", "where are you located", "location"],
            "wrong": ["printer", "monitor", "vpn", "password", "email"],
        },
        "security": {
            "good": ["phishing", "suspicious", "malware", "link", "security", "report email"],
            "neutral": ["restart", "reboot", "check", "verify"],
            "wrong": ["printer", "monitor", "vpn", "password", "email"],
        },
        "general": {
            "good": ["restart", "reboot", "power cycle", "check", "verify", "update"],
            "neutral": ["please", "thank you", "let me know", "I'll check"],
            "wrong": [],
        },
    }

    rule = rules.get(issue_type, rules["general"])
    good = any(keyword in reply for keyword in rule["good"])
    wrong = any(keyword in reply for keyword in rule["wrong"])
    neutral = any(keyword in reply for keyword in rule["neutral"])

    generic_neutral = any(
        keyword in reply for keyword in [
            "please",
            "thank you",
            "let me know",
            "let you know",
            "i'll check",
            "i will try",
        ]
    )

    question_neutral = any(
        keyword in reply for keyword in [
            "did you ",
            "have you ",
            "could you ",
            "can you ",
            "would you ",
            "please check",
        ]
    )

    if wrong:
        return {
            "score_change": -10,
            "user_reply": "That didn't help; the issue is still happening.",
            "evaluation": "bad",
        }

    if good:
        return {
            "score_change": 10,
            "user_reply": "That fixed it, thank you!",
            "evaluation": "good",
        }

    if neutral or generic_neutral or question_neutral:
        return {
            "score_change": 2,
            "user_reply": "I tried that, but it didn't resolve the issue.",
            "evaluation": "neutral",
        }

    return {
        "score_change": -10,
        "user_reply": "That didn't help; the issue is still happening.",
        "evaluation": "bad",
    }


def get_last_sent_reply(ticket):
    message_event = ticket.events.filter(event_type="message_sent").first()
    if not message_event:
        return ""
    if "\n" in message_event.message:
        return message_event.message.split("\n", 1)[1]
    return message_event.message


def process_incoming_tickets(request):
    game = GameState.get_state()

    if not game.simulation_running:
        return JsonResponse({
            "created": False,
            "simulation_running": False,
        })

    created_ticket = None

    speed = getattr(game, "speed", GameState.SPEED_NORMAL)
    if speed == GameState.SPEED_RELAXED:
        chance = 0.1
    elif speed == GameState.SPEED_FAST:
        chance = 0.5
    else:
        chance = 0.25

    if random.random() < chance:
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
            "title": "My keyboard wrote a love letter to IT",
            "description": "User claims their keyboard started typing on its own and left a note.",
            "priority": 3,
            "category": "Fun",
        },
        {
            "title": "Computer possessed by a ghost",
            "description": "User reports strange windows opening and closing by themselves.",
            "priority": 3,
            "category": "Weird",
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

@require_POST
def set_speed(request):
    speed = request.POST.get("speed")
    if speed not in {
        GameState.SPEED_RELAXED,
        GameState.SPEED_NORMAL,
        GameState.SPEED_FAST,
    }:
        speed = GameState.SPEED_NORMAL

    game = GameState.get_state()
    game.speed = speed
    game.save()

    return redirect(f"/reports/dashboard/?speed={speed}")

@require_POST
def reset_game(request):
    game = GameState.get_state()
    game.score = 0
    game.tickets_closed = 0
    game.replies_sent = 0
    game.user_replies_received = 0
    game.simulation_running = False
    game.save()

    return redirect("/reports/dashboard/?reset=game")

@require_POST
def reset_tickets(request):
    TicketEvent.objects.all().delete()
    Ticket.objects.all().delete()

    game = GameState.get_state()
    game.score = 0
    game.tickets_closed = 0
    game.replies_sent = 0
    game.user_replies_received = 0
    game.simulation_running = False
    game.save()

    return redirect("/reports/dashboard/?reset=tickets")


def create_simulated_user_reply(ticket):
    last_reply = get_last_sent_reply(ticket)
    evaluation = evaluate_reply_quality(ticket, last_reply)

    # Entertainment mode: for fun/weird categories or by random chance,
    # return a humorous simulated user reply instead of the normal evaluation.
    if (getattr(ticket, 'category', None) and ticket.category.lower() in ("fun", "weird", "entertainment")) or random.random() < FUNNY_REPLY_CHANCE:
        funny_replies = [
            "I sacrificed a rubber chicken and it still didn't fix the problem.",
            "My cat walked across the keyboard and now it speaks in emojis.",
            "I unplugged it, waved a magic wand, and now it just hums mysteriously.",
            "It started after the midnight update from the mothership — not kidding.",
            "I put a sticker on it and the error went into hiding.",
        ]
        evaluation = {
            "score_change": 0,
            "user_reply": random.choice(funny_replies),
            "evaluation": "fun",
        }

    TicketEvent.objects.create(
        ticket=ticket,
        event_type="user_reply",
        message=f"User replied (!USER)\n{evaluation['user_reply']}"
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
    game.score += evaluation["score_change"]
    game.user_replies_received += 1
    game.save()

    TicketEvent.objects.create(
        ticket=ticket,
        event_type="score",
        message=(
            f"Score changed (!{evaluation['score_change']:+d})\n"
            f"Reply evaluation: {evaluation['evaluation'].title()}"
        )
    )

    return {
        "ticket_id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "reply": evaluation["user_reply"],
        "evaluation": evaluation["evaluation"],
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

    reset_action = request.GET.get("reset")
    speed_action = request.GET.get("speed")
    show_evaluation = request.GET.get("show_evaluation") == "1"
    reply_evaluation_message = None
    reply_evaluation_level = None

    # Only show reply evaluation if explicitly requested via show_evaluation parameter
    if selected_ticket and show_evaluation:
        score_event = selected_ticket.events.filter(
            event_type="score",
            message__icontains="Reply evaluation:"
        ).first()
        if score_event:
            text = score_event.message
            if "Reply evaluation:" in text:
                parts = text.split("Reply evaluation:", 1)
                reply_evaluation_message = parts[1].strip()
            else:
                reply_evaluation_message = text
            if reply_evaluation_message.lower().startswith("good"):
                reply_evaluation_level = "positive"
            elif reply_evaluation_message.lower().startswith("neutral"):
                reply_evaluation_level = "clear"
            else:
                reply_evaluation_level = "negative"

    context = {
        "tickets": page_obj,
        "q": q,
        "status": status,
        "category": category,
        "ordering": ordering,
        "selected_ticket": selected_ticket,
        "selected_ticket_id": selected_ticket_id,
        "game_state": game_state,
        "reset_action": reset_action,
        "speed_action": speed_action,
        "reply_evaluation_message": reply_evaluation_message,
        "reply_evaluation_level": reply_evaluation_level,
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
        "plug_peripheral": "Hi, please unplug the peripheral, wait 10 seconds, then plug it back in and verify whether it starts working.",
        "replace_hardware": "Hi, please let me know your room number and floor so I can arrange a replacement for the hardware if needed.",
        "arrange_replacement": "Thanks for your location. I'm arranging the hardware replacement and escalating this to our hardware team. They'll contact you shortly to schedule delivery.",
        "send_password_reset": "Hi, I have sent a password reset link to your email. Please follow the link to set a new password.",
        "unlock_account": "Hi, I have unlocked your account. Please try signing in again and let me know if you still see the issue.",
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

    evaluation = None
    if reply_template != "closing_message":
        evaluation = evaluate_reply_quality(ticket, reply_message)
        game = GameState.get_state()
        game.score += evaluation["score_change"]
        game.replies_sent += 1
        game.save()

        TicketEvent.objects.create(
            ticket=ticket,
            event_type="score",
            message=(
                f"Score changed (!{evaluation['score_change']:+d})\n"
                f"Reply evaluation: {evaluation['evaluation'].title()}"
            )
        )
    else:
        game = GameState.get_state()
        game.replies_sent += 1
        game.save()

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

        return redirect(f"/reports/dashboard/?selected={ticket.id}&show_evaluation=1")

    # Normal reply: send message, then wait for simulated user reply
    ticket.status = Ticket.STATUS_WAITING_USER

    if game.speed == GameState.SPEED_RELAXED:
        delay_seconds = random.randint(60, 120)
    elif game.speed == GameState.SPEED_FAST:
        delay_seconds = random.randint(10, 40)
    else:
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

    return redirect(f"/reports/dashboard/?selected={ticket.id}&show_evaluation=1")