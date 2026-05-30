import logging
import sys
import os
from Managers.DatabaseManager import DatabaseManager
from Managers.SpotifyAPIManager import SpotifyAPIManager
from Managers.HistoryImportManager import HistoryImportManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

def main():
    if len(sys.argv) < 2:
        print("Usage: python import_history.py <directory_with_json_files> [--cutoff YYYY-MM]")
        sys.exit(1)

    data_dir = sys.argv[1]
    if not os.path.isdir(data_dir):
        logger.error("Directory not found: %s", data_dir)
        sys.exit(1)

    cutoff = None
    if '--cutoff' in sys.argv:
        idx = sys.argv.index('--cutoff')
        if idx + 1 >= len(sys.argv):
            logger.error("--cutoff requires a YYYY-MM argument")
            sys.exit(1)
        raw = sys.argv[idx + 1]
        try:
            cutoff_year, cutoff_month = int(raw[:4]), int(raw[5:7])
            cutoff = (cutoff_year, cutoff_month)
            logger.info("Cutoff: only importing months up to %04d-%02d", cutoff_year, cutoff_month)
        except (ValueError, IndexError):
            logger.error("Invalid --cutoff value '%s'. Expected YYYY-MM format.", raw)
            sys.exit(1)

    logger.info("=== Starting Spotify Historical Data Import ===")

    try:
        database_manager = DatabaseManager()
        spotify_api_manager = SpotifyAPIManager(database_manager)
        import_manager = HistoryImportManager(spotify_api_manager, database_manager)

        logger.info("Scanning for history files in: %s", data_dir)
        entries = import_manager.parse_history_files(data_dir)

        if not entries:
            logger.error("No entries found to process.")
            return

        logger.info("Aggregating entries by month...")
        monthly_data = import_manager.aggregate_by_month(entries)

        if cutoff:
            before = len(monthly_data)
            monthly_data = {period: data for period, data in monthly_data.items() if period <= cutoff}
            logger.info("Filtered from %d to %d months (cutoff %04d-%02d).", before, len(monthly_data), cutoff[0], cutoff[1])

        logger.info("Found data for %d months.", len(monthly_data))

        logger.info("Resolving top items and importing to database...")
        import_manager.resolve_top_items(monthly_data)

        logger.info("=== Historical Data Import Complete ===")

    except Exception as e:
        logger.exception("An error occurred during import: %s", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
