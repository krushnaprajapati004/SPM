import os, sqlite3, json, hashlib, secrets
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, session, send_from_directory, redirect
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "farmpro.db")
app = Flask(__name__, static_folder=None)
app.secret_key = os.environ.get("FARMPRO_SECRET_KEY", "change-this-secret-before-deployment")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, type TEXT NOT NULL, name TEXT NOT NULL, fields_json TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS settings(user_id INTEGER PRIMARY KEY, theme TEXT DEFAULT 'light', name TEXT, email TEXT, FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, title TEXT NOT NULL, message TEXT NOT NULL, is_read INTEGER DEFAULT 0, created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id));
        """)
        # Seed a demo account and starter notifications for first-time local runs.
        row=con.execute("SELECT id FROM users WHERE email=?",("admin@farmpro.local",)).fetchone()
        if not row:
            cur=con.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
                ("Farm Admin","admin@farmpro.local",generate_password_hash("FarmPro@123"),datetime.now().isoformat(timespec="seconds")))
            uid=cur.lastrowid
            con.execute("INSERT OR IGNORE INTO settings(user_id,theme,name,email) VALUES(?,?,?,?)", (uid,"light","Farm Admin","admin@farmpro.local"))
            for title,msg in [("Crop care reminder","Review crop progress and planned field work."),("Inventory stock check","Check low stock items and reorder supplies."),("Welcome to FarmPro","Your farm workspace is ready.")]:
                con.execute("INSERT INTO notifications(user_id,title,message,created_at) VALUES(?,?,?,?)",(uid,title,msg,datetime.now().isoformat(timespec="seconds")))

def current_user():
    return session.get("user_id")

def login_required(fn):
    @wraps(fn)
    def wrapped(*args,**kwargs):
        if not current_user(): return jsonify(error="Please log in to continue."),401
        return fn(*args,**kwargs)
    return wrapped

@app.get("/")
def home():
    return send_from_directory(BASE_DIR,"index.html")

@app.get("/<path:path>")
def files(path):
    if path.startswith("api/"): return jsonify(error="Not found"),404
    if path.endswith(".html") and path not in {"index.html","auth.html","help.html"} and not current_user():
        return redirect("/auth.html")
    return send_from_directory(BASE_DIR,path)

@app.post("/api/signup")
def signup():
    data=request.get_json(silent=True) or {}
    name=(data.get("name") or "").strip()
    email=(data.get("email") or "").strip().lower()
    password=data.get("password") or ""
    if not name or not email or len(password)<4: return jsonify(error="Enter your name, valid email and password (at least 4 characters)."),400
    try:
        with db() as con:
            cur=con.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
                (name,email,generate_password_hash(password),datetime.now().isoformat(timespec="seconds")))
            uid=cur.lastrowid
            con.execute("INSERT INTO settings(user_id,theme,name,email) VALUES(?,?,?,?)",(uid,"light",name,email))
            con.execute("INSERT INTO notifications(user_id,title,message,created_at) VALUES(?,?,?,?)",(uid,"Welcome to FarmPro","Your account has been created.",datetime.now().isoformat(timespec="seconds")))
        session["user_id"]=uid
        return jsonify(ok=True)
    except sqlite3.IntegrityError: return jsonify(error="An account with this email already exists."),409

@app.post("/api/login")
def login():
    data=request.get_json(silent=True) or {}
    email=(data.get("email") or "").strip().lower()
    password=data.get("password") or ""
    with db() as con: user=con.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
    if not user or not check_password_hash(user["password_hash"],password): return jsonify(error="Incorrect email or password."),401
    session["user_id"]=user["id"]
    return jsonify(ok=True)

@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)

@app.get("/api/me")
def me():
    if not current_user(): return jsonify(authenticated=False)
    with db() as con: user=con.execute("SELECT id,name,email FROM users WHERE id=?",(current_user(),)).fetchone()
    return jsonify(authenticated=True,user=dict(user) if user else None)

@app.route("/api/settings",methods=["GET","POST"])
@login_required
def settings():
    uid=current_user()
    if request.method=="GET":
        with db() as con: row=con.execute("SELECT theme,name,email FROM settings WHERE user_id=?",(uid,)).fetchone()
        return jsonify(dict(row) if row else {"theme":"light"})
    data=request.get_json(silent=True) or {}
    with db() as con:
        old=con.execute("SELECT * FROM settings WHERE user_id=?",(uid,)).fetchone()
        theme=data.get("theme",old["theme"] if old else "light")
        name=data.get("name",old["name"] if old else "")
        email=data.get("email",old["email"] if old else "")
        con.execute("INSERT INTO settings(user_id,theme,name,email) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET theme=excluded.theme,name=excluded.name,email=excluded.email",(uid,theme,name,email))
        if data.get("name") or data.get("email"):
            con.execute("UPDATE users SET name=?,email=? WHERE id=?",(name,email,uid))
    return jsonify(ok=True)

@app.route("/api/records",methods=["GET","POST"])
@login_required
def records():
    uid=current_user()
    if request.method=="GET":
        typ=request.args.get("type","")
        with db() as con:
            rows=con.execute("SELECT * FROM records WHERE user_id=? AND type=? ORDER BY id",(uid,typ)).fetchall()
        return jsonify(records=[{"id":r["id"],"type":r["type"],"name":r["name"],"fields":json.loads(r["fields_json"]),"created_at":r["created_at"]} for r in rows])
    data=request.get_json(silent=True) or {}
    typ=(data.get("type") or "").strip()
    name=(data.get("name") or "").strip()
    fields=data.get("fields") or []
    if typ not in {"crops","labor","inventory","expenses","sales"} or not name: return jsonify(error="Invalid record type or missing name."),400
    now=datetime.now().isoformat(timespec="seconds")
    with db() as con:
        cur=con.execute("INSERT INTO records(user_id,type,name,fields_json,created_at) VALUES(?,?,?,?,?)",(uid,typ,name,json.dumps(fields),now))
        rec={"id":cur.lastrowid,"type":typ,"name":name,"fields":fields,"created_at":now}
        con.execute("INSERT INTO notifications(user_id,title,message,created_at) VALUES(?,?,?,?)",(uid,"New "+typ+" record","Added: "+name,now))
    return jsonify(record=rec),201

@app.get("/api/notifications")
@login_required
def get_notifications():
    with db() as con: rows=con.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC",(current_user(),)).fetchall()
    return jsonify(notifications=[dict(r) for r in rows])

@app.post("/api/notifications/read")
@login_required
def mark_notifications():
    with db() as con: con.execute("UPDATE notifications SET is_read=1 WHERE user_id=?",(current_user(),))
    return jsonify(ok=True)

def local_ai_advice(question):
    q=question.lower()
    if any(k in q for k in ["yellow","yellowing","leaves","leaf","spots"]):
        return "Crop health suggestion: Yellowing or spotted leaves can have several causes, including nutrient imbalance, water stress or pests. Check whether symptoms appear on old or new leaves, inspect the underside of leaves, and review soil moisture. Avoid applying chemicals until the cause is identified. If possible, share the crop name and a clear photo for more specific guidance."
    if any(k in q for k in ["fertilizer","manure","nutrient","npk"]):
        return "Fertilizer guidance: Base fertilizer decisions on a soil test and the crop's growth stage. Record product name, N-P-K grade, quantity, application date and field. Follow the product label and local agricultural recommendations; avoid over-application."
    if any(k in q for k in ["irrigation","water","watering","dry"]):
        return "Irrigation guidance: Check soil moisture in the crop root zone before watering. Consider crop stage, soil type, recent rainfall and weather. Prefer measured irrigation and avoid waterlogging. Keep each irrigation date and estimated water quantity in your farm records."
    if any(k in q for k in ["inventory","stock","seed","pesticide","spray"]):
        return "Inventory suggestion: Track each item with category, quantity, unit, purchase date, supplier and reorder level. Use older stock first where safe and appropriate, store chemicals in their original labelled containers, and keep pesticides separate from seeds and animal feed."
    if any(k in q for k in ["profit","expense","cost","income","sales"]):
        return "Farm finance suggestion: Record each expense with category, amount, date and field/crop. Record sales with quantity and unit price. Compare crop-wise revenue against seed, fertilizer, labor, irrigation, machinery and transport costs to estimate net profit."
    if any(k in q for k in ["labor","worker","wage","attendance"]):
        return "Labor management suggestion: Record worker name, work date, task, hours or days worked, agreed wage and payment status. Review daily attendance against the work completed and retain clear payment records."
    return "I can help with crop health, irrigation, fertilizer planning, inventory, labor and farm finances. Please include the crop name, growth stage, field conditions and what you observed so I can give a more useful recommendation. This local assistant provides general guidance, not a substitute for a qualified agronomist or soil test."

@app.post("/api/ai/advice")
@login_required
def ai_advice():
    data=request.get_json(silent=True) or {}
    question=(data.get("question") or "").strip()
    if not question: return jsonify(error="Please enter a question."),400
    # Optional generative AI: configure OPENAI_API_KEY and install requirements.
    key=os.environ.get("OPENAI_API_KEY")
    if key:
        try:
            from openai import OpenAI
            client=OpenAI(api_key=key)
            response=client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL","gpt-4o-mini"),
                messages=[
                    {"role":"system","content":"You are FarmPro AI, a cautious agricultural farm-management assistant. Give practical, concise general guidance. Ask for missing crop/location details. Do not invent diagnoses or pesticide dosages; recommend local agricultural experts and product labels for high-risk decisions."},
                    {"role":"user","content":question}
                ],temperature=0.3)
            answer=response.choices[0].message.content
            return jsonify(answer=answer,mode="generative")
        except Exception:
            pass
    return jsonify(answer=local_ai_advice(question),mode="local-advisor")

if __name__=="__main__":
    init_db()
    app.run(host="127.0.0.1",port=int(os.environ.get("PORT","5000")),debug=True)
