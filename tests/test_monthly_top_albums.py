import os
import sys
import unittest
from datetime import date
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Types.Album import Album
from Types.Artist import Artist
from Types.Track import Track
from Types.MonthlyTopAlbums import MonthlyTopAlbums


def _album(name, album_id):
    return Album(
        name=name,
        album_id=album_id,
        album_type="album",
        images=[],
        artists=[],
        release_date="2024-01-01",
    )


def _track(name, album, track_id=None):
    return Track(
        name=name,
        track_id=track_id or name,
        duration=180000,
        explicit=False,
        disc_number=1,
        track_number=1,
        popularity=80,
        artists=[],
        album=album,
    )


class TestMonthlyTopAlbumsExclusion(unittest.TestCase):
    def test_empty_list_produces_no_albums(self):
        result = MonthlyTopAlbums([], month=1, year=2024)
        self.assertEqual(result.top_albums, {})

    def test_all_single_track_albums_excluded(self):
        tracks = [_track(f"T{i}", _album(f"Album{i}", f"alb{i}"), f"t{i}") for i in range(10)]
        result = MonthlyTopAlbums(tracks, month=1, year=2024)
        self.assertEqual(result.top_albums, {})

    def test_album_with_exactly_one_track_excluded(self):
        solo = _album("Solo", "alb_solo")
        multi = _album("Multi", "alb_multi")
        tracks = [
            _track("T1", solo, "t1"),
            _track("T2", multi, "t2"),
            _track("T3", multi, "t3"),
        ]
        result = MonthlyTopAlbums(tracks, month=1, year=2024)
        album_ids = [a.album_id for a in result.top_albums.values()]
        self.assertNotIn("alb_solo", album_ids)

    def test_album_with_exactly_two_tracks_included(self):
        alb = _album("TwoTrack", "alb_two")
        tracks = [_track("T1", alb, "t1"), _track("T2", alb, "t2")]
        result = MonthlyTopAlbums(tracks, month=1, year=2024)
        self.assertEqual(len(result.top_albums), 1)
        self.assertEqual(result.top_albums[1].album_id, "alb_two")


