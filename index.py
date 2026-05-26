import os
import json
import asyncio
import random
import copy
import hashlib
from pathlib import Path
from flask import Flask, request, jsonify
from telegram import (
    Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import Application

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "gwentsecret")
UPSTASH_URL    = os.environ.get("UPSTASH_URL", "")   # https://xxx.upstash.io
UPSTASH_TOKEN  = os.environ.get("UPSTASH_TOKEN", "") # REST token

app = Flask(__name__)

DATA_PATH = Path(__file__).parent / "data" / "data.json"


# ─────────────────────────────────────────────
# DATA HELPERS
# ─────────────────────────────────────────────
def load_data() -> dict:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────
# REDIS (Upstash REST API)
# ─────────────────────────────────────────────
import httpx

def redis_set(key: str, value: dict, ex: int = 7200):
    """Store JSON value in Upstash Redis with TTL."""
    if not UPSTASH_URL:
        return  # local dev without Redis
    serialized = json.dumps(value, ensure_ascii=False)
    url = f"{UPSTASH_URL}/set/{key}"
    headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
    params = {"ex": ex, "px": None}
    httpx.post(url, headers=headers, params={"ex": ex},
               content=serialized, timeout=5)


def redis_get(key: str) -> dict | None:
    """Get JSON value from Upstash Redis."""
    if not UPSTASH_URL:
        return None
    url = f"{UPSTASH_URL}/get/{key}"
    headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
    try:
        r = httpx.get(url, headers=headers, timeout=5)
        data = r.json()
        if data.get("result"):
            return json.loads(data["result"])
    except Exception:
        pass
    return None


def redis_del(key: str):
    """Delete key from Upstash Redis."""
    if not UPSTASH_URL:
        return
    url = f"{UPSTASH_URL}/del/{key}"
    headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
    httpx.get(url, headers=headers, timeout=5)


# ─────────────────────────────────────────────
# GAME ENGINE
# ─────────────────────────────────────────────

ROWS = ["melee", "ranged", "siege"]
ROW_EMOJI = {"melee": "⚔️", "ranged": "🏹", "siege": "💣"}

# ─────────────────────────────────────────────
# AI ENGINE
# ─────────────────────────────────────────────

AI_USER_ID = 0
AI_NAME_BY_DIFFICULTY = {
    "easy":   "🤖 Новичок",
    "medium": "⚔️ Ветеран",
    "hard":   "💀 Легенда",
}


def ai_choose_card(gs: dict, side: str, difficulty: str) -> tuple[str, str]:
    """Выбирает карту и ряд для хода AI."""
    hand = gs["hand"][side]
    if not hand:
        return None, None

    opp = get_opponent(side)
    scores = calc_scores(gs)
    my_score = scores[side]
    opp_score = scores[opp]

    # ── EASY: случайная карта в случайный ряд ──
    if difficulty == "easy":
        card = random.choice(hand)
        return card["uid"], _valid_row(card)

    # ── MEDIUM: базовая логика ──
    if difficulty == "medium":
        spies = [c for c in hand if c["type"] == "spy"]
        if spies:
            return spies[0]["uid"], _valid_row(spies[0])

        if opp_score > my_score + 10:
            weather = [c for c in hand if c["type"] == "weather"
                       and "clear" not in c.get("abilities", [])]
            if weather:
                return weather[0]["uid"], _valid_row(weather[0])

        playable = [c for c in hand if c["type"] not in ("weather", "horn", "decoy")]
        if playable:
            card = max(playable, key=lambda c: c["val"])
            return card["uid"], _valid_row(card)

        card = random.choice(hand)
        return card["uid"], _valid_row(card)

    # ── HARD: продвинутая логика ──
    if difficulty == "hard":
        # 1. Шпион — всегда первым (бесплатные 2 карты)
        spies = [c for c in hand if c["type"] == "spy"]
        if spies:
            return spies[0]["uid"], _valid_row(spies[0])

        # 2. Медик если есть сильные карты в отбое
        medics = [c for c in hand if "medic" in c.get("abilities", [])]
        good_grave = [c for c in gs["graveyard"][side]
                      if c["val"] >= 5 and c["type"] != "hero"]
        if medics and good_grave:
            return medics[0]["uid"], _valid_row(medics[0])

        # 3. Казнь если у врага сильная карта
        opp_max = max(
            (c["val"] for r in ROWS for c in gs["rows"][opp][r]
             if c["type"] != "hero"),
            default=0
        )
        if opp_max >= 7:
            kazn = [c for c in hand if "kazn" in c.get("abilities", [])]
            if kazn:
                return kazn[0]["uid"], _valid_row(kazn[0])

        # 4. Погода если противник сильно впереди
        if opp_score > my_score + 15:
            weather = [c for c in hand
                       if c["type"] == "weather"
                       and "clear" not in c.get("abilities", [])]
            if weather:
                best_row = max(ROWS, key=lambda r: calc_row_score(
                    gs["rows"][opp][r], gs["horns"][opp][r], gs["wx"][r]
                ))
                row_weather = [c for c in weather if c.get("row") == best_row]
                card = row_weather[0] if row_weather else weather[0]
                return card["uid"], _valid_row(card)

        # 5. Прочная связь — играем пары
        bond_ids: dict[str, list] = {}
        for c in hand:
            if "bond" in c.get("abilities", []):
                bond_ids.setdefault(c["id"], []).append(c)
        for bond_cards in bond_ids.values():
            if len(bond_cards) >= 2:
                return bond_cards[0]["uid"], _valid_row(bond_cards[0])

        # 6. Рог если ряд большой
        horns = [c for c in hand if c["type"] == "horn"]
        if horns:
            best_row = max(ROWS, key=lambda r: len(gs["rows"][side][r]))
            if (len(gs["rows"][side][best_row]) >= 3
                    and not gs["horns"][side][best_row]):
                return horns[0]["uid"], best_row

        # 7. Сильнейшая обычная карта
        playable = [c for c in hand if c["type"] not in ("weather", "horn", "decoy")]
        if playable:
            card = max(playable, key=lambda c: c["val"])
            return card["uid"], _valid_row(card)

        card = random.choice(hand)
        return card["uid"], _valid_row(card)

    return None, None


def ai_should_pass(gs: dict, side: str, difficulty: str) -> bool:
    """Решает — пасовать ли AI в этот момент."""
    opp = get_opponent(side)
    scores = calc_scores(gs)
    my_score = scores[side]
    opp_score = scores[opp]
    hand_size = len(gs["hand"][side])

    if difficulty == "easy":
        return my_score > opp_score and random.random() < 0.2

    if difficulty == "medium":
        if gs["passed"][opp] and my_score > opp_score:
            return True
        if my_score > opp_score + 5 and hand_size <= 3:
            return True
        return False

    if difficulty == "hard":
        if gs["passed"][opp] and my_score > opp_score:
            return True
        if my_score > opp_score + 20 and hand_size <= 4:
            return True
        if hand_size <= 2 and my_score < opp_score:
            return True
        return False

    return False


def _valid_row(card: dict) -> str:
    """Возвращает корректный ряд для карты."""
    row = card.get("row", "melee")
    if row == "any" or row not in ROWS:
        return "melee"
    return row


def ai_pick_medic(gs: dict, side: str) -> str | None:
    """AI выбирает лучшую карту для воскрешения медиком."""
    grave = [c for c in gs["graveyard"][side]
             if c["type"] not in ("weather", "horn", "decoy")]
    if not grave:
        return None
    return max(grave, key=lambda c: c["val"])["uid"]


def uid_card(card: dict, idx: int) -> dict:
    """Give each card a unique uid for tracking."""
    c = copy.deepcopy(card)
    c["uid"] = f"{card['id']}_{idx}"
    return c


def build_deck(faction_key: str, data: dict) -> list[dict]:
    """Build and shuffle a deck for a faction."""
    cards = data["factions"][faction_key]["cards"]
    deck = []
    for i, card in enumerate(cards):
        deck.append(uid_card(card, i))
    random.shuffle(deck)
    return deck


def empty_rows() -> dict:
    return {"melee": [], "ranged": [], "siege": []}


def empty_wx() -> dict:
    return {"melee": False, "ranged": False, "siege": False}


