"""Lokāls serveris Noteikumiem, TOP 10 un spēles game.db datubāzei.

Izmanto tikai Python standarta bibliotēku, tāpēc nav jāinstalē papildinājumi.
"""

import json
import secrets
import sqlite3
import hashlib
import hmac
import ipaddress
from html import escape
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "game.db"


API_DOCS_HTML = r'''<!doctype html>
<html lang="lv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cyber Tower Defense — API dokumentācija</title>
<style>
:root { color-scheme: dark; --bg:#0b1220; --panel:#121c2d; --line:#2a3b54; --text:#e7eef9; --muted:#9db0c9; --cyan:#42d9f5; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font:16px/1.5 Segoe UI,Arial,sans-serif; }
header { padding:34px max(22px, calc((100% - 1050px)/2)); background:linear-gradient(120deg,#101d33,#102d40); border-bottom:1px solid var(--line); }
header .eyebrow { color:var(--cyan); text-transform:uppercase; letter-spacing:.12em; font-size:12px; font-weight:700; }
h1 { margin:8px 0; font-size:clamp(27px,4vw,38px); }
header p { margin:0; color:var(--muted); }
main { max-width:1050px; margin:28px auto; padding:0 22px 40px; }
.notice { border:1px solid #24536a; background:#102a3a; border-radius:12px; padding:14px 16px; margin-bottom:24px; }
h2 { margin:28px 0 12px; font-size:20px; }
.endpoint { background:var(--panel); border:1px solid var(--line); border-radius:12px; margin:10px 0; overflow:hidden; }
.route { display:flex; align-items:center; gap:12px; padding:13px 16px; flex-wrap:wrap; }
.method { min-width:66px; text-align:center; border-radius:6px; padding:4px 8px; color:#06131e; font-size:12px; font-weight:800; }
.get { background:#62d6a8; } .post { background:#71b7ff; } .put { background:#e6c56d; }
.path { font-family:Consolas,monospace; font-weight:700; font-size:16px; }
.desc { color:var(--muted); margin-left:auto; }
.details { border-top:1px solid var(--line); padding:12px 16px; color:var(--muted); }
code { color:#b9eaff; background:#09111e; border-radius:5px; padding:2px 5px; }
a { color:var(--cyan); }
footer { color:var(--muted); font-size:13px; border-top:1px solid var(--line); padding-top:18px; margin-top:32px; }
@media(max-width:620px){ .desc{margin-left:0;width:100%;} }
</style>
</head>
<body>
<header>
  <div class="eyebrow">Cyber Tower Defense</div>
  <h1>Servera API dokumentācija</h1>
  <p>Pieejamie servera maršruti un to paredzētais lietojums.</p>
</header>
<main>
  <div class="notice"><strong>Serveris darbojas.</strong> Šī dokumentācijas lapa ir iebūvēta projektā un izmanto Python standarta bibliotēku.</div>
  <h2>Vietnes lapas</h2>
  <section class="endpoint"><div class="route"><span class="method get">GET</span><span class="path">/</span><span class="desc">Sākumlapa</span></div><div class="details">Atver <code>home.html</code>.</div></section>
  <section class="endpoint"><div class="route"><span class="method get">GET</span><span class="path">/rules</span><span class="desc">Spēles noteikumi</span></div><div class="details">Atver <code>rules.html</code>.</div></section>
  <section class="endpoint"><div class="route"><span class="method get">GET</span><span class="path">/leaderboard</span><span class="desc">Līderu tabula</span></div><div class="details">Atver <code>leaderboard.html</code>, kas rāda spēlētāju rezultātus.</div></section>
  <section class="endpoint"><div class="route"><span class="method get">GET</span><span class="path">/database</span><span class="desc">Spēles datubāzes saturs</span></div><div class="details">Parāda visus spēlētājus, rezultātu vēsturi un saglabāto progresu. Paroļu jaucējvērtības un pieslēgšanās tokeni netiek rādīti.</div></section>
  <h2>API pieprasījumi</h2>
  <section class="endpoint"><div class="route"><span class="method get">GET</span><span class="path">/hello</span><span class="desc">Pārbauda servera darbību</span></div><div class="details">Atgriež JSON ziņojumu, ka Cyber Tower Defense serveris darbojas.</div></section>
  <section class="endpoint"><div class="route"><span class="method get">GET</span><span class="path">/scores/top</span><span class="desc">TOP 10 rezultāti</span></div><div class="details">Atgriež JSON masīvu ar spēlētājiem un viņu labākajiem viļņiem.</div></section>
  <section class="endpoint"><div class="route"><span class="method post">POST</span><span class="path">/login</span><span class="desc">Izveido vai pieslēdz kontu</span></div><div class="details">JSON piemērs: <code>{"name":"Speletajs","password":"parole"}</code>. Atgriež piekļuves tokenu un spēlētāja vārdu.</div></section>
  <section class="endpoint"><div class="route"><span class="method post">POST</span><span class="path">/scores</span><span class="desc">Saglabā jaunu labāko vilni</span></div><div class="details">Nepieciešama <code>token</code> galvene un JSON dati, piemēram, <code>{"wave":15}</code>.</div></section>
  <section class="endpoint"><div class="route"><span class="method get">GET</span><span class="path">/progress/me</span><span class="desc">Ielādē konta progresu</span></div><div class="details">Nepieciešama <code>token</code> galvene. Atgriež atvērtās kartes, prasmes un Infinite Mode statusu.</div></section>
  <section class="endpoint"><div class="route"><span class="method put">PUT</span><span class="path">/progress</span><span class="desc">Saglabā konta progresu</span></div><div class="details">Nepieciešama <code>token</code> galvene un progresa JSON objekts.</div></section>
  <footer>Cyber Tower Defense · Lokālā servera dokumentācija · Datubāze: <code>game.db</code></footer>
</main>
</body>
</html>'''