class TestMonthlyTopAlbumsRanking(unittest.TestCase):
    def test_primary_sort_count_descending(self):
        # alb_many: 3 tracks at positions 8,9,10 (high standings, bad sum)
        # alb_few:  2 tracks at positions 1,2   (low standings, great sum)
        # Count takes priority — alb_many must rank first despite worse sum.
        alb_many = _album("Many", "alb_many")
        alb_few = _album("Few", "alb_few")
        fillers = [_album(f"D{i}", f"d{i}") for i in range(6)]
        tracks = [
            _track("F1", alb_few, "f1"),
            _track("F2", alb_few, "f2"),
            _track("D1", fillers[0], "d1"),
            _track("D2", fillers[1], "d2"),
            _track("D3", fillers[2], "d3"),
            _track("D4", fillers[3], "d4"),
            _track("D5", fillers[4], "d5"),
            _track("M1", alb_many, "m1"),
            _track("M2", alb_many, "m2"),
            _track("M3", alb_many, "m3"),
        ]
        result = MonthlyTopAlbums(tracks, month=1, year=2024)
        self.assertEqual(result.top_albums[1].album_id, "alb_many")
        self.assertEqual(result.top_albums[2].album_id, "alb_few")

    def test_secondary_sort_sum_standing_ascending(self):
        # alb_low_sum: name="Zulu", standings 1+2=3  — should rank first
        # alb_hi_sum:  name="Alpha", standings 3+4=7 — should rank second
        # Names deliberately oppose sum order: without sum logic, alphabetical
        # fallback would rank "Alpha" first. Only correct sum logic ranks "Zulu" first.
        alb_low_sum = _album("Zulu", "alb_low_sum")
        alb_hi_sum = _album("Alpha", "alb_hi_sum")
        tracks = [
            _track("Z1", alb_low_sum, "z1"),  # standing 1
            _track("Z2", alb_low_sum, "z2"),  # standing 2 — sum = 3
            _track("A1", alb_hi_sum, "a1"),   # standing 3
            _track("A2", alb_hi_sum, "a2"),   # standing 4 — sum = 7
        ]
        result = MonthlyTopAlbums(tracks, month=1, year=2024)
        self.assertEqual(result.top_albums[1].album_id, "alb_low_sum")
        self.assertEqual(result.top_albums[2].album_id, "alb_hi_sum")

    def test_tertiary_sort_album_name_ascending(self):
        # Both albums: count=2, sum=5. Only name can break the tie.
        alb_a = _album("Aardvark", "alb_a")
        alb_b = _album("Bison", "alb_b")
        tracks = [
            _track("A1", alb_a, "a1"),  # standing 1 — alb_a sum: 1
            _track("B1", alb_b, "b1"),  # standing 2 — alb_b sum: 2
            _track("B2", alb_b, "b2"),  # standing 3 — alb_b sum: 5
            _track("A2", alb_a, "a2"),  # standing 4 — alb_a sum: 5
        ]
        result = MonthlyTopAlbums(tracks, month=1, year=2024)
        self.assertEqual(result.top_albums[1].album_id, "alb_a")  # "Aardvark" < "Bison"
        self.assertEqual(result.top_albums[2].album_id, "alb_b")

    def test_ranks_are_consecutive_from_one(self):
        alb_a = _album("AlbumA", "a")
        alb_b = _album("AlbumB", "b")
        alb_c = _album("AlbumC", "c")
        tracks = [
            _track("A1", alb_a, "a1"), _track("A2", alb_a, "a2"),
            _track("B1", alb_b, "b1"), _track("B2", alb_b, "b2"),
            _track("C1", alb_c, "c1"), _track("C2", alb_c, "c2"),
        ]
        result = MonthlyTopAlbums(tracks, month=1, year=2024)
        self.assertEqual(sorted(result.top_albums.keys()), [1, 2, 3])

    def test_all_tracks_same_album(self):
        alb = _album("OneAlbum", "solo")
        tracks = [_track(f"T{i}", alb, f"t{i}") for i in range(5)]
        result = MonthlyTopAlbums(tracks, month=1, year=2024)
        self.assertEqual(len(result.top_albums), 1)
        self.assertEqual(result.top_albums[1].album_id, "solo")

    def test_standing_based_on_list_position(self):
        # Track at position 0 → standing 1, which should have lower sum_standing.
        alb_early = _album("Early", "early")
        alb_late = _album("Late", "late")
        tracks = [
            _track("E1", alb_early, "e1"),  # standing 1
            _track("E2", alb_early, "e2"),  # standing 2 — sum = 3
            _track("L1", alb_late, "l1"),   # standing 3
            _track("L2", alb_late, "l2"),   # standing 4 — sum = 7
        ]
        result = MonthlyTopAlbums(tracks, month=1, year=2024)
        self.assertEqual(result.top_albums[1].album_id, "early")


class TestMonthlyTopAlbumsDateHandling(unittest.TestCase):
    def test_explicit_month_and_year_stored(self):
        result = MonthlyTopAlbums([], month=6, year=2023)
        self.assertEqual(result.month, 6)
        self.assertEqual(result.year, 2023)

    def test_default_date_is_previous_month(self):
        fixed_today = date(2024, 3, 15)
        with patch("Types.MonthlyTopAlbums.date") as mock_date:
            mock_date.today.return_value = fixed_today
            result = MonthlyTopAlbums([])
        self.assertEqual(result.month, 2)
        self.assertEqual(result.year, 2024)

    def test_default_date_rolls_year_back_in_january(self):
        fixed_today = date(2024, 1, 10)
        with patch("Types.MonthlyTopAlbums.date") as mock_date:
            mock_date.today.return_value = fixed_today
            result = MonthlyTopAlbums([])
        self.assertEqual(result.month, 12)
        self.assertEqual(result.year, 2023)


if __name__ == "__main__":
    unittest.main()
