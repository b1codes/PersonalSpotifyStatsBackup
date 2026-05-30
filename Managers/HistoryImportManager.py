import json
import logging
import os
import glob
from datetime import datetime
from collections import Counter

from Types.Track import Track
from Types.Artist import Artist
from Types.Album import Album
from Types.Image import Image
from Types.MonthlyTopTracks import MonthlyTopTracks
from Types.MonthlyTopArtists import MonthlyTopArtists
from Types.MonthlyTopAlbums import MonthlyTopAlbums
from Types.MonthlyTopGenres import MonthlyTopGenres

logger = logging.getLogger(__name__)

class HistoryImportManager:
    def __init__(self, spotify_api_manager, database_manager):
        self.spotify_api_manager = spotify_api_manager
        self.database_manager = database_manager

    def parse_history_files(self, directory_path):
        """Scans and parses all Spotify history JSON files in the directory."""
        # Check for Extended History format (Streaming_History_Audio_*.json)
        files = glob.glob(os.path.join(directory_path, "Streaming_History_Audio_*.json"))
        # Also check for standard Account Data format (StreamingHistory*.json)
        if not files:
            files = glob.glob(os.path.join(directory_path, "StreamingHistory*.json"))
        
        if not files:
            logger.error("No Spotify history files found in %s", directory_path)
            return []

        all_entries = []
        for file_path in files:
            logger.info("Parsing file: %s", file_path)
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_entries.extend(data)
        
        logger.info("Total entries parsed: %d", len(all_entries))
        return all_entries

    def aggregate_by_month(self, entries):
        """Groups entries by Year/Month and counts plays."""
        # Key: (year, month), Value: {'tracks': Counter, 'artists': Counter}
        monthly_data = {}

        for entry in entries:
            # Extended History uses 'ts', Standard uses 'endTime'
            ts_str = entry.get('ts') or entry.get('endTime')
            if not ts_str:
                continue
            
            # Use 'spotify_track_uri' if available (Extended), otherwise trackName (Standard)
            track_id = entry.get('spotify_track_uri')
            # artist_id is not directly in JSON, we use artist name and resolve later
            artist_name = entry.get('master_metadata_album_artist_name') or entry.get('artistName')
            track_name = entry.get('master_metadata_track_name') or entry.get('trackName')

            if not track_id and not track_name:
                continue

            # Parse timestamp (e.g., "2023-11-20T18:32:00Z" or "2023-11-20 18:32")
            try:
                if 'T' in ts_str:
                    dt = datetime.strptime(ts_str.split('.')[0].replace('Z', ''), "%Y-%m-%dT%H:%M:%S")
                else:
                    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
            except ValueError:
                continue

            period = (dt.year, dt.month)
            if period not in monthly_data:
                monthly_data[period] = {
                    'tracks': Counter(),
                    'artists': Counter(),
                    'artist_track_map': {}
                }

            # If we have URI, use it as unique identifier
            track_key = track_id if track_id else f"{track_name}||{artist_name}"
            monthly_data[period]['tracks'][track_key] += 1
            if artist_name:
                monthly_data[period]['artists'][artist_name] += 1
            # Track which URIs belong to each artist so we can resolve missing artists later
            if artist_name and track_id and track_id.startswith('spotify:track:'):
                monthly_data[period]['artist_track_map'].setdefault(artist_name, set()).add(track_id)

        return monthly_data

    def resolve_top_items(self, monthly_data, limit=50):
        """For each month, find top items and resolve their full metadata via Spotify API."""
        for (year, month), counts in monthly_data.items():
            logger.info("Processing stats for %02d/%d...", month, year)
            
            # 1. Resolve Tracks
            top_track_keys = [item for item, count in counts['tracks'].most_common(limit)]
            # Filter for keys that are URIs (spotify:track:ID)
            track_ids = [key.split(':')[-1] for key in top_track_keys if key.startswith('spotify:track:')]
            
            resolved_tracks = []
            if track_ids:
                # Batch fetch metadata
                for i in range(0, len(track_ids), 50):
                    batch = track_ids[i:i+50]
                    resolved_tracks.extend(self.spotify_api_manager.get_tracks_batch(batch))
            
            if not resolved_tracks:
                logger.warning("No tracks resolved for %02d/%d. Skipping month.", month, year)
                continue

            # 2. Resolve Artists
            # We need to get artist IDs from the resolved tracks to fetch full artist metadata (genres, images)
            artist_ids = list(set([artist.artist_id for track in resolved_tracks for artist in track.artists]))
            resolved_artists_map = {}
            if artist_ids:
                for i in range(0, len(artist_ids), 50):
                    batch = artist_ids[i:i+50]
                    artists = self.spotify_api_manager.get_artists_batch(batch)
                    for a in artists:
                        resolved_artists_map[a.artist_id] = a

            # Map the resolved artists back to the tracks to ensure consistency
            for track in resolved_tracks:
                new_artists = []
                for a in track.artists:
                    if a.artist_id in resolved_artists_map:
                        new_artists.append(resolved_artists_map[a.artist_id])
                    else:
                        new_artists.append(a)
                track.artists = new_artists

            # Build a name → Artist lookup from what we already resolved via tracks
            name_to_artist = {a.name: a for a in resolved_artists_map.values()}

            top_artist_names = [name for name, _ in counts['artists'].most_common(limit)]

            # Find artists in the top list whose metadata we don't have yet
            missing_names = [name for name in top_artist_names if name not in name_to_artist]
            if missing_names:
                artist_track_map = counts.get('artist_track_map', {})
                # Collect one sample track URI per missing artist
                sample_track_ids = []
                for name in missing_names:
                    uris = artist_track_map.get(name, set())
                    for uri in uris:
                        track_id_str = uri.split(':')[-1]
                        sample_track_ids.append(track_id_str)
                        break  # one sample per artist is enough

                sample_track_ids = list(set(sample_track_ids))
                if sample_track_ids:
                    sample_tracks = []
                    for i in range(0, len(sample_track_ids), 50):
                        sample_tracks.extend(
                            self.spotify_api_manager.get_tracks_batch(sample_track_ids[i:i+50])
                        )

                    # Extract artist IDs for missing artists from those sample tracks
                    new_artist_ids = []
                    for track in sample_tracks:
                        for artist in track.artists:
                            if artist.name in missing_names and artist.artist_id not in resolved_artists_map:
                                new_artist_ids.append(artist.artist_id)

                    new_artist_ids = list(set(new_artist_ids))
                    if new_artist_ids:
                        for i in range(0, len(new_artist_ids), 50):
                            for a in self.spotify_api_manager.get_artists_batch(new_artist_ids[i:i+50]):
                                resolved_artists_map[a.artist_id] = a
                                name_to_artist[a.name] = a

                still_missing = [n for n in missing_names if n not in name_to_artist]
                if still_missing:
                    logger.warning(
                        "Could not resolve %d artists for %02d/%d: %s",
                        len(still_missing), month, year, still_missing[:5]
                    )

            final_top_artists = [name_to_artist[name] for name in top_artist_names if name in name_to_artist]
            
            # 3. Create Monthly Objects
            top_tracks_obj = MonthlyTopTracks(resolved_tracks, month=month, year=year)
            top_artists_obj = MonthlyTopArtists(final_top_artists, month=month, year=year)
            top_albums_obj = MonthlyTopAlbums(resolved_tracks, month=month, year=year)
            top_genres_obj = MonthlyTopGenres(final_top_artists, month=month, year=year)

            # 4. Insert into DB
            logger.info("Inserting resolved data into database for %02d/%d...", month, year)
            self.database_manager.insert_top_tracks_into_db(top_tracks_obj)
            self.database_manager.insert_top_artists_into_db(top_artists_obj)
            self.database_manager.insert_top_albums_into_db(top_albums_obj)
            self.database_manager.insert_top_genres_into_db(top_genres_obj)

        logger.info("Import process complete.")
