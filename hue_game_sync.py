#!/usr/bin/env python3
"""
Syncs Hue bedroom lights to a live NBA game.
- Fetches team colors from ESPN dynamically on startup
- Pulses the scoring team's color on every basket
- Holds the leading team's color between scores
- Fades to warm amber when game ends

Usage: python3 hue_game_sync.py [GAME_ID]
Default: 0042500213 (NYK @ PHI Game 3)
"""

import subprocess, time, sys, json
from urllib.request import urlopen

LIGHTS = ["Corner", "Bed", "Desk"]
GAME_ID = sys.argv[1] if len(sys.argv) > 1 else "0042500213"
POLL_INTERVAL = 5

# ESPN abbreviation → NBA tricode (for color lookup)
ESPN_TO_NBA = {
    "NY": "NYK", "SA": "SAS", "GS": "GSW", "NO": "NOP",
    "PHI": "PHI", "MIN": "MIN", "BOS": "BOS", "MIA": "MIA",
    # most others match directly
}

# Fallback colors if ESPN fetch fails
FALLBACK_COLORS = {
    "NYK": "#F58426", "PHI": "#ED174C", "MIN": "#78BE20",
    "SAS": "#C4CED4", "LAL": "#FDB927", "BOS": "#007A33",
    "MIA": "#98002E", "GSW": "#FFC72C", "DEN": "#FEC524",
    "OKC": "#EF3B24", "DAL": "#00538C", "MIL": "#00471B",
}

def fetch_team_colors():
    """Pull live team colors from ESPN NBA scoreboard."""
    colors = {}
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
        with urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        for evt in data.get("events", []):
            for comp in evt.get("competitions", []):
                for team in comp.get("competitors", []):
                    t = team["team"]
                    espn_abbr = t["abbreviation"]
                    tricode = ESPN_TO_NBA.get(espn_abbr, espn_abbr)
                    primary = "#" + t.get("color", "")
                    alt = "#" + t.get("alternateColor", "")
                    # pick the more vibrant/distinct color
                    colors[tricode] = {"primary": primary, "alt": alt}
        print(f"  ESPN colors loaded: {list(colors.keys())}")
    except Exception as e:
        print(f"  ESPN color fetch failed: {e} — using fallbacks")
    return colors

def pick_color(tricode, team_colors):
    """Pick the best display color for a team."""
    tc = team_colors.get(tricode)
    if tc:
        # Prefer alternate if it's not near-black or near-white
        alt = tc["alt"].lstrip("#")
        try:
            r, g, b = int(alt[0:2],16), int(alt[2:4],16), int(alt[4:6],16)
            brightness = (r + g + b) / 3
            if 30 < brightness < 230:  # not too dark or washed out
                return tc["alt"]
        except Exception:
            pass
        return tc["primary"]
    return FALLBACK_COLORS.get(tricode, "#FFFFFF")

def set_lights(rgb=None, temp=None, brightness=70, transition="2s"):
    # All lights in one command = single bridge call = truly simultaneous
    cmd = ["openhue", "set", "light"] + LIGHTS + [
        "--on", "--brightness", str(brightness), "--transition-time", transition
    ]
    if rgb:
        cmd += ["--rgb", rgb]
    elif temp:
        cmd += ["--temperature", str(temp)]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def pulse(team, color, points, restore_rgb=None, restore_temp=None):
    """1 flash for 2pts, 2 flashes for 3pts."""
    flashes = 2 if points >= 3 else 1
    label = "🔥 THREE" if points >= 3 else "🏀 SCORE"
    print(f"  {label} — {team} (+{points})")
    for i in range(flashes):
        set_lights(rgb=color, brightness=100, transition="0s")
        time.sleep(0.3)
        if i < flashes - 1:
            set_lights(rgb=color, brightness=20, transition="0s")  # visible dip between flashes
            time.sleep(0.2)
    if restore_rgb:
        set_lights(rgb=restore_rgb, brightness=70, transition="1s")
    elif restore_temp:
        set_lights(temp=restore_temp, brightness=65, transition="1s")

