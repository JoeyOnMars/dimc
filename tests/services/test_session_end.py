"""
测试 SessionEndService Auto-Embedding 功能 (Task 013)

覆盖用例：
1. test_auto_embed_batch_success - 批量写入成功
2. test_auto_embed_partial_failure - 部分失败降级
3. test_auto_embed_no_event_vectors_table - 表不存在静默返回
4. test_auto_embed_release_model_called - 释放模型验证
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestAutoEmbedding:
    """测试 Auto-Embedding 功能"""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """创建临时数据库并初始化 schema"""
        db_path = tmp_path / "test_index.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 创建 events 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                type TEXT,
                timestamp TEXT,
                summary TEXT,
                content TEXT,
                json_cache TEXT,
                source TEXT
            )
        """)

        # 不创建 event_vectors 表（模拟首次运行场景）
        conn.commit()
        conn.close()

        return str(db_path)

    @pytest.fixture
    def mock_event(self):
        """创建模拟 Event 对象"""
        from dimcause.core.models import Event, EventType

        return Event(
            id="test_event_001",
            type=EventType.DECISION,
            timestamp=datetime.now(),
            summary="Test Event Summary",
            content="Test Event Content for embedding",
            status="active",
            tags=[],
        )

    @patch("dimcause.services.session_end.VectorStore")
    def test_auto_embed_batch_success(self, mock_vector_store_cls, mock_event, temp_db):
        """测试：批量写入成功时，add_batch 被调用一次，add 未被调用"""
        # Setup mock VectorStore
        mock_vector_store = MagicMock()
        mock_vector_store_cls.return_value = mock_vector_store

        # 插入孤儿事件到 events 表（json_cache 存在）
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO events (id, type, timestamp, summary, content, json_cache) VALUES (?, ?, ?, ?, ?, ?)",
            (
                mock_event.id,
                mock_event.type.value,
                mock_event.timestamp.isoformat(),
                mock_event.summary,
                mock_event.content,
                mock_event.model_dump_json(),
            ),
        )
        conn.commit()
        conn.close()

        # 创建 SessionEndService 并调用 _auto_embed_recent_events
        from dimcause.services.session_end import SessionEndService

        service = SessionEndService()
        service._auto_embed_recent_events(limit=10)

        # 断言：add_batch 被调用，add 未被调用
        mock_vector_store.add_batch.assert_called_once()
        mock_vector_store.add.assert_not_called()

    @patch("dimcause.services.session_end.VectorStore")
    def test_auto_embed_partial_failure(self, mock_vector_store_cls, mock_event, temp_db):
        """测试：add_batch 抛异常时，降级调用 add，dimc down 不中断"""
        # Setup mock VectorStore：add_batch 抛异常，add 成功
        mock_vector_store = MagicMock()
        mock_vector_store.add_batch.side_effect = Exception("Batch failed")
        mock_vector_store.add.return_value = "event_id"
        mock_vector_store_cls.return_value = mock_vector_store

        # 插入孤儿事件
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO events (id, type, timestamp, summary, content, json_cache) VALUES (?, ?, ?, ?, ?, ?)",
            (
                mock_event.id,
                mock_event.type.value,
                mock_event.timestamp.isoformat(),
                mock_event.summary,
                mock_event.content,
                mock_event.model_dump_json(),
            ),
        )
        conn.commit()
        conn.close()

        # 调用
        from dimcause.services.session_end import SessionEndService

        service = SessionEndService()
        # 这应该不会抛出异常
        service._auto_embed_recent_events(limit=10)

        # 断言：add_batch 失败后降级调用 add（至少一次）
        mock_vector_store.add_batch.assert_called_once()
        mock_vector_store.add.assert_called()

    @patch("dimcause.services.session_end.VectorStore")
    def test_auto_embed_no_event_vectors_table(self, mock_vector_store_cls):
        """测试：event_vectors 表不存在时，方法静默返回，不抛出异常"""
        # 真实场景：临时目录只有 events 表，没有 event_vectors 表
        # CREATE TABLE IF NOT EXISTS 正常执行后查询孤儿返回空，断言方法静默返回
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # 创建只有 events 表的数据库
            db_path = tmp_path / "index.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    timestamp TEXT,
                    summary TEXT,
                    content TEXT,
                    json_cache TEXT,
                    source TEXT
                )
            """)
            conn.commit()
            conn.close()

            # patch Path.home() 返回临时目录
            with patch("dimcause.services.session_end.Path.home") as mock_home:
                mock_home.return_value = tmp_path

                # 调用
                from dimcause.services.session_end import SessionEndService

                service = SessionEndService()
                # 这应该静默返回，不抛出异常
                service._auto_embed_recent_events(limit=10)

            # 断言：VectorStore 未被实例化（因为没有孤儿事件）
            mock_vector_store_cls.assert_not_called()

    @patch("dimcause.services.session_end.VectorStore")
    def test_auto_embed_release_model_called(self, mock_vector_store_cls, mock_event, temp_db):
        """测试：无论成功/失败，release_model() 都被调用"""
        # Setup mock VectorStore
        mock_vector_store = MagicMock()
        mock_vector_store_cls.return_value = mock_vector_store

        # 插入孤儿事件
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO events (id, type, timestamp, summary, content, json_cache) VALUES (?, ?, ?, ?, ?, ?)",
            (
                mock_event.id,
                mock_event.type.value,
                mock_event.timestamp.isoformat(),
                mock_event.summary,
                mock_event.content,
                mock_event.model_dump_json(),
            ),
        )
        conn.commit()
        conn.close()

        # 第一次测试：成功路径
        from dimcause.services.session_end import SessionEndService

        service = SessionEndService()
        service._auto_embed_recent_events(limit=10)

        # 断言：release_model 被调用
        mock_vector_store.release_model.assert_called()

        # 重置 mock
        mock_vector_store.reset_mock()

        # 第二次测试：失败路径
        mock_vector_store.add_batch.side_effect = Exception("Batch failed")
        mock_vector_store.add.side_effect = Exception("Add failed")

        service2 = SessionEndService()
        service2._auto_embed_recent_events(limit=10)

        # 断言：release_model 仍被调用
        mock_vector_store.release_model.assert_called()
