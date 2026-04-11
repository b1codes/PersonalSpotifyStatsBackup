import mysql.connector
import os
import json
import logging
from dotenv import load_dotenv

# Add current directory to path so we can import Types and Managers
import sys
sys.path.append(os.getcwd())

from Types.Track import Track
from Types.Album import Album
from Types.Artist import Artist
from Types.Image import Image
from Types.MonthlyTopAlbums import MonthlyTopAlbums
from Managers.DatabaseManager import DatabaseManager

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

def migrate():
    db_manager = DatabaseManager()
    
    # 1. Get all unique (month, year) from tracks table
    db_manager.cursor.execute("SELECT DISTINCT month, year FROM tracks")
    months_years = db_manager.cursor.fetchall()
    
    logger.info(f"Found {len(months_years)} months to process.")
    
    for month, year in months_years:
        logger.info(f"Processing {month}/{year}...")
        
        # 2. Fetch all albums for this month/year to get their full data
        # We need this to recreate Album objects for the new ranking logic and insertion
        db_manager.cursor.execute(
            "SELECT album_id, name, album_type, release_date, images, artist_ids FROM albums WHERE month = %s AND year = %s",
            (month, year)
        )
        album_rows = db_manager.cursor.fetchall()
        album_map = {}
        for row in album_rows:
            aid, name, atype, rdate, imgs_json, art_ids_json = row
            imgs = [Image(url=url, height=None, width=None) for url in json.loads(imgs_json)]
            arts = [Artist(name="", artist_id=art_id) for art_id in json.loads(art_ids_json)]
            album_map[aid] = Album(name=name, album_id=aid, album_type=atype, images=imgs, artists=arts, release_date=rdate)
            
        # 3. Fetch all tracks for this month/year
        db_manager.cursor.execute(
            "SELECT name, track_id, duration_ms, is_explicit, disc_number, track_number, popularity, album_id, artist_ids, standing FROM tracks WHERE month = %s AND year = %s ORDER BY standing ASC",
            (month, year)
        )
        track_rows = db_manager.cursor.fetchall()
        
        tracks = []
        for row in track_rows:
            name, tid, dur, expl, disc, tnum, pop, aid, art_ids_json, standing = row
            # We only need enough info for MonthlyTopAlbums to rank them
            # and enough info to preserve the Album object if it was already in album_map
            if aid in album_map:
                album_obj = album_map[aid]
            else:
                # This album might not have been in the top albums list before (count <= 1)
                # We don't have its full info here, but we can create a placeholder
                # If it becomes a top album now, we might lack some info, but it's unlikely
                # because the threshold (count > 1) is the same.
                album_obj = Album(name="Unknown", album_id=aid, album_type=None, images=[], artists=[], release_date=None)
            
            track = Track(name=name, track_id=tid, duration=dur, explicit=expl, disc_number=disc, track_number=tnum, popularity=pop, artists=[], album=album_obj)
            tracks.append(track)
            
        if not tracks:
            logger.warning(f"No tracks found for {month}/{year}, skipping.")
            continue
            
        # 4. Re-calculate standings using the new logic
        new_top_albums = MonthlyTopAlbums(tracks, month=int(month), year=year)
        
        # 5. Delete existing albums for this month/year
        logger.info(f"  Deleting old album records for {month}/{year}...")
        db_manager.cursor.execute(
            "DELETE FROM albums WHERE month = %s AND year = %s",
            (str(month), year)
        )
        
        # 6. Insert new albums with proper standings
        logger.info(f"  Inserting {len(new_top_albums.top_albums)} ranked albums...")
        db_manager.insert_top_albums_into_db(new_top_albums)
        
    logger.info("Migration complete!")

if __name__ == "__main__":
    migrate()