def create_game(p1_id: int, p1_name: str, p2_id: int, p2_name: str,
                p1_faction: str, p2_faction: str,
                p1_leader_idx: int, p2_leader_idx: int,
                data: dict) -> dict:
    """Create a new GameState dict."""
    p1_deck = build_deck(p1_faction, data)
    p2_deck = build_deck(p2_faction, data)

    p1_hand = p1_deck[:10]; p1_deck = p1_deck[10:]
    p2_hand = p2_deck[:10]; p2_deck = p2_deck[10:]

    p1_leader = data["factions"][p1_faction]["leaders"][p1_leader_idx]
    p2_leader = data["factions"][p2_faction]["leaders"][p2_leader_idx]

    return {
        "round": 1,
        "turn": "p1",          # whose turn: "p1" or "p2"
        "phase": "play",       # play | mulligan_p1 | mulligan_p2 | round_end | game_over
        "passed": {"p1": False, "p2": False},
        "wins": {"p1": 0, "p2": 0},
        "wx": empty_wx(),
        "rows": {"p1": empty_rows(), "p2": empty_rows()},
        "horns": {"p1": {"melee": False, "ranged": False, "siege": False},
                  "p2": {"melee": False, "ranged": False, "siege": False}},
        "graveyard": {"p1": [], "p2": []},
        "deck": {"p1": p1_deck, "p2": p2_deck},
        "hand": {"p1": p1_hand, "p2": p2_hand},
        "mulligan_swaps": {"p1": 0, "p2": 0},
        "selected_card_uid": {"p1": None, "p2": None},
        "awaiting_medic": {"p1": False, "p2": False},
        "players": {
            "p1": {"id": p1_id, "name": p1_name,
                   "faction": p1_faction, "leader": p1_leader,
                   "leader_used": False},
            "p2": {"id": p2_id, "name": p2_name,
                   "faction": p2_faction, "leader": p2_leader,
                   "leader_used": False},
        },
        "log": [],
    }


def calc_row_score(cards: list[dict], horn: bool, wx_active: bool) -> int:
    """Calculate score for one row considering weather and horn."""
    total = 0
    bond_groups: dict[str, int] = {}
    for c in cards:
        if c["type"] == "hero":
            total += c["val"]
            continue
        if wx_active:
            total += 1
            continue
        val = c["val"]
        if "bond" in c.get("abilities", []):
            bond_id = c["id"]
            bond_groups[bond_id] = bond_groups.get(bond_id, 0) + 1
        if "morale" in c.get("abilities", []):
            pass  # counted separately
        total += val

    # morale bonus
    morale_bonus = sum(
        1 for c in cards
        if "morale" in c.get("abilities", []) and c["type"] != "hero"
    )
    non_morale = [c for c in cards if "morale" not in c.get("abilities", [])]
    if morale_bonus and not wx_active:
        total += morale_bonus * len(non_morale)

    # bond doubling
    for bond_id, count in bond_groups.items():
        if count >= 2 and not wx_active:
            base = next((c["val"] for c in cards if c["id"] == bond_id), 0)
            total += base * count  # add extra (already counted once)

    if horn and not wx_active:
        total *= 2

    return total


def calc_scores(gs: dict) -> dict[str, int]:
    """Calculate total scores for both players."""
    scores = {}
    for side in ("p1", "p2"):
        total = 0
        for row in ROWS:
            cards = gs["rows"][side][row]
            horn = gs["horns"][side][row]
            wx = gs["wx"][row]
            total += calc_row_score(cards, horn, wx)
        scores[side] = total
    return scores


def get_opponent(side: str) -> str:
    return "p2" if side == "p1" else "p1"


def add_log(gs: dict, msg: str):
    gs["log"].append(msg)
    if len(gs["log"]) > 10:
        gs["log"] = gs["log"][-10:]


def apply_card(gs: dict, side: str, card_uid: str, target_row: str,
               data: dict) -> tuple[bool, str]:
    """
    Apply a card play. Returns (success, message).
    """
    hand = gs["hand"][side]
    card = next((c for c in hand if c["uid"] == card_uid), None)
    if not card:
        return False, "Карта не найдена в руке"

    opp = get_opponent(side)
    ctype = card["type"]

    # Remove from hand
    gs["hand"][side] = [c for c in hand if c["uid"] != card_uid]

    # ── Weather ──
    if ctype == "weather":
        if "clear" in card.get("abilities", []):
            gs["wx"] = empty_wx()
            gs["graveyard"][side].append(card)
            return True, f"☀️ Ясная погода — весь туман рассеян!"
        else:
            row_map = {"melee": "melee", "ranged": "ranged", "siege": "siege"}
            wx_row = card.get("row", "melee")
            if wx_row in row_map:
                gs["wx"][wx_row] = True
            gs["graveyard"][side].append(card)
            return True, f"{card['emoji']} {card['name']} — погода на {ROW_EMOJI.get(wx_row,'?')} ряду"

    # ── Horn ──
    if ctype == "horn":
        if not target_row:
            return False, "Укажите ряд для рога"
        if gs["horns"][side][target_row]:
            return False, "В этом ряду уже есть рог"
        gs["horns"][side][target_row] = True
        gs["graveyard"][side].append(card)
        return True, f"📯 Командирский рог в {ROW_EMOJI.get(target_row,'?')} ряд!"

    # ── Decoy ──
    if ctype == "decoy":
        # Will be handled as a 2-step action; here just mark awaiting
        # For simplicity: swap with a random non-hero card on field
        field_cards = gs["rows"][side].get(target_row, [])
        swappable = [c for c in field_cards if c["type"] != "hero"]
        if not swappable:
            gs["hand"][side].append(card)  # return decoy
            return False, "Нет карт для замены чучелом"
        swap_card = swappable[0]
        gs["rows"][side][target_row] = [c for c in field_cards if c["uid"] != swap_card["uid"]]
        gs["hand"][side].append(swap_card)
        gs["graveyard"][side].append(card)
        return True, f"🎭 Чучело: {swap_card['name']} вернулась в руку"

    # ── Spy ──
    if ctype == "spy":
        row = card.get("row", "melee")
        if row not in ROWS:
            row = "melee"
        gs["rows"][opp][row].append(card)
        # Draw 2 cards
        drawn = []
        for _ in range(2):
            if gs["deck"][side]:
                drawn.append(gs["deck"][side].pop(0))
                gs["hand"][side].append(drawn[-1])
        drawn_names = ", ".join(c["name"] for c in drawn) if drawn else "нет карт"
        return True, f"👁️ Шпион {card['name']} к врагу! Взято: {drawn_names}"

    # ── Normal / Hero ──
    row = target_row if target_row else card.get("row", "melee")
    if card.get("row") == "any" or not row:
        row = target_row or "melee"
    if row not in ROWS:
        row = "melee"

    gs["rows"][side][row].append(card)

    msg = f"{card['emoji']} {card['name']} ({card['val']}) → {ROW_EMOJI.get(row,'?')}"

    # ── Medic ──
    if "medic" in card.get("abilities", []):
        graveyard = [c for c in gs["graveyard"][side] if c["type"] not in ("weather", "horn", "decoy")]
        if graveyard:
            gs["awaiting_medic"][side] = True
            msg += " | Медик: выберите карту для воскрешения"

    # ── Kazn (Scorch) ──
    if "kazn" in card.get("abilities", []):
        best_val = 0
        best_card = None
        best_row = None
        for r in ROWS:
            for c in gs["rows"][opp][r]:
                if c["type"] != "hero" and c["val"] > best_val:
                    best_val = c["val"]
                    best_card = c
                    best_row = r
        if best_card:
            gs["rows"][opp][best_row] = [c for c in gs["rows"][opp][best_row]
                                          if c["uid"] != best_card["uid"]]
            gs["graveyard"][opp].append(best_card)
            msg += f" | 💀 Казнь: уничтожен {best_card['name']} ({best_val})"

    return True, msg


def check_round_end(gs: dict) -> bool:
    """Returns True if round should end."""
    return gs["passed"]["p1"] and gs["passed"]["p2"]


