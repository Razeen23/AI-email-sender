import os
import tempfile

import pytest
from cryptography.fernet import Fernet

os.environ["MARKET_DATA_DIR"] = tempfile.mkdtemp(prefix="market-test-")
os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["SEND_DELAY_SECONDS"] = "0"
os.environ["DAILY_SEND_CAP"] = "25"
os.environ["OLLAMA_BASE_URL"] = "http://127.0.0.1:9"
os.environ["OLLAMA_MODEL"] = "test-model"


@pytest.fixture(scope="session", autouse=True)
def database():
    from backend.db import init_db

    init_db()
