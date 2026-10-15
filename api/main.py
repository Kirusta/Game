import hashlib
import json
import secrets
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field

from .db import get_connection


app = FastAPI(title="Cyber Tower Defense API", version="1.0")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)


class UserIn(BaseModel):
    name: str = Field(min_length=2, max_length=16)
    password: str = Field(min_length=4, max_length=128)


class UsernameIn(BaseModel):
    name: str = Field(min_length=2, max_length=16)


class ScoreIn(BaseModel):
    # Infinite Mode sasniegtais vilnis
    wave: int = Field(ge=1)


class ProgressIn(BaseModel):
    max_unlocked_map: int = Field(ge=1, le=3)
    skill_points: int = Field(ge=0)
    skills: dict[str, int]
    infinite_unlocked: bool


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def current_player(token: str | None) -> str:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nav pieteicies")
    with get_connection() as conn:
        row = conn.execute(
            "SELECT name FROM players WHERE token = ?", (token,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nederīgs tokens")
    return row[0]


@app.get("/hello")
def hello():
    return {"message": "Cyber Tower Defense serveris darbojas"}


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(PROJECT_ROOT / "home.html")


@app.get("/leaderboard", include_in_schema=False)
def leaderboard_page():
    return FileResponse(PROJECT_ROOT / "leaderboard.html")


@app.get("/rules", include_in_schema=False)
def rules_page():
    return FileResponse(PROJECT_ROOT / "rules.html")


@app.post("/register", status_code=status.HTTP_201_CREATED)
def register(user: UserIn):
    name = user.name.strip()
    if len(name) < 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Vārds ir par īsu")
    with get_connection() as conn:
        exists = conn.execute("SELECT 1 FROM players WHERE name = ?", (name,)).fetchone()
        if exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vārds jau aizņemts")
        conn.execute(
            "INSERT INTO players (name, password_hash) VALUES (?, ?)",
            (name, hash_password(user.password)),
        )
    return {"name": name}


@app.post("/login")
def login(user: UserIn):
    name = user.name.strip()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT password_hash FROM players WHERE name = ?", (name,)
        ).fetchone()
        if row is None or row[0] != hash_password(user.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nepareizs vārds vai parole")
        token = secrets.token_hex(16)
        conn.execute("UPDATE players SET token = ? WHERE name = ?", (token, name))
    return {"token": token, "name": name}


@app.post("/login-name")
def login_with_name(user: UsernameIn):
    """Vienkāršā spēles pieslēgšanās: viens vārds atjauno šī vārda progresu."""
    name = user.name.strip()
    with get_connection() as conn:
        exists = conn.execute("SELECT 1 FROM players WHERE name = ?", (name,)).fetchone()
        if exists is None:
            conn.execute(
                "INSERT INTO players (name, password_hash) VALUES (?, ?)",
                (name, ""),
            )
        token = secrets.token_hex(16)
        conn.execute("UPDATE players SET token = ? WHERE name = ?", (token, name))
    return {"token": token, "name": name}


@app.get("/progress/me")
def get_progress(token: str | None = Header(default=None)):
    player = current_player(token)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT max_unlocked_map, skill_points, skills_json, infinite_unlocked FROM progress WHERE player = ?",
            (player,),
        ).fetchone()
    if row is None:
        return {"max_unlocked_map": 1, "skill_points": 2, "skills": {}, "infinite_unlocked": False}
    return {
        "max_unlocked_map": row[0],
        "skill_points": row[1],
        "skills": json.loads(row[2]),
        "infinite_unlocked": bool(row[3]),
    }


@app.put("/progress")
def save_progress(item: ProgressIn, token: str | None = Header(default=None)):
    player = current_player(token)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO progress (player, max_unlocked_map, skill_points, skills_json, infinite_unlocked)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(player) DO UPDATE SET
                max_unlocked_map = excluded.max_unlocked_map,
                skill_points = excluded.skill_points,
                skills_json = excluded.skills_json,
                infinite_unlocked = excluded.infinite_unlocked
            """,
            (player, item.max_unlocked_map, item.skill_points, json.dumps(item.skills), int(item.infinite_unlocked)),
        )
    return {"saved": True}


@app.post("/scores", status_code=status.HTTP_201_CREATED)
def add_score(item: ScoreIn, token: str | None = Header(default=None)):
    player = current_player(token)
    with get_connection() as conn:
        # Ierakstām tikai tad, ja šis ir spēlētāja jauns personīgais rekords.
        best = conn.execute(
            "SELECT MAX(score) FROM scores WHERE player = ?", (player,)
        ).fetchone()[0]
        if best is None or item.wave > best:
            conn.execute("INSERT INTO scores (player, score) VALUES (?, ?)", (player, item.wave))
            return {"player": player, "wave": item.wave, "new_best": True}
    return {"player": player, "wave": best, "new_best": False}


@app.get("/scores/top")
def top_scores():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT player, MAX(score) AS wave
            FROM scores
            GROUP BY player
            ORDER BY wave DESC, player COLLATE NOCASE ASC
            LIMIT 10
            """
        ).fetchall()
    return [{"player": player, "wave": wave} for player, wave in rows]


@app.get("/players/{name}/stats")
def player_stats(name: str):
    with get_connection() as conn:
        exists = conn.execute("SELECT 1 FROM players WHERE name = ?", (name,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spēlētājs nav atrasts")
        games, best_wave = conn.execute(
            "SELECT COUNT(*), MAX(score) FROM scores WHERE player = ?", (name,)
        ).fetchone()
    return {"player": name, "submitted_records": games, "best_wave": best_wave or 0}
