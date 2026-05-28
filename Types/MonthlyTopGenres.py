from datetime import date, timedelta

from Types.Artist import Artist


class MonthlyTopGenres:
    def __init__(self, top_artists: list[Artist], month: int = None, year: int = None):
        if month is not None and year is not None:
            self.month = month
            self.year = year
        else:
            prev = date.today().replace(day=1) - timedelta(days=1)
            self.month = prev.month
            self.year = prev.year

        genre_counts: dict[str, int] = {}
        if top_artists:
            for artist in top_artists:
                if artist.genres:
                    for genre in artist.genres:
                        genre_counts[genre] = genre_counts.get(genre, 0) + 1

        # Sort: count DESC, then genre name ASC as tiebreaker
        sorted_genres = sorted(genre_counts.items(), key=lambda x: (-x[1], x[0]))

        self.top_genres: dict[int, dict] = {
            rank: {"genre": genre, "count": count}
            for rank, (genre, count) in enumerate(sorted_genres, start=1)
        }
