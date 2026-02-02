import pytest
import asyncio
from src.agents.asset_management.utils import WorkingCopyManager

@pytest.fixture
def test_file(tmp_path):
    f = tmp_path / "original.md"
    f.write_text("# Original Content")
    return f

@pytest.mark.asyncio
async def test_working_copy_lifecycle(test_file):
    manager = WorkingCopyManager(test_file)
    
    # 1. Start session (creates .working)
    working_path = manager.start_session()
    assert working_path.exists()
    assert working_path.name == "original.md.working"
    assert working_path.read_text() == "# Original Content"
    
    # 2. Incremental update
    await manager.update_content("# Updated Content")
    assert working_path.read_text() == "# Updated Content"
    assert test_file.read_text() == "# Original Content" # Original untouched
    
    # 3. Commit
    manager.commit()
    assert not working_path.exists()
    assert test_file.read_text() == "# Updated Content"

@pytest.mark.asyncio
async def test_working_copy_resume(test_file):
    # Simulate a crash happened, .working already exists
    working_path = test_file.with_suffix(test_file.suffix + ".working")
    working_path.write_text("# Recovered Content")
    
    manager = WorkingCopyManager(test_file)
    actual_path = manager.start_session()
    
    assert actual_path == working_path
    assert actual_path.read_text() == "# Recovered Content" # Resumed from existing

@pytest.mark.asyncio
async def test_concurrent_updates(test_file):
    manager = WorkingCopyManager(test_file)
    manager.start_session()
    
    # Simulate many parallel workers trying to update
    async def task(i):
        # In real scenario, they would read current and replace a slice
        # Here we just test the lock mechanism by appending
        async with manager._lock:
            current = (await asyncio.to_thread(manager.working_path.read_text))
            new = current + f"\nUpdate {i}"
            (await asyncio.to_thread(manager.working_path.write_text, new))

    await asyncio.gather(*(task(i) for i in range(10)))
    
    content = test_file.with_suffix(test_file.suffix + ".working").read_text()
    assert len(content.split('\n')) == 11
