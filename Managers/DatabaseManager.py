import logging
import os
import boto3
import json
from datetime import datetime
from dotenv import load_dotenv

from Types.MonthlyTopAlbums import MonthlyTopAlbums
from Types.MonthlyTopArtists import MonthlyTopArtists
from Types.MonthlyTopTracks import MonthlyTopTracks

logger = logging.getLogger(__name__)

load_dotenv()

class DatabaseManager:
    def __init__(self):
        region_name = os.getenv('AWS_DEFAULT_REGION', 'us-east-2')
        logger.info("Initializing DatabaseManager (DynamoDB for stats, Secrets Manager for token) in region %s...", region_name)
        
        # Load configuration from environment variables
        self.secret_name = os.getenv('SECRET_NAME', 'PersonalSpotifyStatsBackup-refresh-token')
        self.tracks_table_name = os.getenv('DYNAMODB_TABLE_TRACKS', 'PersonalSpotifyStatsBackup-tracks')
        self.artists_table_name = os.getenv('DYNAMODB_TABLE_ARTISTS', 'PersonalSpotifyStatsBackup-artists')
        self.albums_table_name = os.getenv('DYNAMODB_TABLE_ALBUMS', 'PersonalSpotifyStatsBackup-albums')

        logger.debug("SECRET_NAME: %s", self.secret_name)
        logger.debug("DYNAMODB_TABLE_TRACKS: %s", self.tracks_table_name)
        logger.debug("DYNAMODB_TABLE_ARTISTS: %s", self.artists_table_name)
        logger.debug("DYNAMODB_TABLE_ALBUMS: %s", self.albums_table_name)

        try:
            self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
            self.secrets_client = boto3.client('secretsmanager', region_name=region_name)
            
            self.tracks_table = self.dynamodb.Table(self.tracks_table_name)
            self.artists_table = self.dynamodb.Table(self.artists_table_name)
            self.albums_table = self.dynamodb.Table(self.albums_table_name)
            logger.info("Successfully initialized AWS DynamoDB and Secrets Manager interfaces.")
        except Exception as e:
            logger.error("Failed to connect to AWS services: %s", e)
            raise

    def get_refresh_token(self):
        """Retrieves the Spotify refresh token from AWS Secrets Manager."""
        try:
            logger.debug("Fetching secret '%s' from AWS Secrets Manager...", self.secret_name)
            response = self.secrets_client.get_secret_value(SecretId=self.secret_name)
            if 'SecretString' in response:
                secret_str = response['SecretString']
                # Check if it is a JSON object or raw string
                try:
                    secret_dict = json.loads(secret_str)
                    token = secret_dict.get('spotify_refresh_token')
                except json.JSONDecodeError:
                    token = secret_str
                
                if token:
                    masked = token[:8] + "..." + token[-4:] if len(token) > 12 else "***"
                    logger.info("Retrieved refresh token from Secrets Manager (masked: %s).", masked)
                    return token
            logger.error("No refresh token found in secret '%s'.", self.secret_name)
            return None
        except Exception as e:
            logger.error("Error reading refresh token from Secrets Manager: %s", e)
            return None

    def update_refresh_token(self, new_token):
        """Stores or updates the Spotify refresh token in AWS Secrets Manager."""
        try:
            logger.info("Updating refresh token in Secrets Manager secret '%s'...", self.secret_name)
            
            # Read existing secret first to preserve any other keys if it's JSON
            try:
                response = self.secrets_client.get_secret_value(SecretId=self.secret_name)
                secret_str = response.get('SecretString', '')
                secret_dict = json.loads(secret_str)
                secret_dict['spotify_refresh_token'] = new_token
                new_secret_str = json.dumps(secret_dict)
            except Exception:
                # Fallback: create fresh JSON structure
                new_secret_str = json.dumps({'spotify_refresh_token': new_token})
                
            self.secrets_client.put_secret_value(
                SecretId=self.secret_name,
                SecretString=new_secret_str
            )
            logger.info("Refresh token updated in AWS Secrets Manager.")
        except Exception as e:
            logger.error("Error updating refresh token in Secrets Manager: %s", e)
            raise

    def insert_top_tracks_into_db(self, top_tracks_of_the_month: MonthlyTopTracks):
        """Batch inserts monthly top tracks into the tracks table."""
        year_month = f"{top_tracks_of_the_month.year:04d}-{top_tracks_of_the_month.month:02d}"
        logger.info("Inserting top tracks for %s into DynamoDB...", year_month)
        
        try:
            with self.tracks_table.batch_writer() as batch:
                for rank, track in top_tracks_of_the_month.top_tracks.items():
                    artist_ids = [artist.artist_id for artist in track.artists]
                    item = {
                        'year_month': year_month,
                        'standing': rank,
                        'name': track.name,
                        'track_id': track.track_id,
                        'duration_ms': track.duration,
                        'is_explicit': track.is_explicit,
                        'disc_number': track.disc_number,
                        'track_number': track.track_number,
                        'popularity': track.popularity,
                        'album_id': track.album.album_id,
                        'artist_ids': artist_ids,
                        'updated_at': datetime.utcnow().isoformat()
                    }
                    batch.put_item(Item=item)
            logger.info("Tracks batch insert complete.")
        except Exception as e:
            logger.error("Error inserting tracks into DynamoDB: %s", e)
            raise

    def insert_top_artists_into_db(self, top_artists_of_the_month: MonthlyTopArtists):
        """Batch inserts monthly top artists into the artists table."""
        year_month = f"{top_artists_of_the_month.year:04d}-{top_artists_of_the_month.month:02d}"
        logger.info("Inserting top artists for %s into DynamoDB...", year_month)
        
        try:
            with self.artists_table.batch_writer() as batch:
                for rank, artist in top_artists_of_the_month.top_artists.items():
                    images_list = [image.url for image in artist.images]
                    item = {
                        'year_month': year_month,
                        'standing': rank,
                        'name': artist.name,
                        'artist_id': artist.artist_id,
                        'popularity': artist.popularity,
                        'genres': artist.genres,
                        'images': images_list,
                        'updated_at': datetime.utcnow().isoformat()
                    }
                    batch.put_item(Item=item)
            logger.info("Artists batch insert complete.")
        except Exception as e:
            logger.error("Error inserting artists into DynamoDB: %s", e)
            raise

    def insert_top_albums_into_db(self, top_albums_of_the_month: MonthlyTopAlbums):
        """Batch inserts monthly top albums into the albums table."""
        year_month = f"{top_albums_of_the_month.year:04d}-{top_albums_of_the_month.month:02d}"
        logger.info("Inserting top albums for %s into DynamoDB...", year_month)
        
        try:
            with self.albums_table.batch_writer() as batch:
                for rank, album in top_albums_of_the_month.top_albums.items():
                    images_list = [image.url for image in album.images]
                    artist_ids = [artist.artist_id for artist in album.artists]
                    item = {
                        'year_month': year_month,
                        'standing': rank,
                        'name': album.name,
                        'album_id': album.album_id,
                        'album_type': album.album_type,
                        'release_date': album.release_date,
                        'images': images_list,
                        'artist_ids': artist_ids,
                        'updated_at': datetime.utcnow().isoformat()
                    }
                    batch.put_item(Item=item)
            logger.info("Albums batch insert complete.")
        except Exception as e:
            logger.error("Error inserting albums into DynamoDB: %s", e)
            raise