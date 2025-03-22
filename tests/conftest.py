import os

import pytest

pytest_plugins = "pytester"
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"


@pytest.fixture
def fixture_for_inspection(request):
    breakpoint()
