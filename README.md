# Scores

A free leaderboard backend service for indie games. Submit and retrieve high scores via REST API, with a Django-based dashboard for game developers.

Open source, self-host if you like, or start now with the free hosted version at
https://scores.fallday.ca. My intention is that this will be free for small
games, and for games that grow to a significant volume (tens of thousands of players
per day), either suggest self-hosting, or have some paid plan to cover costs.

## Features

- REST API for score submission and retrieval
- Dashboard for managing games and leaderboards
- Per-leaderboard API tokens
- Automatic score expiration (configurable, default 7 days)
- Public leaderboard pages

For self-hosting documentation, see the [devops](devops/README.md) folder.

## What about Cheating

There's nothing here to address cheating yet. Scores expiring will make any damage
ephemeral, but if users figure out the API they can post bogus scores. This is a
difficult problem, and impossible to solve completely but I may tackle it in
the future.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Set up demo mini-games (optional)
python manage.py setup_demo_games

# Start development server
python manage.py runserver
```

## Demo Mini-Games

The site includes three playable mini-games at `/play/` that demonstrate the leaderboard functionality:

- **Reaction Timer** - Click when the screen turns green
- **Memory Sequence** - Remember and repeat color patterns
- **Target Shooting** - Click targets within 10 seconds
- **Whack-a-Mole** - Teach those moles a lesson

Try them now, and submit your high scores, at https://scores.fallday.ca/play

Run `python manage.py setup_demo_games` to create the system user and demo leaderboards. This command is idempotent and can be run multiple times safely.

## API Usage

The API documentation is built into the dashboard; in a nutshell:

```bash
# Without player_id: creates a new entry each time
curl -X POST http://scores.fallday.ca/api/v1/scores/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token-from-the-dashboard" \
  -d '{"player_name": "bob", "score": 42000}'

# Submit with player_id (one score per player - updates if exists)
curl -X POST http://scores.fallday.ca/api/v1/scores/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token-from-the-dashboard" \
  -d '{"player_name": "bob", "player_id": "unique-player-identifier", "score": 42000}'
```

### Player ID

The optional `player_id` field enables one-score-per-player:

- **Without `player_id`**: Every submission creates a new score entry
- **With `player_id`**: If a score exists for that player on the leaderboard, it's updated only if the new score is better; otherwise the existing score is kept

"Better" depends on the leaderboard's sort order: higher is better for `desc`, lower is better for `asc`.

Use any unique identifier for your players: a device UUID, Steam ID, Game Centre ID, or your own user ID. The `player_id` is never exposed in API responses to prevent players from overwriting others' scores.

### Response

The API response includes an `is_high_score` boolean indicating whether the submitted score was recorded:

```json
{
  "success": true,
  "message": "Score submitted successfully",
  "is_high_score": true
}
```

- `is_high_score: true` - New score created or existing score was beaten
- `is_high_score: false` - Existing score was better and kept (only when using `player_id`)

## Tech Stack

- Django + Django REST Framework
- PostgreSQL
- Tailwind CSS, htmx, Alpine.js