def resolve_round(gs: dict, data: dict) -> str:
    """Resolve round, update wins, return result message."""
    scores = calc_scores(gs)
    s1, s2 = scores["p1"], scores["p2"]
    p1_name = gs["players"]["p1"]["name"]
    p2_name = gs["players"]["p2"]["name"]

    # Nilfgaard ability: win on draw
    p1_fac = gs["players"]["p1"]["faction"]
    p2_fac = gs["players"]["p2"]["faction"]

    if s1 > s2:
        gs["wins"]["p1"] += 1
        winner_msg = f"🏆 Раунд {gs['round']}: победа {p1_name}! ({s1} vs {s2})"
    elif s2 > s1:
        gs["wins"]["p2"] += 1
        winner_msg = f"🏆 Раунд {gs['round']}: победа {p2_name}! ({s2} vs {s1})"
    else:
        # Draw: Nilfgaard wins
        if p1_fac == "nilfgaard":
            gs["wins"]["p1"] += 1
            winner_msg = f"⚜️ Ничья! Нильфгаард ({p1_name}) побеждает при равном счёте ({s1}:{s2})"
        elif p2_fac == "nilfgaard":
            gs["wins"]["p2"] += 1
            winner_msg = f"⚜️ Ничья! Нильфгаард ({p2_name}) побеждает при равном счёте ({s1}:{s2})"
        else:
            gs["wins"]["p1"] += 1
            gs["wins"]["p2"] += 1
            winner_msg = f"🤝 Ничья в раунде {gs['round']}! ({s1}:{s2}) — оба получают победу"

    add_log(gs, winner_msg)

    # Check game over
    if gs["wins"]["p1"] >= 2 or gs["wins"]["p2"] >= 2:
        gs["phase"] = "game_over"
        return winner_msg

    # Next round
    gs["round"] += 1
    gs["passed"] = {"p1": False, "p2": False}
    gs["wx"] = empty_wx()

    # Move field cards to graveyard
    for side in ("p1", "p2"):
        for row in ROWS:
            gs["graveyard"][side].extend(gs["rows"][side][row])
            gs["rows"][side][row] = []
        gs["horns"][side] = {"melee": False, "ranged": False, "siege": False}

    # Skellige ability: resurrect 2 weakest (simplified: draw 1 card)
    # Draw 2 cards for new round start
    for side in ("p1", "p2"):
        for _ in range(2):
            if gs["deck"][side]:
                gs["hand"][side].append(gs["deck"][side].pop(0))

    gs["turn"] = "p1"
    gs["phase"] = "mulligan_p1"
    gs["mulligan_swaps"] = {"p1": 0, "p2": 0}

    return winner_msg


# ─────────────────────────────────────────────
# BOARD RENDERER
# ─────────────────────────────────────────────

def render_board(gs: dict, pov: str) -> str:
    """
    Render ASCII board from point of view of pov ("p1" or "p2").
    """
    opp = get_opponent(pov)
    scores = calc_scores(gs)

    p_name = gs["players"][pov]["name"]
    o_name = gs["players"][opp]["name"]
    p_score = scores[pov]
    o_score = scores[opp]

    p_wins = "🔴" * gs["wins"][pov] + "⚪" * (2 - gs["wins"][pov])
    o_wins = "🔴" * gs["wins"][opp] + "⚪" * (2 - gs["wins"][opp])

    lines = []
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"👤 {o_name}  {o_wins}  [{o_score}]")
    lines.append(f"─────────────────────────")

    # Opponent rows (reversed order)
    for row in reversed(ROWS):
        wx_icon = "🌪" if gs["wx"][row] else ""
        horn_icon = "📯" if gs["horns"][opp][row] else ""
        cards_str = _render_row_cards(gs["rows"][opp][row], gs["wx"][row])
        row_score = calc_row_score(gs["rows"][opp][row],
                                   gs["horns"][opp][row], gs["wx"][row])
        lines.append(
            f"{ROW_EMOJI[row]}{wx_icon}{horn_icon} [{row_score:>3}] {cards_str}"
        )

    lines.append(f"─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─")

    # Player rows
    for row in ROWS:
        wx_icon = "🌪" if gs["wx"][row] else ""
        horn_icon = "📯" if gs["horns"][pov][row] else ""
        cards_str = _render_row_cards(gs["rows"][pov][row], gs["wx"][row])
        row_score = calc_row_score(gs["rows"][pov][row],
                                   gs["horns"][pov][row], gs["wx"][row])
        lines.append(
            f"{ROW_EMOJI[row]}{wx_icon}{horn_icon} [{row_score:>3}] {cards_str}"
        )

    lines.append(f"─────────────────────────")

    # Hand info
    hand_count = len(gs["hand"][pov])
    deck_count = len(gs["deck"][pov])
    grave_count = len(gs["graveyard"][pov])
    lines.append(f"👤 {p_name}  {p_wins}  [{p_score}]")
    lines.append(f"🃏 Рука: {hand_count}  📚 Колода: {deck_count}  🪦 Отбой: {grave_count}")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Turn indicator
    turn_side = gs["turn"]
    if turn_side == pov:
        lines.append("▶️  ВАШ ХОД")
    else:
        lines.append(f"⏳ Ждём {o_name}...")

    # Pass status
    if gs["passed"][pov]:
        lines.append("✋ Вы спасовали")
    if gs["passed"][opp]:
        lines.append(f"✋ {o_name} спасовал(а)")

    # Last log
    if gs["log"]:
        lines.append(f"\n📜 {gs['log'][-1]}")

    return "\n".join(lines)


def _render_row_cards(cards: list[dict], wx: bool) -> str:
    if not cards:
        return "—"
    parts = []
    for c in cards:
        val = 1 if wx and c["type"] != "hero" else c["val"]
        badge = "👑" if c["type"] == "hero" else ""
        parts.append(f"{c['emoji']}{badge}{val}")
    return " ".join(parts)


# ─────────────────────────────────────────────
# KEYBOARD BUILDERS
# ─────────────────────────────────────────────

def kb_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Играть с человеком",    callback_data="find_game")],
        [InlineKeyboardButton("🤖 Играть с компьютером", callback_data="vs_ai")],
        [InlineKeyboardButton("📚 Правила",               callback_data="rules")],
        [InlineKeyboardButton("🃏 Фракции",               callback_data="factions")],
    ])
def kb_difficulty() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Новичок — случайные ходы",  callback_data="ai_diff:easy")],
        [InlineKeyboardButton("🟡 Ветеран — базовая тактика", callback_data="ai_diff:medium")],
        [InlineKeyboardButton("🔴 Легенда — полная стратегия",callback_data="ai_diff:hard")],
    ])


def kb_faction_select(data: dict) -> InlineKeyboardMarkup:
    rows = []
    for fkey, fval in data["factions"].items():
        rows.append([InlineKeyboardButton(
            f"{fval['icon']} {fval['name']}",
            callback_data=f"faction:{fkey}"
        )])
    return InlineKeyboardMarkup(rows)


def kb_leader_select(faction_key: str, data: dict) -> InlineKeyboardMarkup:
    leaders = data["factions"][faction_key]["leaders"]
    rows = []
    for i, ldr in enumerate(leaders):
        rows.append([InlineKeyboardButton(
            f"{ldr['icon']} {ldr['name']}",
            callback_data=f"leader:{faction_key}:{i}"
        )])
    return InlineKeyboardMarkup(rows)


def kb_hand(gs: dict, side: str) -> InlineKeyboardMarkup:
    """Build keyboard from player's hand (max 8 buttons + pass)."""
    hand = gs["hand"][side]
    rows = []
    # Cards in pairs
    for i in range(0, min(len(hand), 16), 2):
        row_btns = []
        for j in range(2):
            if i + j < len(hand):
                c = hand[i + j]
                val_str = f"({c['val']})" if c["val"] else ""
                label = f"{c['emoji']}{c['name'][:12]}{val_str}"
                row_btns.append(InlineKeyboardButton(
                    label, callback_data=f"card:{c['uid']}"
                ))
        rows.append(row_btns)

    # Pass button
    rows.append([InlineKeyboardButton("✋ Пас", callback_data="pass_round")])
    rows.append([InlineKeyboardButton("🏳️ Сдаться", callback_data="surrender")])
    return InlineKeyboardMarkup(rows)


def kb_row_select(card_uid: str, card: dict) -> InlineKeyboardMarkup:
    """Choose a row to place the card."""
    rows_available = []
    card_row = card.get("row", "melee")
    if card_row == "any":
        rows_available = ROWS
    elif card_row in ROWS:
        rows_available = [card_row]
    else:
        rows_available = ROWS

    btns = []
    for r in rows_available:
        btns.append([InlineKeyboardButton(
            f"{ROW_EMOJI[r]} {r.capitalize()}",
            callback_data=f"place:{card_uid}:{r}"
        )])
    btns.append([InlineKeyboardButton("↩️ Назад", callback_data="cancel_select")])
    return InlineKeyboardMarkup(btns)


