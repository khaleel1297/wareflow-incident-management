from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from contextlib import asynccontextmanager
import sqlite3
import smtplib
import os
from email.mime.text import MIMEText

DB_NAME = "wareflow.db"


# ---------------- DATABASE ---------------- #

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE,
            incident TEXT,
            priority TEXT,
            customer TEXT,
            contact TEXT,
            channel TEXT,
            category TEXT,
            assigned_team TEXT,
            response_sla TEXT,
            resolve_sla TEXT,
            status TEXT,
            created_at TEXT
        )
        """)

        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="WareFlow Incident Management",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------- MODEL ---------------- #

class TicketCreate(BaseModel):
    incident: str
    priority: str = "P2"
    customer: str = ""
    contact: str = ""
    channel: str = "Portal"


# ---------------- TICKET ID ---------------- #

def generate_ticket_id():
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM tickets")
        next_num = cur.fetchone()[0]

    return f"WF{next_num:06d}"


# ---------------- SLA ---------------- #

def get_sla(priority: str):

    sla_map = {
        "P1": {"response": "5-15 min", "resolve": "1-4 hours"},
        "P2": {"response": "15-30 min", "resolve": "4-8 hours"},
        "P3": {"response": "1-4 hours", "resolve": "1-3 business days"},
        "P4": {"response": "4-8 hours", "resolve": "3-5 business days"},
        "P5": {"response": "1 business day", "resolve": "5-7 business days"},
        "P6": {"response": "2 business days", "resolve": "Planned release"}
    }

    return sla_map.get(priority, sla_map["P3"])


# ---------------- AI INCIDENT ANALYSIS ---------------- #

def analyze_incident(text: str):

    text = text.lower()

    if "deadlock" in text or "db lock" in text:
        return "Database Lock Issue", "WareFlow L2 Team"

    if "orders not processing" in text or "queue stuck" in text:
        return "Interface Issue", "WareFlow L2 Team"

    if "slowness" in text or "cpu" in text:
        return "Performance Issue", "Infrastructure Team"

    if "login" in text or "password" in text:
        return "Access Issue", "Network Team"

    if "printer" in text or "barcode" in text:
        return "Printer Issue", "Printer Support Team"

    return "General Support", "WareFlow Support Team"


# ---------------- EMAIL ALERT ---------------- #

def send_email(ticket_id, ticket, category, team, sla):

    sender_email = os.getenv("WAREFLOW_EMAIL", "xxxxx@gmail.com")
    app_password = os.getenv("WAREFLOW_APP_PASSWORD", "xxxxx")
    receiver_email = os.getenv("WAREFLOW_ALERT_EMAIL", "xxxxx@gmail.com")

    body = f"""
New Incident Raised

Ticket ID: {ticket_id}
Incident: {ticket.incident}
Priority: {ticket.priority}
Customer: {ticket.customer}
Contact: {ticket.contact}

Category: {category}
Assigned Team: {team}

