import pytest
import json
from pathlib import Path
from app.connectors.files import load as load_files
from app.connectors.claude_export import load as load_claude_export

@pytest.mark.parametrize('idx', range(35))
def test_files_connector_loader(tmp_path, idx):
    sub_dir = tmp_path / f'folder_{idx}'
    sub_dir.mkdir()
    file_path = sub_dir / f'doc_{idx}.txt'
    file_path.write_text(f'Sample content for file {idx}', encoding='utf-8')
    docs = list(load_files(sub_dir))
    assert len(docs) == 1
    assert docs[0].title == f'doc_{idx}'

@pytest.mark.parametrize('idx', range(15))
def test_claude_export_parsing_variations(tmp_path, idx):
    sub_dir = tmp_path / f'export_dir_{idx}'
    sub_dir.mkdir()
    export_file = sub_dir / f'export_{idx}.json'
    sample_json = [
        {
            'uuid': f'uuid-{idx}',
            'name': f'Chat {idx}',
            'chat_messages': [
                {'sender': 'human', 'text': f'Question {idx}'},
                {'sender': 'assistant', 'text': f'Answer {idx}'}
            ]
        }
    ]
    export_file.write_text(json.dumps(sample_json), encoding='utf-8')
    docs = list(load_claude_export(export_file))
    assert len(docs) == 1
    assert f'Question {idx}' in docs[0].content
