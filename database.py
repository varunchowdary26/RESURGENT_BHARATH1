import hashlib
import os
import sqlite3
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = DATABASE_URL is not None and DATABASE_URL.strip() != ""

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_FILE = os.path.join(BASE_DIR, "registrations.db")


def get_db_connection():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        conn.autocommit = True
        return conn
    else:
        conn = sqlite3.connect(DB_FILE, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = sqlite3.Row
        return conn


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_db():
    try:
        conn = get_db_connection()
        c = conn.cursor()

        if USE_POSTGRES:
            c.execute("""
                CREATE TABLE IF NOT EXISTS admin_auth (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                );
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS registrations (
                    id SERIAL PRIMARY KEY,
                    registration_id TEXT UNIQUE,
                    name TEXT NOT NULL,
                    phone TEXT UNIQUE NOT NULL,
                    age TEXT,
                    gender TEXT,
                    location TEXT,
                    questions TEXT,
                    checked_in TEXT DEFAULT 'False',
                    created_at TEXT
                );
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_phone ON registrations (phone);")
            c.execute("CREATE INDEX IF NOT EXISTS idx_reg_id ON registrations (registration_id);")
        else:
            c.execute("""
                CREATE TABLE IF NOT EXISTS admin_auth (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                );
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS registrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    registration_id TEXT UNIQUE,
                    name TEXT NOT NULL,
                    phone TEXT UNIQUE NOT NULL,
                    age TEXT,
                    gender TEXT,
                    location TEXT,
                    questions TEXT,
                    checked_in TEXT DEFAULT 'False',
                    created_at TEXT
                );
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_phone ON registrations (phone);")
            c.execute("CREATE INDEX IF NOT EXISTS idx_reg_id ON registrations (registration_id);")
            conn.commit()

        conn.close()
    except Exception as e:
        print(f"[DB INIT ERROR] Could not initialize database: {e}")


# Initialize database schema safely
init_db()


def get_admin_status():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT username FROM admin_auth LIMIT 1;")
    row = c.fetchone()
    conn.close()
    if row:
        return {"exists": True, "username": row["username"]}
    return {"exists": False}


def setup_admin(username, password):
    status = get_admin_status()
    if status["exists"]:
        return False, "Admin account already exists."

    conn = get_db_connection()
    c = conn.cursor()
    try:
        if USE_POSTGRES:
            c.execute(
                "INSERT INTO admin_auth (username, password_hash) VALUES (%s, %s);",
                (username.strip(), hash_password(password))
            )
        else:
            c.execute(
                "INSERT INTO admin_auth (username, password_hash) VALUES (?, ?);",
                (username.strip(), hash_password(password))
            )
            conn.commit()
        return True, "Admin created successfully"
    except Exception as e:
        return False, f"Failed to save credentials: {str(e)}"
    finally:
        conn.close()


def verify_admin(username, password):
    conn = get_db_connection()
    c = conn.cursor()
    param = (username.strip(),)
    if USE_POSTGRES:
        c.execute("SELECT username, password_hash FROM admin_auth WHERE username = %s LIMIT 1;", param)
    else:
        c.execute("SELECT username, password_hash FROM admin_auth WHERE username = ? LIMIT 1;", param)

    row = c.fetchone()
    conn.close()

    if not row:
        return False, "Invalid username or password"

    if row["password_hash"] == hash_password(password):
        return True, "Login successful"

    return False, "Invalid username or password"


def add_registration(data):
    phone = "".join(filter(str.isdigit, str(data.get("phone", ""))))
    if not phone or len(phone) < 10:
        return None, "Please provide a valid 10-digit mobile number."

    conn = get_db_connection()
    c = conn.cursor()

    try:
        if USE_POSTGRES:
            c.execute("SELECT registration_id FROM registrations WHERE phone = %s;", (phone,))
        else:
            c.execute("SELECT registration_id FROM registrations WHERE phone = ?;", (phone,))

        if c.fetchone():
            return None, "This mobile number has already been registered."

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Process optional fields: Idea Brief and Guest Questions
        idea = str(data.get("ideaBrief", "") or "").strip()
        guest_q = str(data.get("guestQuestion", "") or "").strip()
        combined_text = str(data.get("questions", "") or "").strip()

        if not combined_text:
            parts = []
            if idea:
                parts.append(f"[Idea/Patent Brief]: {idea}")
            if guest_q:
                parts.append(f"[Question to Chief Guests]: {guest_q}")
            combined_text = "\n\n".join(parts) if parts else "None"

        if USE_POSTGRES:
            c.execute("""
                INSERT INTO registrations (name, phone, age, gender, location, questions, checked_in, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'False', %s)
                RETURNING id;
            """, (
                str(data.get("name", "")).strip(),
                phone,
                str(data.get("age", "")).strip(),
                str(data.get("gender", "")).strip(),
                str(data.get("location", "")).strip(),
                combined_text,
                now_str
            ))
            row_id = c.fetchone()["id"]
            reg_id = f"RB-2026-{row_id:04d}"
            c.execute("UPDATE registrations SET registration_id = %s WHERE id = %s;", (reg_id, row_id))
        else:
            c.execute("""
                INSERT INTO registrations (name, phone, age, gender, location, questions, checked_in, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'False', ?);
            """, (
                str(data.get("name", "")).strip(),
                phone,
                str(data.get("age", "")).strip(),
                str(data.get("gender", "")).strip(),
                str(data.get("location", "")).strip(),
                combined_text,
                now_str
            ))
            row_id = c.lastrowid
            reg_id = f"RB-2026-{row_id:04d}"
            c.execute("UPDATE registrations SET registration_id = ? WHERE id = ?;", (reg_id, row_id))
            conn.commit()

        return reg_id, None

    except Exception as e:
        if not USE_POSTGRES:
            conn.rollback()
        return None, f"Database error: {str(e)}"
    finally:
        conn.close()


def get_registration(reg_id):
    conn = get_db_connection()
    c = conn.cursor()
    clean_id = reg_id.strip()

    if USE_POSTGRES:
        c.execute("SELECT * FROM registrations WHERE registration_id = %s OR phone = %s LIMIT 1;", (clean_id, clean_id))
    else:
        c.execute("SELECT * FROM registrations WHERE registration_id = ? OR phone = ? LIMIT 1;", (clean_id, clean_id))

    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_registrations():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM registrations ORDER BY id DESC;")
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def check_in(reg_id):
    conn = get_db_connection()
    c = conn.cursor()
    clean_id = reg_id.strip()

    if USE_POSTGRES:
        c.execute("SELECT * FROM registrations WHERE registration_id = %s LIMIT 1;", (clean_id,))
    else:
        c.execute("SELECT * FROM registrations WHERE registration_id = ? LIMIT 1;", (clean_id,))

    row = c.fetchone()
    if not row:
        conn.close()
        return None, False

    already_checked = (row["checked_in"] == "True")
    if not already_checked:
        if USE_POSTGRES:
            c.execute("UPDATE registrations SET checked_in = 'True' WHERE registration_id = %s;", (clean_id,))
            c.execute("SELECT * FROM registrations WHERE registration_id = %s LIMIT 1;", (clean_id,))
        else:
            c.execute("UPDATE registrations SET checked_in = 'True' WHERE registration_id = ?;", (clean_id,))
            conn.commit()
            c.execute("SELECT * FROM registrations WHERE registration_id = ? LIMIT 1;", (clean_id,))
        row = c.fetchone()

    conn.close()
    return dict(row), already_checked
