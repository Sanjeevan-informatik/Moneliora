"""Run daily: python -m moneliora.maintenance. Uses MONELIORA_DB."""
from moneliora.settings import Settings
from moneliora.services.pilot import connect, prune, now
from moneliora.database import connect_database
from moneliora import security


def main():
    with connect(Settings().database) as db:
        deleted = prune(db, now())
    with connect_database(Settings().database, security.SCHEMA) as db:
        security.cleanup(db)
    print(f'Expired pilot requests deleted: {deleted}')

if __name__ == '__main__':
    main()
