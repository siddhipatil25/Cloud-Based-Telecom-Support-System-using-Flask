# Telesupport Hub

Cloud-Based Telecom Support System using Flask.

## Features

- Customer registration and login
- Customer support ticket creation
- Admin dashboard for all complaints
- Support agent and technician ticket assignment
- Status and priority tracking
- SQLite database with demo seed data

## Demo Login

| Role | Email | Password |
| --- | --- | --- |
| Admin | admin@telesupport.com | admin123 |
| Agent | agent@telesupport.com | agent123 |
| Technician | tech@telesupport.com | tech123 |
| Customer | customer@telesupport.com | customer123 |

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.
