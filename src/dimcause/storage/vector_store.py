"""VectorStore - 向量数据库存储

语义搜索支持，使用 BGE 嵌入模型

模型选型约束:
- 具体模型由 docs/research/RT-000_model_selection_evaluation.md 定义
- 业务代码禁止硬编码模型路径
- 通过 get_model_config() 获取配置
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

from ..core.models import Event, ModelConfig, get_model_config
from ..extractors.chunking import Chunk

logger = logging.getLogger(__name__)


class VectorStore:
    """
    向量存储（已迁移至 SQLite + sqlite-vec）

    实现 IVectorStore 接口

    不再使用 ChromaDB。

    支持的嵌入模型 (参见 RT-000 模型选型评估):
    - 模式 A (Performance): Jina v3
    - 模式 B (Trust): BGE-M3
    - 模式 C (Geek): GTE-Qwen2
    - 当前默认值由 `get_model_config()` 决定；live 默认是 TRUST / BGE-M3
    """

    def __init__(
        self,
        persist_dir: str = "~/.dimcause/chroma",
        embedding_model: Optional[str] = None,
        model_config: Optional[ModelConfig] = None,
        db_path: Optional[str] = None,
    ):
        # 优先使用 ModelConfig，其次使用显式参数
        if model_config is None:
            model_config = get_model_config()

        self._model_config = model_config

        # 从 ModelConfig 获取模型名称（不再使用硬编码 fallback）
        if embedding_model:
            self.embedding_model_name = embedding_model
        elif model_config.embed_model:
            self.embedding_model_name = model_config.embed_model
        else:
            self.embedding_model_name = "BAAI/bge-m3"  # 安全默认（多语言）

        # 兼容旧参数 persist_dir，但主要使用 db_path
        self.persist_dir = Path(os.path.expanduser(persist_dir))
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # 确定 SQLite DB 路径
        if db_path:
            self.db_path = os.path.expanduser(db_path)
        else:
            # 默认使用 ~/.dimcause/index.db (与 GraphStore 共享)
            self.db_path = os.path.expanduser("~/.dimcause/index.db")
            # 确保父目录存在
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._st_model = None  # Lazy loaded in embed_chunks

    def add(self, event: Event) -> str:
        """添加 Event 到向量库 (SQLite)"""
        # 1. Chunking (Simplified for direct add)
        # In real pipeline, chunking happens before. Here we treat event content as 1 chunk.
        from dimcause.extractors.chunking import Chunk

        text = f"{event.summary}\n\n{event.content}"
        chunk = Chunk(event_id=event.id, seq=0, pos=0, text=text, token_count=len(text) // 4)

        # 2. Embed
        embeddings = self.embed_chunks([chunk])

        # 3. Store
        self.store_vectors([chunk], embeddings)

        return event.id

    def add_batch(self, events: List[Event]) -> None:
        """批量添加 Events 到向量库，一次 forward pass 完成所有 embedding"""
        from dimcause.extractors.chunking import Chunk

        if not events:
            return

        # 1. Chunking - 构造所有 events 的 Chunk
        chunks = []
        for event in events:
            text = f"{event.summary}\n\n{event.content}"
            chunk = Chunk(event_id=event.id, seq=0, pos=0, text=text, token_count=len(text) // 4)
            chunks.append(chunk)

        # 2. Embed - 一次性传入所有 chunks，利用批量推理
        embeddings = self.embed_chunks(chunks)

        # 3. Store - 批量写入
        if embeddings:
            self.store_vectors(chunks, embeddings)

    def search(self, query: str, top_k: int = 10) -> List[Event]:
        """语义搜索 (SQLite)"""
        import sqlite3
        from datetime import datetime

        from dimcause.core.models import EventType
        from dimcause.extractors.chunking import Chunk

        events = []
        try:
            # 1. Embed query (Construct a dummy chunk)
            dummy_chunk = Chunk(
                event_id="query", seq=0, pos=0, text=query, token_count=len(query) // 4
            )
            embeddings = self.embed_chunks([dummy_chunk])
            if not embeddings:
                return []

            query_vec = embeddings[0]

            # 2. Vector Search → 返回 (event_id, score) 列表
            results = self.vector_search(query_vec, top_k=top_k)

            if not results:
                return []

            # 3. 从 EventIndex (events 表) 恢复完整 Event 对象
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            seen_ids = set()  # 去重

            for event_id, _score in results:
                if event_id in seen_ids:
                    continue
                seen_ids.add(event_id)

                try:
                    # 优先：从 events 表的 json_cache 恢复完整 Event
                    cursor.execute(
                        "SELECT json_cache FROM events WHERE id = ? LIMIT 1", (event_id,)
                    )
                    cache_row = cursor.fetchone()

                    if cache_row and cache_row[0]:
                        event = Event.model_validate_json(cache_row[0])
                        events.append(event)
                        continue

                    # 回退：从 event_vectors 取 chunk_text，结合 events 表基础元数据构造 Stub
                    cursor.execute(
                        "SELECT chunk_text FROM event_vectors WHERE event_id = ? LIMIT 1",
                        (event_id,),
                    )
                    chunk_row = cursor.fetchone()
                    content = chunk_row[0] if chunk_row else ""

                    cursor.execute(
                        "SELECT type, timestamp, summary FROM events WHERE id = ? LIMIT 1",
                        (event_id,),
                    )
                    meta_row = cursor.fetchone()

                    if meta_row:
                        try:
                            event_type = EventType(meta_row[0])
                        except (ValueError, KeyError):
                            event_type = EventType.UNKNOWN
                        try:
                            ts = datetime.fromisoformat(meta_row[1])
                        except (ValueError, TypeError):
                            ts = datetime.now()
                        summary = meta_row[2] or content[:100]
                    else:
                        event_type = EventType.UNKNOWN
                        ts = datetime.now()
                        summary = content[:100] + "..." if len(content) > 100 else content

                    event = Event(
                        id=event_id,
                        content=content,
                        timestamp=ts,
                        type=event_type,
                        summary=summary,
                        status="pending",
                        tags=[],
                    )
                    events.append(event)

                except Exception as e:
                    logger.debug(f"VectorStore.search stub restore failed for {event_id}: {e}")
                    continue

            conn.close()

        except Exception as e:
            logger.error(f"VectorStore.search execution failed: {e}")

        finally:
            # 4. 强制释放 MPS/GPU 内存 (遵照 STORAGE_ARCHITECTURE)
            self.release_model()

        return events

    def delete(self, event_id: str) -> bool:
        """删除 Event (SQLite)"""
        import sqlite3

        db_path = self.db_path
        if not os.path.exists(db_path):
            return False

        conn = None
        try:
            conn = sqlite3.connect(db_path)
            conn.isolation_level = "IMMEDIATE"
            cursor = conn.cursor()

            # 1. Find rowids
            cursor.execute("SELECT rowid FROM vector_metadata WHERE event_id = ?", (event_id,))
            rows = cursor.fetchall()
            rowids = [r[0] for r in rows]

            if not rowids:
                conn.rollback()
                return False

            # 2. Delete from vec0 (best-effort if extension/table exists)
            try:
                for rid in rowids:
                    cursor.execute("DELETE FROM vectors_index WHERE rowid = ?", (rid,))
            except Exception:
                pass

            # 3. Delete from metadata & vectors
            cursor.execute("DELETE FROM vector_metadata WHERE event_id = ?", (event_id,))
            cursor.execute("DELETE FROM event_vectors WHERE event_id = ?", (event_id,))

            conn.commit()
            return True
        except Exception as e:
            if conn is not None:
                conn.rollback()
            logger.error(f"Delete failed for event_id={event_id}: {e}")
            return False
        finally:
            if conn is not None:
                conn.close()

    def release_model(self) -> None:
        """
        释放 Embedding 模型，归还 MPS/GPU 内存（用完即释放策略）

        遵循 RT-000 §4.2 设计：Embedding 和 Reranker 不同时驻留内存。
        调用时机：embed_chunks / search 完成后，Reranker 加载前。
        """
        import gc

        if hasattr(self, "_st_model") and self._st_model is not None:
            try:
                # 先移回 CPU，再删除（确保 MPS 内存被释放）
                self._st_model = self._st_model.to("cpu")
            except Exception:
                pass
            del self._st_model
            self._st_model = None
            gc.collect()
            try:
                import torch

                if torch.backends.mps.is_available():
                    torch.mps.empty_cache()
                    torch.mps.synchronize()
            except Exception:
                pass

    @property
    def embedding_model(self) -> str:
        """当前使用的嵌入模型"""
        return self.embedding_model_name

    def stats(self) -> dict:
        """获取统计信息 (SQLite)"""
        import sqlite3

        db_path = self.db_path
        count = 0
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT count(*) FROM event_vectors")
                row = cursor.fetchone()
                if row:
                    count = row[0]
                conn.close()
            except Exception:
                pass

        return {"count": count, "model": self.embedding_model_name, "backend": "sqlite"}

    # =========================================================================
    # SEARCH-001: SQLite-based Vector Operations
    # 以下方法用于 EventIndex 数据库中的向量存储和检索
    # =========================================================================

    def _init_vector_db(self, conn) -> None:
        """初始化向量数据库表结构 (SQLite)"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS event_vectors (
                event_id TEXT,
                chunk_seq INTEGER,
                chunk_pos INTEGER,
                chunk_text TEXT,
                embedding BLOB,
                PRIMARY KEY (event_id, chunk_seq)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS vector_metadata (
                rowid INTEGER PRIMARY KEY,
                event_id TEXT,
                chunk_seq INTEGER
            )
        """)

        # Try to initialize vec0 virtual table
        try:
            import sqlite_vec

            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS vectors_index USING vec0(
                    embedding float[1024]
                )
            """)
        except (ImportError, Exception):
            # print(f"Warning: sqlite-vec not available or failed to init: {e}")
            pass

        conn.commit()

    def embed_chunks(self, chunks: List["Chunk"]) -> List["np.ndarray"]:  # noqa: F821
        """
        为分块生成向量嵌入

        使用 ModelConfig 中配置的 embedding 模型。
        支持批量推理以提高效率。

        Args:
            chunks: Chunk 对象列表

        Returns:
            对应的向量列表 (np.ndarray)
        """

        if not chunks:
            return []

        texts = [chunk.text for chunk in chunks]

        try:
            from sentence_transformers import SentenceTransformer

            # 延迟加载模型
            # 延迟加载模型
            if not hasattr(self, "_st_model") or self._st_model is None:
                # 0. 特殊处理 BGE-M3 (针对当前环境的离线修复)
                if self.embedding_model_name == "BAAI/bge-m3":
                    local_snapshot = os.path.expanduser(
                        "~/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181"
                    )
                    if os.path.exists(os.path.join(local_snapshot, "config.json")):
                        try:
                            # print(f"DEBUG: Loading local snapshot from {local_snapshot}")
                            self._st_model = SentenceTransformer(local_snapshot)
                            # 批量编码
                            embeddings = self._st_model.encode(texts, convert_to_numpy=True)
                            return list(embeddings)
                        except Exception as e:
                            print(f"Warning: Failed to load local snapshot: {e}")

                # 1. 优先尝试离线加载 (local_files_only=True) 以避免 SSL/网络问题
                try:
                    self._st_model = SentenceTransformer(
                        self.embedding_model_name, local_files_only=True
                    )
                except Exception:
                    # 2. 如果离线失败 (例如初次运行)，再尝试联网
                    print(
                        f"Warning: Offline load failed for {self.embedding_model_name}, trying online..."
                    )
                    self._st_model = SentenceTransformer(self.embedding_model_name)

            # 批量编码
            embeddings = self._st_model.encode(texts, convert_to_numpy=True)
            return list(embeddings)

        except ImportError as e:
            raise RuntimeError(
                "sentence-transformers 未安装，无法生成向量嵌入。"
                "请运行: pip install sentence-transformers"
            ) from e
        except Exception as e:
            raise RuntimeError(f"向量嵌入生成失败，拒绝写入脏数据: {e}") from e

    def store_vectors(
        self,
        chunks: List["Chunk"],
        embeddings: List["np.ndarray"],  # noqa: F821
        db_path: Optional[str] = None,
    ) -> int:
        """
        将分块及其向量存储到 SQLite 数据库

        写入 event_vectors 表，并维护 vectors_index (vec0) 和 vector_metadata。

        Args:
            chunks: Chunk 对象列表
            embeddings: 对应的向量列表
            db_path: 数据库路径 (默认 ~/.dimcause/index.db)

        Returns:
            成功存储的向量数量
        """
        import sqlite3

        if not chunks or not embeddings:
            return 0

        if len(chunks) != len(embeddings):
            raise ValueError(f"chunks ({len(chunks)}) 和 embeddings ({len(embeddings)}) 数量不匹配")

        if db_path is None:
            db_path = self.db_path
            # db_path = os.path.expanduser("~/.dimcause/index.db") # LEGACY

        stored = 0
        conn = None
        try:
            conn = sqlite3.connect(db_path)
            conn.isolation_level = "IMMEDIATE"

            # Ensure tables exist
            self._init_vector_db(conn)
            cursor = conn.cursor()

            for chunk, embedding in zip(chunks, embeddings, strict=False):
                # 转换为 bytes
                embedding_bytes = embedding.astype("float32").tobytes()

                # 写入 event_vectors
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO event_vectors
                    (event_id, chunk_seq, chunk_pos, chunk_text, embedding)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        chunk.event_id,
                        chunk.seq,
                        chunk.pos,
                        chunk.text,
                        embedding_bytes,
                    ),
                )

                # 尝试写入 vec0 索引
                try:
                    # 检查 vectors_index 是否存在
                    cursor.execute("""
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name='vectors_index'
                    """)
                    if cursor.fetchone():
                        # 插入到 vec0 并获取 rowid
                        cursor.execute(
                            "INSERT INTO vectors_index(embedding) VALUES (?)", (embedding_bytes,)
                        )
                        rowid = cursor.lastrowid

                        # 写入元数据
                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO vector_metadata
                            (rowid, event_id, chunk_seq)
                            VALUES (?, ?, ?)
                        """,
                            (rowid, chunk.event_id, chunk.seq),
                        )
                except sqlite3.OperationalError:
                    # vec0 不可用，跳过索引
                    pass

                stored += 1

            conn.commit()
        except Exception:
            if conn is not None:
                conn.rollback()
            raise
        finally:
            if conn is not None:
                conn.close()

        return stored

    def vector_search(
        self,
        query_embedding: "np.ndarray",  # noqa: F821
        top_k: int = 30,
        db_path: Optional[str] = None,
    ) -> List[tuple]:
        """
        基于向量索引进行 KNN 搜索

        优先使用 vec0 索引，降级使用暴力搜索。

        Args:
            query_embedding: 查询向量
            top_k: 返回结果数量
            db_path: 数据库路径 (默认 ~/.dimcause/index.db)

        Returns:
            (event_id, score) 列表，score 为相似度 (0.0~1.0)
        """
        import sqlite3

        import numpy as np

        if db_path is None:
            db_path = self.db_path
            # db_path = os.path.expanduser("~/.dimcause/index.db") # LEGACY

        if not os.path.exists(db_path):
            return []

        conn = sqlite3.connect(db_path)
        results = []

        try:
            cursor = conn.cursor()
            query_bytes = query_embedding.astype("float32").tobytes()

            # 尝试使用 vec0 搜索 (需要 sqlite-vec 已安装)
            try:
                import sqlite_vec

                conn.enable_load_extension(True)
                sqlite_vec.load(conn)

                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='vectors_index'
                """)
                if cursor.fetchone():
                    # vec0 KNN 搜索
                    cursor = conn.cursor()

                    cursor.execute(
                        """
                        SELECT v.rowid, v.distance
                        FROM vectors_index v
                        WHERE v.embedding MATCH ?
                        ORDER BY v.distance
                        LIMIT ?
                    """,
                        (query_bytes, top_k),
                    )

                    vec_results = cursor.fetchall()

                    for rowid, distance in vec_results:
                        # 查询元数据获取 event_id
                        cursor.execute(
                            "SELECT event_id FROM vector_metadata WHERE rowid = ?", (rowid,)
                        )
                        row = cursor.fetchone()
                        if row:
                            # 转换距离为相似度 (cosine: 1 - distance)
                            score = max(0.0, min(1.0, 1.0 - distance))
                            results.append((row[0], score))

                    return results

            except ImportError:
                logger.warning(
                    "sqlite-vec 未安装，向量搜索将使用 O(N) 暴力计算。如需加速: pip install 'dimcause[full]'"
                )
            except sqlite3.OperationalError as e:
                logger.warning(f"sqlite-vec 加载失败 ({e})，降级到暴力搜索。")

            # 暴力搜索 (vec0 不可用时)
            cursor.execute("""
                SELECT DISTINCT event_id, embedding FROM event_vectors
            """)

            rows = cursor.fetchall()
            if not rows:
                return []

            # 计算余弦相似度
            query_norm = np.linalg.norm(query_embedding)
            if query_norm == 0:
                return []

            scored = []
            seen_events = set()

            for event_id, emb_bytes in rows:
                if event_id in seen_events:
                    continue
                seen_events.add(event_id)

                try:
                    emb = np.frombuffer(emb_bytes, dtype=np.float32)
                    emb_norm = np.linalg.norm(emb)
                    if emb_norm == 0:
                        continue

                    similarity = np.dot(query_embedding, emb) / (query_norm * emb_norm)
                    scored.append((event_id, float(similarity)))
                except Exception:
                    continue

            # 按相似度排序
            scored.sort(key=lambda x: x[1], reverse=True)
            results = scored[:top_k]
            # print(f"DEBUG: Brute force results: {len(results)}")

        except Exception as e:
            print(f"Warning: vector_search failed: {e}")

        finally:
            conn.close()

        return results
