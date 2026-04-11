import json
import logging
import requests
import os
import time
import string
import random
import base64
from dotenv import load_dotenv

from Types.Album import Album
from Types.Artist import Artist
from Types.Image import Image
from Types.Track import Track

logger = logging.getLogger(__name__)

load_dotenv()
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
    
class SpotifyAPIManager():
    def __init__(self, database_manager):
        logger.info("Initializing SpotifyAPIManager...")
        self.state = self.generate_random_state(16)
        self.auth_code = ''
        self.access_token = ''
        self.token_type = ''
        self.refresh_token = ''
        self.database_manager = database_manager

        logger.debug("CLIENT_ID loaded: %s", "Yes" if CLIENT_ID else "MISSING")
        logger.debug("CLIENT_SECRET loaded: %s", "Yes" if CLIENT_SECRET else "MISSING")
        logger.debug("REDIRECT_URI loaded: %s", REDIRECT_URI or "MISSING")

        logger.info("Retrieving refresh token from database...")
        self.refresh_token = self.database_manager.get_refresh_token()
        if self.refresh_token:
            masked_token = self.refresh_token[:8] + "..." + self.refresh_token[-4:] if len(self.refresh_token) > 12 else "***"
            logger.debug("Refresh token retrieved (masked): %s", masked_token)
        else:
            logger.error("Failed to retrieve refresh token from database!")

        logger.info("Exchanging refresh token for access token...")
        self.get_access_token_from_refresh_token()
        logger.info("SpotifyAPIManager initialized successfully.")

        
    def generate_random_state(self, length):
        letters = string.ascii_letters
        random_string = ''.join(random.choice(letters) for i in range(length))
        return random_string
        

    def get_access_token(self, code): 
        logger.info("Requesting access token with authorization code...")
        url = 'https://accounts.spotify.com/api/token'
        client_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
        client_string_bytes = client_string.encode("ascii") 
        
        base64_bytes = base64.b64encode(client_string_bytes) 
        base64_string = base64_bytes.decode("ascii") 
        headers = { 
            'Authorization' : 'Basic ' + base64_string,
            'Content-Type' : 'application/x-www-form-urlencoded' 
        }
        params = {
            'grant_type' : 'authorization_code',
            'redirect_uri' : REDIRECT_URI,
            'code' : code
        } 
        try:
            logger.debug("POST %s (grant_type=authorization_code)", url)
            access_response = requests.post(url, params=params, headers=headers)
            logger.debug("Response status: %d", access_response.status_code)

            if access_response.status_code == 200:
                access_json = access_response.json()
                self.access_token = access_json['access_token']
                self.token_type = access_json['token_type']
                self.refresh_token = access_json['refresh_token']
                logger.info("Access token obtained successfully via authorization code.")
                logger.debug("Token type: %s", self.token_type)
            else:
                logger.error("Failed to get access token. Status: %d, Response: %s",
                             access_response.status_code, access_response.text)
                return None
        except requests.exceptions.RequestException as e:
            logger.error("Request exception during access token exchange: %s", e)
            return None
        

        
    def get_access_token_from_refresh_token(self): 
        logger.info("Requesting new access token using refresh token...")
        url = 'https://accounts.spotify.com/api/token'
        client_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
        client_string_bytes = client_string.encode("ascii") 
        
        base64_bytes = base64.b64encode(client_string_bytes) 
        base64_string = base64_bytes.decode("ascii") 
        if not self.refresh_token:
            logger.error("No refresh token available. Cannot obtain access token.")
            return None
        headers = { 
            'Authorization' : 'Basic ' + base64_string,
            'Content-Type' : 'application/x-www-form-urlencoded' 
        }
        params = {
            'grant_type' : 'refresh_token',
            'redirect_uri' : REDIRECT_URI,
            'refresh_token' : self.refresh_token
        } 
        try:
            logger.debug("POST %s (grant_type=refresh_token)", url)
            access_response = requests.post(url, params=params, headers=headers)
            logger.debug("Response status: %d", access_response.status_code)

            if access_response.status_code == 200:
                access_json = access_response.json()
                self.access_token = access_json['access_token']
                self.token_type = access_json['token_type']
                logger.info("Access token obtained successfully via refresh token.")
                logger.debug("Token type: %s", self.token_type)
                if 'refresh_token' in access_json:
                    logger.info("New refresh token received from Spotify — updating in database.")
                    self.refresh_token = access_json['refresh_token']
                    self.database_manager.update_refresh_token(self.refresh_token)
                else:
                    logger.debug("No new refresh token in response (existing one is still valid).")
            else:
                logger.error("Failed to refresh access token. Status: %d, Response: %s",
                             access_response.status_code, access_response.text)
                return None
        except requests.exceptions.RequestException as e:
            logger.error("Request exception during refresh token exchange: %s", e)
            return None

    def get_top_tracks(self):
        logger.info("Fetching top tracks from Spotify API...")
        url = 'https://api.spotify.com/v1/me/top/tracks'
        params = {
            'time_range' : 'short_term',
            'limit' : '50',
            'offset' : '0'
        } 
        headers = { 
            'Authorization' : f"{self.token_type} {self.access_token}",
            'Content-Type': 'application/json' 
        }
        try:
            logger.debug("GET %s (time_range=short_term, limit=50)", url)
            top_tracks_response = requests.get(url, headers=headers, params=params)
            logger.debug("Response status: %d", top_tracks_response.status_code)

            if top_tracks_response.status_code == 200:
                top_tracks_json = top_tracks_response.json()
                items = top_tracks_json.get('items', [])
                logger.info("Received %d tracks from Spotify API.", len(items))

                top_tracks_list = []
                for i, track in enumerate(items):
                    artists = []
                    for artist in track['artists']:
                        artists.append(Artist(name=artist['name'], artist_id=artist['id']))
                    album_images = []
                    for image in track['album']['images']:
                        album_images.append(Image(url=image['url'], height=image['height'], width=image['width']))
                    album_artists = []
                    for artist in track['album']['artists']:
                        album_artists.append(Artist(name=artist['name'], artist_id=artist['id']))
                    album = Album(name=track['album']['name'], album_id=track['album']['id'], 
                        album_type=track['album']['album_type'], release_date=track['album']['release_date'], 
                        images=album_images, artists=album_artists)
                    top_tracks_list.append(Track(name=track['name'], track_id=track['id'], 
                        duration=track['duration_ms'], explicit=track['explicit'], disc_number=track['disc_number'], 
                        track_number=track['track_number'], artists=artists, album=album, popularity=track['popularity']))
                    logger.debug("  #%d: '%s' by %s", i + 1, track['name'],
                                 ', '.join(a['name'] for a in track['artists']))

                logger.info("Successfully parsed %d tracks.", len(top_tracks_list))
                return top_tracks_list
            elif top_tracks_response.status_code == 401:
                logger.error("Spotify API returned 401 Unauthorized — access token may be expired or invalid.")
                logger.debug("Response body: %s", top_tracks_response.text)
                return None
            elif top_tracks_response.status_code == 429:
                retry_after = top_tracks_response.headers.get('Retry-After', 'unknown')
                logger.error("Spotify API rate limit hit (429). Retry after: %s seconds.", retry_after)
                return None
            else:
                logger.error("Spotify API error fetching top tracks. Status: %d, Response: %s",
                             top_tracks_response.status_code, top_tracks_response.text)
                return None
        except requests.exceptions.RequestException as e:
            logger.error("Request exception fetching top tracks: %s", e)
    def get_top_artists(self):
        logger.info("Fetching top artists from Spotify API...")
        url = 'https://api.spotify.com/v1/me/top/artists'
        headers = { 
            'Authorization' : f"{self.token_type} {self.access_token}",
            'Content-Type' : 'application/json' 
        }
        params = {
            'time_range' : 'short_term',
            'limit' : '50',
            'offset' : '0'
        } 
        try:
            logger.debug("GET %s (time_range=short_term, limit=50)", url)
            top_artists_response = requests.get(url, headers=headers, params=params)
            logger.debug("Response status: %d", top_artists_response.status_code)

            if top_artists_response.status_code == 200:
                top_artists_json = top_artists_response.json()
                items = top_artists_json.get('items', [])
                logger.info("Received %d artists from Spotify API.", len(items))

                top_artists_list = []
                for i, artist in enumerate(items):
                    artist_images = []
                    for image in artist['images']:
                        artist_images.append(Image(url=image['url'], height=image['height'], width=image['width']))
                    genres_list = []
                    for genre in artist['genres']:
                        genres_list.append(genre)
                    top_artists_list.append(Artist(name=artist['name'], artist_id=artist['id'], genres=genres_list, 
                        images=artist_images, popularity=artist['popularity']))
                    logger.debug("  #%d: '%s' (genres: %s)", i + 1, artist['name'],
                                 ', '.join(artist['genres']) if artist['genres'] else 'none')

                logger.info("Successfully parsed %d artists.", len(top_artists_list))
                return top_artists_list
            elif top_artists_response.status_code == 401:
                logger.error("Spotify API returned 401 Unauthorized — access token may be expired or invalid.")
                logger.debug("Response body: %s", top_artists_response.text)
                return None
            elif top_artists_response.status_code == 429:
                retry_after = top_artists_response.headers.get('Retry-After', 'unknown')
                logger.error("Spotify API rate limit hit (429). Retry after: %s seconds.", retry_after)
                return None
            else:
                logger.error("Spotify API error fetching top artists. Status: %d, Response: %s",
                             top_artists_response.status_code, top_artists_response.text)
                return None
        except requests.exceptions.RequestException as e:
            logger.error("Request exception fetching top artists: %s", e)
            return None 

    def get_tracks_batch(self, track_ids: list[str]):
        """Fetches metadata for up to 50 tracks in a single batch."""
        if not track_ids:
            return []
        
        url = 'https://api.spotify.com/v1/tracks'
        headers = { 
            'Authorization' : f"{self.token_type} {self.access_token}",
            'Content-Type': 'application/json' 
        }
        params = {
            'ids': ','.join(track_ids)
        }
        
        try:
            logger.debug("GET %s (ids=%d)", url, len(track_ids))
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                tracks_json = response.json()
                items = tracks_json.get('tracks', [])
                
                track_list = []
                for track in items:
                    if not track: continue # Handle potential nulls in response
                    artists = [Artist(name=a['name'], artist_id=a['id']) for a in track['artists']]
                    album_images = [Image(url=img['url'], height=img['height'], width=img['width']) 
                                   for img in track['album']['images']]
                    album_artists = [Artist(name=a['name'], artist_id=a['id']) for a in track['album']['artists']]
                    album = Album(name=track['album']['name'], album_id=track['album']['id'], 
                        album_type=track['album']['album_type'], release_date=track['album']['release_date'], 
                        images=album_images, artists=album_artists)
                    
                    track_list.append(Track(name=track['name'], track_id=track['id'], 
                        duration=track['duration_ms'], explicit=track['explicit'], disc_number=track['disc_number'], 
                        track_number=track['track_number'], artists=artists, album=album, popularity=track['popularity']))
                
                return track_list
            else:
                logger.error("Spotify API error in batch tracks. Status: %d, Response: %s",
                             response.status_code, response.text)
                return []
        except requests.exceptions.RequestException as e:
            logger.error("Request exception in batch tracks: %s", e)
            return []

    def get_artists_batch(self, artist_ids: list[str]):
        """Fetches metadata for up to 50 artists in a single batch."""
        if not artist_ids:
            return []
            
        url = 'https://api.spotify.com/v1/artists'
        headers = { 
            'Authorization' : f"{self.token_type} {self.access_token}",
            'Content-Type': 'application/json' 
        }
        params = {
            'ids': ','.join(artist_ids)
        }
        
        try:
            logger.debug("GET %s (ids=%d)", url, len(artist_ids))
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                artists_json = response.json()
                items = artists_json.get('artists', [])
                
                artist_list = []
                for artist in items:
                    if not artist: continue
                    artist_images = [Image(url=img['url'], height=img['height'], width=img['width']) 
                                    for img in artist['images']]
                    genres = artist.get('genres', [])
                    artist_list.append(Artist(name=artist['name'], artist_id=artist['id'], genres=genres, 
                        images=artist_images, popularity=artist['popularity']))
                
                return artist_list
            else:
                logger.error("Spotify API error in batch artists. Status: %d, Response: %s",
                             response.status_code, response.text)
                return []
        except requests.exceptions.RequestException as e:
            logger.error("Request exception in batch artists: %s", e)
            return []
 None 