"""
测试 VectorStore 向量存储扩展

SEARCH-001 v5.2

注意: 使用假模型（返回固定维度随机向量）以避免加载真实模型。
"""

import sqlite3
import tempfile

import numpy as np
import pytest


class MockChunk:
    """模拟 Chunk 对象"""

    def __init__(self, event_id: str, seq: int, pos: int, text: str, token_count: int):
        self.event_id = event_id
        self.seq = seq
        self.pos = pos
        self.text = text
        self.token_count = token_count


class TestVectorStoreExtension:
    """测试 VectorStore 的 SQLite 向量操作扩展"""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """创建临时数据库并初始化 schema"""
        db_path = tmp_path / "test_index.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 创建必要的表（简化版，不使用 vec0）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                type TEXT,
                timestamp TEXT,
                summary TEXT,
                content TEXT,
                source TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_vectors (
                event_id    TEXT    NOT NULL,
                chunk_seq   INTEGER NOT NULL,
                chunk_pos   INTEGER NOT NULL,
                chunk_text  TEXT    NOT NULL,
                embedding   BLOB    NOT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (event_id, chunk_seq)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vector_metadata (
                rowid      INTEGER PRIMARY KEY,
                event_id   TEXT    NOT NULL,
                chunk_seq  INTEGER NOT NULL,
                UNIQUE(event_id, chunk_seq)
            )
        """)

        conn.commit()
        conn.close()

        return str(db_path)

    @pytest.fixture
    def vector_store(self):
        """创建 VectorStore 实例"""
        from dimcause.storage.vector_store import VectorStore

        with tempfile.TemporaryDirectory() as tmpdir:
            # 使用临时目录避免污染真实数据
            store = VectorStore(persist_dir=tmpdir)
            yield store

    @pytest.fixture
    def sample_chunks(self):
        """创建样例分块"""
        return [
            MockChunk(
                event_id="evt_001",
                seq=0,
                pos=0,
                text="This is the first chunk of event 1",
                token_count=8,
            ),
            MockChunk(
                event_id="evt_001",
                seq=1,
                pos=100,
                text="This is the second chunk of event 1",
                token_count=8,
            ),
            MockChunk(
                event_id="evt_002",
                seq=0,
                pos=0,
                text="This is the only chunk of event 2",
                token_count=8,
            ),
        ]

    def test_embed_chunks_returns_correct_count(self, vector_store, sample_chunks):
        """embed_chunks 应返回与输入相同数量的向量"""
        embeddings = vector_store.embed_chunks(sample_chunks)

        assert len(embeddings) == len(sample_chunks)

    def test_embed_chunks_returns_numpy_arrays(self, vector_store, sample_chunks):
        """embed_chunks 返回的每个元素应该是 numpy array"""
        embeddings = vector_store.embed_chunks(sample_chunks)

        for emb in embeddings:
            assert isinstance(emb, np.ndarray)
            assert emb.dtype in [np.float32, np.float64]

    def test_embed_chunks_empty_input(self, vector_store):
        """空输入应返回空列表"""
        embeddings = vector_store.embed_chunks([])

        assert embeddings == []

    def test_store_vectors_writes_to_db(self, vector_store, sample_chunks, temp_db):
        """store_vectors 应将数据写入数据库"""
        # 生成随机向量
        dim = 384
        embeddings = [np.random.rand(dim).astype(np.float32) for _ in sample_chunks]

        # 存储
        stored = vector_store.store_vectors(sample_chunks, embeddings, db_path=temp_db)

        assert stored == len(sample_chunks)

        # 验证数据库中的行数
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM event_vectors")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == len(sample_chunks)

    def test_store_vectors_mismatched_lengths(self, vector_store, sample_chunks, temp_db):
        """chunks 和 embeddings 数量不匹配时应抛出异常"""
        dim = 384
        embeddings = [np.random.rand(dim).astype(np.float32)]  # 只有 1 个

        with pytest.raises(ValueError, match="数量不匹配"):
            vector_store.store_vectors(sample_chunks, embeddings, db_path=temp_db)

    def test_store_vectors_empty_input(self, vector_store, temp_db):
        """空输入应返回 0"""
        stored = vector_store.store_vectors([], [], db_path=temp_db)

        assert stored == 0

    def test_vector_search_returns_event_ids(self, vector_store, sample_chunks, temp_db):
        """vector_search 应返回 event_id 列表"""
        # 存储测试数据
        dim = 384
        embeddings = [np.random.rand(dim).astype(np.float32) for _ in sample_chunks]
        vector_store.store_vectors(sample_chunks, embeddings, db_path=temp_db)

        # 搜索
        query = np.random.rand(dim).astype(np.float32)
        results = vector_store.vector_search(query, top_k=10, db_path=temp_db)

        # 验证结果格式
        assert isinstance(results, list)

        # 每个结果应该是 (event_id, score) 元组
        for result in results:
            assert len(result) == 2
            event_id, score = result
            assert isinstance(event_id, str)
            assert isinstance(score, float)

    def test_vector_search_scores_in_range(self, vector_store, sample_chunks, temp_db):
        """vector_search 返回的分数应在 0.0~1.0 范围内"""
        # 存储测试数据
        dim = 384
        embeddings = [np.random.rand(dim).astype(np.float32) for _ in sample_chunks]
        vector_store.store_vectors(sample_chunks, embeddings, db_path=temp_db)

        # 搜索
        query = np.random.rand(dim).astype(np.float32)
        results = vector_store.vector_search(query, top_k=10, db_path=temp_db)

        for _, score in results:
            assert -1.0 <= score <= 1.0  # 余弦相似度范围

    def test_vector_search_respects_top_k(self, vector_store, temp_db):
        """vector_search 应遵守 top_k 限制"""
        # 创建更多分块
        chunks = [MockChunk(f"evt_{i:03d}", 0, 0, f"Content {i}", 10) for i in range(20)]

        dim = 384
        embeddings = [np.random.rand(dim).astype(np.float32) for _ in chunks]
        vector_store.store_vectors(chunks, embeddings, db_path=temp_db)

        # 搜索 top_k=5
        query = np.random.rand(dim).astype(np.float32)
        results = vector_store.vector_search(query, top_k=5, db_path=temp_db)

        assert len(results) <= 5

    def test_vector_search_nonexistent_db(self, vector_store):
        """搜索不存在的数据库应返回空列表"""
        dim = 384
        query = np.random.rand(dim).astype(np.float32)

        results = vector_store.vector_search(query, top_k=10, db_path="/nonexistent/path/db.sqlite")

        assert results == []