def is_break(status_text):
    t = (status_text or "").upper()
    return any(x in t for x in ["END Q", "HALFTIME", "HALF TIME", "END OF"])

def get_score():
    url = f"https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{GAME_ID}.json"
    try:
        with urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        game = data["game"]
        home = game["homeTeam"]
        away = game["awayTeam"]
        return {
            "home_tri": home["teamTricode"],
            "away_tri": away["teamTricode"],
            "home_score": int(home["score"] or 0),
            "away_score": int(away["score"] or 0),
            "status": game.get("gameStatus", 1),
            "status_text": game.get("gameStatusText", ""),
            "period": game.get("period", 0),
        }
    except Exception as e:
        print(f"  Fetch error: {e}")
        return None

def main():
    print(f"Hue Game Sync — {GAME_ID}")

    # Fetch team colors on startup
    team_colors = fetch_team_colors()

    # Seed initial state
    s = get_score()
    if not s:
        print("Can't reach game data. Exiting.")
        return

    home_tri, away_tri = s["home_tri"], s["away_tri"]
    home_color = pick_color(home_tri, team_colors)
    away_color = pick_color(away_tri, team_colors)
    print(f"  {away_tri} ({away_color}) @ {home_tri} ({home_color})")
    print(f"  Score: {away_tri} {s['away_score']} — {home_tri} {s['home_score']} | Q{s['period']}\n")

    # Set initial lead color
    lead_color = {"rgb": None, "temp": 400}
    if s["home_score"] > s["away_score"]:
        lead_color = {"rgb": home_color, "temp": None}
        set_lights(rgb=home_color, brightness=70, transition="2s")
    elif s["away_score"] > s["home_score"]:
        lead_color = {"rgb": away_color, "temp": None}
        set_lights(rgb=away_color, brightness=70, transition="2s")
    else:
        set_lights(temp=400, brightness=65, transition="2s")

    prev_home, prev_away = s["home_score"], s["away_score"]
    last_leader = None
    in_break = False

    while True:
        time.sleep(POLL_INTERVAL)
        s = get_score()
        if not s:
            continue

        hs, as_ = s["home_score"], s["away_score"]
        on_break = is_break(s["status_text"])

        # Quarter break / halftime → neutral warm
        if on_break and not in_break:
            print(f"  ⏸ Break: {s['status_text']} — neutral")
            set_lights(temp=370, brightness=55, transition="3s")
            in_break = True
            prev_home, prev_away = hs, as_
            continue

        # Resuming from break → restore lead color
        if not on_break and in_break:
            print(f"  ▶ Resuming Q{s['period']}")
            in_break = False
            last_leader = None  # force re-apply lead color

        if not on_break:
            home_scored = hs > prev_home
            away_scored = as_ > prev_away

            if home_scored:
                pulse(home_tri, home_color, hs - prev_home, restore_rgb=lead_color["rgb"], restore_temp=lead_color["temp"])
            if away_scored:
                pulse(away_tri, away_color, as_ - prev_away, restore_rgb=lead_color["rgb"], restore_temp=lead_color["temp"])

            if home_scored or away_scored:
                time.sleep(1.2)

            # Update lead color
            if hs > as_:
                leader = home_tri
                new_color = {"rgb": home_color, "temp": None}
            elif as_ > hs:
                leader = away_tri
                new_color = {"rgb": away_color, "temp": None}
            else:
                leader = "TIE"
                new_color = {"rgb": None, "temp": 400}

            if leader != last_leader:
                print(f"  Lead → {leader}")
                if new_color["rgb"]:
                    set_lights(rgb=new_color["rgb"], brightness=70, transition="1.5s")
                else:
                    set_lights(temp=new_color["temp"], brightness=65, transition="1.5s")
                lead_color = new_color
                last_leader = leader

        prev_home, prev_away = hs, as_

        prev_home, prev_away = hs, as_
        print(f"  {away_tri} {as_} @ {home_tri} {hs} | Q{s['period']}")

        if s["status"] == 3:
            print("  Final — fading to warm.")
            set_lights(temp=380, brightness=55, transition="10s")
            break

    print("Done.")

if __name__ == "__main__":
    main()
