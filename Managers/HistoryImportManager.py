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
                    'artists': Counter()
                }
            
            # If we have URI, use it as unique identifier
            track_key = track_id if track_id else f"{track_name}||{artist_name}"
            monthly_data[period]['tracks'][track_key] += 1
            if artist_name:
                monthly_data[period]['artists'][artist_name] += 1

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

            # Also prepare a list of top 50 Artists for the month based on play counts
            # (Note: simpler to just use the artists from the top 50 tracks or recalculate)
            # For now, let's take the top artists from the play count aggregation
            top_artist_names = [name for name, count in counts['artists'].most_common(limit)]
            # We need to find the ID for these names. Most will be in our resolved_artists_map.
            final_top_artists = []
            for name in top_artist_names:
                # Find an artist object with this name in our resolved map
                found = next((a for a in resolved_artists_map.values() if a.name == name), None)
                if found:
                    final_top_artists.append(found)
            
            # 3. Create Monthly Objects
            top_tracks_obj = MonthlyTopTracks(resolved_tracks, month=month, year=year)
            top_artists_obj = MonthlyTopArtists(final_top_artists, month=month, year=year)
            top_albums_obj = MonthlyTopAlbums(resolved_tracks, month=month, year=year)

            # 4. Insert into DB
            logger.info("Inserting resolved data into database for %02d/%d...", month, year)
            self.database_manager.insert_top_tracks_into_db(top_tracks_obj)
            self.database_manager.insert_top_artists_into_db(top_artists_obj)
            self.database_manager.insert_top_albums_into_db(top_albums_obj)

        logger.info("Import process complete.")
