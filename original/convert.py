"""Convert the DATA statements in Anita Straker's MERLIN2 (BBC BASIC) into
data/world.json. Run from this directory after detok.py:  python3 convert.py

Original format (see PROCroom, PROCmove, PROCstart in MERLIN2.bas):
  Room r lives at line 19000 + r*10 (continuations follow). Fields:
    description, then four exits read in the order SOUTH, WEST, NORTH, EAST.
  Exit value 0 or >99: plain exit to room value/100 (0 = no exit).
  Exit value 1..99: guarded exit to room `value`, followed by
    item, useMessage, blockedFatal("E"), blockedMessage, passFatal("E"), passMessage
  Items: 20 names at 18000, start rooms at 18010. A value <100 means
    value+1 or value+2 at random, otherwise the fixed room value/100.
  Score: 3 per item on the grassy bank, +8 for items 9-12 and 20 (treasures).
"""
import json, re

ROOM_KEYS = {
    1: "clue-spell", 2: "wizards-kitchen", 3: "coach-house", 4: "small-room",
    5: "grand-hall", 6: "dungeon", 7: "merlins-lair", 8: "courtyard",
    9: "moat", 10: "forest-edge", 11: "river-south-bank", 12: "beautiful-chamber",
    13: "dark-tunnels", 14: "clue-silver", 15: "dragon-cave", 16: "cave-entrance",
    17: "mountain-path", 18: "evergreen-glade", 19: "deep-river", 20: "grassy-bank",
    21: "old-stone-wall", 22: "old-wall", 23: "rusty-gate", 24: "yellow-flowers",
    25: "mossy-steps", 26: "tower", 27: "forest-witches", 28: "forest-crossroads",
    29: "charcoal-hut", 30: "mountain", 31: "maze", 32: "damp-tunnels",
    33: "trolls", 34: "treasure-room", 35: "giant", 36: "oak-door",
    37: "clue-mask", 38: "clue-ring", 39: "clue-plank", 40: "clue-rope",
}
COLOURS = {129: "red", 130: "green", 131: "yellow", 132: "blue",
           133: "magenta", 134: "cyan", 135: "white"}
READ_ORDER = ["south", "west", "north", "east"]
TREASURES = {9, 10, 11, 12, 20}

lines = {}
for line in open("MERLIN2.bas"):
    m = re.match(r"\s*(\d+)\s?DATA\s?(.*)$", line.rstrip("\n"))
    if m:
        lines[int(m.group(1))] = m.group(2)

def split_data(s):
    out, cur, q, i = [], "", False, 0
    while i < len(s):
        c = s[i]
        if c == '"':
            q = not q
        elif c == "," and not q:
            out.append(cur); cur = ""
        else:
            cur += c
        i += 1
    out.append(cur)
    return [x if x.startswith(" ") and x.strip() == "" else x.strip() if not x.startswith('"') else x for x in out]

def teletext(s):
    # Keep teletext colour control codes inline: {129} -> {red}
    return re.sub(r"\{(\d+)\}", lambda m: "{" + COLOURS[int(m.group(1))] + "}", s)

def stream_from(n):
    for ln in sorted(k for k in lines if k >= n):
        for v in split_data(lines[ln]):
            yield v

world_rooms = {}
for r, key in ROOM_KEYS.items():
    vals = stream_from(19000 + r * 10)
    desc = teletext(next(vals))
    exits = {}
    for d in READ_ORDER:
        v = int(next(vals))
        if v == 0 or v > 99:
            if v:
                exits[d] = {"to": ROOM_KEYS[v // 100]}
            continue
        item, use_msg, block_fatal, blocked, pass_fatal, pass_msg = (next(vals) for _ in range(6))
        ex = {"to": ROOM_KEYS.get(v)}
        if pass_msg: ex["message"] = teletext(pass_msg)
        if pass_fatal == "E": ex["fatal"] = True
        if int(item):
            ex["obstacle"] = {"needs": int(item), "useMessage": teletext(use_msg),
                              "blocked": teletext(blocked)}
            if block_fatal == "E": ex["obstacle"]["fatal"] = True
        exits[d] = ex
    world_rooms[key] = {"description": desc, "exits": exits}

names = split_data(lines[18000])
starts = [int(x) for x in split_data(lines[18010])]
items, ids = {}, {}
for i, (full, w) in enumerate(zip(names, starts), start=1):
    article, name = full.split(" ", 1)
    ids[i] = name
    items[name] = {
        "name": name, "article": article,
        "score": 11 if i in TREASURES else 3,
        "startsIn": [ROOM_KEYS[w // 100]] if w >= 100 else [ROOM_KEYS[w + 1], ROOM_KEYS[w + 2]],
    }

for room in world_rooms.values():
    for ex in room["exits"].values():
        if "obstacle" in ex:
            ex["obstacle"]["needs"] = ids[ex["obstacle"]["needs"]]

# "You are lost" clue rooms: every exit goes to the same room, so the player is
# stuck. The remake ends the game there instead, so they get no exits.
for room in world_rooms.values():
    targets = {ex.get("to") for ex in room["exits"].values()}
    if len(room["exits"]) == 4 and len(targets) == 1 and not any("obstacle" in ex for ex in room["exits"].values()):
        room["exits"] = {}
        room["deadEnd"] = True

bank = world_rooms["grassy-bank"]
bank["firstVisitDescription"] = bank["description"]
bank["description"] = "You are standing at a cross-roads. On a{green}grassy{green}bank{white}a figure lies sleeping."
# Original quirk: with more than 12 objects on the bank the text shortens (to fit the screen)
bank["crowdedDescription"] = "You are by a{green}grassy{green}bank."

world = {
    "title": "Merlin's Castle",
    "author": "Anita Straker",
    "year": 1983,
    "startRoom": "grassy-bank",
    "homeRoom": "grassy-bank",
    "carryLimit": 5,
    "rooms": world_rooms,
    "items": items,
}
json.dump(world, open("../data/world.json", "w"), indent=2, ensure_ascii=False)
print(len(world_rooms), "rooms,", len(items), "items, best score",
      sum(i["score"] for i in items.values()))
