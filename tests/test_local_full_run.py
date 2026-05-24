#!/usr/bin/env python3
"""
test_local_full_run.py — Run the full backup pipeline locally with safety controls.

Modes:
  --dry-run       Fetch from Spotify API and process data, but DO NOT write to the database.
                  (Default behavior — safe to run anytime)

  --skip-db       Same as --dry-run (alias for clarity).

  --live          Actually write to the database. Use with caution!

  --verbose       Enable DEBUG-level logging for every module.

Usage:
    python test_local_full_run.py                     # Dry run (default — no DB writes)
    python test_local_full_run.py --verbose            # Dry run with debug logging
    python test_local_full_run.py --live               # Full run WITH database writes
    python test_local_full_run.py --live --verbose     # Full run with debug logging
"""

import argparse
import json
import logging
import os
import sys
import time

# Ensure the project root is on the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Run the Spotify stats backup pipeline locally."
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable DEBUG-level logging.")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Fetch and process data but skip database writes. (Default)")
    parser.add_argument("--skip-db", action="store_true",
                        help="Alias for --dry-run.")
    parser.add_argument("--live", action="store_true",
                        help="Actually write to the database. Overrides --dry-run.")
    args = parser.parse_args()

    # --live overrides default --dry-run
    dry_run = not args.live
    if args.skip_db:
        dry_run = True

    setup_logging(args.verbose)
    logger = logging.getLogger("test_local_full_run")

    mode = "DRY RUN (no DB writes)" if dry_run else "LIVE (will write to DB!)"
    logger.info("=" * 60)
    logger.info("  Spotify Stats Backup — Local Test Run")
    logger.info("  Mode: %s", mode)
    logger.info("=" * 60)

    if not dry_run:
        logger.warning("⚠️  LIVE MODE — Database writes are ENABLED.")
        logger.warning("    Press Ctrl+C within 3 seconds to abort...")
        try:
            time.sleep(3)
        except KeyboardInterrupt:
            logger.info("Aborted by user.")
            sys.exit(0)

    start_time = time.time()

    # ── Step 1: Verify environment variables ───────────────────────────────────
    logger.info("-" * 60)
    logger.info("Step 1: Checking environment variables")
    logger.info("-" * 60)

    spotify_vars = ["CLIENT_ID", "CLIENT_SECRET", "REDIRECT_URI", "SECRET_NAME",
                    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION"]
    db_vars = ["DYNAMODB_TABLE_TRACKS", "DYNAMODB_TABLE_ARTISTS", "DYNAMODB_TABLE_ALBUMS"]

    all_vars = spotify_vars
    missing = [var for var in all_vars if not os.getenv(var)]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)
    logger.info("✅ All required environment variables are present.")

    # Show DynamoDB variables status (they are optional and will default if not set)
    set_db_vars = [var for var in db_vars if os.getenv(var)]
    unset_db_vars = [var for var in db_vars if not os.getenv(var)]
    if set_db_vars:
        logger.info("  DynamoDB tables set in environment: %s", ", ".join(set_db_vars))
    if unset_db_vars:
        logger.info("  DynamoDB tables not set in environment (will use defaults): %s", ", ".join(unset_db_vars))

    # ── Step 2: Initialize Spotify API Manager ─────────────────────────────────
    logger.info("-" * 60)
    logger.info("Step 2: Initialize SpotifyAPIManager")
    logger.info("-" * 60)
    try:
        from Managers.SpotifyAPIManager import SpotifyAPIManager
        spotify = SpotifyAPIManager()
    except Exception as e:
        logger.error("❌ Failed to initialize SpotifyAPIManager: %s", e, exc_info=True)
        sys.exit(1)

    if not spotify.access_token:
        logger.error("❌ No access token — cannot proceed.")
        sys.exit(1)
    logger.info("✅ SpotifyAPIManager initialized with valid access token.")

    # ── Step 3: Fetch data from Spotify ────────────────────────────────────────
    logger.info("-" * 60)
    logger.info("Step 3: Fetch data from Spotify Web API")
    logger.info("-" * 60)

    top_tracks = spotify.get_top_tracks()
    if top_tracks is None:
        logger.error("❌ get_top_tracks() failed. See errors above.")
        sys.exit(1)
    logger.info("✅ Fetched %d top tracks.", len(top_tracks))

    top_artists = spotify.get_top_artists()
    if top_artists is None:
        logger.error("❌ get_top_artists() failed. See errors above.")
        sys.exit(1)
    logger.info("✅ Fetched %d top artists.", len(top_artists))

    # ── Step 4: Process data ───────────────────────────────────────────────────
    logger.info("-" * 60)
    logger.info("Step 4: Process data into monthly snapshots")
    logger.info("-" * 60)
    try:
        from Types.MonthlyTopTracks import MonthlyTopTracks
        from Types.MonthlyTopArtists import MonthlyTopArtists
        from Types.MonthlyTopAlbums import MonthlyTopAlbums

        monthly_tracks = MonthlyTopTracks(top_tracks)
        monthly_artists = MonthlyTopArtists(top_artists)
        monthly_albums = MonthlyTopAlbums(top_tracks)

        logger.info("  Monthly period: %d/%d", monthly_tracks.month, monthly_tracks.year)
        logger.info("  Tracks:  %d", len(monthly_tracks.top_tracks))
        logger.info("  Artists: %d", len(monthly_artists.top_artists))
        logger.info("  Album groups: %d", len(monthly_albums.top_albums))
        logger.info("✅ Data processing complete.")
    except Exception as e:
        logger.error("❌ Data processing failed: %s", e, exc_info=True)
        sys.exit(1)

    # ── Step 5: Database insert (or skip) ──────────────────────────────────────
    if dry_run:
        logger.info("-" * 60)
        logger.info("Step 5: SKIPPING database writes (dry-run mode)")
        logger.info("-" * 60)
        logger.info("  Would insert %d tracks, %d artists, and %d album groups.",
                     len(monthly_tracks.top_tracks),
                     len(monthly_artists.top_artists),
                     len(monthly_albums.top_albums))
        logger.info("  Run with --live to actually write to the database.")
    else:
        logger.info("-" * 60)
        logger.info("Step 5: Writing data to database")
        logger.info("-" * 60)
        try:
            from Managers.DatabaseManager import DatabaseManager
            db = DatabaseManager()
            db.insert_top_artists_into_db(monthly_artists)
            db.insert_top_tracks_into_db(monthly_tracks)
            db.insert_top_albums_into_db(monthly_albums)
            logger.info("✅ Database writes complete.")
        except Exception as e:
            logger.error("❌ Database operation failed: %s", e, exc_info=True)
            sys.exit(1)

    # ── Summary ────────────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info("  Run complete in %.2f seconds.", elapsed)
    logger.info("  Mode: %s", mode)
    logger.info("  Tracks: %d | Artists: %d | Album groups: %d",
                 len(monthly_tracks.top_tracks),
                 len(monthly_artists.top_artists),
                 len(monthly_albums.top_albums))
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
