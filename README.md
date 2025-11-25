# Scores

A free leaderboard backend service for indie games. Submit and retrieve high scores via REST API, with a Django-based dashboard for game developers.

Open source, self-host if you like. My intention is that this will be free for small
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

Run `python manage.py setup_demo_games` to create the system user and demo leaderboards. This command is idempotent and can be run multiple times safely.

## API Usage

The API documentation is built into the dashboard; in a nutshell:

```bash
curl -X POST http://scores.fallday.ca/api/v1/scores/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-game-from-the-dashboard" \
  -d '{"player_name": "bob", "score": 42000}'
```

## Tech Stack

- Django + Django REST Framework
- PostgreSQL
- Tailwind CSS, htmx, Alpine.js
