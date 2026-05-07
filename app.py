from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import sqlite3
import io
import base64
import datetime
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

# 1x1 transparent GIF (tracking pixel)
PIXEL = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)

def get_db():
    db_path = os.environ.get("DB_PATH", "tracker.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id TEXT PRIMARY KEY,
            recipient TEXT,
            subject TEXT,
            sent_at TEXT,
            opened_at TEXT,
            open_count INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

# Pixel endpoint - alıcı maili açtığında bu çalışır
@app.route("/pixel/<email_id>.gif")
def pixel(email_id):
    conn = get_db()
    now = datetime.datetime.utcnow().isoformat()
    
    row = conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
    if row:
        if not row["opened_at"]:
            conn.execute(
                "UPDATE emails SET opened_at = ?, open_count = 1 WHERE id = ?",
                (now, email_id)
            )
        else:
            conn.execute(
                "UPDATE emails SET open_count = open_count + 1 WHERE id = ?",
                (email_id,)
            )
        conn.commit()
    conn.close()

    return send_file(
        io.BytesIO(PIXEL),
        mimetype="image/gif",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

# Mail kaydı oluştur (eklenti gönderirken çağırır)
@app.route("/track", methods=["POST"])
def track():
    data = request.json
    conn = get_db()
    now = datetime.datetime.utcnow().isoformat()
    
    conn.execute(
        "INSERT OR REPLACE INTO emails (id, recipient, subject, sent_at) VALUES (?, ?, ?, ?)",
        (data["id"], data.get("recipient", ""), data.get("subject", ""), now)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# Mail durumunu sorgula (eklenti popup'ı çağırır)
@app.route("/status/<email_id>")
def status(email_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
    conn.close()
    
    if not row:
        return jsonify({"found": False})
    
    return jsonify({
        "found": True,
        "id": row["id"],
        "recipient": row["recipient"],
        "subject": row["subject"],
        "sent_at": row["sent_at"],
        "opened_at": row["opened_at"],
        "open_count": row["open_count"],
        "opened": row["opened_at"] is not None
    })

# Tüm takip edilen mailler
@app.route("/emails")
def emails():
    conn = get_db()
    rows = conn.execute("SELECT * FROM emails ORDER BY sent_at DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
