"""
Wipes all items from the four DynamoDB stat tables.
Reads table names from env vars (with the same defaults as DatabaseManager).
Does NOT drop or modify the tables themselves — schema and Terraform state are preserved.

Usage:
    python scripts/wipe_dynamodb.py [--confirm]

Pass --confirm to skip the interactive prompt (for non-interactive use).
"""
import boto3
import logging
import os
import sys
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("wipe_dynamodb")

TABLE_ENV_VARS = [
    ('DYNAMODB_TABLE_TRACKS',  'PersonalSpotifyStatsBackup-tracks'),
    ('DYNAMODB_TABLE_ARTISTS', 'PersonalSpotifyStatsBackup-artists'),
    ('DYNAMODB_TABLE_ALBUMS',  'PersonalSpotifyStatsBackup-albums'),
    ('DYNAMODB_TABLE_GENRES',  'PersonalSpotifyStatsBackup-genres'),
]


def wipe_table(table):
    """Scan and delete every item in a DynamoDB table."""
    key_schema = table.key_schema
    key_names = [k['AttributeName'] for k in key_schema]
    logger.info("Wiping table '%s' (keys: %s)...", table.name, key_names)

    deleted = 0
    scan_kwargs = {'ProjectionExpression': ', '.join(f'#k{i}' for i in range(len(key_names))),
                   'ExpressionAttributeNames': {f'#k{i}': key_names[i] for i in range(len(key_names))}}

    while True:
        response = table.scan(**scan_kwargs)
        items = response.get('Items', [])
        if not items:
            break

        with table.batch_writer() as batch:
            for item in items:
                key = {k: item[k] for k in key_names}
                batch.delete_item(Key=key)
                deleted += 1

        last_key = response.get('LastEvaluatedKey')
        if not last_key:
            break
        scan_kwargs['ExclusiveStartKey'] = last_key

    logger.info("Deleted %d items from '%s'.", deleted, table.name)
    return deleted


def main():
    skip_confirm = '--confirm' in sys.argv

    region = os.getenv('AWS_DEFAULT_REGION', 'us-east-2')
    dynamodb = boto3.resource('dynamodb', region_name=region)

    table_names = [os.getenv(env_var, default) for env_var, default in TABLE_ENV_VARS]

    logger.info("Tables to wipe in region %s:", region)
    for name in table_names:
        logger.info("  - %s", name)

    if not skip_confirm:
        answer = input("\nThis will permanently delete ALL items from these tables. Type 'yes' to proceed: ")
        if answer.strip().lower() != 'yes':
            logger.info("Aborted.")
            sys.exit(0)

    total = 0
    for name in table_names:
        table = dynamodb.Table(name)
        total += wipe_table(table)

    logger.info("Wipe complete. Total items deleted: %d", total)


if __name__ == "__main__":
    main()
