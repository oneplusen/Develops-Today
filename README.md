# Travel Planner (FastAPI)

CRUD API for managing travel projects and places (Art Institute of Chicago artworks).

## Requirements

- Python 3.11+

## Configuration

Environment variables:

- `DATABASE_URL` (optional): SQLAlchemy database URL  
  Default: `sqlite:///./travel_planner.db`

## Local run

Install dependencies:

```bash
py -m pip install -r requirements.txt
```

Run the server:

```bash
py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

If port 8000 is busy (Windows), use a different port:

```bash
py -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
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

## Postman collection

Import `postman_collection.json` into Postman.

## API notes

- A project must contain **1..10** places
- The same external place (`external_id`) cannot be added to the same project twice
- Place is validated against the Art Institute of Chicago API before storing
- Project cannot be deleted if any place is marked as visited
