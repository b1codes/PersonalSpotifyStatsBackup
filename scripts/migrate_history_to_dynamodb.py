import mysql.connector
import boto3
import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("migrate_history")

load_dotenv()

def migrate():
    # 1. Connect to MySQL using active credentials in .env
    db_host = os.getenv('DB_HOST')
    db_user = os.getenv('DB_USERNAME')
    db_password = os.getenv('DB_PASSWORD')
    db_name = os.getenv('DB_NAME')
    db_port = os.getenv('DB_PORT', '3306')

    if not db_host or not db_user or not db_password or not db_name:
        logger.error("MySQL connection environment variables are missing from .env!")
        return

    logger.info("Connecting to MySQL database %s at %s:%s...", db_name, db_host, db_port)
    try:
        db = mysql.connector.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            port=db_port
        )
        cursor = db.cursor()
    except Exception as e:
        logger.error("Failed to connect to MySQL: %s", e)
        return

    # 2. Connect to DynamoDB
    region_name = os.getenv('AWS_DEFAULT_REGION', 'us-east-2')
    tracks_table_name = os.getenv('DYNAMODB_TABLE_TRACKS', 'PersonalSpotifyStatsBackup-tracks')
    artists_table_name = os.getenv('DYNAMODB_TABLE_ARTISTS', 'PersonalSpotifyStatsBackup-artists')
    albums_table_name = os.getenv('DYNAMODB_TABLE_ALBUMS', 'PersonalSpotifyStatsBackup-albums')

    logger.info("Connecting to DynamoDB in region %s...", region_name)
    try:
        dynamodb = boto3.resource('dynamodb', region_name=region_name)
        tracks_table = dynamodb.Table(tracks_table_name)
        artists_table = dynamodb.Table(artists_table_name)
        albums_table = dynamodb.Table(albums_table_name)
    except Exception as e:
        logger.error("Failed to connect to DynamoDB: %s", e)
        db.close()
        return

    # --- Migrate Tracks ---
    logger.info("Migrating tracks from MySQL to DynamoDB table '%s'...", tracks_table_name)
    try:
        cursor.execute("SELECT month, year, standing, name, track_id, duration_ms, is_explicit, disc_number, track_number, popularity, album_id, artist_ids FROM tracks")
        tracks_rows = cursor.fetchall()
        logger.info("Found %d tracks to migrate.", len(tracks_rows))
        
        with tracks_table.batch_writer() as batch:
            for row in tracks_rows:
                month, year, standing, name, track_id, duration_ms, is_explicit, disc_number, track_number, popularity, album_id, artist_ids_json = row
                
                # Format composite key
                year_month = f"{int(year):04d}-{int(month):02d}"
                
                # Parse artist_ids JSON list
                artist_ids = []
                if artist_ids_json:
                    try:
                        artist_ids = json.loads(artist_ids_json)
                    except Exception:
                        artist_ids = [artist_ids_json]

                item = {
                    'year_month': year_month,
                    'standing': int(standing),
                    'name': name,
                    'track_id': track_id,
                    'duration_ms': int(duration_ms) if duration_ms is not None else 0,
                    'is_explicit': bool(is_explicit),
                    'disc_number': int(disc_number) if disc_number is not None else 1,
                    'track_number': int(track_number) if track_number is not None else 1,
                    'popularity': int(popularity) if popularity is not None else 0,
                    'album_id': album_id,
                    'artist_ids': artist_ids,
                    'updated_at': datetime.utcnow().isoformat()
                }
                batch.put_item(Item=item)
        logger.info("Successfully migrated tracks!")
    except Exception as e:
        logger.error("Error migrating tracks: %s", e)

    # --- Migrate Artists ---
    logger.info("Migrating artists from MySQL to DynamoDB table '%s'...", artists_table_name)
    try:
        cursor.execute("SELECT month, year, standing, name, artist_id, popularity, genres, images FROM artists")
        artists_rows = cursor.fetchall()
        logger.info("Found %d artists to migrate.", len(artists_rows))
        
        with artists_table.batch_writer() as batch:
            for row in artists_rows:
                month, year, standing, name, artist_id, popularity, genres_json, images_json = row
                
                year_month = f"{int(year):04d}-{int(month):02d}"
                
                genres = []
                if genres_json:
                    try:
                        genres = json.loads(genres_json)
                    except Exception:
                        genres = [genres_json]
                        
                images = []
                if images_json:
                    try:
                        images = json.loads(images_json)
                    except Exception:
                        images = [images_json]

                item = {
                    'year_month': year_month,
                    'standing': int(standing),
                    'name': name,
                    'artist_id': artist_id,
                    'popularity': int(popularity) if popularity is not None else 0,
                    'genres': genres,
                    'images': images,
                    'updated_at': datetime.utcnow().isoformat()
                }
                batch.put_item(Item=item)
        logger.info("Successfully migrated artists!")
    except Exception as e:
        logger.error("Error migrating artists: %s", e)

    # --- Migrate Albums ---
    logger.info("Migrating albums from MySQL to DynamoDB table '%s'...", albums_table_name)
    try:
        cursor.execute("SELECT month, year, standing, name, album_id, album_type, release_date, images, artist_ids FROM albums")
        albums_rows = cursor.fetchall()
        logger.info("Found %d albums to migrate.", len(albums_rows))
        
        with albums_table.batch_writer() as batch:
            for row in albums_rows:
                month, year, standing, name, album_id, album_type, release_date, images_json, artist_ids_json = row
                
                year_month = f"{int(year):04d}-{int(month):02d}"
                
                images = []
                if images_json:
                    try:
                        images = json.loads(images_json)
                    except Exception:
                        images = [images_json]
                        
                artist_ids = []
                if artist_ids_json:
                    try:
                        artist_ids = json.loads(artist_ids_json)
                    except Exception:
                        artist_ids = [artist_ids_json]

                item = {
                    'year_month': year_month,
                    'standing': int(standing),
                    'name': name,
                    'album_id': album_id,
                    'album_type': album_type,
                    'release_date': release_date,
                    'images': images,
                    'artist_ids': artist_ids,
                    'updated_at': datetime.utcnow().isoformat()
                }
                batch.put_item(Item=item)
        logger.info("Successfully migrated albums!")
    except Exception as e:
        logger.error("Error migrating albums: %s", e)

    # 3. Clean up
    cursor.close()
    db.close()
    logger.info("Data migration complete!")

if __name__ == "__main__":
    migrate()