Response SLA: {sla['response']}
Resolve SLA: {sla['resolve']}
"""

    msg = MIMEText(body)

    msg["Subject"] = f"WareFlow Alert - {ticket_id}"
    msg["From"] = sender_email
    msg["To"] = receiver_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, app_password)
            server.send_message(msg)

        print("Email sent successfully")

    except Exception as e:
        print(f"Email failed: {e}")


# ---------------- HOME PAGE ---------------- #

@app.get("/")
def home():

    return HTMLResponse("""

    <html>

    <head>

        <title>WareFlow Incident Portal</title>

        <style>

            body {
                font-family: Arial;
                background: #f4f6f9;
                padding: 40px;
            }

            .container {
                background: white;
                max-width: 700px;
                margin: auto;
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0px 4px 12px rgba(0,0,0,0.1);
            }

            input, textarea, select {
                width: 100%;
                padding: 12px;
                margin-top: 10px;
                margin-bottom: 20px;
                border: 1px solid #ccc;
                border-radius: 8px;
            }

            button {
                background: #2563eb;
                color: white;
                border: none;
                padding: 12px 20px;
                border-radius: 8px;
                cursor: pointer;
            }

        </style>

    </head>

    <body>

        <div class="container">

            <h1>WareFlow Incident Portal</h1>

            <form id="incidentForm">

                <textarea id="incident" placeholder="Describe the incident" required></textarea>

                <select id="priority">
                    <option>P1</option>
                    <option selected>P2</option>
                    <option>P3</option>
                    <option>P4</option>
                    <option>P5</option>
                    <option>P6</option>
                </select>

                <input id="customer" placeholder="Customer / Site" />
                <input id="contact" placeholder="Contact Person" />

                <button type="submit">Submit Incident</button>

            </form>

            <div id="result"></div>

        </div>

        <script>

            document.getElementById('incidentForm').addEventListener('submit', async (e) => {

                e.preventDefault()

                const payload = {
                    incident: document.getElementById('incident').value,
                    priority: document.getElementById('priority').value,
                    customer: document.getElementById('customer').value,
                    contact: document.getElementById('contact').value,
                    channel: 'Portal'
                }

                const response = await fetch('/tickets', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                })

                const data = await response.json()

                document.getElementById('result').innerHTML = `
                    <h3>Ticket Created Successfully</h3>
                    <p><b>Ticket ID:</b> ${data.ticket_id}</p>
                    <p><b>Category:</b> ${data.category}</p>
                    <p><b>Assigned Team:</b> ${data.assigned_team}</p>
                    <p><b>Response SLA:</b> ${data.response_sla}</p>
                    <p><b>Resolve SLA:</b> ${data.resolve_sla}</p>
                `
            })

        </script>

    </body>

    </html>

    """)


# ---------------- CREATE INCIDENT ---------------- #

@app.post("/tickets")
def create_ticket(ticket: TicketCreate):

    ticket_id = generate_ticket_id()

    category, team = analyze_incident(ticket.incident)

    sla = get_sla(ticket.priority)

    created_at = datetime.utcnow().isoformat()

    with sqlite3.connect(DB_NAME) as conn:

        cur = conn.cursor()

        cur.execute("""
        INSERT INTO tickets (
            ticket_id,
            incident,
            priority,
            customer,
            contact,
            channel,
            category,
            assigned_team,
            response_sla,
            resolve_sla,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket_id,
            ticket.incident,
            ticket.priority,
            ticket.customer,
            ticket.contact,
            ticket.channel,
            category,
            team,
            sla['response'],
            sla['resolve'],
            'Open',
            created_at
        ))

        conn.commit()

    send_email(ticket_id, ticket, category, team, sla)

    return {
        "ticket_id": ticket_id,
        "category": category,
        "assigned_team": team,
        "response_sla": sla['response'],
        "resolve_sla": sla['resolve'],
        "status": "Open"
    }


# ---------------- TICKET API ---------------- #

@app.get("/tickets")
def get_tickets():

    with sqlite3.connect(DB_NAME) as conn:

        conn.row_factory = sqlite3.Row

        cur = conn.cursor()

        cur.execute("""
        SELECT *
        FROM tickets
        ORDER BY id DESC
        """)

        rows = cur.fetchall()

    return [dict(row) for row in rows]


# ---------------- DASHBOARD ---------------- #

@app.get("/dashboard")
def dashboard():

    return HTMLResponse("""

    <html>

    <head>

        <title>WareFlow Dashboard</title>

        <style>

            body {
                font-family: Arial;
                background: #f4f6f9;
                padding: 30px;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                background: white;
            }

            th, td {
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }

            th {
                background: #2563eb;
                color: white;
            }

        </style>

    </head>

    <body>

        <h1>Support Incident Dashboard</h1>

        <table>

            <thead>

                <tr>
                    <th>Ticket ID</th>
                    <th>Incident</th>
                    <th>Priority</th>
                    <th>Assigned Team</th>
                    <th>Response SLA</th>
                    <th>Resolve SLA</th>
                    <th>Status</th>
                </tr>

            </thead>

            <tbody id="ticketTable"></tbody>

        </table>

        <script>

            async function loadTickets() {

                const response = await fetch('/tickets')

                const tickets = await response.json()

                const table = document.getElementById('ticketTable')

                table.innerHTML = ''

                tickets.forEach(ticket => {

                    table.innerHTML += `
                        <tr>
                            <td>${ticket.ticket_id}</td>
                            <td>${ticket.incident}</td>
                            <td>${ticket.priority}</td>
                            <td>${ticket.assigned_team}</td>
                            <td>${ticket.response_sla}</td>
                            <td>${ticket.resolve_sla}</td>
                            <td>${ticket.status}</td>
                        </tr>
                    `
                })
            }

            loadTickets()

        </script>

    </body>

    </html>

    """)