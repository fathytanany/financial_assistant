import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from make_fixture import FIXTURE, build  # noqa: E402


@pytest.fixture(scope="session")
def fixture_backup() -> Path:
    if not FIXTURE.exists():
        build(FIXTURE)
    return FIXTURE
