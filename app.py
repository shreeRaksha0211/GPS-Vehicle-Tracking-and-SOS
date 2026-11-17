import os, sqlite3, secrets, time
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, request, jsonify, render_template, session
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash
from twilio.rest import Client

app=Flask(__name__); app.secret_key=os.getenv("FLASK_SECRET","dev-change-me")
socketio=SocketIO(app,cors_allowed_origins="*",async_mode="threading")
DB=os.getenv("DATABASE_PATH","tracker.db")
def conn():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init():
 with conn() as c:
  c.executescript("""
  CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT,email TEXT UNIQUE,password TEXT,phone TEXT);
  CREATE TABLE IF NOT EXISTS vehicles(id INTEGER PRIMARY KEY,owner INTEGER,reg TEXT,label TEXT,secret TEXT,UNIQUE(owner,reg));
  CREATE TABLE IF NOT EXISTS access(vehicle INTEGER,viewer INTEGER,PRIMARY KEY(vehicle,viewer));
  CREATE TABLE IF NOT EXISTS locations(id INTEGER PRIMARY KEY,vehicle INTEGER,lat REAL,lon REAL,accuracy REAL,speed REAL,heading REAL,at TEXT);
  CREATE TABLE IF NOT EXISTS contacts(id INTEGER PRIMARY KEY,owner INTEGER,name TEXT,phone TEXT);
  CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY,owner INTEGER,vehicle INTEGER,message TEXT,at TEXT);
  """)
init()
def me():
 if not session.get("uid"): return None
 with conn() as c: return c.execute("SELECT * FROM users WHERE id=?",(session["uid"],)).fetchone()
def auth(f):
 @wraps(f)
 def w(*a,**k):
  if not me(): return jsonify(error="Sign in required"),401
  return f(*a,**k)
 return w
def stamp(): return datetime.now(timezone.utc).isoformat()
def regnorm(s): return "".join(x for x in (s or "").upper() if x.isalnum())
def permitted(c,vid,uid):
 return c.execute("SELECT v.* FROM vehicles v LEFT JOIN access a ON a.vehicle=v.id AND a.viewer=? WHERE v.id=? AND (v.owner=? OR a.viewer=?)",(uid,vid,uid,uid)).fetchone()
@app.get("/")
def home(): return render_template("index.html")
@app.get("/api/me")
def who(): 
 u=me(); return jsonify(user=dict(id=u["id"],name=u["name"],email=u["email"]) if u else None)
@app.post("/api/register")
def register():
 d=request.json or {}; 
 if not d.get("name") or "@" not in d.get("email","") or len(d.get("password",""))<10: return jsonify(error="Name, valid email and 10+ character password required"),400
 try:
  with conn() as c: cur=c.execute("INSERT INTO users(name,email,password,phone) VALUES(?,?,?,?)",(d["name"],d["email"].lower(),generate_password_hash(d["password"]),d.get("phone",""))); session["uid"]=cur.lastrowid
  return jsonify(ok=True)
 except sqlite3.IntegrityError: return jsonify(error="Email already registered"),409
@app.post("/api/login")
def login():
 d=request.json or {}
 with conn() as c: u=c.execute("SELECT * FROM users WHERE email=?",(d.get("email","").lower(),)).fetchone()
 if not u or not check_password_hash(u["password"],d.get("password","")): return jsonify(error="Invalid login"),401
 session["uid"]=u["id"]; return jsonify(ok=True)
@app.post("/api/logout")
def logout(): session.clear(); return jsonify(ok=True)
@app.get("/api/vehicles")
@auth
def list_vehicles():
 with conn() as c:
  rows=c.execute("""SELECT DISTINCT v.id,v.reg,v.label,v.owner,
  (SELECT lat FROM locations WHERE vehicle=v.id ORDER BY id DESC LIMIT 1) lat,
  (SELECT lon FROM locations WHERE vehicle=v.id ORDER BY id DESC LIMIT 1) lon,
  (SELECT at FROM locations WHERE vehicle=v.id ORDER BY id DESC LIMIT 1) at
  FROM vehicles v LEFT JOIN access a ON a.vehicle=v.id WHERE v.owner=? OR a.viewer=?""",(me()["id"],me()["id"])).fetchall()
 return jsonify(vehicles=[dict(x) for x in rows])
@app.post("/api/vehicles")
@auth
def add_vehicle():
 d=request.json or {}; r=regnorm(d.get("reg"))
 if not 5<=len(r)<=15: return jsonify(error="Enter a valid vehicle registration"),400
 secret=secrets.token_urlsafe(32)
 try:
  with conn() as c: cur=c.execute("INSERT INTO vehicles(owner,reg,label,secret) VALUES(?,?,?,?)",(me()["id"],r,d.get("label",""),generate_password_hash(secret)))
  return jsonify(ok=True,vehicle_id=cur.lastrowid,device_secret=secret,note="Copy the device secret now; it is shown once.")
 except sqlite3.IntegrityError: return jsonify(error="Vehicle already registered in your account"),409
