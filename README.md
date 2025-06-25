# 🍽️ RMSPOS - Restaurant Management System Backend

RMSPOS is a modern backend system built with **FastAPI** for managing restaurants efficiently. It supports features like user roles, orders, menu management, and more.

> Developed by [Hari Moradiya](https://github.com/harimoradiya)

---

## 🚀 Features

- FastAPI-based RESTful API
- Role-based user management (admin, staff, owner)
- Restaurant, menu, category, and order item management
- SQLite or PostgreSQL support (customizable)
- JWT authentication
- Dependency injection and modular architecture

---

## 🧰 Tech Stack

- Python 3.10+
- FastAPI
- SQLAlchemy
- Alembic (for DB migrations)
- Pydantic
- Uvicorn
- JWT (OAuth2)

---

## 🖥️ How to Run (Windows / Linux / macOS)

### 🧾 Prerequisites

- Python 3.10 or later
- Git
- (Optional) Virtual Environment tool: `venv` or `virtualenv`

---

### 1. 🔁 Clone the repository

```bash
git clone https://github.com/harimoradiya/rmspos.git
cd rmspos
```

### 2. Create and activate a virtual environment (On Windows)

```bash
python -m venv venv
venv\Scripts\activate
```

### On Linux/macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. ⚙️ Set environment variables
You can configure the database URL and secret keys via a .env file.

Create a .env file in the root directory:

```bash
DATABASE_URL=sqlite:///./rmspos.db
SECRET_KEY=your_super_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### 5. Start the FastAPI server

```bash
uvicorn app.main:app --reload
```

It's will be running on the 
API Docs: http://127.0.0.1:8000/docs
Redoc: http://127.0.0.1:8000/redoc


Contributing
Contributions are welcome! Just fork the repository, create a feature branch, and open a pull request.



---

Let me know if you'd like:

- Postman collection link
- Swagger schema file

Or if your repo uses a PostgreSQL database by default, I’ll update the `.env` and DB steps.

