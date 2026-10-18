import math
import os
import random
import sqlite3
import hashlib
import hmac
import socket
import subprocess
import sys
import time
import webbrowser
import json
import urllib.error
import urllib.request
import pygame

pygame.init()

WIDTH, HEIGHT = 1024, 768
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Cyber Tower Defense - Kristers Brēdiķis")

clock = pygame.time.Clock()
GAME_SPEED = 1.5
MAX_ACTIVE_ENEMIES = 35
MAX_ACTIVE_BULLETS = 150
MAX_IMPLANTS_PER_UNIT = 10
API_URL = "http://localhost:8000"
LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game.db")

def load_map_image(filename):
    try:
        return pygame.transform.scale(pygame.image.load(filename), (WIDTH, HEIGHT))
    except (pygame.error, FileNotFoundError):
        return None

MAP_IMAGES = {
    1: load_map_image("map1.png"),
    2: load_map_image("map2_neon_chasm.jpg"),
    3: load_map_image("map3_cyber_district.jpg"),
}

BG_COLOR = (7, 10, 20)
PATH_COLOR = (27, 32, 54)
RED = (255, 50, 50)
BOSS_COLOR = (255, 40, 150)
GREEN = (80, 255, 170)
YELLOW = (255, 205, 65)
CYAN = (30, 220, 255)
WHITE = (225, 240, 255)
DARK_GRAY = (17, 24, 43)
PANEL_COLOR = (12, 18, 34)
NEON_PINK = (255, 55, 165)

game_state = "NAME_ENTRY"
show_route = False
max_unlocked_map = 1
leaderboard_unlocked = False
infinite_unlocked = False
infinite_mode = False
skill_points = 2
skills = {
    "damage": 0, "credits": 0, "lives": 0, "range": 0,
    "fire_rate": 0, "start_money": 0, "discount": 0,
}
leaderboard = []
leaderboard_page = 0
player_name = "Spēlētājs"
name_buffer = ""
password_buffer = ""
api_token = None
local_database_mode = False
account_name_buffer = ""
account_password_buffer = ""
account_field = "name"
account_message = ""

lives = 3
money = 250
selected_tower_type = 1
current_level = 1
current_wave = 1
max_waves = 15

GAME_MODES = {
    1: {"name": "KARTE 1: STREET PATROL", "waves": 15, "hp": 1.00, "speed": 1.00, "reward": 1.00},
    2: {"name": "KARTE 2: NEON CHASM", "waves": 15, "hp": 1.25, "speed": 1.08, "reward": 1.20},
    3: {"name": "KARTE 3: CYBER DISTRICT", "waves": 20, "hp": 1.60, "speed": 1.16, "reward": 1.45},
}

UNIT_STATS = {
    1: {"name": "Blue Cyborg", "limit": 3, "cost": 75,
        "levels": [(12, 155, 33, 0), (25, 175, 24, 90), (52, 205, 17, 180)]},
    2: {"name": "Red Cyborg", "limit": 2, "cost": 110,
        "levels": [(7, 95, 57, 0), (10, 110, 48, 120), (15, 125, 39, 240)]},
    3: {"name": "Green Hacker", "limit": 1, "cost": 100,
        "levels": [(0, 0, 0, 0), (0, 0, 0, 110), (0, 0, 0, 220)]},
}
HACKER_INCOME = (20, 35, 60)
SKILL_INFO = {
    "damage": "Damage +10%",
    "credits": "Hacker Income +$5",
    "lives": "Lives +1",
    "range": "Targeting Range +10",
    "fire_rate": "Fire Rate +8%",
    "start_money": "Starting Credits +$50",
    "discount": "Unit Cost -$5",
}
SKILL_MAX = {
    "damage": 10, "fire_rate": 10, "range": 10,
    "credits": 3, "lives": 3, "start_money": 3, "discount": 3,
}
status_message = ""
status_timer = 0
floating_texts = []
implants = []
active_pet = None
secret_pet = None
pet_quest_active = None
pet_quest_progress = 0

