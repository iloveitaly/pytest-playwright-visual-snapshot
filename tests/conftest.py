import pytest

pytest_plugins = "pytester"


@pytest.fixture
def fixture_for_inspection(request):
    "for inspecting `request`"
    breakpoint()
