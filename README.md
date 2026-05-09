# NBA Hue Sync

Sync your Philips Hue lights to a live NBA game. Lights pulse your team's color on every basket — once for a 2-pointer, twice for a 3-pointer. Leading team's color holds between scores. Neutral warm light during quarter breaks and halftime.

## Features
- **Live team colors** pulled from ESPN on startup — no hardcoding
- **2pt = 1 flash, 3pt = 2 flashes** in the scoring team's color
- **Leading team color** held between scores
- **Quarter breaks & halftime** → neutral warm amber
- **Auto-stops** when game ends and fades back to warm
- Works for any NBA game

## Requirements

- [openhue CLI](https://www.openhue.io/cli) — `brew install openhue-cli/homebrew-tap/openhue`
- Python 3.9+
- Philips Hue bridge + lights on your local network

## Setup

1. Set up openhue: `openhue setup`
2. Verify lights work: `openhue get lights`

## Usage

```bash
# Default game (edit GAME_ID in script or pass as argument)
python3 hue_game_sync.py

# Specific game by NBA CDN game ID
python3 hue_game_sync.py 0042500213
```

### Finding a Game ID

Game IDs follow the format `004{SEASON}00{ROUND}{SERIES}{GAME}`. You can find today's game IDs from the NBA CDN scoreboard:

```bash
curl -s "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json" | \
  python3 -c "
import json,sys
for g in json.load(sys.stdin)['scoreboard']['games']:
    print(g['awayTeam']['teamTricode'],'@',g['homeTeam']['teamTricode'],'|',g['gameId'])
"
```

## Configuration

Edit the top of `hue_game_sync.py`:

| Variable | Default | Description |
|---|---|---|
| `LIGHTS` | `["Corner", "Bed", "Desk"]` | Your light names from `openhue get lights` |
| `GAME_ID` | `0042500213` | NBA CDN game ID |
| `POLL_INTERVAL` | `5` | Seconds between score checks |

## How It Works

Polls the [NBA CDN live boxscore](https://cdn.nba.com/static/json/liveData/boxscore/) every 5 seconds. On score change, detects delta (2pt or 3pt) and fires the corresponding pulse pattern. Team colors fetched from ESPN's public API on startup.