def local_db_connection():
    """Nodrošina vietējo SQLite datubāzi, arī ja API serveris nav palaists."""
    conn = sqlite3.connect(LOCAL_DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS players (name TEXT PRIMARY KEY, password_hash TEXT NOT NULL, token TEXT)"
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player TEXT NOT NULL,
            score INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(player) REFERENCES players(name))"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS progress (
            player TEXT PRIMARY KEY,
            max_unlocked_map INTEGER NOT NULL DEFAULT 1,
            skill_points INTEGER NOT NULL DEFAULT 2,
            skills_json TEXT NOT NULL DEFAULT '{}',
            infinite_unlocked INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(player) REFERENCES players(name))"""
    )
    return conn

_initial_database = local_db_connection()
_initial_database.commit()
_initial_database.close()

def server_is_running():
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=0.15):
            return True
    except OSError:
        return False

def ensure_server_is_running():
    """Palaiž Leaderboard serveri automātiski, ja tas vēl nav palaists."""
    if server_is_running():
        return
    try:
        subprocess.Popen(
            [sys.executable, "start_server.py"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        for _ in range(20):
            if server_is_running():
                return
            time.sleep(0.1)
    except OSError:
        pass

ensure_server_is_running()

LEVEL_PATHS = {
    1: [
        (135, 655),  # ENTRY — ceļa vidus
        (185, 655),
        (185, 560),
        (365, 560),
        (365, 425),
        (325, 425),
        (325, 260),
        (525, 260),
        (525, 560),
        (730, 560),
        (730, 370),
        (660, 370),
        (660, 345),
        (660, 203),
        (910, 203),
        (910, 150),  # GATE vidus
    ],
    2: [
        (113, 168), (218, 170), (270, 195), (300, 235),
        (305, 280), (285, 330), (270, 385), (270, 430),
        (295, 470), (350, 488), (405, 470), (470, 415),
        (535, 355), (615, 330), (675, 345), (702, 390),
        (700, 430), (680, 470), (655, 530), (670, 590),
        (720, 635), (800, 650), (870, 650), (932, 650),
    ],
    3: [
        (153, 180), (153, 225), (195, 250), (310, 250),
        (455, 250), (472, 272), (472, 360), (472, 460),
        (478, 510), (505, 548), (550, 570), (640, 575),
        (720, 595), (805, 645), (880, 675), (940, 685),
        (982, 685),
    ],
}

path = LEVEL_PATHS[1]

BUILD_ZONES_LVL1 = [
    pygame.Rect(140, 245, 130, 250),  # Kreisais lielais zaļais laukums
    pygame.Rect(230, 610, 145, 60),   # Apakšējais kreisais zaļais laukums
    pygame.Rect(690, 245, 240, 360),  # Labais lielais zaļais laukums
    pygame.Rect(610, 620, 310, 65),   # Apakšējais labais zaļais laukums
]

BUILD_ZONES = {
    1: BUILD_ZONES_LVL1,
    2: [
        pygame.Rect(165, 330, 70, 75), pygame.Rect(345, 390, 65, 70),
        pygame.Rect(490, 415, 65, 75), pygame.Rect(585, 235, 65, 65),
        pygame.Rect(755, 385, 70, 70), pygame.Rect(335, 510, 70, 70),
        pygame.Rect(600, 510, 60, 70),
    ],
    3: [
        pygame.Rect(150, 120, 175, 70), pygame.Rect(540, 160, 115, 300),
        pygame.Rect(520, 430, 350, 135), pygame.Rect(570, 570, 240, 100),
    ],
}

def can_build_here(x, y, level):
    if y < 120:
        return False

    if level in GAME_MODES:
        tower_area = pygame.Rect(x - 15, y - 15, 30, 30)
        in_valid_zone = False
        for zone in BUILD_ZONES[level]:
            if zone.contains(tower_area):
                in_valid_zone = True
                break
        if not in_valid_zone:
            return False # Ja nav zaļajā zonā, neļauj novietot torni

        for i in range(len(path) - 1):
            p1 = path[i]
            p2 = path[i + 1]
            dist = dist_to_segment((x, y), p1, p2)
            if dist < 22:
                return False # Pārāk tuvu ceļam
        return True

    return True

def dist_to_segment(p, p1, p2):
    x, y = p
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)
    t = ((x - x1) * dx + (y - y1) * dy) / float(dx * dx + dy * dy)
    t = max(0, min(1, t))
    nearest_x = x1 + t * dx
    nearest_y = y1 + t * dy
    return math.hypot(x - nearest_x, y - nearest_y)

class Button:
    def __init__(self, x, y, width, height, text, font):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font

    def draw(self, surface, mouse_pos):
        is_hovered = self.rect.collidepoint(mouse_pos)
        fill = (25, 46, 75) if is_hovered else PANEL_COLOR
        accent = NEON_PINK if is_hovered else CYAN
        cut = 7
        points = [
            (self.rect.left + cut, self.rect.top), (self.rect.right - cut, self.rect.top),
            (self.rect.right, self.rect.top + cut), (self.rect.right, self.rect.bottom - cut),
            (self.rect.right - cut, self.rect.bottom), (self.rect.left + cut, self.rect.bottom),
            (self.rect.left, self.rect.bottom - cut), (self.rect.left, self.rect.top + cut),
        ]
        pygame.draw.polygon(surface, fill, points)
        pygame.draw.lines(surface, accent, True, points, 2)
        pygame.draw.line(surface, accent, (self.rect.left + 10, self.rect.bottom - 7), (self.rect.left + 34, self.rect.bottom - 7), 1)
        pygame.draw.line(surface, accent, (self.rect.right - 34, self.rect.top + 7), (self.rect.right - 10, self.rect.top + 7), 1)
        txt_surf = self.font.render(self.text, False, WHITE if is_hovered else accent)
        txt_rect = txt_surf.get_rect(center=self.rect.center)
        surface.blit(txt_surf, txt_rect)

    def is_clicked(self, mouse_pos, click):
        return click and self.rect.collidepoint(mouse_pos)

def remove_checkered_background(image):
    """Noņem gaišo rūtiņu fonu no lietotāja dotajām PNG atsaucēm."""
    image = image.convert_alpha()
    for y in range(image.get_height()):
        for x in range(image.get_width()):
            r, g, b, _ = image.get_at((x, y))
            if r > 185 and g > 185 and b > 185 and max(r, g, b) - min(r, g, b) < 18:
                image.set_at((x, y), (r, g, b, 0))
    return image

def remove_edge_background(image):
    """Padara caurspīdīgu tikai fonu, kas savienots ar attēla malām."""
    image = image.convert_alpha()
    width, height = image.get_size()
    visited, pending = set(), []

    def is_background(x, y):
        red, green, blue, _ = image.get_at((x, y))
        return max(red, green, blue) - min(red, green, blue) < 34

    for x in range(width):
        pending.extend(((x, 0), (x, height - 1)))
    for y in range(height):
        pending.extend(((0, y), (width - 1, y)))
    while pending:
        x, y = pending.pop()
        if (x, y) in visited or not (0 <= x < width and 0 <= y < height) or not is_background(x, y):
            continue
        visited.add((x, y))
        image.set_at((x, y), (0, 0, 0, 0))
        pending.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return image

def clean_dark_background(image, size):
    """Noņem tumšo studijas fonu un cieši apgriež tēlu līdz redzamajai formai."""
    image = image.convert_alpha()
    for y in range(image.get_height()):
        for x in range(image.get_width()):
            r, g, b, _ = image.get_at((x, y))
            if max(r, g, b) < 52:
                image.set_at((x, y), (r, g, b, 0))
    bounds = image.get_bounding_rect()
    if bounds.width > 0 and bounds.height > 0:
        image = image.subsurface(bounds).copy()
    return pygame.transform.smoothscale(image, size)

def load_unit_sprite(filename, crop, size, remove_light_background=False):
    """Ielādē lietotāja dotās tēlu atsauces; ja faila nav, spēle paliek spēlējama."""
    try:
        image = pygame.image.load(filename).convert()
        image = image.subsurface(pygame.Rect(crop)).copy()
        image.set_colorkey((0, 0, 0), pygame.RLEACCEL)
        image = pygame.transform.smoothscale(image, (size[0] * 2, size[1] * 2))
        if remove_light_background:
            image = remove_edge_background(remove_checkered_background(image))
            bounds = image.get_bounding_rect()
            if bounds.width > 0 and bounds.height > 0:
                image = image.subsurface(bounds).copy()
            return pygame.transform.smoothscale(image, size)
        return clean_dark_background(image, size)
    except (pygame.error, ValueError, FileNotFoundError):
        return None

def load_direct_sprite(filename, size):
    """Ielādē jau caurspīdīgu PNG sprite bez papildu izgriešanas."""
    try:
        image = pygame.image.load(filename).convert_alpha()
        return pygame.transform.smoothscale(image, size)
    except (pygame.error, FileNotFoundError):
        return None

def load_implant_sprite(filename, size):
    """Mazs, caurspīdīgs implanta sprites, kas redzams kā kritiens kartē."""
    try:
        image = pygame.image.load(filename).convert_alpha()
        image = pygame.transform.smoothscale(image, size)
        return clean_dark_background(image, size)
    except (pygame.error, FileNotFoundError):
        return None

def load_secret_pet_sprite(filename, crop, size):
    """Izgriež mazo pixel pet no lietotāja dotās atsauces un noņem tumšo fonu."""
    try:
        image = pygame.image.load(filename).convert_alpha()
        if crop:
            image = image.subsurface(pygame.Rect(crop)).copy()
        image = pygame.transform.smoothscale(image, size)
        return clean_dark_background(image, size)
    except (pygame.error, ValueError, FileNotFoundError):
        return None

UNIT_SPRITES = {
    1: [
        load_direct_sprite("cyborg_blue_1.png", (38, 68)),
        load_direct_sprite("cyborg_blue_2.png", (42, 70)),
        load_direct_sprite("cyborg_blue_3.png", (56, 72)),
    ],
    2: [
        load_direct_sprite("shotgun_red_1.png", (42, 66)),
        load_direct_sprite("shotgun_red_2.png", (46, 68)),
        load_direct_sprite("shotgun_red_3.png", (56, 72)),
    ],
    3: [
        load_direct_sprite("hacker_green_1.png", (34, 68)),
        load_direct_sprite("hacker_green_2.png", (38, 70)),
        load_direct_sprite("hacker_green_3 (1).png", (42, 74)),
    ],
}

def load_enemy_sprite(filename, crop, size, remove_light_background=False):
    try:
        image = pygame.image.load(filename).convert()
        image = image.subsurface(pygame.Rect(crop)).copy()
        image.set_colorkey((0, 0, 0), pygame.RLEACCEL)
        image = pygame.transform.smoothscale(image, size).convert_alpha()
        return remove_edge_background(remove_checkered_background(image))
    except (pygame.error, ValueError, FileNotFoundError):
        return None

ENEMY_SPRITES = {
    "basic": load_direct_sprite("mech_red_1.png", (30, 48)),
    "mini_boss": load_direct_sprite("mech_red_2.png", (44, 62)),
    "heavy": load_direct_sprite("mech_red_3.png", (66, 84)),
    "final_boss": load_direct_sprite("crimson_dragon.png", (132, 104)),
}

IMPLANT_SPRITES = {
    "pistol": load_implant_sprite("implant_pistol.png", (30, 18)),
    "arm": load_implant_sprite("implant_arm.png", (30, 18)),
    "eye": load_implant_sprite("implant_eye.png", (22, 22)),
}
IMPLANT_COLORS = {"pistol": RED, "arm": (210, 210, 220), "eye": (255, 120, 80)}
IMPLANT_NAMES = {"pistol": "Pistole +10% damage", "arm": "Roka +5% attack speed", "eye": "Acs +10% range"}

PET_DATA = {
    "octopus": {
        "name": "OCTOPUS", "buff": "+30% RANGE", "range": 1.30, "speed": 1.00, "damage": 1.00,
        "quest_type": "kills", "quest_target": 50, "quest_text": "Defeat 50 enemies",
    },
    "platypus": {
        "name": "PLATYPUS", "buff": "+15% ATTACK SPEED", "range": 1.00, "speed": 1.15, "damage": 1.00,
        "quest_type": "shots", "quest_target": 100, "quest_text": "Fire 100 shots",
    },
    "sphinx": {
        "name": "SPHINX CAT", "buff": "+30% DAMAGE", "range": 1.00, "speed": 1.00, "damage": 1.30,
        "quest_type": "damage", "quest_target": 5000, "quest_text": "Deal 5000 damage",
    },
}
PET_SPRITES = {
    "octopus": load_secret_pet_sprite("secret_pets.png", (1000, 170, 500, 590), (44, 44)),
    "platypus": load_secret_pet_sprite("secret_pets.png", (465, 290, 520, 500), (44, 44)),
    "sphinx": load_secret_pet_sprite("secret_sphinx_cat.png", (260, 120, 720, 1040), (44, 50)),
}
SECRET_PET_POSITIONS = {
    1: (105, 705),
    2: (975, 285),
    3: (340, 640),
}

class Tower:
    def __init__(self, x, y, t_type):
        self.x, self.y = x, y
        self.type = t_type
        self.level = 1
        self.cooldown = 0
        self.aim_angle = 0
        self._rotation_key = None
        self._rotated_sprite = None
        self.implants = {"pistol": 0, "arm": 0, "eye": 0}
        self.apply_level_stats()

    def apply_level_stats(self):
        damage, attack_range, fire_rate, _ = UNIT_STATS[self.type]["levels"][self.level - 1]
        pet = PET_DATA.get(active_pet, {"range": 1.0, "speed": 1.0, "damage": 1.0})
        self.damage = int(damage * (1 + skills["damage"] * 0.10) * (1 + self.implants["pistol"] * 0.10) * pet["damage"])
        self.range = int((attack_range + skills["range"] * 10) * (1 + self.implants["eye"] * 0.10) * pet["range"])
        self.fire_rate = max(4, int(fire_rate / (GAME_SPEED * (1 + skills["fire_rate"] * 0.10) * (1 + self.implants["arm"] * 0.05) * pet["speed"])))

    def upgrade(self):
        global money, status_message, status_timer
        if self.level >= 3:
            status_message, status_timer = "Maksimālais līmenis!", 120
            return False
        upgrade_cost = max(1, UNIT_STATS[self.type]["levels"][self.level][3] - skills["discount"] * 10)
        if money < upgrade_cost:
            status_message, status_timer = f"Vajag ${upgrade_cost}", 120
            return False
        money -= upgrade_cost
        self.level += 1
        self.apply_level_stats()
        status_message, status_timer = f"{UNIT_STATS[self.type]['name']} uzlabots uz L{self.level}", 120
        return True

    def draw(self, surface):
        color = (0, 180, 255) if self.type == 1 else ((255, 70, 70) if self.type == 2 else GREEN)
        if self.type != 3:
            pygame.draw.circle(surface, color, (self.x, self.y), self.range, 1)
        implant_count = sum(self.implants.values())
        if implant_count:
            aura_w = 62 if self.level < 3 else 70
            aura_h = 88 if self.level < 3 else 94
            glow_alpha = min(150, 38 + implant_count * 18)
            glow = pygame.Surface((aura_w, aura_h), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (255, 70, 50, glow_alpha), (3, 3, aura_w - 6, aura_h - 6), 4)
            pygame.draw.ellipse(glow, (255, 150, 90, min(205, glow_alpha + 35)), (8, 9, aura_w - 16, aura_h - 18), 2)
            surface.blit(glow, glow.get_rect(center=(self.x, self.y)))
        sprite = UNIT_SPRITES[self.type][self.level - 1]
        if sprite:
            if self.type == 3:
                rotated_sprite = sprite
            else:
                rotation_key = (self.level, round(self.aim_angle / 10) * 10)
                if rotation_key != self._rotation_key:
                    self._rotation_key = rotation_key
                    self._rotated_sprite = pygame.transform.rotate(sprite, rotation_key[1])
                rotated_sprite = self._rotated_sprite
            rect = rotated_sprite.get_rect(center=(self.x, self.y))
            surface.blit(rotated_sprite, rect)
        else:
            pygame.draw.circle(surface, (18, 18, 30), (self.x, self.y), 17)
            pygame.draw.circle(surface, color, (self.x, self.y), 17, 3)
        level_text = font_ui.render(f"L{self.level}", True, WHITE)
        surface.blit(level_text, level_text.get_rect(center=(self.x, self.y)))

class Enemy:
    def __init__(self, kind="basic"):
        self.x, self.y = path[0]
        self.path_index = 0
        self.kind = kind
        self.is_boss = kind in ("mini_boss", "final_boss")
        mode = GAME_MODES[current_level]
        base_health = (35 + current_wave * 10) * mode["hp"]
        stats = {
            "basic": (1.0, 1.85, 13, 1),
            "heavy": (4.5, 0.95, 24, 2),
            "mini_boss": (7.0, 1.30, 19, 2),
            "final_boss": (18.0, 0.72, 44, 5),
        }
        health_multiplier, speed, self.radius, self.leak_damage = stats[kind]
        self.health = int(base_health * health_multiplier)
        self.max_health = self.health
        self.speed = speed * mode["speed"] * GAME_SPEED

class Bullet:
    def __init__(self, x, y, target, damage, owner, angle_offset=0):
        self.x = x
        self.y = y
        self.damage = damage
        self.owner = owner
        self.speed = 9.0 * GAME_SPEED
        angle = math.atan2(target.y - y, target.x - x) + math.radians(angle_offset)
        self.vx = math.cos(angle) * self.speed
        self.vy = math.sin(angle) * self.speed

class Implant:
    """Vispirms nokrīt pie uzvarētā pretinieka, tad aizlido pie šāvēja."""
    def __init__(self, kind, x, y, target):
        self.kind = kind
        self.x, self.y = x, y
        self.floor_y = min(HEIGHT - 24, y + 26)
        self.target = target
        self.fall_frames = 20

    def update(self):
        if self.fall_frames > 0:
            self.y += (self.floor_y - self.y) * 0.22
            self.fall_frames -= 1
            return False
        dx, dy = self.target.x - self.x, self.target.y - self.y
        distance = math.hypot(dx, dy)
        if distance <= 8:
            if sum(self.target.implants.values()) < MAX_IMPLANTS_PER_UNIT:
                self.target.implants[self.kind] += 1
                self.target.apply_level_stats()
                floating_texts.append([self.target.x, self.target.y - 54, IMPLANT_NAMES[self.kind], 100])
            return True
        speed = 6.5
        self.x += dx / distance * min(speed, distance)
        self.y += dy / distance * min(speed, distance)
        return False

    def draw(self, surface):
        sprite = IMPLANT_SPRITES.get(self.kind)
        if sprite:
            surface.blit(sprite, sprite.get_rect(center=(int(self.x), int(self.y))))
        else:
            pygame.draw.circle(surface, IMPLANT_COLORS[self.kind], (int(self.x), int(self.y)), 8)

class SecretPet:
    """Mazs, klikšķināms slepenais pet konkrētajai kartei."""
    def __init__(self, kind, x, y):
        self.kind, self.x, self.y = kind, x, y

    def is_clicked(self, x, y):
        return math.hypot(self.x - x, self.y - y) <= 30

    def draw(self, surface):
        sprite = PET_SPRITES.get(self.kind)
        if sprite:
            surface.blit(sprite, sprite.get_rect(center=(self.x, self.y)))
        else:
            pygame.draw.circle(surface, YELLOW, (self.x, self.y), 15)

def start_pet_quest():
    """Uzklikšķinot uz pet, parāda tā unikālo questu."""
    global pet_quest_active, pet_quest_progress, status_message, status_timer
    if secret_pet is None:
        return
    if pet_quest_active:
        status_message, status_timer = "Quest already active", 90
        return
    pet_quest_active = secret_pet.kind
    pet_quest_progress = 0
    pet = PET_DATA[pet_quest_active]
    status_message = f"SECRET QUEST: {pet['quest_text']}"
    status_timer = 180

def collect_secret_pet():
    """Aktivizē pet buffu visām esošajām vienībām un arī nākamajām."""
    global active_pet, secret_pet, pet_quest_active, status_message, status_timer
    if secret_pet is None or pet_quest_active is None:
        return
    active_pet = secret_pet.kind
    for tower in towers:
        tower.apply_level_stats()
    status_message = f"SECRET PET: {PET_DATA[active_pet]['name']} — {PET_DATA[active_pet]['buff']}"
    status_timer = 210
    floating_texts.append([secret_pet.x, secret_pet.y - 28, "SECRET PET FOUND!", 130])
    secret_pet = None
    pet_quest_active = None

def advance_pet_quest(action, amount=1):
    """Pieskaita progresu tikai aktīvā pet atbilstošajam questam."""
    global pet_quest_progress
    if not pet_quest_active:
        return
    pet = PET_DATA[pet_quest_active]
    if pet["quest_type"] != action:
        return
    pet_quest_progress = min(pet["quest_target"], pet_quest_progress + amount)
    if pet_quest_progress >= pet["quest_target"]:
        collect_secret_pet()

def try_drop_implant(enemy, owner):
    """5% iespēja nomest implantu, nepārsniedzot 10 implantus vienībai."""
    if not owner or random.random() >= 0.05:
        return
    pending = sum(implant.target is owner for implant in implants)
    if sum(owner.implants.values()) + pending < MAX_IMPLANTS_PER_UNIT:
        implants.append(Implant(random.choice(("pistol", "arm", "eye")), enemy.x, enemy.y, owner))

def pay_hacker_income(phase):
    global money, floating_texts
    for tower in towers:
        if tower.type == 3:
            amount = HACKER_INCOME[tower.level - 1] + skills["credits"] * 5
            money += amount
            floating_texts.append([tower.x, tower.y - 48, f"+${amount}", 90])

def api_request(method, endpoint, payload=None, token=None):
    """Nosūta pieprasījumu uz lokālo FastAPI serveri."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    if token:
        headers["token"] = token
    request = urllib.request.Request(API_URL + endpoint, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.loads(error.read().decode("utf-8"))
        except json.JSONDecodeError:
            return error.code, {"detail": "Servera kļūda"}
    except (urllib.error.URLError, TimeoutError):
        return 0, {"detail": "Serveris nav palaists"}

def password_hash(password, salt=None):
    """Parolei datubāzē glabājas PBKDF2 hash, nevis pats paroles teksts."""
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 180000).hex()
    return f"{salt}${digest}"

