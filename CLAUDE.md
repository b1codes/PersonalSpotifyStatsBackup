# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

AWS Lambda function that runs monthly (via EventBridge) to fetch your top 50 Spotify tracks and artists, derive top albums from the track list, and persist everything to a MySQL database. The Spotify refresh token is stored and rotated in the database's `config` table — there are no long-lived secrets in env vars.

## Key Commands

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Generate initial Spotify refresh token (one-time setup, opens browser)
python SpotifyRefreshTokenGenerator.py

# Run the Lambda handler locally (requires .env with DB + Spotify credentials)
python -c "import lambda_function; lambda_function.lambda_handler({}, {})"
```

### Deployment (Terraform — primary method)

```bash
cd terraform/

# First-time: import existing Lambda into Terraform state
terraform import aws_lambda_function.spotify_backup PersonalSpotifyStatsBackup

# Deploy code and infrastructure changes
terraform plan
terraform apply
```

## Architecture

**Execution flow** (`lambda_function.py:lambda_handler`):
1. `DatabaseManager` — connects to MySQL, ensures `config` table exists
2. `SpotifyAPIManager(database_manager)` — reads refresh token from DB, exchanges it for an access token; if Spotify returns a new refresh token it is written back to the DB immediately
3. Fetch top 50 tracks + artists (`short_term` = last ~4 weeks)
4. Construct `MonthlyTopTracks`, `MonthlyTopArtists`, `MonthlyTopAlbums` snapshots (dated to the previous month)
5. Batch-insert into `tracks`, `artists`, `albums` MySQL tables with `ON DUPLICATE KEY UPDATE`

**Top albums** (`Types/MonthlyTopAlbums.py`) are derived — not fetched from Spotify. Albums are ranked by how many of their tracks appear in the top-50 list; only albums with ≥ 2 tracks are included.

**Manager responsibilities:**
- `Managers/DatabaseManager.py` — MySQL connection, CRUD for the `config` table (refresh token), and batch inserts for the three stat tables
- `Managers/SpotifyAPIManager.py` — Spotify OAuth (Authorization Code + Refresh Token flows), `get_top_tracks()`, `get_top_artists()`

**Types** (`Types/`) are plain dataclasses: `Track`, `Artist`, `Album`, `Image`, `MonthlyTopTracks`, `MonthlyTopArtists`, `MonthlyTopAlbums`.

## Environment Variables

Copy `sample.env` to `.env` for local development. Lambda reads these via Terraform-managed environment variables.

| Variable | Purpose |
|---|---|
| `CLIENT_ID` / `CLIENT_SECRET` | Spotify app credentials |
| `REDIRECT_URI` | Must match Spotify app settings (e.g. `http://localhost:8888/callback`) |
| `DB_HOST`, `DB_PORT`, `DB_USERNAME`, `DB_PASSWORD`, `DB_NAME` | MySQL connection |

## Database Schema Notes

The DB tables (`tracks`, `artists`, `albums`) use `(month, year, standing)` as a composite key. `artist_ids` and `images` are stored as JSON strings. The `config` table stores the Spotify refresh token under key `spotify_refresh_token`.

Initial token seeding:
```sql
INSERT INTO config (config_key, config_value)
VALUES ('spotify_refresh_token', 'YOUR_REFRESH_TOKEN');
```

## Terraform

All infrastructure is defined in `terraform/`. `terraform.tfvars` is gitignored — fill it from `variables.tf`. The existing VPC, subnets, security groups, and RDS instance are **not** managed by Terraform; they are referenced as input variables only.
