# FastAPI Clean Architecture

เขียน [golang-clean-code-architecture](../golang-clean-code-architecture) ใหม่เป็น Python (FastAPI)
route, JSON, JWT และตาราง Postgres เหมือนต้นฉบับ

## โครงสร้างโค้ด

1. `02_backend/` คือ API ด้วย FastAPI, `01_frontend/` คือหน้า console ด้วย React + TypeScript
2. `02_backend/src/app` แบ่งเป็น 4 ชั้นตาม Clean Architecture
   - `domain`: entity, SQLAlchemy model, interface ของ repository (ABC) และ error ไม่ import ชั้นอื่นเลย
   - `usecases`: business logic (`user`, `crud`) คุยกับ repository ผ่าน interface เท่านั้น
   - `interface`: `handlers` คือ FastAPI router และ `repositories` คือตัวเขียนจริงของ Postgres/Mongo
   - `infrastructure`: ต่อสายทุกอย่างเข้าด้วยกัน (app factory, dependency injection, session ของ DB, migrate)
3. Dependency ชี้เข้าด้านในเสมอ `infrastructure` → `interface` → `usecases` → `domain` ทำให้เปลี่ยน DB หรือ framework ได้โดยไม่แตะ business logic
4. `shared` เก็บ helper ที่ใช้ร่วมกัน (JWT, bcrypt, slug, schema)
5. Generic CRUD: เพิ่ม `CrudResource` ใน `infrastructure/api/registry.py` ที่เดียว ก็ได้ endpoint `/api/v1/data/{slug}/` ของ model นั้น โดยเลือก datasource ได้ทั้ง Postgres และ Mongo
6. ที่ตั้งใจต่างจากต้นฉบับ Go
   - ไม่เปิด `user_tokens` ผ่าน CRUD เพราะ user ที่ login แล้วจะอ่าน token ของทุกคนได้
   - user ที่ไม่มีแถวใน `user_permissions` ใช้ CRUD ได้ (ต้นฉบับ Go panic)
   - `_pageSize` ต่ำกว่า 1 ใช้ค่า 10 แทนการส่งค่าติดลบให้ DB
7. Test อยู่ใน `02_backend/tests` ใช้ SQLite in-memory กับ mongomock จึงรันได้โดยไม่ต้องเปิด DB
8. `01_frontend/src` แบ่งตาม feature (`features/auth`, `features/data_browser`) ส่วนของที่ใช้ร่วมกันอยู่ใน `shared/`

## Run the project

Requirements: Python 3.12+, Node.js, Docker.

### 1. Start the databases

From the repo root:

```bash
docker-compose up db mongodb
```

### 2. Backend

```bash
cd 02_backend
cp env.template .env.dev         # rename the template, then edit values (change GOAPP_SECRET_KEY)
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python -m app.infrastructure.db.migrate          # create tables
python -m app.mock.seed --yes                    # optional: mock users and data
uvicorn app.infrastructure.api.main:create_app --factory --port 3000 --reload
```

API docs: http://localhost:3000/docs

### 3. Frontend

In a new terminal:

```bash
cd 01_frontend
cp env.template .env             # rename the template; API address and proxy target live here
npm install
npm run dev                      # http://localhost:5173/ui/ (proxies /api to :3000)
```

Or build it and let FastAPI serve it at http://localhost:3000/ui/:

```bash
npm run build
```

Mock users (after seeding): `admin@example.com`, `viewer@example.com`, `nopermission@example.com`.
Password for all: `Passw0rd!`.

### Everything in Docker

```bash
cp 02_backend/env.template 02_backend/.env.dev
docker-compose up --build
```

### Tests

```bash
cd 02_backend && pytest             # backend
cd 01_frontend && npm test          # frontend
```
