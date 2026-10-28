"""Each test gets a disposable database, independent of import order or local data."""
import pytest

@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    import main
    import platform_features
    database = tmp_path / 'test.db'
    monkeypatch.setattr(main, 'DB', database)
    monkeypatch.setattr(platform_features, 'DB', database)
    main.requests_by_client.clear()
