"""Run daily: python -m moneliora.maintenance. Uses MONELIORA_DB."""
from moneliora.settings import Settings
from moneliora.services.pilot import connect, prune, now


def main():
    with connect(Settings().database) as db:
        deleted = prune(db, now())
    print(f'Expired pilot requests deleted: {deleted}')

if __name__ == '__main__':
    main()
