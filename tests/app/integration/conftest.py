import gc

import pytest
import pytest_asyncio
from nicegui.testing import User
from nicegui.testing.general_fixtures import get_path_to_main_file
from nicegui.testing.user_simulation import user_simulation


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def default_page(request) -> User:
    async with user_simulation(main_file=get_path_to_main_file(request)) as built:
        await built.open("/")
    yield built


@pytest.fixture(autouse=True)
def _collect_render_garbage():
    yield
    gc.collect()