def kb_mulligan(hand: list[dict]) -> InlineKeyboardMarkup:
    """Build mulligan keyboard."""
    rows = []
    for i in range(0, min(len(hand), 16), 2):
        row_btns = []
        for j in range(2):
            if i + j < len(hand):
                c = hand[i + j]
                val_str = f"({c['val']})" if c["val"] else ""
                label = f"{c['emoji']}{c['name'][:12]}{val_str}"
                row_btns.append(InlineKeyboardButton(
                    label, callback_data=f"mulligan:{c['uid']}"
                ))
        rows.append(row_btns)
    rows.append([InlineKeyboardButton("✅ Готов к игре", callback_data="mulligan_done")])
    return InlineKeyboardMarkup(rows)


def kb_medic(graveyard: list[dict]) -> InlineKeyboardMarkup:
    """Choose card to resurrect."""
    eligible = [c for c in graveyard
                if c["type"] not in ("weather", "horn", "decoy")]
    rows = []
    for i in range(0, len(eligible), 2):
        row_btns = []
        for j in range(2):
            if i + j < len(eligible):
                c = eligible[i + j]
                label = f"{c['emoji']}{c['name'][:12]}({c['val']})"
                row_btns.append(InlineKeyboardButton(
                    label, callback_data=f"medic:{c['uid']}"
                ))
        rows.append(row_btns)
    rows.append([InlineKeyboardButton("⏭️ Пропустить", callback_data="medic_skip")])
    return InlineKeyboardMarkup(rows)


# ─────────────────────────────────────────────
# SESSION HELPERS
# ─────────────────────────────────────────────

def game_key(game_id: str) -> str:
    return f"gwent:game:{game_id}"


def queue_key() -> str:
    return "gwent:queue"


def lobby_key(lobby_id: str) -> str:
    return f"gwent:lobby:{lobby_id}"


def user_game_key(user_id: int) -> str:
    return f"gwent:user:{user_id}:game"


def user_setup_key(user_id: int) -> str:
    return f"gwent:user:{user_id}:setup"


def get_game(game_id: str) -> dict | None:
    return redis_get(game_key(game_id))


def save_game(game_id: str, gs: dict):
    redis_set(game_key(game_id), gs, ex=7200)


def get_user_game_id(user_id: int) -> str | None:
    data = redis_get(user_game_key(user_id))
    return data.get("game_id") if data else None


def set_user_game_id(user_id: int, game_id: str):
    redis_set(user_game_key(user_id), {"game_id": game_id}, ex=7200)


def get_user_setup(user_id: int) -> dict | None:
    return redis_get(user_setup_key(user_id))


def set_user_setup(user_id: int, setup: dict):
    redis_set(user_setup_key(user_id), setup, ex=3600)


def get_side_for_user(gs: dict, user_id: int) -> str | None:
    for side in ("p1", "p2"):
        if gs["players"][side]["id"] == user_id:
            return side
    return None


# ─────────────────────────────────────────────
# TELEGRAM HANDLERS
# ─────────────────────────────────────────────

async def handle_start(bot: Bot, chat_id: int, user_id: int,
                       user_name: str, args: str, data: dict):
    # Deep link: start game via invite
    if args and args.startswith("lobby_"):
        await handle_join_lobby(bot, chat_id, user_id, user_name, args, data)
        return

    text = (
        f"♟️ *Добро пожаловать в ГВИНТ!*\n\n"
        f"Карточная игра из «Ведьмака 3».\n"
        f"Сразись с реальным противником!\n\n"
        f"🏆 Побеждает тот, кто выиграет *2 раунда из 3*.\n"
        f"🃏 Каждый ход — одна карта или *пас*."
    )
    await bot.send_message(chat_id, text,
                           reply_markup=kb_main_menu(),
                           parse_mode="Markdown")


async def delete_msg(bot, chat_id, message_id):
    """Тихо удаляет сообщение."""
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


async def handle_find_game(bot: Bot, chat_id: int, user_id: int,
                           user_name: str, data: dict):
    # Check if already in game
    existing = get_user_game_id(user_id)
    if existing:
        gs = get_game(existing)
        if gs and gs["phase"] not in ("game_over",):
            await bot.send_message(
                chat_id,
                "⚠️ Ты уже в игре! Напиши /game чтобы вернуться.",
            )
            return

    # Check queue
    queue = redis_get(queue_key())
    if queue and queue.get("user_id") and queue["user_id"] != user_id:
        # Match found!
        p2_id = queue["user_id"]
        p2_name = queue["user_name"]
        redis_del(queue_key())

        # Both need to pick faction
        set_user_setup(user_id, {
            "role": "p1", "opponent_id": p2_id, "opponent_name": p2_name
        })
        set_user_setup(p2_id, {
            "role": "p2", "opponent_id": user_id, "opponent_name": user_name
        })

        await bot.send_message(
            chat_id,
            f"⚔️ Найден противник: *{p2_name}*!\n\nВыберите фракцию:",
            reply_markup=kb_faction_select(data),
            parse_mode="Markdown"
        )
        await bot.send_message(
            p2_id,
            f"⚔️ Найден противник: *{user_name}*!\n\nВыберите фракцию:",
            reply_markup=kb_faction_select(data),
            parse_mode="Markdown"
        )
    else:
        # Add to queue
        redis_set(queue_key(), {"user_id": user_id, "user_name": user_name}, ex=300)
        lobby_id = hashlib.md5(f"{user_id}_{user_name}".encode()).hexdigest()[:8]
        redis_set(lobby_key(lobby_id), {"host_id": user_id, "host_name": user_name}, ex=300)
        invite_link = f"https://t.me/{(await bot.get_me()).username}?start=lobby_{lobby_id}"

        await bot.send_message(
            chat_id,
            f"🔍 Ищем противника...\n\n"
            f"Или пригласи друга по ссылке:\n`{invite_link}`\n\n"
            f"Ожидание до 5 минут.",
            parse_mode="Markdown"
        )


async def handle_join_lobby(bot: Bot, chat_id: int, user_id: int,
                            user_name: str, args: str, data: dict):
    lobby_id = args.replace("lobby_", "")
    lobby = redis_get(lobby_key(lobby_id))
    if not lobby:
        await bot.send_message(chat_id, "❌ Лобби не найдено или истекло.")
        return

    host_id = lobby["host_id"]
    host_name = lobby["host_name"]
    if host_id == user_id:
        await bot.send_message(chat_id, "⚠️ Нельзя играть с самим собой!")
        return

    redis_del(queue_key())
    redis_del(lobby_key(lobby_id))

    set_user_setup(user_id, {
        "role": "p2", "opponent_id": host_id, "opponent_name": host_name
    })
    set_user_setup(host_id, {
        "role": "p1", "opponent_id": user_id, "opponent_name": user_name
    })

    await bot.send_message(
        chat_id,
        f"⚔️ Присоединился к игре с *{host_name}*!\n\nВыберите фракцию:",
        reply_markup=kb_faction_select(data),
        parse_mode="Markdown"
    )
    await bot.send_message(
        host_id,
        f"⚔️ *{user_name}* принял приглашение!\n\nВыберите фракцию:",
        reply_markup=kb_faction_select(data),
        parse_mode="Markdown"
    )


async def handle_faction_pick(bot: Bot, chat_id: int, user_id: int,
                              faction_key: str, data: dict, prev_msg_id: int = None):
    setup = get_user_setup(user_id)
    if not setup:
        await bot.send_message(chat_id, "❌ Сессия устарела. Начни заново: /start")
        return

    setup["faction"] = faction_key
    set_user_setup(user_id, setup)

    await delete_msg(bot, chat_id, prev_msg_id)

    faction = data["factions"][faction_key]
    msg = await bot.send_message(
        chat_id,
        f"{faction['icon']} *{faction['name']}*\n\n"
        f"Особенность: _{faction['ability']}_\n\n"
        f"Теперь выберите лидера:",
        reply_markup=kb_leader_select(faction_key, data),
        parse_mode="Markdown"
    )
    setup["last_msg_id"] = msg.message_id
    set_user_setup(user_id, setup)