def password_matches(password, stored_hash):
    try:
        salt, _ = stored_hash.split("$", 1)
        return hmac.compare_digest(password_hash(password, salt), stored_hash)
    except (ValueError, TypeError):
        return False

def local_login(name, password):
    """Atver vai izveido ar paroli aizsargātu profilu vietējā game.db failā."""
    with local_db_connection() as conn:
        row = conn.execute("SELECT password_hash FROM players WHERE name = ?", (name,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO players (name, password_hash) VALUES (?, ?)", (name, password_hash(password)))
        elif not row[0]:
            conn.execute("UPDATE players SET password_hash = ? WHERE name = ?", (password_hash(password), name))
        elif not password_matches(password, row[0]):
            return False
    return True

def local_load_progress():
    with local_db_connection() as conn:
        row = conn.execute(
            "SELECT max_unlocked_map, skill_points, skills_json, infinite_unlocked FROM progress WHERE player = ?",
            (player_name,),
        ).fetchone()
    if row is None:
        return {"max_unlocked_map": 1, "skill_points": 2, "skills": {}, "infinite_unlocked": False}
    return {"max_unlocked_map": row[0], "skill_points": row[1], "skills": json.loads(row[2]), "infinite_unlocked": bool(row[3])}

def local_save_progress():
    with local_db_connection() as conn:
        conn.execute(
            """INSERT INTO progress (player, max_unlocked_map, skill_points, skills_json, infinite_unlocked)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(player) DO UPDATE SET
              max_unlocked_map = excluded.max_unlocked_map,
              skill_points = excluded.skill_points,
              skills_json = excluded.skills_json,
              infinite_unlocked = excluded.infinite_unlocked""",
            (player_name, max_unlocked_map, skill_points, json.dumps(skills), int(infinite_unlocked)),
        )

def local_save_score(wave):
    with local_db_connection() as conn:
        best = conn.execute("SELECT MAX(score) FROM scores WHERE player = ?", (player_name,)).fetchone()[0]
        if best is None or wave > best:
            conn.execute("INSERT INTO scores (player, score) VALUES (?, ?)", (player_name, wave))

def login_account():
    global api_token, player_name, account_message, local_database_mode
    name = account_name_buffer.strip()
    password = account_password_buffer
    if len(name) < 2:
        account_message = "Lietotājvārdā vajag vismaz 2 burtus."
        return False
    if len(password) < 4:
        account_message = "Parolei vajag vismaz 4 simbolus."
        return False
    status, data = api_request("POST", "/login", {
        "name": account_name_buffer.strip(),
        "password": password,
    })
    if status == 200:
        api_token = data["token"]
        player_name = data["name"]
        local_database_mode = False
        load_player_progress()
        account_message = f"Pieslēdzies kā {player_name}. Progress atjaunots."
        return True
    else:
        player_name = name
        if not local_login(player_name, password):
            account_message = "Nepareiza parole šim lietotājvārdam."
            return False
        local_database_mode = True
        api_token = "LOCAL_DATABASE"
        load_player_progress()
        account_message = f"Pieslēdzies kā {player_name}. Progress saglabājas game.db."
        return True

def load_online_leaderboard():
    global leaderboard
    status, data = api_request("GET", "/scores/top")
    if status == 200:
        leaderboard = [(entry["player"], entry["wave"]) for entry in data]
        return True
    with local_db_connection() as conn:
        rows = conn.execute(
            """SELECT player, MAX(score) AS wave FROM scores
            GROUP BY player ORDER BY wave DESC, player COLLATE NOCASE ASC LIMIT 10"""
        ).fetchall()
    leaderboard = [(name, wave) for name, wave in rows]
    return bool(rows)

def save_player_progress():
    """Saglabā kartes un Skill Tree progresu pieteiktajam spēlētājam."""
    if not api_token:
        return
    if local_database_mode:
        local_save_progress()
        return
    status, _ = api_request("PUT", "/progress", {
        "max_unlocked_map": max_unlocked_map,
        "skill_points": skill_points,
        "skills": skills,
        "infinite_unlocked": infinite_unlocked,
    }, api_token)
    if status == 0:
        local_save_progress()

def load_player_progress():
    """Atjauno iepriekš saglabāto progresu pēc pieteikšanās ar to pašu kontu."""
    global max_unlocked_map, skill_points, infinite_unlocked, leaderboard_unlocked
    if local_database_mode:
        data = local_load_progress()
    else:
        status, data = api_request("GET", "/progress/me", token=api_token)
        if status != 200:
            data = local_load_progress()
    max_unlocked_map = data["max_unlocked_map"]
    skill_points = data["skill_points"]
    infinite_unlocked = data["infinite_unlocked"]
    leaderboard_unlocked = infinite_unlocked
    for skill_name in skills:
        skills[skill_name] = 0
    for skill_name, level in data["skills"].items():
        if skill_name in skills:
            skills[skill_name] = level

def record_infinite_result():
    """Saglabā tikai katra spēlētāja augstāko Infinite Mode vilni."""
    global leaderboard
    reached_wave = current_wave
    best_previous = max((wave for name, wave in leaderboard if name == player_name), default=0)
    if reached_wave > best_previous:
        leaderboard = [(name, wave) for name, wave in leaderboard if name != player_name]
        leaderboard.append((player_name, reached_wave))
    if api_token:
        if local_database_mode:
            local_save_score(reached_wave)
        else:
            status, _ = api_request("POST", "/scores", {"wave": reached_wave}, api_token)
            if status == 0:
                local_save_score(reached_wave)

def enemies_for_wave(level, wave, is_infinite):
    """Nosaka viļņa izmēru, saglabājot Infinite Mode ātru arī augstos viļņos."""
    if level == 3 and (wave == 20 or (is_infinite and wave % 20 == 0)):
        return 1
    return 4 + min(wave, 18)

def start_level(lvl, is_infinite=False):
    global current_level, path, lives, money, towers, enemies, bullets, implants, active_pet, secret_pet, pet_quest_active, pet_quest_progress, spawn_timer, current_wave, max_waves, enemies_spawned_in_wave, enemies_to_spawn, floating_texts, wave_start_paid, infinite_mode, wave_transition_start, game_over_recorded
    current_level = lvl
    infinite_mode = is_infinite
    path = LEVEL_PATHS[lvl]
    lives = 3 + skills["lives"]
    money = 250 + skills["start_money"] * 50
    towers = []
    enemies = []
    bullets = []
    implants = []
    active_pet = None
    pet_quest_active = None
    pet_quest_progress = 0
    pet_kind = {1: "octopus", 2: "platypus", 3: "sphinx"}[lvl]
    pet_x, pet_y = SECRET_PET_POSITIONS[lvl]
    secret_pet = SecretPet(pet_kind, pet_x, pet_y)
    spawn_timer = 0
    current_wave = 1
    max_waves = 999999 if is_infinite else GAME_MODES[lvl]["waves"]
    enemies_spawned_in_wave = 0
    enemies_to_spawn = enemies_for_wave(lvl, current_wave, is_infinite)
    floating_texts = []
    wave_start_paid = False
    wave_transition_start = None
    game_over_recorded = False

towers = []
enemies = []
bullets = []
spawn_timer = 0
enemies_spawned_in_wave = 0
enemies_to_spawn = 5
wave_start_paid = False
wave_transition_start = None
game_over_recorded = False

font_ui = pygame.font.SysFont("consolas", 21, bold=True)
font_btn = pygame.font.SysFont("consolas", 27, bold=True)
font_title = pygame.font.SysFont("consolas", 44, bold=True)
font_card = pygame.font.SysFont("consolas", 17, bold=True)

btn_w, btn_h = 280, 55
center_x = WIDTH // 2 - btn_w // 2

btn_play = Button(center_x, 200, btn_w, btn_h, "SPĒLĒT", font_btn)
btn_infinite_menu = Button(center_x, 265, btn_w, btn_h, "INFINITE MODE", font_btn)
btn_skills = Button(center_x, 330, btn_w, btn_h, "SKILL TREE", font_btn)
btn_settings = Button(center_x, 395, btn_w, btn_h, "IESTATĪJUMI", font_btn)
btn_account = Button(center_x, 460, btn_w, btn_h, "KONTS / PIESLĒGTIES", font_btn)
btn_exit = Button(center_x, 525, btn_w, btn_h, "IZIET", font_btn)
btn_rules = Button(center_x, 590, btn_w, btn_h, "NOTEIKUMI", font_btn)
btn_html_leaderboard = Button(center_x, 655, btn_w, btn_h, "LEADERBOARD", font_btn)

btn_lvl1 = Button(center_x, 270, btn_w, btn_h, "KARTE 1: 15 VIĻŅI", font_btn)
btn_lvl2 = Button(center_x, 340, btn_w, btn_h, "KARTE 2: 15 VIĻŅI", font_btn)
btn_lvl3 = Button(center_x, 410, btn_w, btn_h, "KARTE 3: 20 VIĻŅI", font_btn)
btn_infinite = Button(center_x, 480, btn_w, btn_h, "INFINITE MODE", font_btn)
btn_back = Button(center_x, 550, btn_w, btn_h, "ATPAKAĻ", font_btn)
btn_name = Button(center_x, 285, btn_w, btn_h, "SPĒLĒTĀJA VĀRDS", font_btn)
btn_route = Button(center_x, 355, btn_w, btn_h, "RĀDĪT CEĻU: JĀ", font_btn)
btn_settings_back = Button(center_x, 425, btn_w, btn_h, "ATPAKAĻ", font_btn)
skill_buttons = {
    "damage": Button(60, 265, 410, 46, "", font_ui),
    "credits": Button(554, 265, 410, 46, "", font_ui),
    "lives": Button(60, 325, 410, 46, "", font_ui),
    "range": Button(554, 325, 410, 46, "", font_ui),
    "fire_rate": Button(60, 385, 410, 46, "", font_ui),
    "start_money": Button(554, 385, 410, 46, "", font_ui),
    "discount": Button(60, 445, 410, 46, "", font_ui),
}
btn_skills_back = Button(center_x, 520, btn_w, btn_h, "ATPAKAĻ", font_btn)
btn_board_back = Button(center_x, 610, btn_w, btn_h, "ATPAKAĻ", font_btn)
btn_login = Button(center_x, 405, btn_w, 55, "SAGLABĀT / TURPINĀT", font_btn)
btn_account_back = Button(center_x, 550, btn_w, btn_h, "ATPAKAĻ", font_btn)

running = True

while running:
    mouse_pos = pygame.mouse.get_pos()
    mouse_clicked = False
    mouse_right_clicked = False

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            save_player_progress()
            pygame.quit()
            sys.exit()

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                mouse_clicked = True
            elif event.button == 3:
                mouse_right_clicked = True

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if game_state in ["GAME", "LEVEL_SELECT", "SETTINGS", "SKILLS", "NAME_ENTRY", "ACCOUNT", "LEADERBOARD", "VICTORY"]:
                    if game_state == "GAME":
                        save_player_progress()
                    game_state = "MENU"
                else:
                    save_player_progress()
                    pygame.quit()
                    sys.exit()

            if game_state == "GAME":
                if event.key == pygame.K_1: selected_tower_type = 1
                elif event.key == pygame.K_2: selected_tower_type = 2
                elif event.key == pygame.K_3: selected_tower_type = 3
                elif event.key == pygame.K_e:
                    mx, my = mouse_pos
                    for t in towers:
                        if math.hypot(t.x - mx, t.y - my) < 30:
                            t.upgrade()
                            break
                elif event.key == pygame.K_q:
                    mx, my = mouse_pos
                    for tower in towers[:]:
                        if math.hypot(tower.x - mx, tower.y - my) < 32:
                            spent = UNIT_STATS[tower.type]["cost"]
                            for upgraded_level in range(2, tower.level + 1):
                                spent += UNIT_STATS[tower.type]["levels"][upgraded_level - 1][3]
                            refund = spent // 2
                            money += refund
                            towers.remove(tower)
                            status_message, status_timer = f"Vienība pārdota: +${refund}", 120
                            break
            elif game_state == "NAME_ENTRY":
                if event.key == pygame.K_RETURN:
                    account_name_buffer = name_buffer.strip()
                    account_password_buffer = password_buffer
                    if login_account():
                        game_state = "MENU"
                elif event.key == pygame.K_TAB:
                    account_field = "password" if account_field == "name" else "name"
                elif event.key == pygame.K_BACKSPACE:
                    if account_field == "password":
                        password_buffer = password_buffer[:-1]
                    else:
                        name_buffer = name_buffer[:-1]
                elif event.unicode.isprintable():
                    if account_field == "password" and len(password_buffer) < 32:
                        password_buffer += event.unicode
                    elif account_field == "name" and len(name_buffer) < 16:
                        name_buffer += event.unicode
            elif game_state == "ACCOUNT":
                if event.key == pygame.K_RETURN:
                    if login_account():
                        game_state = "MENU"
                elif event.key == pygame.K_TAB:
                    account_field = "password" if account_field == "name" else "name"
                elif event.key == pygame.K_BACKSPACE:
                    if account_field == "password":
                        account_password_buffer = account_password_buffer[:-1]
                    else:
                        account_name_buffer = account_name_buffer[:-1]
                elif event.unicode.isprintable():
                    if account_field == "password" and len(account_password_buffer) < 32:
                        account_password_buffer += event.unicode
                    elif account_field == "name" and len(account_name_buffer) < 16:
                        account_name_buffer += event.unicode
            elif game_state == "VICTORY" and event.key == pygame.K_l and leaderboard_unlocked:
                load_online_leaderboard()
                game_state = "LEADERBOARD"
                leaderboard_page = 0
            elif game_state == "LEADERBOARD":
                max_page = max(0, (min(len(leaderboard), 100) - 1) // 10)
                if event.key in (pygame.K_DOWN, pygame.K_PAGEDOWN):
                    leaderboard_page = min(max_page, leaderboard_page + 1)
                elif event.key in (pygame.K_UP, pygame.K_PAGEUP):
                    leaderboard_page = max(0, leaderboard_page - 1)

    if game_state == "MENU":
        screen.fill(BG_COLOR)
        title_surf = font_title.render("CYBER TOWER DEFENSE", True, CYAN)
        screen.blit(title_surf, title_surf.get_rect(center=(WIDTH // 2, 180)))

        btn_play.draw(screen, mouse_pos)
        btn_infinite_menu.text = "INFINITE MODE" if infinite_unlocked else "INFINITE: SLĒGTS"
        btn_infinite_menu.draw(screen, mouse_pos)
        btn_skills.draw(screen, mouse_pos)
        btn_settings.draw(screen, mouse_pos)
        btn_account.text = f"KONTS: {player_name}" if api_token else "KONTS / PIESLĒGTIES"
        btn_account.draw(screen, mouse_pos)
        btn_exit.draw(screen, mouse_pos)
        btn_rules.draw(screen, mouse_pos)
        btn_html_leaderboard.draw(screen, mouse_pos)

        if btn_play.is_clicked(mouse_pos, mouse_clicked):
            game_state = "LEVEL_SELECT"
        if infinite_unlocked and btn_infinite_menu.is_clicked(mouse_pos, mouse_clicked):
            start_level(3, True)
            game_state = "GAME"
        if btn_exit.is_clicked(mouse_pos, mouse_clicked):
            save_player_progress()
            pygame.quit()
            sys.exit()
        if btn_settings.is_clicked(mouse_pos, mouse_clicked):
            game_state = "SETTINGS"
        if btn_account.is_clicked(mouse_pos, mouse_clicked):
            account_name_buffer = player_name if player_name != "Spēlētājs" else ""
            account_password_buffer = ""
            account_field = "name"
            account_message = "Ievadi lietotājvārdu un paroli, lai atjaunotu progresu."
            game_state = "ACCOUNT"
        if btn_rules.is_clicked(mouse_pos, mouse_clicked):
            webbrowser.open(API_URL + "/rules")
        if btn_html_leaderboard.is_clicked(mouse_pos, mouse_clicked):
            webbrowser.open(API_URL + "/leaderboard")
        if btn_skills.is_clicked(mouse_pos, mouse_clicked):
            game_state = "SKILLS"

    elif game_state == "ACCOUNT":
        screen.fill(BG_COLOR)
        title_surf = font_title.render("KONTS", True, CYAN)
        name_color = YELLOW if account_field == "name" else WHITE
        password_color = YELLOW if account_field == "password" else WHITE
        name_surf = font_btn.render(f"Lietotājvārds: {account_name_buffer}", True, name_color)
        password_surf = font_btn.render(f"Parole: {'*' * len(account_password_buffer)}", True, password_color)
        hint_surf = font_ui.render("TAB — pārslēgt lauku | ENTER — turpināt", True, WHITE)
        message_surf = font_ui.render(account_message, True, GREEN if api_token else YELLOW)
        screen.blit(title_surf, title_surf.get_rect(center=(WIDTH // 2, 190)))
        screen.blit(name_surf, name_surf.get_rect(center=(WIDTH // 2, 270)))
        screen.blit(password_surf, password_surf.get_rect(center=(WIDTH // 2, 315)))
        screen.blit(hint_surf, hint_surf.get_rect(center=(WIDTH // 2, 355)))
        screen.blit(message_surf, message_surf.get_rect(center=(WIDTH // 2, 380)))
        btn_login.draw(screen, mouse_pos)
        btn_account_back.draw(screen, mouse_pos)
        if btn_login.is_clicked(mouse_pos, mouse_clicked):
            if login_account():
                game_state = "MENU"
        if btn_account_back.is_clicked(mouse_pos, mouse_clicked):
            game_state = "MENU"

    elif game_state == "LEVEL_SELECT":
        screen.fill(BG_COLOR)
        title_surf = font_title.render("IZVĒLIES LĪMENI", True, CYAN)
        screen.blit(title_surf, title_surf.get_rect(center=(WIDTH // 2, 160)))
        btn_lvl2.text = "KARTE 2: 15 VIĻŅI" if max_unlocked_map >= 2 else "KARTE 2: SLĒGTA"
        btn_lvl3.text = "KARTE 3: 20 VIĻŅI" if max_unlocked_map >= 3 else "KARTE 3: SLĒGTA"

        btn_lvl1.draw(screen, mouse_pos)
        btn_lvl2.draw(screen, mouse_pos)
        btn_lvl3.draw(screen, mouse_pos)
        if infinite_unlocked:
            btn_infinite.draw(screen, mouse_pos)
        btn_back.draw(screen, mouse_pos)

        if btn_lvl1.is_clicked(mouse_pos, mouse_clicked):
            start_level(1)
            game_state = "GAME"
        if max_unlocked_map >= 2 and btn_lvl2.is_clicked(mouse_pos, mouse_clicked):
            start_level(2)
            game_state = "GAME"
        if max_unlocked_map >= 3 and btn_lvl3.is_clicked(mouse_pos, mouse_clicked):
            start_level(3)
            game_state = "GAME"
        if infinite_unlocked and btn_infinite.is_clicked(mouse_pos, mouse_clicked):
            start_level(3, True)
            game_state = "GAME"
        if btn_back.is_clicked(mouse_pos, mouse_clicked):
            game_state = "MENU"

    elif game_state == "SETTINGS":
        screen.fill(BG_COLOR)
        title_surf = font_title.render("IESTATĪJUMI", True, CYAN)
        screen.blit(title_surf, title_surf.get_rect(center=(WIDTH // 2, 210)))
        btn_name.text = f"VĀRDS: {player_name}"
        btn_route.text = f"RĀDĪT CEĻU: {'JĀ' if show_route else 'NĒ'}"
        btn_name.draw(screen, mouse_pos)
        btn_route.draw(screen, mouse_pos)
        btn_settings_back.draw(screen, mouse_pos)
        if btn_name.is_clicked(mouse_pos, mouse_clicked):
            account_name_buffer = player_name if player_name != "Spēlētājs" else ""
            account_password_buffer = ""
            account_field = "name"
            account_message = "Ievadi lietotājvārdu un paroli."
            game_state = "ACCOUNT"
        if btn_route.is_clicked(mouse_pos, mouse_clicked):
            show_route = not show_route
        if btn_settings_back.is_clicked(mouse_pos, mouse_clicked):
            game_state = "MENU"

    elif game_state == "NAME_ENTRY":
        screen.fill(BG_COLOR)
        title_surf = font_title.render("IZVEIDO / ATVĒR PROFILU", True, CYAN)
        name_color = YELLOW if account_field == "name" else WHITE
        password_color = YELLOW if account_field == "password" else WHITE
        name_surf = font_btn.render(f"Lietotājvārds: {name_buffer}" + ("_" if account_field == "name" else ""), True, name_color)
        password_surf = font_btn.render(f"Parole: {'*' * len(password_buffer)}" + ("_" if account_field == "password" else ""), True, password_color)
        hint_surf = font_ui.render("TAB — pārslēgt lauku | ENTER — turpināt | parolei vismaz 4 simboli", True, YELLOW)
        message_surf = font_ui.render(account_message, True, RED if account_message else WHITE)
        screen.blit(title_surf, title_surf.get_rect(center=(WIDTH // 2, 240)))
        screen.blit(name_surf, name_surf.get_rect(center=(WIDTH // 2, 315)))
        screen.blit(password_surf, password_surf.get_rect(center=(WIDTH // 2, 360)))
        screen.blit(hint_surf, hint_surf.get_rect(center=(WIDTH // 2, 420)))
        if account_message:
            screen.blit(message_surf, message_surf.get_rect(center=(WIDTH // 2, 455)))

    elif game_state == "SKILLS":
        screen.fill(BG_COLOR)
        title_surf = font_title.render("SKILL TREE", True, CYAN)
        point_surf = font_btn.render(f"Punkti: {skill_points}", True, YELLOW)
        hint_surf = font_ui.render("Katrs pabeigts līmenis dod vairāk Skill Tree punktu: 1., 2., 3.", True, WHITE)
        screen.blit(title_surf, title_surf.get_rect(center=(WIDTH // 2, 140)))
        screen.blit(point_surf, point_surf.get_rect(center=(WIDTH // 2, 195)))
        screen.blit(hint_surf, hint_surf.get_rect(center=(WIDTH // 2, 228)))
        for skill_name, button in skill_buttons.items():
            button.text = f"{SKILL_INFO[skill_name]}  ({skills[skill_name]}/{SKILL_MAX[skill_name]})"
            button.draw(screen, mouse_pos)
        for button in (btn_skills_back,):
            button.draw(screen, mouse_pos)
        selected_skill = None
        for skill_name, button in skill_buttons.items():
            if button.is_clicked(mouse_pos, mouse_clicked):
                selected_skill = skill_name
                break
        if selected_skill and skill_points > 0 and skills[selected_skill] < SKILL_MAX[selected_skill]:
            skills[selected_skill] += 1
            skill_points -= 1
            save_player_progress()
        if btn_skills_back.is_clicked(mouse_pos, mouse_clicked):
            game_state = "MENU"

    elif game_state == "LEADERBOARD":
        screen.fill(BG_COLOR)
        title_surf = font_title.render("LEADERBOARD", True, GREEN)
        screen.blit(title_surf, title_surf.get_rect(center=(WIDTH // 2, 155)))
        if leaderboard:
            top_results = sorted(leaderboard, key=lambda entry: entry[1], reverse=True)[:10]
            max_page = max(0, (len(top_results) - 1) // 10)
            leaderboard_page = min(leaderboard_page, max_page)
            start_index = leaderboard_page * 10
            page_results = top_results[start_index:start_index + 10]
            page_surf = font_ui.render(f"TOP 10 | {start_index + 1}-{start_index + len(page_results)}", True, YELLOW)
            screen.blit(page_surf, page_surf.get_rect(center=(WIDTH // 2, 195)))
            for offset, result in enumerate(page_results):
                rank = start_index + offset + 1
                result_surf = font_ui.render(f"{rank}. {result[0]} — Infinite vilnis {result[1]}", True, WHITE)
                screen.blit(result_surf, result_surf.get_rect(center=(WIDTH // 2, 230 + offset * 28)))
        else:
            empty_surf = font_btn.render("Vēl nav rezultātu", True, WHITE)
            screen.blit(empty_surf, empty_surf.get_rect(center=(WIDTH // 2, 340)))
        btn_board_back.draw(screen, mouse_pos)
        if btn_board_back.is_clicked(mouse_pos, mouse_clicked):
            game_state = "MENU"

    elif game_state == "GAME":
        current_map_image = MAP_IMAGES.get(current_level)
        if current_map_image:
            screen.blit(current_map_image, (0, 0))
            if show_route:
                for i in range(len(path) - 1):
                    pygame.draw.line(screen, (255, 0, 0), path[i], path[i + 1], 2)
        else:
            screen.fill(BG_COLOR)
            for i in range(len(path) - 1):
                pygame.draw.line(screen, PATH_COLOR, path[i], path[i + 1], 35)

        if mouse_clicked:
            mx, my = mouse_pos
            if secret_pet and secret_pet.is_clicked(mx, my):
                start_pet_quest()
            else:
                unit = UNIT_STATS[selected_tower_type]
                cost = max(1, unit["cost"] - skills["discount"] * 5)
                if money >= cost:
                    if can_build_here(mx, my, current_level):
                        placed_count = sum(t.type == selected_tower_type for t in towers)
                        if placed_count < unit["limit"]:
                            towers.append(Tower(mx, my, selected_tower_type))
                            money -= cost
                        else:
                            status_message = f"{unit['name']}: limits {placed_count}/{unit['limit']}"
                            status_timer = 120
                else:
                    status_message, status_timer = f"Vajag ${cost}", 120

        if mouse_right_clicked:
            mx, my = mouse_pos
            for tower in towers[:]:
                if math.hypot(tower.x - mx, tower.y - my) < 32:
                    spent = UNIT_STATS[tower.type]["cost"]
                    for upgraded_level in range(2, tower.level + 1):
                        spent += UNIT_STATS[tower.type]["levels"][upgraded_level - 1][3]
                    refund = spent // 2
                    money += refund
                    towers.remove(tower)
                    status_message, status_timer = f"Vienība pārdota: +${refund}", 120
                    break

        if lives > 0:
            spawn_timer += GAME_SPEED
            if (spawn_timer > 50 and enemies_spawned_in_wave < enemies_to_spawn
                    and len(enemies) < MAX_ACTIVE_ENEMIES):
                if not wave_start_paid:
                    pay_hacker_income("start")
                    wave_start_paid = True
                if current_level == 3 and (current_wave == 20 or (infinite_mode and current_wave % 20 == 0)):
                    enemy_kind = "final_boss"
                elif current_wave % 5 == 0 and enemies_spawned_in_wave == enemies_to_spawn - 1:
                    enemy_kind = "mini_boss"
                elif current_wave >= 4 and enemies_spawned_in_wave % 4 == 3:
                    enemy_kind = "heavy"
                else:
                    enemy_kind = "basic"
                enemies.append(Enemy(enemy_kind))
                enemies_spawned_in_wave += 1
                spawn_timer = 0

            if enemies_spawned_in_wave >= enemies_to_spawn:
                if wave_transition_start is None:
                    wave_transition_start = pygame.time.get_ticks()
                if not enemies or pygame.time.get_ticks() - wave_transition_start >= int(10000 / GAME_SPEED):
                    if current_wave < max_waves:
                        pay_hacker_income("end")
                        current_wave += 1
                        enemies_spawned_in_wave = 0
                        enemies_to_spawn = enemies_for_wave(current_level, current_wave, infinite_mode)
                        money += int(45 * GAME_MODES[current_level]["reward"])
                        wave_start_paid = False
                        wave_transition_start = None
                    else:
                        pay_hacker_income("end")
                        if current_level < 3:
                            max_unlocked_map = max(max_unlocked_map, current_level + 1)
                            skill_points += current_level
                        else:
                            leaderboard_unlocked = True
                            infinite_unlocked = True
                            skill_points += current_level
                        save_player_progress()
                        game_state = "VICTORY"

            for enemy in enemies[:]:
                target_x, target_y = path[enemy.path_index + 1]
                dx = target_x - enemy.x
                dy = target_y - enemy.y
                dist = math.hypot(dx, dy)

                if dist < enemy.speed:
                    enemy.x, enemy.y = target_x, target_y
                    enemy.path_index += 1
                    if enemy.path_index >= len(path) - 1:
                        lives -= enemy.leak_damage
                        enemies.remove(enemy)
                        continue
                else:
                    enemy.x += (dx / dist) * enemy.speed
                    enemy.y += (dy / dist) * enemy.speed

            for t in towers:
                if t.type == 3:
                    continue
                target = next((enemy for enemy in enemies if math.hypot(t.x - enemy.x, t.y - enemy.y) <= t.range), None)
                if target:
                    t.aim_angle = -math.degrees(math.atan2(target.y - t.y, target.x - t.x))
                if t.cooldown > 0:
                    t.cooldown -= 1
                elif target:
                    shots_fired = 0
                    if t.type == 1:
                        if len(bullets) < MAX_ACTIVE_BULLETS:
                            bullets.append(Bullet(t.x, t.y, target, t.damage, t))
                            shots_fired = 1
                    else:
                        spread = [-18, 0, 18]
                        if t.level >= 2:
                            spread.extend([-30, 30])
                        available_slots = max(0, MAX_ACTIVE_BULLETS - len(bullets))
                        for angle_offset in spread[:available_slots]:
                            bullets.append(Bullet(t.x, t.y, target, t.damage, t, angle_offset))
                            shots_fired += 1
                    t.cooldown = t.fire_rate
                    if shots_fired:
                        advance_pet_quest("shots", shots_fired)

            for b in bullets[:]:
                b.x += b.vx
                b.y += b.vy
                hit_enemy = next((enemy for enemy in enemies if math.hypot(enemy.x - b.x, enemy.y - b.y) <= enemy.radius + 3), None)
                if hit_enemy:
                    hit_enemy.health -= b.damage
                    advance_pet_quest("damage", b.damage)
                    if hit_enemy.health <= 0:
                        reward = 250 if hit_enemy.kind == "final_boss" else (100 if hit_enemy.is_boss else 20)
                        money += int(reward * GAME_MODES[current_level]["reward"])
                        try_drop_implant(hit_enemy, b.owner)
                        advance_pet_quest("kills")
                        enemies.remove(hit_enemy)
                    bullets.remove(b)
                elif b.x < 0 or b.x > WIDTH or b.y < 115 or b.y > HEIGHT:
                    bullets.remove(b)

        for t in towers:
            t.draw(screen)

        if secret_pet:
            secret_pet.draw(screen)

        for implant in implants[:]:
            if implant.update():
                implants.remove(implant)
            else:
                implant.draw(screen)

        for enemy in enemies:
            color = BOSS_COLOR if enemy.is_boss else RED
            sprite = ENEMY_SPRITES.get(enemy.kind)
            if sprite:
                sprite_rect = sprite.get_rect(midbottom=(int(enemy.x), int(enemy.y + enemy.radius)))
                screen.blit(sprite, sprite_rect)
                head_y = sprite_rect.top
                bar_width = min(90, max(enemy.radius * 2, sprite_rect.width - 8))
            else:
                pygame.draw.circle(screen, color, (int(enemy.x), int(enemy.y)), enemy.radius)
                head_y = enemy.y - enemy.radius
                bar_width = enemy.radius * 2
            bar_y = int(head_y - 12)
            bar_x = int(enemy.x - bar_width / 2)
            hp_w = int(bar_width * (enemy.health / enemy.max_health))
            pygame.draw.rect(screen, (100, 0, 0), (bar_x, bar_y, int(bar_width), 5))
            pygame.draw.rect(screen, GREEN, (bar_x, bar_y, hp_w, 5))
            hp_text = font_ui.render(str(max(0, int(enemy.health))), True, WHITE)
            hp_rect = hp_text.get_rect(center=(int(enemy.x), int(head_y - 23)))
            screen.blit(hp_text, hp_rect)

        for b in bullets:
            pygame.draw.circle(screen, YELLOW, (int(b.x), int(b.y)), 4)

        for text in floating_texts[:]:
            text[1] -= 0.35
            text[3] -= 1
            floating = font_btn.render(text[2], True, GREEN)
            screen.blit(floating, floating.get_rect(center=(text[0], text[1])))
            if text[3] <= 0:
                floating_texts.remove(text)

        pygame.draw.rect(screen, PANEL_COLOR, (0, 0, WIDTH, 118))
        pygame.draw.line(screen, CYAN, (0, 117), (WIDTH, 117), 2)
        pygame.draw.line(screen, NEON_PINK, (0, 120), (260, 120), 2)
        mode_name = "INFINITE MODE" if infinite_mode else GAME_MODES[current_level]["name"]
        wave_total = "∞" if infinite_mode else str(max_waves)
        ui_text = font_ui.render(f"{mode_name} | Vilnis: {current_wave}/{wave_total} | Dzīv: {lives} | Nauda: ${money}", True, GREEN)
        screen.blit(ui_text, (15, 7))
        if active_pet:
            pet_status = PET_DATA[active_pet]
            pet_text = font_card.render(f"PET: {pet_status['name']} {pet_status['buff']}", False, YELLOW)
            screen.blit(pet_text, pet_text.get_rect(topright=(WIDTH - 14, 8)))
        elif pet_quest_active:
            quest_pet = PET_DATA[pet_quest_active]
            quest_panel = pygame.Rect(WIDTH - 350, 122, 340, 44)
            pygame.draw.rect(screen, PANEL_COLOR, quest_panel)
            pygame.draw.rect(screen, NEON_PINK, quest_panel, 2)
            quest_text = font_card.render(
                f"QUEST: {quest_pet['quest_text']} {pet_quest_progress}/{quest_pet['quest_target']}", False, WHITE
            )
            screen.blit(quest_text, quest_text.get_rect(center=quest_panel.center))

        for unit_type in (1, 2, 3):
            unit = UNIT_STATS[unit_type]
            x = 10 + (unit_type - 1) * 338
            count = sum(t.type == unit_type for t in towers)
            unit_color = CYAN if unit_type == 1 else (NEON_PINK if unit_type == 2 else GREEN)
            selected_color = unit_color if selected_tower_type == unit_type else (72, 91, 122)
            card = pygame.Rect(x, 33, 328, 52)
            pygame.draw.rect(screen, (14, 22, 40), card)
            pygame.draw.rect(screen, selected_color, card, 2)
            pygame.draw.line(screen, unit_color, (x + 8, 37), (x + 52, 37), 2)
            name = font_card.render(f"[{unit_type}] {unit['name']}", True, selected_color)
            current_cost = max(1, unit['cost'] - skills['discount'] * 5)
            details = font_card.render(f"Cena ${current_cost} | Novietots: {count}/{unit['limit']}", True, WHITE)
            screen.blit(name, (x + 8, 40))
            screen.blit(details, (x + 8, 62))

        tower_text = font_card.render("Kreisais: novietot | [E]: uzlabot | [Q] vai labais klikšķis: pārdot par 50%", True, YELLOW)
        screen.blit(tower_text, (15, 94))

        if status_timer > 0:
            status_timer -= 1
            message = font_ui.render(status_message, True, RED)
            screen.blit(message, message.get_rect(center=(WIDTH // 2, 132)))

        if lives <= 0:
            if infinite_mode and not game_over_recorded:
                record_infinite_result()
                game_over_recorded = True
            screen.fill(BG_COLOR)
            pygame.draw.rect(screen, PANEL_COLOR, (170, 285, WIDTH - 340, 190))
            pygame.draw.rect(screen, RED, (170, 285, WIDTH - 340, 190), 2)
            over_surf = font_title.render("GAME OVER", True, RED)
            sub_surf = font_ui.render("Nospied ESC, lai atgrieztos izvēlnē", True, WHITE)
            screen.blit(over_surf, over_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20)))
            screen.blit(sub_surf, sub_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 35)))

    elif game_state == "VICTORY":
        screen.fill(BG_COLOR)
        win_surf = font_title.render("APSVEICUMI - BOSS UZVARĒTS!", True, GREEN)
        reward_surf = font_ui.render(f"Iegūti {current_level} Skill Tree punkti!", True, WHITE)
        sub_surf = font_ui.render("[L] Leaderboard | [ESC] Izvēlne", True, CYAN)
        screen.blit(win_surf, win_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40)))
        screen.blit(reward_surf, reward_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 10)))
        screen.blit(sub_surf, sub_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 60)))

    pygame.display.flip()
    clock.tick(60)
