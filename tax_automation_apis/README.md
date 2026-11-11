# Tax Automation API (FastAPI + MySQL)

1. Create DB and tables:   `mysql -u root -p < schema.sql`
2. `python -m venv venv && source venv/bin/activate`  (Windows: `venv\Scripts\activate`)
3. `pip install -r requirements.txt`
4. `cp .env.example .env` and set your MySQL password
5. `uvicorn main:app --reload`
6. Open http://127.0.0.1:8000/docs

Endpoints (each supports GET list, GET by id, POST, PATCH, DELETE):
/categories /staff /clients /compliance-dates /invoices /messages /tasks
Extras: /clients/{id}/tasks, /clients/{id}/invoices, /clients/{id}/messages
Filters: e.g. /tasks?client_id=1&status=PENDING