async def handle_leader_pick(bot: Bot, chat_id: int, user_id: int,
                             user_name: str, faction_key: str, leader_idx: int, data: dict,
                             prev_msg_id: int = None):
    setup = get_user_setup(user_id)
    if not setup:
        await bot.send_message(chat_id, "❌ Сессия устарела.")
        return

    setup["leader_idx"] = leader_idx
    set_user_setup(user_id, setup)

    await delete_msg(bot, chat_id, prev_msg_id)

    leader = data["factions"][faction_key]["leaders"][leader_idx]
    if not setup.get("ai_difficulty"):
        await bot.send_message(
            chat_id,
            f"{leader['icon']} *{leader['name']}*\n_{leader['power']}_\n\n"
            f"⏳ Ожидаем выбор противника...",
            parse_mode="Markdown"
        )

    # AI-игра или PvP?
    if setup.get("ai_difficulty"):
        await launch_ai_game(bot, user_id, user_name, setup,
                             faction_key, leader_idx, data)
    else:
        opp_id = setup["opponent_id"]
        opp_setup = get_user_setup(opp_id)
        if opp_setup and opp_setup.get("faction") and opp_setup.get("leader_idx") is not None:
            await launch_game(bot, user_id, opp_id, setup, opp_setup, data)


async def launch_ai_game(bot: Bot, user_id: int, user_name: str,
                         setup: dict, faction_key: str, leader_idx: int,
                         data: dict):
    """Запускает игру против AI."""
    difficulty = setup.get("ai_difficulty", "medium")
    ai_name = AI_NAME_BY_DIFFICULTY[difficulty]

    ai_faction = random.choice(list(data["factions"].keys()))
    ai_leader_idx = random.randint(
        0, len(data["factions"][ai_faction]["leaders"]) - 1
    )

    game_id = hashlib.md5(
        f"{user_id}_ai_{random.random()}".encode()
    ).hexdigest()[:12]

    gs = create_game(
        user_id, user_name,
        AI_USER_ID, ai_name,
        faction_key, ai_faction,
        leader_idx, ai_leader_idx,
        data
    )
    gs["is_ai_game"] = True
    gs["ai_difficulty"] = difficulty
    gs["phase"] = "mulligan_p1"
    gs["turn"] = "p1"

    save_game(game_id, gs)
    set_user_game_id(user_id, game_id)

    ai_faction_name = data["factions"][ai_faction]["name"]
    ai_leader_name = data["factions"][ai_faction]["leaders"][ai_leader_idx]["name"]

    msg = await bot.send_message(
        user_id,
        f"🎮 *Игра против {ai_name}!*\n\n"
        f"Фракция противника: {ai_faction_name}\n"
        f"Лидер: {ai_leader_name}\n\n"
        f"Муллиган: замените до 2 карт из руки.",
        reply_markup=kb_mulligan(gs["hand"]["p1"]),
        parse_mode="Markdown"
    )
    gs.setdefault("mulligan_msg_id", {})["p1"] = msg.message_id
    save_game(game_id, gs)

async def launch_game(bot: Bot, user_a_id: int, user_b_id: int,
                      setup_a: dict, setup_b: dict, data: dict):
    """Create game and start mulligan phase."""
    # Determine p1/p2
    if setup_a["role"] == "p1":
        p1_id, p1_setup = user_a_id, setup_a
        p2_id, p2_setup = user_b_id, setup_b
    else:
        p1_id, p1_setup = user_b_id, setup_b
        p2_id, p2_setup = user_a_id, setup_a

    p1_name = p1_setup.get("opponent_name", "Player 1")  # wrong — fix:
    # We need actual names; store them in setup
    p1_name = redis_get(user_setup_key(p1_id)).get("my_name", f"Player {p1_id}")
    p2_name = redis_get(user_setup_key(p2_id)).get("my_name", f"Player {p2_id}")

    game_id = hashlib.md5(f"{p1_id}_{p2_id}_{random.random()}".encode()).hexdigest()[:12]

    gs = create_game(
        p1_id, p1_name, p2_id, p2_name,
        p1_setup["faction"], p2_setup["faction"],
        p1_setup["leader_idx"], p2_setup["leader_idx"],
        data
    )
    gs["phase"] = "mulligan_p1"
    save_game(game_id, gs)
    set_user_game_id(p1_id, game_id)
    set_user_game_id(p2_id, game_id)

    # Send mulligan to p1
    await bot.send_message(
        p1_id,
        f"🎮 Игра начинается!\n\nМуллиган: замените до 2 карт из руки.\n"
        f"Нажмите карту чтобы заменить, затем *«Готов»*.",
        reply_markup=kb_mulligan(gs["hand"]["p1"]),
        parse_mode="Markdown"
    )
    await bot.send_message(
        p2_id,
        "⏳ Противник делает муллиган. Подождите...",
    )


async def handle_mulligan(bot: Bot, chat_id: int, user_id: int,
                          card_uid: str, game_id: str, data: dict):
    gs = get_game(game_id)
    if not gs:
        await bot.send_message(chat_id, "❌ Игра не найдена.")
        return

    side = get_side_for_user(gs, user_id)
    if not side:
        return

    # Check it's this player's mulligan turn
    expected_phase = f"mulligan_{side}"
    if gs["phase"] != expected_phase:
        await bot.send_message(chat_id, "⏳ Сейчас не ваш муллиган.")
        return

    if gs["mulligan_swaps"][side] >= 2:
        await bot.send_message(chat_id, "❌ Лимит замен исчерпан (2/2).")
        return

    hand = gs["hand"][side]
    deck = gs["deck"][side]
    card = next((c for c in hand if c["uid"] == card_uid), None)
    if not card:
        return

    if not deck:
        await bot.send_message(chat_id, "Колода пуста — замена невозможна.")
        return

    # Swap
    gs["hand"][side] = [c for c in hand if c["uid"] != card_uid]
    insert_at = max(1, random.randint(1, len(deck)))
    deck.insert(insert_at, card)
    new_card = deck.pop(0)
    gs["hand"][side].append(new_card)
    gs["mulligan_swaps"][side] += 1
    gs["deck"][side] = deck

    save_game(game_id, gs)

    swaps = gs["mulligan_swaps"][side]
    prev_mid = gs.get("mulligan_msg_id", {}).get(side)
    await delete_msg(bot, chat_id, prev_mid)
    msg = await bot.send_message(
        chat_id,
        f"🔄 Замена {swaps}/2: {card['name']} → {new_card['emoji']}{new_card['name']}\n\n"
        f"{'Ещё можно заменить 1 карту.' if swaps < 2 else 'Лимит замен исчерпан.'}",
        reply_markup=kb_mulligan(gs["hand"][side]),
    )
    gs.setdefault("mulligan_msg_id", {})[side] = msg.message_id
    save_game(game_id, gs)


async def handle_mulligan_done(bot: Bot, chat_id: int, user_id: int,
                               game_id: str, data: dict):
    gs = get_game(game_id)
    if not gs:
        return

    side = get_side_for_user(gs, user_id)
    if not side:
        return

    if gs["phase"] == "mulligan_p1" and side == "p1":
        prev_mid = gs.get("mulligan_msg_id", {}).get(side)
        await delete_msg(bot, chat_id, prev_mid)
        if gs.get("is_ai_game"):
            gs["phase"] = "play"
            gs["turn"] = "p1"
            save_game(game_id, gs)
            await start_turn(bot, gs, game_id, "p1")
            return
        gs["phase"] = "mulligan_p2"
        save_game(game_id, gs)

        opp_id = gs["players"]["p2"]["id"]
        await bot.send_message(chat_id, "✅ Готов! Ждём противника...")
        await bot.send_message(
            opp_id,
            f"⚔️ Муллиган!\nЗамените до 2 карт из руки.\n"
            f"Нажмите карту чтобы заменить, затем *«Готов»*.",
            reply_markup=kb_mulligan(gs["hand"]["p2"]),
            parse_mode="Markdown"
        )

    elif gs["phase"] == "mulligan_p2" and side == "p2":
        gs["phase"] = "play"
        gs["turn"] = "p1"
        save_game(game_id, gs)

        await bot.send_message(chat_id, "✅ Готов! Игра начинается!")
        await start_turn(bot, gs, game_id, "p1")

    elif gs.get("is_ai_game") and gs["phase"] == "mulligan_p1" and side == "p1":
        gs["phase"] = "play"
        gs["turn"] = "p1"
        save_game(game_id, gs)
        await bot.send_message(chat_id, "✅ Готов! Игра начинается!")
        await start_turn(bot, gs, game_id, "p1")


