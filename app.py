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

app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True
)

CORS(app, origins=[
    "http://localhost:3000",
    "https://komodo-hub-5005-cmd.vercel.app"
], supports_credentials=True)



def get_conn():
    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    dbname = os.getenv("DB_NAME")
    port = int(os.getenv("DB_PORT", 3306))  # ADD THIS

    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=dbname,
        ssl_disabled=False
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)