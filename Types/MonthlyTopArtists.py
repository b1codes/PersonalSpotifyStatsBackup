from datetime import date, timedelta

from Types.Artist import Artist

class MonthlyTopArtists:
    def __init__(self, top_artists: list[Artist], month: int = None, year: int = None):
        top_artists_dict = {}
        for artist in top_artists:
            top_artists_dict[top_artists.index(artist) + 1] = artist
        self.top_artists : dict[int, Artist] = top_artists_dict
        
        if month is not None and year is not None:
            self.month = month
            self.year = year
        else:
            prev = date.today().replace(day=1) - timedelta(days=1)
            self.month = prev.month
            self.year = prev.year
        