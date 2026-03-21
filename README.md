#  Ticketing Automation System

A helpdesk-inspired ticket management system designed to simulate how support teams handle incoming issues, prioritize requests, and manage workflows efficiently.

##  Description

This project is a backend-focused application built with Django and Django REST Framework. It simulates a real-world helpdesk dashboard where tickets can be created, categorized, prioritized, and managed.

The goal of the project is to explore how support systems work internally and how automation (including AI) can improve efficiency and reduce manual workload.

##  Features

- Create and manage support tickets
- Assign priority levels (Low, Medium, High)
- Track ticket status (Open, In Progress, Closed)
- REST API for interacting with tickets
- Structured backend with scalable architecture

##  Future Improvements (AI Integration)

- Detect duplicate tickets using AI/NLP
- Suggest automatic ticket categorization
- Priority prediction based on ticket content
- Smart recommendations for support agents

##  Tech Stack

- Python
- Django
- Django REST Framework

##  What I Learned

- Designing REST APIs
- Structuring backend applications
- Handling data models and relationships
- Simulating real-world systems
- Thinking about automation and scalability

##  How to Run

```bash
git clone https://github.com/Tystr12/TicketingAutomation.git
cd TicketingAutomation
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
