"""Lokāls serveris Noteikumiem, TOP 10 un spēles game.db datubāzei.

Tas izmanto tikai Python standarta bibliotēku, tāpēc nav jāinstalē papildinājumi.
"""

import json
import secrets
import sqlite3
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "game.db"


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
        pages = {"/": "home.html", "/rules": "rules.html", "/leaderboard": "leaderboard.html"}
        if path in pages:
            self.path = "/" + pages[path]
            return super().do_GET()
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
        if path == "/login-name":
            name = str(item.get("name", "")).strip()
            if not 2 <= len(name) <= 16:
                return self.json_response({"detail": "Vārdam jābūt 2–16 simboliem"}, HTTPStatus.UNPROCESSABLE_ENTITY)
            token = secrets.token_hex(16)
            with database() as conn:
                exists = conn.execute("SELECT 1 FROM players WHERE name = ?", (name,)).fetchone()
                if not exists:
                    conn.execute("INSERT INTO players (name, password_hash) VALUES (?, ?)", (name, ""))
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
        server.serve_forever()
