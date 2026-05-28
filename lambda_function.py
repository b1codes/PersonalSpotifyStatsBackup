import json
import logging
import os
from dotenv import load_dotenv

# It's good practice to load environment variables at the start
load_dotenv()

# Configure logging for Lambda (CloudWatch captures root logger output)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Import your project's custom modules
from Managers.DatabaseManager import DatabaseManager
from Managers.SpotifyAPIManager import SpotifyAPIManager
from Types.MonthlyTopAlbums import MonthlyTopAlbums
from Types.MonthlyTopArtists import MonthlyTopArtists
from Types.MonthlyTopGenres import MonthlyTopGenres
from Types.MonthlyTopTracks import MonthlyTopTracks

def lambda_handler(event, context):
    """
    Triggered monthly by EventBridge. Fetches top Spotify stats and stores
    them in DynamoDB.

    Dry-run mode: pass {"dry_run": true} (or {"dry-run": true}) in the event
    to authenticate, fetch, and process data without writing to DynamoDB or
    rotating the Spotify refresh token in Secrets Manager.
    """
    dry_run = bool(event.get('dry_run', False) or event.get('dry-run', False))

    mode_label = "DRY RUN" if dry_run else "LIVE"
    logger.info("=== Starting Spotify stats backup (Lambda) [%s] ===", mode_label)
    if dry_run:
        logger.info("[DRY RUN] Database writes and Secrets Manager updates are disabled.")

    try:
        # 1. Initialize Managers
        database_manager = DatabaseManager()
        spotify_api_manager = SpotifyAPIManager(database_manager, dry_run=dry_run)
        logger.info("Successfully initialized Database and Spotify API managers.")

        # 2. Fetch Data from Spotify
        logger.info("Fetching top tracks and artists from Spotify API...")
        top_tracks_obj = spotify_api_manager.get_top_tracks()
        top_artists_obj = spotify_api_manager.get_top_artists()

        if top_tracks_obj is None or top_artists_obj is None:
            raise Exception("Failed to fetch data from Spotify. The API response was empty.")

        logger.info("Received %d tracks and %d artists from Spotify.",
                     len(top_tracks_obj), len(top_artists_obj))

        # 3. Process Data into Monthly Snapshots
        logger.info("Processing data into monthly snapshots...")
        last_month_top_tracks = MonthlyTopTracks(top_tracks_obj)
        last_month_top_artists = MonthlyTopArtists(top_artists_obj)
        last_month_top_albums = MonthlyTopAlbums(top_tracks_obj)
        last_month_top_genres = MonthlyTopGenres(top_artists_obj)

        logger.info("Snapshots created — Tracks: %d, Artists: %d, Albums: %d, Genres: %d",
                     len(last_month_top_tracks.top_tracks),
                     len(last_month_top_artists.top_artists),
                     len(last_month_top_albums.top_albums),
                     len(last_month_top_genres.top_genres))

        # 4. Insert Data into DynamoDB (skipped in dry-run mode)
        if dry_run:
            logger.info("[DRY RUN] Skipping all DynamoDB writes.")
            logger.info("=== Spotify stats backup finished (DRY RUN — no changes made) ===")
            return {
                'statusCode': 200,
                'body': json.dumps('Spotify stats backup completed successfully (Dry Run - No database changes made).')
            }

        logger.info("Inserting data into the database...")
        database_manager.insert_top_artists_into_db(last_month_top_artists)
        database_manager.insert_top_tracks_into_db(last_month_top_tracks)
        database_manager.insert_top_albums_into_db(last_month_top_albums)
        database_manager.insert_top_genres_into_db(last_month_top_genres)

        logger.info("=== Spotify stats backup finished successfully! ===")
        return {
            'statusCode': 200,
            'body': json.dumps('Spotify stats backup completed successfully!')
        }

    except Exception as e:
        logger.error("An error occurred during execution: %s", e, exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps(f'An error occurred: {str(e)}')
        }