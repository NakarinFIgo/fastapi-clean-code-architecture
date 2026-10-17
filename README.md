## FastAPI Clean Architecture Template

Python port of [golang-clean-code-architecture](../golang-clean-code-architecture). Same Clean
Architecture layers, same routes, same JSON shapes, same JWT tokens and Postgres tables, so the two
services can run side by side against one database.

Stack: FastAPI, SQLAlchemy 2 (PostgreSQL), PyMongo (MongoDB), pydantic-settings, PyJWT, bcrypt.

## Project structure

```
src/app
 |-config.py                        Settings (GOAPP_* env vars, same names as the Go project)
 |-domain
    |-entities                      pydantic request/response objects
    |-models                        SQLAlchemy models (users, user_tokens, user_permissions)
    |-repositories                  repository interfaces (ABC)
    |-errors.py
 |-usecases                         business logic (user, crud)
 |-interface
    |-handlers                      FastAPI routers (monitor, user, crud)
    |-repositories                  postgres / mongo repository implementations
 |-infrastructure
    |-api                           app factory, dependency wiring, error handlers, CRUD registry
    |-db                            postgres session factory, mongo client, table creation
 |-shared                           JWT + bcrypt, slug and schema helpers
```

Dependencies point inward: `domain` imports nothing from the other layers.

## Setup

1. `cp .env.template .env.dev` and edit values (change `GOAPP_SECRET_KEY`).
2. Start databases: `docker-compose up db mongodb`
3. Install: `python3.12 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"`
4. Create tables: `python -m app.infrastructure.db.migrate`
5. Run: `uvicorn app.infrastructure.api.main:create_app --factory --port 3000 --reload`
6. API docs: http://localhost:3000/docs

Or everything in Docker: `docker-compose up --build`.

## Endpoints (all under `/api/v1`)

| Method | Path | Auth |
|---|---|---|
| GET | `/` | no |
| POST | `/users/register` `/users/login` `/users/logout` `/users/refresh-token` | no |
| POST | `/users/profile` | JWT |
| GET | `/data/{slug}/describe` `/data/{slug}/` `/data/{slug}/{id}` | JWT |

Success responses are the bare payload; errors are `{"trace_id": "...", "message": "..."}`.

## Add a model to the generic CRUD

Add a `CrudResource` to `src/app/infrastructure/api/registry.py`. The slug is the table name with
`_` replaced by `-`. Mongo resources use `Datasource.MONGODB` and a pydantic model.

## Tests

```bash
pytest                      # unit + API tests (SQLite in memory, mongomock)
ruff check . && mypy src
```

Parity check against the Go service (needs both running on the same Postgres, same
`GOAPP_SECRET_KEY` and `GOAPP_NAME`):

```bash
GO_URL=http://127.0.0.1:3000 PY_URL=http://127.0.0.1:3001 pytest -m contract tests/contract
```

## Known differences from the Go project

- Kept on purpose (Go behaviour reproduced): refresh tokens use `GOAPP_JWT_ACCESS_EXPIRES`;
  duplicate email and >72-byte passwords return 500 on register; Postgres list totals
  (`total_data`, `total_page`) count only the rows on the current page; not-found and bad id on
  `/data/{slug}/{id}` return 400.
- Changed:
  1. `user_tokens` is not registered in the CRUD registry. In Go, any logged-in user can list every
     user's access and refresh tokens through `/data/user-tokens/`.
  2. A user without a `user_permissions` row can use the CRUD endpoints (Go panics on a nil
     type assertion).
  3. `_pageSize` below 1 falls back to 10 (Go passes a negative limit straight to GORM).
- Not ported: Go's swagger docs (FastAPI serves `/docs`), nested `user` object inside
  `user_permissions` rows.
