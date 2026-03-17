# MySubs

MySubs is a local-first subscription tracker built with Flask, Jinja templates, and SQLite.
It is designed to be easy to clone, run, and self-host without requiring a managed backend or cloud database.

## Why this version is local-first

- Your subscription data stays in your own SQLite database file.
- No login flow or hosted API is required.
- Anyone can clone the repo and start using it in a few minutes.
- The architecture stays simple enough to evolve later into a hosted version if needed.

## Features

- Track service name, plan name, billing cycle, price, currency, and next billing date
- See monthly cost in TWD plus a USD estimate
- Highlight what is due this month and what is billing next
- Edit and delete subscriptions from a single dashboard

## Stack

- Python 3.14+
- Flask
- SQLite
- Jinja templates

## Getting started

1. Install dependencies:

```bash
uv sync
```

2. Initialize the database:

```bash
uv run python init_db.py
```

3. Start the app:

```bash
uv run python main.py
```

4. Open `http://127.0.0.1:5000`

## Configuration

By default, the app stores data in `mysubs.db` at the project root.

You can override the database path with `MYSUBS_DB_PATH`:

```bash
MYSUBS_DB_PATH=./data/mysubs.db uv run python init_db.py
MYSUBS_DB_PATH=./data/mysubs.db uv run python main.py
```

## Resetting the database

If you want to recreate the table from scratch, run:

```bash
uv run python init_db.py --reset
```

This will delete existing subscription data in that database.

## Project structure

```text
.
├── config.py
├── init_db.py
├── main.py
├── subscription.py
├── static/
│   └── styles.css
└── templates/
    ├── add.html
    ├── base.html
    ├── edit.html
    └── index.html
```

## Open-source direction

This repo is currently optimized for personal use and local deployment.
If the project later grows into a multi-user hosted app, the next steps would be:

- move from SQLite to Postgres
- add authentication
- associate subscriptions with users
- introduce migrations and deployment config

For now, the simpler local-first setup keeps the project easier to maintain and easier for contributors to adopt.