async def start_turn(bot: Bot, gs: dict, game_id: str, side: str):
    """Send or edit board message for both players."""
    opp = get_opponent(side)
    player_id = gs["players"][side]["id"]
    opp_id = gs["players"][opp]["id"]

    board_pov = render_board(gs, side)
    board_opp = render_board(gs, opp)

    # --- Active player ---
    text_active = f"```\n{board_pov}\n```\n\n🃏 Выберите карту или спасуйте:"
    msg_id_active = gs.get("msg_id", {}).get(side)
    if msg_id_active:
        try:
            await bot.edit_message_text(
                chat_id=player_id,
                message_id=msg_id_active,
                text=text_active,
                reply_markup=kb_hand(gs, side),
                parse_mode="Markdown"
            )
        except Exception:
            msg = await bot.send_message(
                player_id, text_active,
                reply_markup=kb_hand(gs, side),
                parse_mode="Markdown"
            )
            gs.setdefault("msg_id", {})[side] = msg.message_id
    else:
        msg = await bot.send_message(
            player_id, text_active,
            reply_markup=kb_hand(gs, side),
            parse_mode="Markdown"
        )
        gs.setdefault("msg_id", {})[side] = msg.message_id

    # --- Opponent ---
    if opp_id != AI_USER_ID:
        text_opp = f"```\n{board_opp}\n```"
        msg_id_opp = gs.get("msg_id", {}).get(opp)
        if msg_id_opp:
            try:
                await bot.edit_message_text(
                    chat_id=opp_id,
                    message_id=msg_id_opp,
                    text=text_opp,
                    parse_mode="Markdown"
                )
            except Exception:
                msg = await bot.send_message(
                    opp_id, text_opp,
                    parse_mode="Markdown"
                )
                gs.setdefault("msg_id", {})[opp] = msg.message_id
        else:
            msg = await bot.send_message(
                opp_id, text_opp,
                parse_mode="Markdown"
            )
            gs.setdefault("msg_id", {})[opp] = msg.message_id

    save_game(game_id, gs)


async def handle_card_select(bot: Bot, chat_id: int, user_id: int,
                             card_uid: str, game_id: str, data: dict):
    gs = get_game(game_id)
    if not gs:
        await bot.send_message(chat_id, "❌ Игра не найдена.")
        return

    side = get_side_for_user(gs, user_id)
    if not side or gs["turn"] != side:
        await bot.send_message(chat_id, "⏳ Сейчас не ваш ход.")
        return

    if gs["passed"][side]:
        await bot.send_message(chat_id, "✋ Вы уже спасовали.")
        return

    card = next((c for c in gs["hand"][side] if c["uid"] == card_uid), None)
    if not card:
        await bot.send_message(chat_id, "❌ Карта не найдена.")
        return

    gs["selected_card_uid"][side] = card_uid
    save_game(game_id, gs)

    ctype = card["type"]
    if ctype in ("normal", "hero", "spy", "horn", "weather", "decoy"):
        msg = await bot.send_message(
            chat_id,
            f"Выбрана: {card['emoji']} *{card['name']}*\n_{card.get('tip','')}_\n\nКуда поставить?",
            reply_markup=kb_row_select(card_uid, card),
            parse_mode="Markdown"
        )
        gs.setdefault("tmp_msg_id", {})[side] = msg.message_id
        save_game(game_id, gs)
    else:
        msg = await bot.send_message(chat_id, f"Выбрана карта: {card['name']}")
        gs.setdefault("tmp_msg_id", {})[side] = msg.message_id
        save_game(game_id, gs)


async def handle_place_card(bot: Bot, chat_id: int, user_id: int,
                            card_uid: str, row: str, game_id: str, data: dict):
    gs = get_game(game_id)
    if not gs:
        return

    side = get_side_for_user(gs, user_id)
    if not side or gs["turn"] != side:
        await bot.send_message(chat_id, "⏳ Сейчас не ваш ход.")
        return

    # Удаляем уточняющее сообщение
    tmp_id = gs.get("tmp_msg_id", {}).get(side)
    if tmp_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=tmp_id)
        except Exception:
            pass
        gs.setdefault("tmp_msg_id", {})[side] = None

    gdata = load_data()
    ok, msg = apply_card(gs, side, card_uid, row, gdata)
    if not ok:
        await bot.send_message(chat_id, f"❌ {msg}")
        return

    add_log(gs, f"{gs['players'][side]['name']}: {msg}")

    # Check if medic triggered
    if gs["awaiting_medic"][side]:
        grave = [c for c in gs["graveyard"][side]
                 if c["type"] not in ("weather", "horn", "decoy")]
        if grave:
            save_game(game_id, gs)
            await bot.send_message(
                chat_id,
                f"⚕️ Медик! Выберите карту для воскрешения из отбоя:",
                reply_markup=kb_medic(grave)
            )
            return

    gs["awaiting_medic"][side] = False

    # Switch turn
    opp = get_opponent(side)
    if gs["passed"][opp]:
        # Opponent already passed, keep same side's turn
        pass
    else:
        gs["turn"] = opp

    save_game(game_id, gs)

    # Check round end
    if check_round_end(gs):
        await end_round(bot, gs, game_id, gdata)
        return

    # Continue game
    gs = get_game(game_id)  # перечитываем свежий gs из Redis
    next_side = gs["turn"]
    if gs.get("is_ai_game") and next_side == "p2":
        await do_ai_turn(bot, gs, game_id, load_data())
    else:
        await start_turn(bot, gs, game_id, next_side)


async def handle_pass(bot: Bot, chat_id: int, user_id: int,
                      game_id: str, data: dict):
    gs = get_game(game_id)
    if not gs:
        return

    side = get_side_for_user(gs, user_id)
    if not side or gs["turn"] != side:
        await bot.send_message(chat_id, "⏳ Сейчас не ваш ход.")
        return

    if gs["passed"][side]:
        await bot.send_message(chat_id, "✋ Вы уже спасовали.")
        return

    gs["passed"][side] = True
    opp = get_opponent(side)
    opp_id = gs["players"][opp]["id"]
    p_name = gs["players"][side]["name"]

    add_log(gs, f"✋ {p_name} спасовал(а)")

    if check_round_end(gs):
        save_game(game_id, gs)
        await end_round(bot, gs, game_id, data)
        return

    gs["turn"] = opp
    save_game(game_id, gs)

    if gs.get("is_ai_game") and opp == "p2":
        await bot.send_message(chat_id, "✋ Вы спасовали. AI ходит...")
        await do_ai_turn(bot, gs, game_id, data)
    else:
        await bot.send_message(chat_id, "✋ Вы спасовали. Ждём противника...")
        await bot.send_message(opp_id,
                               f"✋ {p_name} спасовал(а). Ваш ход — можете продолжить или тоже спасовать.")
        await start_turn(bot, gs, game_id, opp)


async def handle_medic(bot: Bot, chat_id: int, user_id: int,
                       card_uid: str, game_id: str):
    gs = get_game(game_id)
    if not gs:
        return

    side = get_side_for_user(gs, user_id)
    if not side or not gs["awaiting_medic"].get(side):
        return

    if card_uid == "skip":
        gs["awaiting_medic"][side] = False
    else:
        grave = gs["graveyard"][side]
        card = next((c for c in grave if c["uid"] == card_uid), None)
        if card:
            gs["graveyard"][side] = [c for c in grave if c["uid"] != card_uid]
            row = card.get("row", "melee")
            if row not in ROWS:
                row = "melee"
            gs["rows"][side][row].append(card)
            gs["awaiting_medic"][side] = False
            await bot.send_message(
                chat_id,
                f"⚕️ Воскрешён: {card['emoji']} {card['name']} ({card['val']}) → {ROW_EMOJI[row]}"
            )

    # Switch turn
    opp = get_opponent(side)
    if not gs["passed"][opp]:
        gs["turn"] = opp
    save_game(game_id, gs)

    if check_round_end(gs):
        await end_round(bot, gs, game_id, load_data())
        return

    await start_turn(bot, gs, game_id, gs["turn"])


