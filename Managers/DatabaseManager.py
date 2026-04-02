import logging
import mysql.connector
import os
from dotenv import load_dotenv
import json

from Types.MonthlyTopAlbums import MonthlyTopAlbums
from Types.MonthlyTopArtists import MonthlyTopArtists
from Types.MonthlyTopTracks import MonthlyTopTracks

logger = logging.getLogger(__name__)

load_dotenv()

class DatabaseManager:
    def __init__(self):
        db_host = os.getenv('DB_HOST')
        db_user = os.getenv('DB_USERNAME')
        db_name = os.getenv('DB_NAME')
        db_port = os.getenv('DB_PORT')

        logger.info("Connecting to MySQL database...")
        logger.debug("DB_HOST: %s", db_host or "MISSING")
        logger.debug("DB_USERNAME: %s", db_user or "MISSING")
        logger.debug("DB_NAME: %s", db_name or "MISSING")
        logger.debug("DB_PORT: %s", db_port or "MISSING")
        logger.debug("DB_PASSWORD: %s", "set" if os.getenv('DB_PASSWORD') else "MISSING")

        try:
            self.db = mysql.connector.connect(
                host=db_host,
                user=db_user,
                password=os.getenv('DB_PASSWORD'),
                database=db_name,
                port=db_port
            )
            self.cursor = self.db.cursor()
            logger.info("Successfully connected to MySQL database '%s' at %s:%s.", db_name, db_host, db_port)
        except mysql.connector.Error as err:
            logger.error("Failed to connect to MySQL database: %s", err)
            raise

        self._ensure_config_table()

    def _ensure_config_table(self):
        """Creates the config table if it doesn't already exist."""
        logger.debug("Ensuring 'config' table exists...")
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                config_key VARCHAR(255) PRIMARY KEY,
                config_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        self.db.commit()
        logger.debug("'config' table ready.")

    def get_refresh_token(self):
        """Retrieves the Spotify refresh token from the config table."""
        try:
            self.cursor.execute(
                "SELECT config_value FROM config WHERE config_key = %s",
                ('spotify_refresh_token',)
            )
            row = self.cursor.fetchone()
            if row:
                token = row[0]
                masked = token[:8] + "..." + token[-4:] if len(token) > 12 else "***"
                logger.info("Retrieved refresh token from database (masked: %s).", masked)
                return token
            else:
                logger.error("No refresh token found in config table.")
                return None
        except mysql.connector.Error as err:
            logger.error("Error reading refresh token from database: %s", err)
            return None

    def update_refresh_token(self, new_token):
        """Stores or updates the Spotify refresh token in the config table."""
        try:
            self.cursor.execute(
                """INSERT INTO config (config_key, config_value)
                   VALUES (%s, %s)
                   ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)""",
                ('spotify_refresh_token', new_token)
            )
            self.db.commit()
            logger.info("Refresh token updated in database.")
        except mysql.connector.Error as err:
            logger.error("Error updating refresh token in database: %s", err)
            raise

    def insert_top_tracks_into_db(self, top_tracks_of_the_month: MonthlyTopTracks):
        logger.info("Inserting top tracks for %d/%d into database...",
                     top_tracks_of_the_month.month, top_tracks_of_the_month.year)
        sql = """
        INSERT INTO tracks (month, year, standing, name, track_id, duration_ms, is_explicit,
        disc_number, track_number, popularity, album_id, artist_ids)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE name=VALUES(name), popularity=VALUES(popularity);
        """
        track_list = []
        for rank, track in top_tracks_of_the_month.top_tracks.items():
            artist_ids = json.dumps([artist.artist_id for artist in track.artists])
            track_data = (
                top_tracks_of_the_month.month, top_tracks_of_the_month.year, rank,
                track.name, track.track_id, track.duration, track.is_explicit,
                track.disc_number, track.track_number, track.popularity,
                track.album.album_id, artist_ids
            )
            track_list.append(track_data)
            logger.debug("  Prepared track #%d: '%s' (id: %s)", rank, track.name, track.track_id)

        logger.debug("Executing batch insert for %d tracks...", len(track_list))
        self.cursor.executemany(sql, track_list)
        self.db.commit()
        logger.info("Tracks insert complete: %d rows affected.", self.cursor.rowcount)

    def insert_top_artists_into_db(self, top_artists_of_the_month: MonthlyTopArtists):
        logger.info("Inserting top artists for %d/%d into database...",
                     top_artists_of_the_month.month, top_artists_of_the_month.year)
        sql = """
        INSERT INTO artists (month, year, standing, name, artist_id, popularity, genres, images)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE name=VALUES(name), popularity=VALUES(popularity);
        """
        artist_list = []
        for rank, artist in top_artists_of_the_month.top_artists.items():
            genres_list = json.dumps(artist.genres)
            images_list = json.dumps([image.url for image in artist.images])
            artist_data = (
                top_artists_of_the_month.month, top_artists_of_the_month.year, rank,
                artist.name, artist.artist_id, artist.popularity, genres_list, images_list
            )
            artist_list.append(artist_data)
            logger.debug("  Prepared artist #%d: '%s' (id: %s)", rank, artist.name, artist.artist_id)

        logger.debug("Executing batch insert for %d artists...", len(artist_list))
        self.cursor.executemany(sql, artist_list)
        self.db.commit()
        logger.info("Artists insert complete: %d rows affected.", self.cursor.rowcount)

    def insert_top_albums_into_db(self, top_albums_of_the_month: MonthlyTopAlbums):
        logger.info("Inserting top albums for %d/%d into database...",
                     top_albums_of_the_month.month, top_albums_of_the_month.year)
        sql = """
        INSERT INTO albums (month, year, standing, name, album_id, album_type, release_date, images, artist_ids)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE name=VALUES(name);
        """
        album_list = []
        for rank, albums in top_albums_of_the_month.top_albums.items():
            for album in albums:
                images_list = json.dumps([image.url for image in album.images])
                artist_ids = json.dumps([artist.artist_id for artist in album.artists])
                album_data = (
                    top_albums_of_the_month.month, top_albums_of_the_month.year, rank,
                    album.name, album.album_id, album.album_type, album.release_date,
                    images_list, artist_ids
                )
                album_list.append(album_data)
                logger.debug("  Prepared album (rank %d): '%s' (id: %s, type: %s)",
                             rank, album.name, album.album_id, album.album_type)

        logger.debug("Executing batch insert for %d albums...", len(album_list))
        self.cursor.executemany(sql, album_list)
        self.db.commit()
        logger.info("Albums insert complete: %d rows affected.", self.cursor.rowcount)