def database():
    conn = sqlite3.connect(DATABASE)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("CREATE TABLE IF NOT EXISTS players (name TEXT PRIMARY KEY, password_hash TEXT NOT NULL, token TEXT)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS scores (id INTEGER PRIMARY KEY AUTOINCREMENT, player TEXT NOT NULL, "
        "score INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "FOREIGN KEY(player) REFERENCES players(name))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS progress (player TEXT PRIMARY KEY, max_unlocked_map INTEGER NOT NULL DEFAULT 1, "
        "skill_points INTEGER NOT NULL DEFAULT 2, skills_json TEXT NOT NULL DEFAULT '{}', "
        "infinite_unlocked INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(player) REFERENCES players(name))"
    )
    return conn


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 180000).hex()
    return f"{salt}${digest}"


def password_matches(password, stored_hash):
    try:
        salt, _ = stored_hash.split("$", 1)
        return hmac.compare_digest(password_hash(password, salt), stored_hash)
    except (ValueError, TypeError):
        return False


class GameServer(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, _format, *_args):
        return

    def json_response(self, data, status=HTTPStatus.OK):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def html_response(self, html, status=HTTPStatus.OK):
        raw = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self):
        size = int(self.headers.get("Content-Length", "0"))
        try:
            return json.loads(self.rfile.read(size).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    def player_from_token(self):
        token = self.headers.get("token")
        if not token:
            return None
        with database() as conn:
            row = conn.execute("SELECT name FROM players WHERE token = ?", (token,)).fetchone()
        return row[0] if row else None

    def do_GET(self):
        path = urlparse(self.path).path
        print("DEBUG REQUEST:", repr(self.path), "PATH:", repr(path))
        # Iebūvēta dokumentācija: serverim nav vajadzīgs FastAPI vai citi papildinājumi.
        if path == "/docs":
            return self.html_response(API_DOCS_HTML)
        pages = {
            "/": "home.html",
            "/rules": "rules.html",
            "/leaderboard": "leaderboard.html",
            "/database": "database.html",
        }
        if path in pages:
            self.path = "/" + pages[path]
            return super().do_GET()
        if path == "/database/data":
            address = ipaddress.ip_address(self.client_address[0])
            if not address.is_loopback:
                return self.json_response({"detail": "Datubāzes apskate pieejama tikai šajā datorā"}, HTTPStatus.FORBIDDEN)
            with database() as conn:
                players = conn.execute("SELECT name FROM players ORDER BY name COLLATE NOCASE").fetchall()
                scores = conn.execute(
                    "SELECT id, player, score, created_at FROM scores ORDER BY id DESC"
                ).fetchall()
                progress = conn.execute(
                    "SELECT player, max_unlocked_map, skill_points, skills_json, infinite_unlocked "
                    "FROM progress ORDER BY player COLLATE NOCASE"
                ).fetchall()
            return self.json_response({
                "database": DATABASE.name,
                "players": [{"name": row[0]} for row in players],
                "scores": [
                    {"id": row[0], "player": row[1], "score": row[2], "created_at": row[3]}
                    for row in scores
                ],
                "progress": [
                    {
                        "player": row[0],
                        "max_unlocked_map": row[1],
                        "skill_points": row[2],
                        "skills": row[3],
                        "infinite_unlocked": bool(row[4]),
                    }
                    for row in progress
                ],
            })
        if path == "/hello":
            return self.json_response({"message": "Cyber Tower Defense serveris darbojas"})
        if path == "/scores/top":
            with database() as conn:
                rows = conn.execute(
                    "SELECT player, MAX(score) AS wave FROM scores GROUP BY player "
                    "ORDER BY wave DESC, player COLLATE NOCASE ASC LIMIT 10"
                ).fetchall()
            return self.json_response([{"player": name, "wave": wave} for name, wave in rows])
        if path == "/progress/me":
            player = self.player_from_token()
            if not player:
                return self.json_response({"detail": "Nav pieteicies"}, HTTPStatus.UNAUTHORIZED)
            with database() as conn:
                row = conn.execute(
                    "SELECT max_unlocked_map, skill_points, skills_json, infinite_unlocked "
                    "FROM progress WHERE player = ?", (player,)
                ).fetchone()
            if not row:
                return self.json_response({"max_unlocked_map": 1, "skill_points": 2, "skills": {}, "infinite_unlocked": False})
            return self.json_response({
                "max_unlocked_map": row[0], "skill_points": row[1],
                "skills": json.loads(row[2]), "infinite_unlocked": bool(row[3]),
            })
        return self.json_response({"detail": "Nav atrasts"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        path = urlparse(self.path).path
        item = self.read_json()
        if not isinstance(item, dict):
            return self.json_response({"detail": "Nederīgi dati"}, HTTPStatus.BAD_REQUEST)
        if path == "/login":
            name = str(item.get("name", "")).strip()
            password = str(item.get("password", ""))
            if not 2 <= len(name) <= 16:
                return self.json_response({"detail": "Vārdam jābūt 2–16 simboliem"}, HTTPStatus.UNPROCESSABLE_ENTITY)
            if len(password) < 4:
                return self.json_response({"detail": "Parolei vajag vismaz 4 simbolus"}, HTTPStatus.UNPROCESSABLE_ENTITY)
            token = secrets.token_hex(16)
            with database() as conn:
                row = conn.execute("SELECT password_hash FROM players WHERE name = ?", (name,)).fetchone()
                if row is None:
                    conn.execute("INSERT INTO players (name, password_hash) VALUES (?, ?)", (name, password_hash(password)))
                elif not row[0]:
                    # Iepriekšējie vārda-only profili tiek aizsargāti ar pirmo paroli.
                    conn.execute("UPDATE players SET password_hash = ? WHERE name = ?", (password_hash(password), name))
                elif not password_matches(password, row[0]):
                    return self.json_response({"detail": "Nepareiza parole"}, HTTPStatus.UNAUTHORIZED)
                conn.execute("UPDATE players SET token = ? WHERE name = ?", (token, name))
            return self.json_response({"token": token, "name": name})
        if path == "/scores":
            player = self.player_from_token()
            try:
                wave = int(item.get("wave", 0))
            except (TypeError, ValueError):
                wave = 0
            if not player:
                return self.json_response({"detail": "Nav pieteicies"}, HTTPStatus.UNAUTHORIZED)
            if wave < 1:
                return self.json_response({"detail": "Nederīgs vilnis"}, HTTPStatus.UNPROCESSABLE_ENTITY)
            with database() as conn:
                best = conn.execute("SELECT MAX(score) FROM scores WHERE player = ?", (player,)).fetchone()[0]
                if best is None or wave > best:
                    conn.execute("INSERT INTO scores (player, score) VALUES (?, ?)", (player, wave))
                    return self.json_response({"player": player, "wave": wave, "new_best": True}, HTTPStatus.CREATED)
            return self.json_response({"player": player, "wave": best, "new_best": False})
        return self.json_response({"detail": "Nav atrasts"}, HTTPStatus.NOT_FOUND)

    def do_PUT(self):
        if urlparse(self.path).path != "/progress":
            return self.json_response({"detail": "Nav atrasts"}, HTTPStatus.NOT_FOUND)
        player = self.player_from_token()
        item = self.read_json()
        if not player:
            return self.json_response({"detail": "Nav pieteicies"}, HTTPStatus.UNAUTHORIZED)
        if not isinstance(item, dict):
            return self.json_response({"detail": "Nederīgi dati"}, HTTPStatus.BAD_REQUEST)
        try:
            map_number = max(1, min(3, int(item.get("max_unlocked_map", 1))))
            skill_points = max(0, int(item.get("skill_points", 2)))
            skills = item.get("skills", {})
            if not isinstance(skills, dict):
                skills = {}
            infinite = int(bool(item.get("infinite_unlocked", False)))
        except (TypeError, ValueError):
            return self.json_response({"detail": "Nederīgi dati"}, HTTPStatus.BAD_REQUEST)
        with database() as conn:
            conn.execute(
                "INSERT INTO progress (player, max_unlocked_map, skill_points, skills_json, infinite_unlocked) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(player) DO UPDATE SET "
                "max_unlocked_map = excluded.max_unlocked_map, skill_points = excluded.skill_points, "
                "skills_json = excluded.skills_json, infinite_unlocked = excluded.infinite_unlocked",
                (player, map_number, skill_points, json.dumps(skills), infinite),
            )
        return self.json_response({"saved": True})


if __name__ == "__main__":
    with ThreadingHTTPServer(("0.0.0.0", 8000), GameServer) as server:
        print("Cyber Tower Defense saites: http://localhost:8000/")
        print("API dokumentācija: http://localhost:8000/docs")
        server.serve_forever()
