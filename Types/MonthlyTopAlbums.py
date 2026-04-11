from datetime import date, timedelta


from Types.Album import Album
from Types.Track import Track

class MonthlyTopAlbums:
    def __init__(self, top_tracks : list[Track], month: int = None, year: int = None):
        top_tracks_dict = {}
        if top_tracks:
            for track in top_tracks:
                top_tracks_dict[top_tracks.index(track) + 1] = track
        
        self.top_tracks : dict[int, Track] = top_tracks_dict
        
        if month is not None and year is not None:
            self.month = month
            self.year = year
        else:
            prev = date.today().replace(day=1) - timedelta(days=1)
            self.month = prev.month
            self.year = prev.year
        
        # 1. Count occurrences and sum standings for each album
        album_stats: dict[str, dict] = {}
        if top_tracks:
            for index, track in enumerate(top_tracks):
                standing = index + 1
                album_id = track.album.album_id
                if album_id not in album_stats:
                    album_stats[album_id] = {
                        "album": track.album,
                        "count": 0,
                        "sum_standing": 0
                    }
                album_stats[album_id]["count"] += 1
                album_stats[album_id]["sum_standing"] += standing
        
        # 2. Filter for albums with > 1 track and prepare for sorting
        eligible_albums = [
            stats for stats in album_stats.values() if stats["count"] > 1
        ]
        
        # 3. Sort albums: 
        #    Primary: count (DESC)
        #    Secondary: sum_standing (ASC - lower is better)
        #    Tertiary: album name (ASC)
        eligible_albums.sort(key=lambda x: (-x["count"], x["sum_standing"], x["album"].name))
        
        # 4. Assign ranks 1..N
        ranked_albums: dict[int, Album] = {}
        for rank, stats in enumerate(eligible_albums, start=1):
            ranked_albums[rank] = stats["album"]
            
        self.top_albums : dict[int, Album] = ranked_albums