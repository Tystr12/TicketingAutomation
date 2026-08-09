# Ticketing Automation

A Django-based simulation of an IT service desk workflow. The application
generates support tickets and lets the user prioritize, investigate, respond
to, escalate, and close incidents through an interactive dashboard.

## Live demo

[Open Ticketing Automation](https://ticketing-tystrodev.pythonanywhere.com/reports/dashboard/?speed=fast)

## Features

- Automatic generation of simulated IT incidents
- Search, filtering, sorting, and ticket categorization
- Priority and status management
- Escalation and duplicate handling
- User replies and internal notes
- Event history for every ticket
- Performance score and activity statistics
- Configurable simulation speed
- REST API built with Django REST Framework
- Automated tests for important workflows

## Technology

- Python
- Django and Django REST Framework
- Django ORM and SQLite
- HTML, CSS, and JavaScript
- PythonAnywhere

## Local setup

1. Clone the repository:

   ```bash
   git clone https://github.com/Tystr12/TicketingAutomation.git
   cd TicketingAutomation
   ```

2. Create and activate a virtual environment.

3. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and replace its development values.

5. Run the migrations and start the development server:

   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

## Tests

```bash
python manage.py test
```

## Purpose

This project was developed to explore data modelling, incident history,
workflow design, and automation in an IT support environment.
