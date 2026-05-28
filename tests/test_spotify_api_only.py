#!/usr/bin/env python3
"""
test_spotify_api_only.py — Test Spotify Web API calls WITHOUT touching the database.

Use this to verify:
  - Your Spotify credentials (CLIENT_ID, CLIENT_SECRET) are valid
  - Your refresh token in AWS Secrets Manager is working
  - The Spotify /me/top/tracks and /me/top/artists endpoints return data
  - The response data parses correctly into Track/Artist/Album objects

Usage:
    python test_spotify_api_only.py                 # Normal run
    python test_spotify_api_only.py --verbose        # Show DEBUG-level logs
    python test_spotify_api_only.py --dump-json      # Also save raw API responses to JSON files
"""

import argparse
import json
import logging
import os
import sys

# Ensure the project root is on the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── Logging setup ──────────────────────────────────────────────────────────────

def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Test Spotify Web API calls locally (no database).")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable DEBUG-level logging for all modules.")
    parser.add_argument("--dump-json", action="store_true",
                        help="Save the parsed results as JSON files for inspection.")
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger("test_spotify_api_only")

    # ── Verify environment variables ───────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("  Spotify Web API Test — API Calls Only (No Database)")
    logger.info("=" * 60)

    required_env_vars = ["CLIENT_ID", "CLIENT_SECRET", "REDIRECT_URI", "SECRET_NAME",
                         "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION"]
    missing = [var for var in required_env_vars if not os.getenv(var)]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        logger.error("Make sure your .env file is configured. See sample.env for reference.")
        sys.exit(1)
    logger.info("All required environment variables are present.")

    # ── Initialize SpotifyAPIManager ───────────────────────────────────────────
    logger.info("-" * 60)
    logger.info("Step 1: Initialize SpotifyAPIManager (auth + token exchange)")
    logger.info("-" * 60)
    try:
        from Managers.SpotifyAPIManager import SpotifyAPIManager
        spotify = SpotifyAPIManager()
    except Exception as e:
        logger.error("FAILED to initialize SpotifyAPIManager: %s", e, exc_info=True)
        sys.exit(1)

    if not spotify.access_token:
        logger.error("No access token obtained. Check your CLIENT_ID, CLIENT_SECRET, and refresh token.")
        sys.exit(1)
    logger.info("✅ SpotifyAPIManager initialized. Access token is set.")

    # ── Fetch top tracks ───────────────────────────────────────────────────────
    logger.info("-" * 60)
    logger.info("Step 2: Fetch Top Tracks (GET /v1/me/top/tracks)")
    logger.info("-" * 60)
    top_tracks = spotify.get_top_tracks()
    if top_tracks is None:
        logger.error("❌ get_top_tracks() returned None. See errors above.")
        sys.exit(1)

    logger.info("✅ Received %d tracks.", len(top_tracks))
    logger.info("")
    logger.info("  Top 10 Tracks:")
    for i, track in enumerate(top_tracks[:10]):
        artist_names = ", ".join(a.name for a in track.artists)
        logger.info("    #%d  %s — %s  (popularity: %s)", i + 1, track.name, artist_names, track.popularity)

    # ── Fetch top artists ──────────────────────────────────────────────────────
    logger.info("-" * 60)
    logger.info("Step 3: Fetch Top Artists (GET /v1/me/top/artists)")
    logger.info("-" * 60)
    top_artists = spotify.get_top_artists()
    if top_artists is None:
        logger.error("❌ get_top_artists() returned None. See errors above.")
        sys.exit(1)

    logger.info("✅ Received %d artists.", len(top_artists))
    logger.info("")
    logger.info("  Top 10 Artists:")
    for i, artist in enumerate(top_artists[:10]):
        genres = ", ".join(artist.genres) if artist.genres else "no genres"
        logger.info("    #%d  %s  (popularity: %s, genres: %s)", i + 1, artist.name, artist.popularity, genres)

    # ── Test data processing ───────────────────────────────────────────────────
    logger.info("-" * 60)
    logger.info("Step 4: Test data processing (MonthlyTopTracks, Artists, Albums)")
    logger.info("-" * 60)
    try:
        from Types.MonthlyTopTracks import MonthlyTopTracks
        from Types.MonthlyTopArtists import MonthlyTopArtists
        from Types.MonthlyTopAlbums import MonthlyTopAlbums

        monthly_tracks = MonthlyTopTracks(top_tracks)
        logger.info("  MonthlyTopTracks: %d tracks for %d/%d",
                     len(monthly_tracks.top_tracks), monthly_tracks.month, monthly_tracks.year)

        monthly_artists = MonthlyTopArtists(top_artists)
        logger.info("  MonthlyTopArtists: %d artists for %d/%d",
                     len(monthly_artists.top_artists), monthly_artists.month, monthly_artists.year)

        monthly_albums = MonthlyTopAlbums(top_tracks)
        logger.info("  MonthlyTopAlbums: %d album rank groups for %d/%d",
                     len(monthly_albums.top_albums), monthly_albums.month, monthly_albums.year)

        # Show top albums
        if monthly_albums.top_albums:
            logger.info("")
            logger.info("  Top Albums (by track count):")
            for rank, album in sorted(monthly_albums.top_albums.items()):
                album_artists = ", ".join(a.name for a in album.artists)
                logger.info("    #%d  %s — %s", rank, album.name, album_artists)
        else:
            logger.info("  No albums with multiple tracks found (only 1 track per album).")

    except Exception as e:
        logger.error("❌ Error during data processing: %s", e, exc_info=True)
        sys.exit(1)
    logger.info("✅ Data processing completed successfully.")

    # ── Optionally dump to JSON ────────────────────────────────────────────────
    if args.dump_json:
        logger.info("-" * 60)
        logger.info("Step 5: Dumping parsed data to JSON files...")
        logger.info("-" * 60)

        tracks_data = []
        for rank, track in monthly_tracks.top_tracks.items():
            tracks_data.append({
                "rank": rank,
                "name": track.name,
                "track_id": track.track_id,
                "duration_ms": track.duration,
                "explicit": track.is_explicit,
                "popularity": track.popularity,
                "artists": [{"name": a.name, "id": a.artist_id} for a in track.artists],
                "album": {
                    "name": track.album.name,
                    "album_id": track.album.album_id,
                    "album_type": track.album.album_type,
                    "release_date": track.album.release_date,
                }
            })
        with open("test_output_tracks.json", "w") as f:
            json.dump(tracks_data, f, indent=2)
        logger.info("  Wrote test_output_tracks.json (%d tracks)", len(tracks_data))

        artists_data = []
        for rank, artist in monthly_artists.top_artists.items():
            artists_data.append({
                "rank": rank,
                "name": artist.name,
                "artist_id": artist.artist_id,
                "popularity": artist.popularity,
                "genres": artist.genres,
            })
        with open("test_output_artists.json", "w") as f:
            json.dump(artists_data, f, indent=2)
        logger.info("  Wrote test_output_artists.json (%d artists)", len(artists_data))

        albums_data = []
        for rank, album in monthly_albums.top_albums.items():
            albums_data.append({
                "rank": rank,
                "name": album.name,
                "album_id": album.album_id,
                "album_type": album.album_type,
                "release_date": album.release_date,
            })
        with open("test_output_albums.json", "w") as f:
            json.dump(albums_data, f, indent=2)
        logger.info("  Wrote test_output_albums.json (%d albums)", len(albums_data))

    # ── Done ───────────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("  All Spotify API tests passed! ✅")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