async def do_ai_turn(bot: Bot, gs: dict, game_id: str, data: dict):
    """AI делает ход автоматически."""
    side = "p2"
    difficulty = gs.get("ai_difficulty", "medium")

    # пауза убрана для совместимости с serverless

    # Пасовать?
    if not gs["passed"][side] and ai_should_pass(gs, side, difficulty):
        gs["passed"][side] = True
        add_log(gs, f"✋ {gs['players'][side]['name']} спасовал(а)")
        save_game(game_id, gs)

        p1_id = gs["players"]["p1"]["id"]
        await bot.send_message(
            p1_id,
            f"✋ *{gs['players']['p2']['name']}* спасовал(а)!\n"
            f"Ваш ход — продолжите или тоже спасуйте.",
            parse_mode="Markdown"
        )

        if check_round_end(gs):
            await end_round(bot, gs, game_id, data)
            return

        gs["turn"] = "p1"
        save_game(game_id, gs)
        await start_turn(bot, gs, game_id, "p1")
        return

    # Выбрать карту
    card_uid, row = ai_choose_card(gs, side, difficulty)
    if not card_uid:
        gs["passed"][side] = True
        save_game(game_id, gs)
        if check_round_end(gs):
            await end_round(bot, gs, game_id, data)
            return
        gs["turn"] = "p1"
        save_game(game_id, gs)
        await start_turn(bot, gs, game_id, "p1")
        return

    ok, msg = apply_card(gs, side, card_uid, row, data)
    if ok:
        add_log(gs, f"{gs['players'][side]['name']}: {msg}")

    # Медик AI
    if gs["awaiting_medic"].get(side):
        revive_uid = ai_pick_medic(gs, side)
        if revive_uid:
            grave = gs["graveyard"][side]
            card = next((c for c in grave if c["uid"] == revive_uid), None)
            if card:
                gs["graveyard"][side] = [
                    c for c in grave if c["uid"] != revive_uid
                ]
                r = card.get("row", "melee")
                if r not in ROWS:
                    r = "melee"
                gs["rows"][side][r].append(card)
        gs["awaiting_medic"][side] = False

    if not gs["passed"]["p1"]:
        gs["turn"] = "p1"
    save_game(game_id, gs)

    if check_round_end(gs):
        await end_round(bot, gs, game_id, data)
        return

    await start_turn(bot, gs, game_id, "p1")
    
async def end_round(bot: Bot, gs: dict, game_id: str, data: dict):
    result_msg = resolve_round(gs, data)
    save_game(game_id, gs)

    p1_id = gs["players"]["p1"]["id"]
    p2_id = gs["players"]["p2"]["id"]

    if gs["phase"] == "game_over":
        w1, w2 = gs["wins"]["p1"], gs["wins"]["p2"]
        p1_name = gs["players"]["p1"]["name"]
        p2_name = gs["players"]["p2"]["name"]
        if w1 > w2:
            final = f"🏆 *{p1_name}* побеждает в игре! ({w1}:{w2})"
        elif w2 > w1:
            final = f"🏆 *{p2_name}* побеждает в игре! ({w2}:{w1})"
        else:
            final = f"🤝 Ничья! ({w1}:{w2})"

        for pid in (p1_id, p2_id):
            await bot.send_message(
                pid,
                f"{result_msg}\n\n{final}\n\n/start — начать новую игру",
                parse_mode="Markdown"
            )
        redis_del(game_key(game_id))
    else:
        # New round: send mulligan
        for pid in (p1_id, p2_id):
            await bot.send_message(
                pid,
                f"{result_msg}\n\n⚔️ *Раунд {gs['round']} начинается!*\nМуллиган: замените до 2 карт.",
                parse_mode="Markdown"
            )

        side_now = "p1" if gs["phase"] == "mulligan_p1" else "p2"
        opp_side = get_opponent(side_now)
        pid_now = gs["players"][side_now]["id"]
        pid_opp = gs["players"][opp_side]["id"]

        await bot.send_message(
            pid_now,
            "Замените карты:",
            reply_markup=kb_mulligan(gs["hand"][side_now])
        )
        await bot.send_message(pid_opp, "⏳ Ждём противника (муллиган)...")


async def handle_surrender(bot: Bot, chat_id: int, user_id: int, game_id: str):
    """Игрок сдаётся."""
    gs = get_game(game_id)
    if not gs:
        return

    side = get_side_for_user(gs, user_id)
    if not side:
        return

    opp = get_opponent(side)
    p_name = gs["players"][side]["name"]
    opp_name = gs["players"][opp]["name"]
    opp_id = gs["players"][opp]["id"]

    redis_del(game_key(game_id))
    redis_del(user_game_key(user_id))

    await bot.send_message(
        chat_id,
        f"Вы сдались. {opp_name} побеждает! /start - новая игра",
    )
    if opp_id != AI_USER_ID:
        await bot.send_message(
            opp_id,
            f"{p_name} сдался! Вы победили! /start - новая игра",


        )
        redis_del(user_game_key(opp_id))


async def handle_hand(bot: Bot, chat_id: int, user_id: int):
    """Показывает карты в руке с описанием."""
    game_id = get_user_game_id(user_id)
    if not game_id:
        await bot.send_message(chat_id, "Нет активной игры. /start чтобы начать.")
        return
    gs = get_game(game_id)
    if not gs:
        await bot.send_message(chat_id, "Игра не найдена. /start")
        return

    side = get_side_for_user(gs, user_id)
    if not side:
        return

    hand = gs["hand"][side]
    if not hand:
        await bot.send_message(chat_id, "🃏 Рука пуста.")
        return

    lines = ["🃏 *Карты в руке:*\n"]
    for i, card in enumerate(hand, 1):
        type_icon = {
            "hero":    "👑 Герой",
            "spy":     "👁 Шпион",
            "weather": "🌪 Погода",
            "horn":    "📯 Рог",
            "decoy":   "🎭 Чучело",
            "normal":  "⚔️ Отряд",
        }.get(card["type"], "")

        row_label = {
            "melee":  "Рукопашный ⚔️",
            "ranged": "Дальнобойный 🏹",
            "siege":  "Осадный 💣",
            "any":    "Любой ряд",
        }.get(card.get("row", ""), "")

        val_str = f"Сила: *{card['val']}*  " if card["val"] else ""
        tip = f"_{card['tip']}_" if card.get("tip") else ""

        lines.append(
            f"{i}. {card['emoji']} *{card['name']}*\n"
            f"   {type_icon}  {row_label}\n"
            f"   {val_str}{tip}\n"
        )

    await bot.send_message(
        chat_id,
        "\n".join(lines),
        parse_mode="Markdown"
    )


async def handle_game_view(bot: Bot, chat_id: int, user_id: int):
    game_id = get_user_game_id(user_id)
    if not game_id:
        await bot.send_message(chat_id, "Нет активной игры. /start чтобы начать.")
        return
    gs = get_game(game_id)
    if not gs:
        await bot.send_message(chat_id, "Игра завершена или не найдена. /start")
        return

    side = get_side_for_user(gs, user_id)
    if not side:
        return

    board = render_board(gs, side)
    await bot.send_message(
        chat_id,
        f"```\n{board}\n```",
        reply_markup=kb_hand(gs, side) if gs["turn"] == side else None,
        parse_mode="Markdown"
    )


async def handle_help(bot: Bot, chat_id: int):
    text = (
        "📋 *Команды бота:*\n\n"
        "/start — главное меню\n"
        "/game — посмотреть текущее поле\n"
        "/hand — карты в руке с описанием\n"
        "/rules — правила игры\n"
        "/stats — твоя статистика\n"
        "/cancel — выйти из очереди поиска\n\n"
        "🎮 *Как играть:*\n\n"
        "1️⃣ /start → выбери режим игры\n"
        "2️⃣ Выбери фракцию и лидера\n"
        "3️⃣ Замени до 2 карт (муллиган)\n"
        "4️⃣ Нажми карту → выбери ряд\n"
        "5️⃣ Или нажми ✋ Пас\n"
        "6️⃣ Победи в 2 из 3 раундов!\n\n"
        "💡 *Подсказка:* нажми на карту чтобы "
        "увидеть её способность перед размещением."
    )
    await bot.send_message(chat_id, text,
                           reply_markup=kb_main_menu(),
                           parse_mode="Markdown")


