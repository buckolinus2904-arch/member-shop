import os
import secrets
import string
from flask import Flask, request, render_template_string, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
BASE_URL = os.environ.get(
    "BASE_URL", "https://membershop.vercel.app"
)

def get_db():
    return psycopg2.connect(DATABASE_URL)

def generate_key():
    alphabet = string.ascii_uppercase + string.digits
    parts = [
        "".join(secrets.choice(alphabet) for _ in range(4))
        for _ in range(4)
    ]
    return "MEMBER-" + "-".join(parts)

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS redeem_keys (
                    id BIGSERIAL PRIMARY KEY,
                    code TEXT UNIQUE NOT NULL,
                    redeemed BOOLEAN NOT NULL DEFAULT FALSE,
                    redeemed_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

HTML = """
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Member Shop Admin</title>
<style>
body {
    background: #0f1117;
    color: white;
    font-family: Arial, sans-serif;
    max-width: 650px;
    margin: 50px auto;
    padding: 20px;
}
.card {
    background: #1b1e27;
    border: 1px solid #333846;
    border-radius: 12px;
    padding: 24px;
}
input, button {
    box-sizing: border-box;
    width: 100%;
    padding: 12px;
    margin-top: 10px;
    border-radius: 8px;
    border: 1px solid #414657;
}
input {
    background: #10131a;
    color: white;
}
button {
    background: #6555e8;
    color: white;
    border: none;
    cursor: pointer;
    font-weight: bold;
}
pre {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    background: #10131a;
    padding: 15px;
    border-radius: 8px;
}
</style>
</head>
<body>
<div class="card">
<h1>Redeem-Key Generator</h1>
<form id="form">
<label>Admin Token</label>
<input id="token" type="password" required>
<label>Anzahl der Keys (1–500)</label>
<input id="amount" type="number" min="1" max="500"
       value="10" required>
<button type="submit">Keys generieren</button>
</form>
<h3>Generierte Keys</h3>
<pre id="result">Hier erscheinen deine Keys.</pre>
<button id="copy">Keys kopieren</button>
</div>
<script>
const form = document.getElementById("form");
const result = document.getElementById("result");

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    result.textContent = "Generiere Keys ...";

    try {
        const response = await fetch("/api/admin/generate-keys", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer " +
                    document.getElementById("token").value
            },
            body: JSON.stringify({
                amount: Number(
                    document.getElementById("amount").value
                )
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Fehler beim Generieren");
        }

        result.textContent = data.keys.join("\\n");
    } catch (error) {
        result.textContent = "Fehler: " + error.message;
    }
});

document.getElementById("copy").addEventListener("click", async () => {
    await navigator.clipboard.writeText(result.textContent);
});
</script>
</body>
</html>
"""

@app.get("/admin")
def admin_page():
    return render_template_string(HTML)

@app.post("/api/admin/generate-keys")
def generate_keys():
    if not ADMIN_TOKEN:
        return jsonify(error="ADMIN_TOKEN ist nicht konfiguriert"), 500

    auth = request.headers.get("Authorization", "")
    supplied_token = auth.removeprefix("Bearer ").strip()

    import hmac
    if not hmac.compare_digest(supplied_token, ADMIN_TOKEN):
        return jsonify(error="Nicht autorisiert"), 401

    data = request.get_json(silent=True) or {}
    amount = data.get("amount")

    if isinstance(amount, bool) or not isinstance(amount, int):
        return jsonify(error="Anzahl muss eine ganze Zahl sein"), 400

    if amount < 1 or amount > 500:
        return jsonify(error="Erlaubt sind 1 bis 500 Keys"), 400

    try:
        init_db()
        keys = []

        with get_db() as conn:
            with conn.cursor() as cur:
                attempts = 0
                while len(keys) < amount and attempts < amount * 3:
                    attempts += 1
                    code = generate_key()
                    cur.execute("""
                        INSERT INTO redeem_keys (code)
                        VALUES (%s)
                        ON CONFLICT (code) DO NOTHING
                        RETURNING code
                    """, (code,))
                    row = cur.fetchone()
                    if row:
                        keys.append(row[0])

        if len(keys) != amount:
            return jsonify(error="Nicht alle Keys konnten erstellt werden"), 500

        return jsonify(keys=keys, count=len(keys))

    except Exception:
        app.logger.exception("Key-Generierung fehlgeschlagen")
        return jsonify(error="Datenbankfehler beim Erstellen der Keys"), 500

if __name__ == "__main__":
    app.run(debug=False)
