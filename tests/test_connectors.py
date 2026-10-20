import json

from app.connectors.claude_export import load as load_claude_export
from app.connectors.files import load as load_files


def test_claude_export_old_format(tmp_path):
    export = [
        {
            "name": "Steuer-Fragen",
            "created_at": "2026-01-01T10:00:00Z",
            "chat_messages": [
                {"sender": "human", "text": "Wie funktioniert die Abschreibung?"},
                {"sender": "assistant", "text": "Grundsätzlich linear über die Nutzungsdauer."},
            ],
        }
    ]
    path = tmp_path / "conversations.json"
    path.write_text(json.dumps(export), encoding="utf-8")

    docs = list(load_claude_export(path))
    assert len(docs) == 1
    assert docs[0].title == "Steuer-Fragen"
    assert "Mensch: Wie funktioniert" in docs[0].content
    assert "Assistent: Grundsätzlich" in docs[0].content


def test_claude_export_new_format_content_blocks(tmp_path):
    export = [
        {
            "title": "Neues Format",
            "chat_messages": [
                {
                    "sender": "human",
                    "content": [{"type": "text", "text": "Hallo Claude"}],
                },
                {
                    "sender": "assistant",
                    "content": [
                        {"type": "text", "text": "Hallo!"},
                        {"type": "tool_use", "name": "x"},
                    ],
                },
            ],
        }
    ]
    path = tmp_path / "conversations.json"
    path.write_text(json.dumps(export), encoding="utf-8")

    docs = list(load_claude_export(path))
    assert len(docs) == 1
    assert "Mensch: Hallo Claude" in docs[0].content
    assert "Assistent: Hallo!" in docs[0].content


def test_claude_export_skips_empty_conversations(tmp_path):
    export = [{"name": "Leer", "chat_messages": []}, "kein-dict"]
    path = tmp_path / "conversations.json"
    path.write_text(json.dumps(export), encoding="utf-8")
    assert list(load_claude_export(path)) == []


def test_files_connector_reads_directory(tmp_path):
    (tmp_path / "a.md").write_text("# Notiz A\nInhalt", encoding="utf-8")
    (tmp_path / "b.txt").write_text("Inhalt B", encoding="utf-8")
    (tmp_path / "ignored.xyz").write_text("egal", encoding="utf-8")
    sub = tmp_path / ".versteckt"
    sub.mkdir()
    (sub / "c.md").write_text("versteckt", encoding="utf-8")

    docs = list(load_files(tmp_path))
    titles = {d.title for d in docs}
    assert titles == {"a", "b"}
