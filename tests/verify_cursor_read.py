import json
import sqlite3
import unittest
from pathlib import Path


class TestCursorRead(unittest.TestCase):
    def setUp(self):
        # Create a mock SQLite db
        self.db_path = Path("test_cursor.vscdb")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("CREATE TABLE IF NOT EXISTS ItemTable (key TEXT, value TEXT)")

        # Insert mock chat data (simulating Cursor schema)
        # Cursor usually stores state in JSON structure within 'value'
        chat_data = {
            "tabs": [
                {
                    "bubbles": [
                        {"type": "user", "text": "Hello Cursor"},
                        {"type": "ai", "text": "Hello User"},
                    ]
                }
            ]
        }
        self.conn.execute(
            "INSERT INTO ItemTable (key, value) VALUES (?, ?)",
            ("workbench.panel.aichat.view.state", json.dumps(chat_data)),
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_read_cursor_chat(self):
        """Simulate reading Cursor chat history from SQLite"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Query for chat state
        cursor.execute(
            "SELECT value FROM ItemTable WHERE key = 'workbench.panel.aichat.view.state'"
        )
        row = cursor.fetchone()

        self.assertIsNotNone(row)
        data = json.loads(row[0])

        # Verify content extraction
        bubbles = data["tabs"][0]["bubbles"]
        self.assertEqual(bubbles[0]["text"], "Hello Cursor")
        self.assertEqual(bubbles[1]["text"], "Hello User")

        print(f"[Pass] Successfully extracted {len(bubbles)} messages from mock Cursor DB")


if __name__ == "__main__":
    unittest.main()