@app.post("/api/location")
def ingest():
 d=request.json or {}
 try: vid=int(d["vehicle_id"]); lat=float(d["lat"]); lon=float(d["lon"])
 except: return jsonify(error="vehicle_id, lat and lon required"),400
 if not -90<=lat<=90 or not -180<=lon<=180: return jsonify(error="Invalid coordinates"),400
 with conn() as c:
  v=c.execute("SELECT * FROM vehicles WHERE id=?",(vid,)).fetchone()
  if not v or not check_password_hash(v["secret"],d.get("device_secret","")): return jsonify(error="Invalid device credentials"),403
  loc={"vehicle_id":vid,"lat":lat,"lon":lon,"accuracy":d.get("accuracy"),"speed":d.get("speed"),"heading":d.get("heading"),"at":stamp()}
  c.execute("INSERT INTO locations(vehicle,lat,lon,accuracy,speed,heading,at) VALUES(?,?,?,?,?,?,?)",(vid,lat,lon,loc["accuracy"],loc["speed"],loc["heading"],loc["at"]))
 socketio.emit("location_update",loc,room=f"v{vid}"); return jsonify(ok=True)
@app.get("/api/vehicles/<int:vid>/location")
@auth
def latest(vid):
 with conn() as c:
  if not permitted(c,vid,me()["id"]): return jsonify(error="Not authorized for this vehicle"),403
  x=c.execute("SELECT vehicle vehicle_id,lat,lon,accuracy,speed,heading,at FROM locations WHERE vehicle=? ORDER BY id DESC LIMIT 1",(vid,)).fetchone()
 return jsonify(location=dict(x) if x else None)
@app.post("/api/vehicles/<int:vid>/share")
@auth
def share(vid):
 email=(request.json or {}).get("email","").lower()
 with conn() as c:
  v=c.execute("SELECT * FROM vehicles WHERE id=? AND owner=?",(vid,me()["id"])).fetchone()
  u=c.execute("SELECT id FROM users WHERE email=?",(email,)).fetchone()
  if not v: return jsonify(error="Only owner can share"),403
  if not u: return jsonify(error="Viewer must create an account first"),404
  c.execute("INSERT OR IGNORE INTO access VALUES(?,?)",(vid,u["id"]))
 return jsonify(ok=True)
@app.delete("/api/vehicles/<int:vid>/share/<int:uid>")
@auth
def revoke(vid,uid):
 with conn() as c:
  if not c.execute("SELECT id FROM vehicles WHERE id=? AND owner=?",(vid,me()["id"])).fetchone(): return jsonify(error="Only owner can revoke"),403
  c.execute("DELETE FROM access WHERE vehicle=? AND viewer=?",(vid,uid))
 return jsonify(ok=True)
@app.post("/api/contacts")
@auth
def contact():
 d=request.json or {}
 if not d.get("name") or len(d.get("phone",""))<8: return jsonify(error="Name and phone required"),400
 with conn() as c: c.execute("INSERT INTO contacts(owner,name,phone) VALUES(?,?,?)",(me()["id"],d["name"],d["phone"]))
 return jsonify(ok=True)
def send_sms(to,body):
 keys=[os.getenv("TWILIO_ACCOUNT_SID"),os.getenv("TWILIO_AUTH_TOKEN"),os.getenv("TWILIO_FROM_NUMBER")]
 if not all(keys): return False,"SMS not configured; alert saved in app"
 try: Client(keys[0],keys[1]).messages.create(to=to,from_=keys[2],body=body); return True,"SMS submitted"
 except Exception: app.logger.exception("SMS failure"); return False,"SMS provider error"
@app.post("/api/vehicles/<int:vid>/sos")
@auth
def sos(vid):
 with conn() as c:
  v=c.execute("SELECT * FROM vehicles WHERE id=? AND owner=?",(vid,me()["id"])).fetchone()
  if not v: return jsonify(error="Only vehicle owner can send SOS"),403
  l=c.execute("SELECT * FROM locations WHERE vehicle=? ORDER BY id DESC LIMIT 1",(vid,)).fetchone()
  contacts=c.execute("SELECT * FROM contacts WHERE owner=?",(me()["id"],)).fetchall()
  link=f"https://maps.google.com/?q={l['lat']},{l['lon']}" if l else "Location unavailable"
  message=f"EMERGENCY SOS for {v['reg']}. Last GPS location: {link}. Please contact the owner."
  c.execute("INSERT INTO alerts(owner,vehicle,message,at) VALUES(?,?,?,?)",(me()["id"],vid,message,stamp()))
 results=[{"name":x["name"],"result":send_sms(x["phone"],message)[1]} for x in contacts]
 socketio.emit("sos_alert",{"vehicle_id":vid,"message":message},room=f"v{vid}")
 return jsonify(ok=True,message=message,results=results)
@socketio.on("watch_vehicle")
def watch(data):
 if not session.get("uid"): emit("watch_error",{"error":"Sign in required"}); return
 with conn() as c:
  if not permitted(c,(data or {}).get("vehicle_id"),session["uid"]): emit("watch_error",{"error":"Not authorized"}); return
 join_room(f"v{data['vehicle_id']}")
if __name__=="__main__": socketio.run(app,host="0.0.0.0",port=int(os.getenv("PORT",5000)),debug=False)
