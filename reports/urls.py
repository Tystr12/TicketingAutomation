from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path("ticket/<int:ticket_id>/action/", views.ticket_action, name="ticket_action"),
    path("ticket/<int:ticket_id>/reply/", views.send_reply, name="send_reply"),
    path("ticket/<int:ticket_id>/simulate-reply/", views.simulate_user_reply, name="simulate_user_reply"),
    
]