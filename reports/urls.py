from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="reports_home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("ticket/<int:ticket_id>/action/", views.ticket_action, name="ticket_action"),
    path("ticket/<int:ticket_id>/reply/", views.send_reply, name="send_reply"),
    path("process-replies/", views.process_simulated_replies, name="process_simulated_replies"),
    path("process-incoming-tickets/", views.process_incoming_tickets, name="process_incoming_tickets"),
    path("ticket/<int:ticket_id>/note/", views.add_internal_note, name="add_internal_note"),
    path("ticket/<int:ticket_id>/note/", views.add_internal_note, name="add_internal_note"),
    path("toggle-simulation/", views.toggle_simulation, name="toggle_simulation"),
]