async def handle_rules(bot: Bot, chat_id: int):
    text = (
        "📜 *Правила Гвинта*\n\n"
        "🏆 Победить нужно в *2 из 3 раундов*\n"
        "🃏 В начале раздаётся *10 карт*, можно заменить 2\n"
        "⚔️ 3 ряда: Рукопашный · Дальнобойный · Осадный\n"
        "👑 Герои — иммунитет к погоде и способностям\n"
        "👁 Шпион — играется к врагу, вы берёте 2 карты\n"
        "❄️ Погода — все обычные карты ряда = 1\n"
        "☀️ Ясная погода — снимает всю погоду\n"
        "📯 Командирский рог — удваивает ряд\n"
        "🎭 Чучело — верните карту с поля в руку\n"
        "⚕️ Медик — воскресите карту из отбоя\n"
        "🔗 Прочная связь — удвоение при двух одинаковых\n"
        "♪ Прилив сил — +1 всем картам в ряду\n"
        "💀 Казнь — уничтожает сильнейшую карту\n\n"
        "Нажмите карту в руке → выберите ряд для размещения."
    )
    await bot.send_message(chat_id, text,
                           reply_markup=kb_main_menu(),
                           parse_mode="Markdown")


async def handle_factions_info(bot: Bot, chat_id: int, data: dict):
    lines = ["🃏 *Фракции Гвинта:*\n"]
    for fkey, fval in data["factions"].items():
        leaders_str = ", ".join(l["name"] for l in fval["leaders"])
        lines.append(
            f"{fval['icon']} *{fval['name']}*\n"
            f"  _{fval['ability']}_\n"
            f"  Лидеры: {leaders_str}\n"
        )
    await bot.send_message(chat_id, "\n".join(lines),
                           reply_markup=kb_main_menu(),
                           parse_mode="Markdown")


# ─────────────────────────────────────────────
# MAIN UPDATE DISPATCHER
# ─────────────────────────────────────────────

async def process_update(update_data: dict):
    bot = Bot(token=BOT_TOKEN)
    data = load_data()
    update = Update.de_json(update_data, bot)

    # ── Message ──
    if update.message:
        msg = update.message
        user_id = msg.from_user.id
        chat_id = msg.chat_id
        user_name = msg.from_user.first_name or str(user_id)
        text = msg.text or ""

        # Store user's name for future reference
        redis_set(user_setup_key(user_id), {
            **(redis_get(user_setup_key(user_id)) or {}),
            "my_name": user_name
        }, ex=86400)

        if text.startswith("/start"):
            args = text.split(" ", 1)[1] if " " in text else ""
            await handle_start(bot, chat_id, user_id, user_name, args, data)

        elif text == "/game" or text == "/board":
            await handle_game_view(bot, chat_id, user_id)

        elif text == "/hand":
            await handle_hand(bot, chat_id, user_id)

        elif text == "/cancel":
            redis_del(queue_key())
            await bot.send_message(chat_id, "❌ Поиск отменён.")

        elif text == "/help":
            await handle_help(bot, chat_id)

        elif text == "/rules":
            await handle_rules(bot, chat_id)

        else:
            await bot.send_message(
                chat_id,
                "Используй /start для главного меню.",
                reply_markup=kb_main_menu()
            )

    # ── Callback Query ──
    elif update.callback_query:
        cq = update.callback_query
        user_id = cq.from_user.id
        chat_id = cq.message.chat_id
        user_name = cq.from_user.first_name or str(user_id)
        cbd = cq.data or ""

        await cq.answer()  # Remove loading spinner

        # Store name
        stored = redis_get(user_setup_key(user_id)) or {}
        stored["my_name"] = user_name
        redis_set(user_setup_key(user_id), stored, ex=86400)

        # ── Menu ──
        if cbd == "find_game":
            await handle_find_game(bot, chat_id, user_id, user_name, data)

        elif cbd == "vs_ai":
            msg = await bot.send_message(
                chat_id,
                "🤖 *Игра против компьютера*\n\nВыберите уровень сложности:",
                reply_markup=kb_difficulty(),
                parse_mode="Markdown"
            )
            setup = get_user_setup(user_id) or {}
            setup["last_msg_id"] = msg.message_id
            set_user_setup(user_id, setup)

        elif cbd.startswith("ai_diff:"):
            difficulty = cbd.split(":")[1]
            diff_name = AI_NAME_BY_DIFFICULTY.get(difficulty, "AI")
            setup = get_user_setup(user_id) or {}
            prev_msg_id = setup.get("last_msg_id")
            await delete_msg(bot, chat_id, prev_msg_id)
            setup["my_name"] = user_name
            setup["ai_difficulty"] = difficulty
            set_user_setup(user_id, setup)
            msg = await bot.send_message(
                chat_id,
                f"Противник: *{diff_name}*\n\nВыберите фракцию:",
                reply_markup=kb_faction_select(data),
                parse_mode="Markdown"
            )
            setup["last_msg_id"] = msg.message_id
            set_user_setup(user_id, setup)
        elif cbd == "rules":
            await handle_rules(bot, chat_id)

        elif cbd == "factions":
            await handle_factions_info(bot, chat_id, data)

        # ── Faction select ──
        elif cbd.startswith("faction:"):
            faction_key = cbd.split(":")[1]
            setup = get_user_setup(user_id) or {}
            prev_msg_id = setup.get("last_msg_id")
            await handle_faction_pick(bot, chat_id, user_id, faction_key, data, prev_msg_id)

        # ── Leader select ──
        elif cbd.startswith("leader:"):
            parts = cbd.split(":")
            faction_key = parts[1]
            leader_idx = int(parts[2])
            setup2 = get_user_setup(user_id) or {}
            prev_msg_id2 = setup2.get("last_msg_id")
            await handle_leader_pick(bot, chat_id, user_id, user_name,
                                     faction_key, leader_idx, data, prev_msg_id2)

        else:
            # All following require an active game
            game_id = get_user_game_id(user_id)
            if not game_id:
                await bot.send_message(chat_id, "Нет активной игры. /start")
                return

            # ── Mulligan ──
            if cbd.startswith("mulligan:"):
                card_uid = cbd.split(":", 1)[1]
                gs_debug = get_game(game_id)
                print(f"DEBUG mulligan: phase={gs_debug and gs_debug.get('phase')}, side={get_side_for_user(gs_debug, user_id) if gs_debug else None}")
                await handle_mulligan(bot, chat_id, user_id, card_uid, game_id, data)

            elif cbd == "mulligan_done":
                await handle_mulligan_done(bot, chat_id, user_id, game_id, data)

            # ── Card select ──
            elif cbd.startswith("card:"):
                card_uid = cbd.split(":", 1)[1]
                await handle_card_select(bot, chat_id, user_id, card_uid, game_id, data)

            elif cbd == "cancel_select":
                gs = get_game(game_id)
                if gs:
                    side = get_side_for_user(gs, user_id)
                    if side:
                        gs["selected_card_uid"][side] = None
                        tmp_id = gs.get("tmp_msg_id", {}).get(side)
                        await delete_msg(bot, chat_id, tmp_id)
                        gs.setdefault("tmp_msg_id", {})[side] = None
                        save_game(game_id, gs)
                gs2 = get_game(game_id)
                if gs2:
                    await start_turn(bot, gs2, game_id, side)

            # ── Place card ──
            elif cbd.startswith("place:"):
                parts = cbd.split(":")
                card_uid = parts[1]
                row = parts[2]
                await handle_place_card(bot, chat_id, user_id,
                                        card_uid, row, game_id, data)

            # ── Pass ──
            elif cbd == "pass_round":
                await handle_pass(bot, chat_id, user_id, game_id, data)

            elif cbd == "surrender":
                await handle_surrender(bot, chat_id, user_id, game_id)

            # ── Medic ──
            elif cbd.startswith("medic:"):
                card_uid = cbd.split(":", 1)[1]
                await handle_medic(bot, chat_id, user_id, card_uid, game_id)

            elif cbd == "medic_skip":
                await handle_medic(bot, chat_id, user_id, "skip", game_id)

            else:
                await bot.send_message(chat_id, "Неизвестная команда.")


# ─────────────────────────────────────────────
# FLASK ROUTES
# ─────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok"})


@app.route("/webhook", methods=["GET"])
def webhook_ping():
    return jsonify({"status": "ok"})


@app.route("/webhook", methods=["POST"])
def webhook():
    # Verify secret header
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
        return jsonify({"error": "unauthorized"}), 403

    update_data = request.get_json(force=True)
    if not update_data:
        return jsonify({"error": "no data"}), 400

    try:
        asyncio.run(process_update(update_data))
    except Exception as e:
        print(f"Error processing update: {e}")

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
