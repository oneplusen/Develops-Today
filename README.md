# Travel Planner (FastAPI)

CRUD API for managing travel projects and places (Art Institute of Chicago artworks).

## Requirements

- Python 3.11+

## Local run

Install dependencies:

```bash
py -m pip install -r requirements.txt
```

Run the server:

```bash
py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open Swagger UI:

- `http://127.0.0.1:8000/docs`

## Docker

Build and run:

```bash
docker compose up --build
```

Swagger UI:

- `http://127.0.0.1:8000/docs`

## API notes

- A project can contain up to **10** places
- The same external place (`external_id`) cannot be added to the same project twice
- Place is validated against the Art Institute of Chicago API before storing
- Project cannot be deleted if any place is marked as visited

# Develops-Today
Develops Today test task
