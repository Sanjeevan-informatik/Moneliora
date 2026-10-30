"""Each test gets disposable data and isolated application settings."""
from dataclasses import replace
import pytest

@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    from main import app
    import moneliora.accounts as accounts
    from moneliora.routes import consultations, pilot
    database = tmp_path / 'test.db'
    monkeypatch.setitem(app.state._state, 'settings', replace(app.state.settings, database=database, admin_token='a'*64, public_preview=False, pilot_only=False, pilot_enabled=False))
    monkeypatch.setattr(accounts, 'DB', database)
    consultations.requests_by_client.clear()
    pilot.HITS.clear()
