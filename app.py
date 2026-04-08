from flask import Flask, jsonify, request, session
from flask_cors import CORS
import mysql.connector
import hashlib
import os
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-to-a-random-string")

#allow Next.js dev server to call Flask
CORS(app, origins=["http://localhost:3000"], supports_credentials=True)


def get_conn():
    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    dbname = os.getenv("DB_NAME")
    port = int(os.getenv("DB_PORT", 3306))  # ADD THIS

    return mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=dbname,
        port=port,
        ssl_ca="ca.pem"
    )


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/test-db")
def test_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT NOW()")
    now = cur.fetchone()[0]
    cur.close()
    conn.close()
    return jsonify({"db_time": str(now)})


@app.post("/api/auth/login")
def login():
    data = request.get_json(force=True)
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "email and password required"}), 400

    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        "SELECT id, email, password_hash, role_id, organization_id FROM users WHERE email=%s",
        (email,),
    )
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user:
        return jsonify({"error": "invalid credentials"}), 401

    entered_sha = hashlib.sha256(password.encode("utf-8")).hexdigest()
    stored = user.get("password_hash")

    if stored not in (password, entered_sha):
        return jsonify({"error": "invalid credentials"}), 401

    session["user"] = {
        "id": user["id"],
        "email": user["email"],
        "role_id": user["role_id"],
        "organization_id": user["organization_id"],
    }

    return jsonify({"ok": True, "user": session["user"]})


@app.get("/api/auth/me")
def me():
    return jsonify({"user": session.get("user")})


@app.post("/api/auth/logout")
def logout():
    session.pop("user", None)
    return jsonify({"ok": True})

@app.get("/api/debug-tables")
def debug_tables():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SHOW TABLES")
    tables = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify({"tables": tables})

@app.get("/api/debug-users")
def debug_users():
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users")
    users = cur.fetchall()
    cur.close()
    conn.close()
    return {"users": users}

@app.get("/api/import-db")
def import_db():
    conn = get_conn()
    cur = conn.cursor()

    sql_path = BASE_DIR / "DB.sql"

    with open(sql_path, "r", encoding="utf-8") as f:
        sql = f.read()

    try:
        # ✅ Disable FK checks
        cur.execute("SET FOREIGN_KEY_CHECKS=0")

        # ✅ Split and execute
        statements = sql.split(";")
        for statement in statements:
            stmt = statement.strip()
            if stmt:
                try:
                    cur.execute(stmt)
                except Exception as e:
                    print("Skipping error:", e)

        # ✅ Re-enable FK checks
        cur.execute("SET FOREIGN_KEY_CHECKS=1")

        conn.commit()
        return {"status": "Database imported (with skips if needed)"}

    except Exception as e:
        return {"error": str(e)}

    finally:
        cur.close()
        conn.close()

@app.get("/api/create-test-user")
def create_test_user():
    conn = get_conn()
    cur = conn.cursor()

    password = "test123"
    hashed = hashlib.sha256(password.encode()).hexdigest()

    cur.execute("""
        INSERT INTO users (full_name, email, password_hash, role_id, organization_id)
        VALUES (%s, %s, %s, %s, %s)
    """, ("New User", "new@example.com", hashed, 1, 1))

    conn.commit()
    cur.close()
    conn.close()

    return {"status": "user created"}

@app.get("/api/reset-db")
def reset_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SET FOREIGN_KEY_CHECKS=0")

    cur.execute("SHOW TABLES")
    tables = cur.fetchall()

    for table in tables:
        cur.execute(f"DROP TABLE {table[0]}")

    cur.execute("SET FOREIGN_KEY_CHECKS=1")

    conn.commit()
    cur.close()
    conn.close()

    return {"status": "Database cleared"}
    
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)