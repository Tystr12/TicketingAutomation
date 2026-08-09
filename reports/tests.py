from django.test import TestCase
from django.urls import reverse

from tickets.models import Ticket, TicketEvent, GameState


class DashboardResetTests(TestCase):
    def test_reset_game_resets_counters_and_stops_simulation(self):
        game = GameState.get_state()
        game.score = 42
        game.tickets_closed = 3
        game.replies_sent = 5
        game.user_replies_received = 7
        game.simulation_running = True
        game.save()

        response = self.client.post(reverse("reset_game"))

        self.assertRedirects(response, "/reports/dashboard/?reset=game")

        game.refresh_from_db()
        self.assertEqual(game.score, 0)
        self.assertEqual(game.tickets_closed, 0)
        self.assertEqual(game.replies_sent, 0)
        self.assertEqual(game.user_replies_received, 0)
        self.assertFalse(game.simulation_running)

    def test_reset_tickets_deletes_tickets_and_resets_game(self):
        ticket = Ticket.objects.create(
            title="Sample issue",
            description="Example description",
            status=Ticket.STATUS_OPEN,
        )
        TicketEvent.objects.create(
            ticket=ticket,
            event_type="created",
            message="Ticket created",
        )

        game = GameState.get_state()
        game.score = 10
        game.tickets_closed = 1
        game.replies_sent = 2
        game.user_replies_received = 3
        game.simulation_running = True
        game.save()

        response = self.client.post(reverse("reset_tickets"))

        self.assertRedirects(response, "/reports/dashboard/?reset=tickets")
        self.assertEqual(Ticket.objects.count(), 0)
        self.assertEqual(TicketEvent.objects.count(), 0)

        game.refresh_from_db()
        self.assertEqual(game.score, 0)
        self.assertEqual(game.tickets_closed, 0)
        self.assertEqual(game.replies_sent, 0)
        self.assertEqual(game.user_replies_received, 0)
        self.assertFalse(game.simulation_running)

    def test_closing_message_do_not_trigger_reply_evaluation(self):
        ticket = Ticket.objects.create(
            title="VPN keeps disconnecting",
            description="User says VPN disconnects every few minutes while working from home.",
            category="Network",
            status=Ticket.STATUS_OPEN,
        )
        TicketEvent.objects.create(
            ticket=ticket,
            event_type="created",
            message="Ticket created",
        )

        game = GameState.get_state()
        game.score = 0
        game.replies_sent = 0
        game.simulation_running = True
        game.save()

        response = self.client.post(
            reverse("send_reply", args=[ticket.id]),
            {"reply_template": "closing_message"}
        )

        self.assertRedirects(response, f"/reports/dashboard/?selected={ticket.id}&show_evaluation=1")
        self.assertFalse(ticket.events.filter(event_type="score", message__icontains="Reply evaluation:").exists())
        game.refresh_from_db()
        self.assertEqual(game.replies_sent, 1)

    def test_let_me_know_on_hardware_ticket_is_neutral(self):
        ticket = Ticket.objects.create(
            title="Keyboard not working",
            description="User says their keyboard stopped working after docking their laptop.",
            category="PC peripheral",
            status=Ticket.STATUS_OPEN,
        )

        game = GameState.get_state()
        game.score = 0
        game.replies_sent = 0
        game.simulation_running = True
        game.save()

        response = self.client.post(
            reverse("send_reply", args=[ticket.id]),
            {"custom_message": "Let me know if that fixes it."}
        )

        self.assertRedirects(response, f"/reports/dashboard/?selected={ticket.id}&show_evaluation=1")
        self.assertTrue(ticket.events.filter(event_type="score", message__icontains="Reply evaluation:").exists())
        score_event = ticket.events.filter(event_type="score", message__icontains="Reply evaluation:").first()
        self.assertIn("Neutral", score_event.message)
        game.refresh_from_db()
        self.assertEqual(game.replies_sent, 1)

    def test_security_question_reply_is_neutral(self):
        ticket = Ticket.objects.create(
            title="Possible phishing email reported",
            description="User received a suspicious email with a link asking them to verify their account.",
            category="Security",
            status=Ticket.STATUS_OPEN,
        )

        game = GameState.get_state()
        game.score = 0
        game.replies_sent = 0
        game.simulation_running = True
        game.save()

        response = self.client.post(
            reverse("send_reply", args=[ticket.id]),
            {"custom_message": "Did you click on the link?"}
        )

        self.assertRedirects(response, f"/reports/dashboard/?selected={ticket.id}&show_evaluation=1")
        score_event = ticket.events.filter(event_type="score", message__icontains="Reply evaluation:").first()
        self.assertIn("Neutral", score_event.message)
        game.refresh_from_db()
        self.assertEqual(game.replies_sent, 1)

    def test_affect_multiple_reply_is_neutral_and_specific(self):
        ticket = Ticket.objects.create(
            title="Login problem affecting multiple users",
            description="Several users report they cannot access the system.",
            category="Access",
            status=Ticket.STATUS_OPEN,
        )

        game = GameState.get_state()
        game.score = 0
        game.replies_sent = 0
        game.simulation_running = True
        game.save()

        response = self.client.post(
            reverse("send_reply", args=[ticket.id]),
            {"custom_message": "Does this affect multiple users?"}
        )

        self.assertRedirects(response, f"/reports/dashboard/?selected={ticket.id}&show_evaluation=1")
        score_event = ticket.events.filter(event_type="score", message__icontains="Reply evaluation:").first()
        self.assertIn("Neutral", score_event.message)
        # simulate the user's follow-up reply and assert contents
        from reports.views import create_simulated_user_reply
        create_simulated_user_reply(Ticket.objects.get(id=ticket.id))
        user_reply_event = Ticket.objects.get(id=ticket.id).events.filter(event_type="user_reply").first()
        self.assertIsNotNone(user_reply_event)
        self.assertTrue("multiple" in user_reply_event.message.lower() or "only me" in user_reply_event.message.lower())
        game.refresh_from_db()
        self.assertEqual(game.replies_sent, 1)

    def test_more_info_reply_provides_details(self):
        ticket = Ticket.objects.create(
            title="Printer error",
            description="Users get an access denied error when printing.",
            category="Printer",
            status=Ticket.STATUS_OPEN,
        )

        game = GameState.get_state()
        game.score = 0
        game.replies_sent = 0
        game.simulation_running = True
        game.save()

        response = self.client.post(
            reverse("send_reply", args=[ticket.id]),
            {"custom_message": "Could you provide more information about the issue?"}
        )

        self.assertRedirects(response, f"/reports/dashboard/?selected={ticket.id}&show_evaluation=1")
        score_event = ticket.events.filter(event_type="score", message__icontains="Reply evaluation:").first()
        self.assertIn("Neutral", score_event.message)
        # simulate the user's follow-up reply and assert contents
        from reports.views import create_simulated_user_reply
        create_simulated_user_reply(Ticket.objects.get(id=ticket.id))
        user_reply_event = Ticket.objects.get(id=ticket.id).events.filter(event_type="user_reply").first()
        self.assertIsNotNone(user_reply_event)
        self.assertTrue("started" in user_reply_event.message.lower() or "error" in user_reply_event.message.lower())
        game.refresh_from_db()
        self.assertEqual(game.replies_sent, 1)

    def test_funny_replies_for_fun_category(self):
        ticket = Ticket.objects.create(
            title="Keyboard wrote a love letter",
            description="User says their keyboard typed a note to IT.",
            category="Fun",
            status=Ticket.STATUS_OPEN,
        )

        # create a simulated user reply for this ticket and verify it's one of the funny options
        from reports.views import create_simulated_user_reply
        reply_data = create_simulated_user_reply(ticket)
        self.assertIn('reply', reply_data)
        self.assertTrue(len(reply_data['reply']) > 0)
        self.assertEqual(reply_data['evaluation'], 'fun')

    def test_random_funny_injection_forces_funny_when_chance_is_one(self):
        import reports.views as views
        # force funny replies
        old = views.FUNNY_REPLY_CHANCE
        views.FUNNY_REPLY_CHANCE = 1.0
        try:
            ticket = Ticket.objects.create(
                title="Normal ticket",
                description="Just a normal problem",
                category="Hardware",
                status=Ticket.STATUS_OPEN,
            )
            from reports.views import create_simulated_user_reply
            reply_data = create_simulated_user_reply(ticket)
            self.assertEqual(reply_data['evaluation'], 'fun')
        finally:
            views.FUNNY_REPLY_CHANCE = old

    def test_replace_hardware_asks_for_room_and_floor(self):
        ticket = Ticket.objects.create(
            title="Laptop battery drains very quickly",
            description="User says their laptop battery goes from full to empty in less than one hour.",
            category="Hardware",
            status=Ticket.STATUS_OPEN,
        )

        response = self.client.post(
            reverse("send_reply", args=[ticket.id]),
            {"reply_template": "replace_hardware"}
        )

        self.assertRedirects(response, f"/reports/dashboard/?selected={ticket.id}&show_evaluation=1")
        latest_message = ticket.events.filter(event_type="message_sent").first()
        self.assertIn("room number", latest_message.message)
        self.assertIn("floor", latest_message.message)

    def test_send_password_reset_scoring_good(self):
        ticket = Ticket.objects.create(
            title="Password reset needed",
            description="User cannot sign in and needs a new password.",
            category="Password",
            status=Ticket.STATUS_OPEN,
        )

        game = GameState.get_state()
        game.score = 0
        game.replies_sent = 0
        game.simulation_running = True
        game.save()

        response = self.client.post(
            reverse("send_reply", args=[ticket.id]),
            {"reply_template": "send_password_reset"}
        )

        self.assertRedirects(response, f"/reports/dashboard/?selected={ticket.id}&show_evaluation=1")
        score_event = ticket.events.filter(event_type="score", message__icontains="Reply evaluation:").first()
        self.assertIn("Good", score_event.message)
        game.refresh_from_db()
        self.assertEqual(game.replies_sent, 1)

    def test_unlock_account_scoring_good(self):
        ticket = Ticket.objects.create(
            title="Account locked after failed attempts",
            description="User reports their account is locked and cannot sign in.",
            category="Password",
            status=Ticket.STATUS_OPEN,
        )

        game = GameState.get_state()
        game.score = 0
        game.replies_sent = 0
        game.simulation_running = True
        game.save()

        response = self.client.post(
            reverse("send_reply", args=[ticket.id]),
            {"reply_template": "unlock_account"}
        )

        self.assertRedirects(response, f"/reports/dashboard/?selected={ticket.id}&show_evaluation=1")
        score_event = ticket.events.filter(event_type="score", message__icontains="Reply evaluation:").first()
        self.assertIn("Good", score_event.message)
        game.refresh_from_db()
        self.assertEqual(game.replies_sent, 1)
