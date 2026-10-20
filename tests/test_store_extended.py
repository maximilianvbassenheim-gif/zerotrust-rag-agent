import pytest
from app.memory.store import MemoryStore
from app.memory.ingest import chunk_text

@pytest.mark.parametrize('idx', range(55))
def test_store_memory_isolation_and_search(tmp_path, idx):
    sub_dir = tmp_path / f'db_{idx}'
    sub_dir.mkdir()
    store = MemoryStore(path=sub_dir / 'memory.db')
    added = store.add_chunk(source='test', title=f'Doc{idx}', content=f'Document chunk item{idx} for search validation.')
    assert added is True
    results = store.search(f'item{idx}')
    assert len(results) >= 1
    assert f'item{idx}' in results[0].content

@pytest.mark.parametrize('size,overlap', [
    (100, 10), (200, 20), (500, 50), (1000, 100), (50, 5),
    (300, 30), (400, 40), (600, 60), (700, 70), (800, 80),
    (150, 15), (250, 25), (350, 35), (450, 45), (550, 55)
])
def test_chunking_variations(size, overlap):
    sample_text = 'Hello world testing chunking logic. ' * 50
    chunks = chunk_text(sample_text, size=size, overlap=overlap)
    assert len(chunks) > 0
