"""长期记忆存储 — MemoryStore 抽象层 + 双实现

MemoryStore ABC: index/search/delete 标准接口

SimpleMemoryStore: 关键词匹配（零依赖，默认启用）
  适用场景: 小数据量（<1万条）、无需GPU

ChromaMemoryStore: 语义向量检索（可选，需 chromadb）
  适用场景: 大数据量、语义搜索、跨语言

Embedding 模块: 轻量嵌入生成
  优先级: sentence-transformers → TF-IDF → 关键词
"""
from __future__ import annotations

import json
import re
import math
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from praxis.core.logging_config import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════
# MemoryStore ABC
# ═══════════════════════════════════════════════════════════════


class MemoryStore(ABC):
    """长期记忆存储抽象基类"""

    @abstractmethod
    def index(self, documents: list[dict], collection: str = "default") -> int:
        """索引文档。每个文档含 text/metadata。返回索引数"""
        ...

    @abstractmethod
    def search(self, query: str, collection: str = "default",
               top_k: int = 5, min_score: float = 0.15) -> list[dict]:
        """语义检索。返回 [{text, metadata, score, id}]"""
        ...

    @abstractmethod
    def delete(self, ids: list[str], collection: str = "default") -> int:
        """删除文档。返回删除数"""
        ...

    @abstractmethod
    def count(self, collection: str = "default") -> int:
        """集合中文档数量"""
        ...


# ═══════════════════════════════════════════════════════════════
# Embedding 引擎
# ═══════════════════════════════════════════════════════════════


class EmbeddingEngine:
    """嵌入向量生成引擎 — 多后端自动选择

    优先级: sentence-transformers > TF-IDF > 关键词
    """

    _model = None
    _engine_type: str = "keyword"

    @classmethod
    def _init_tfidf(cls):
        cls._engine_type = "tfidf"
        cls._vocabulary: dict[str, int] = {}
        cls._idf: dict[str, float] = {}
        cls._doc_count = 0

    @classmethod
    def encode(cls, text: str) -> list[float]:
        """生成文本嵌入向量。自动选择最优后端"""
        try:
            return cls._encode_sentence_transformers(text)
        except Exception:
            pass

        try:
            return cls._encode_tfidf(text)
        except Exception:
            pass

        return cls._encode_keyword(text)

    @classmethod
    def _encode_sentence_transformers(cls, text: str) -> list[float]:
        if cls._model is None and cls._engine_type != "sentence_transformers":
            try:
                from sentence_transformers import SentenceTransformer
                cls._model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
                cls._engine_type = "sentence_transformers"
                logger.info("embedding_engine", backend="sentence-transformers")
            except ImportError:
                raise

        if cls._model is not None:
            return cls._model.encode(text).tolist()
        raise ImportError("sentence_transformers not available")

    @classmethod
    def _encode_tfidf(cls, text: str) -> list[float]:
        if cls._engine_type != "tfidf":
            cls._init_tfidf()

        # 简单 TF-IDF 向量化（基于字符bigram）
        tokens = cls._tokenize(text)
        if not tokens:
            return [0.0] * 100

        vec = [0.0] * 100
        for token in tokens:
            h = hash(token) % 100
            vec[h] += 1.0

        # 归一化
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm > 0 else vec

    @classmethod
    def _encode_keyword(cls, text: str) -> list[float]:
        """关键词兜底向量 — 基于中文字符频率"""
        vec = [0.0] * 50
        for i, ch in enumerate(text[:200]):
            if '\u4e00' <= ch <= '\u9fff':
                h = ord(ch) % 50
                vec[h] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        return [round(v / norm, 6) for v in vec] if norm > 0 else vec

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """中文简单分词"""
        tokens = []
        for i in range(len(text) - 1):
            bigram = text[i:i + 2]
            if re.match(r'[\u4e00-\u9fff]{2}', bigram):
                tokens.append(bigram)
        return tokens

    @classmethod
    def cosine_similarity(cls, a: list[float], b: list[float]) -> float:
        """余弦相似度"""
        if len(a) != len(b):
            min_len = min(len(a), len(b))
            a, b = a[:min_len], b[:min_len]
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# ═══════════════════════════════════════════════════════════════
# SimpleMemoryStore — 关键词匹配（默认，零依赖）
# ═══════════════════════════════════════════════════════════════


class SimpleMemoryStore(MemoryStore):
    """关键词/向量混合检索存储

    使用 EmbeddingEngine 做向量化，余弦相似度检索。
    数据持久化到 JSONL 文件。
    """

    def __init__(self, storage_dir: str | Path = "."):
        self._dir = Path(storage_dir) / "memory_store"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._collections: dict[str, list[dict]] = {}
        self._load_all()

    def _collection_path(self, name: str) -> Path:
        return self._dir / f"{name}.jsonl"

    def _load_all(self):
        for path in self._dir.glob("*.jsonl"):
            name = path.stem
            docs = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        docs.append(json.loads(line.strip()))
                    except Exception:
                        continue
            self._collections[name] = docs

    def index(self, documents: list[dict], collection: str = "default") -> int:
        if collection not in self._collections:
            self._collections[collection] = []

        count = 0
        path = self._collection_path(collection)
        with open(path, "a", encoding="utf-8") as f:
            for doc in documents:
                doc_id = doc.get("id", f"mem-{datetime.now(timezone.utc).timestamp()}-{count}")
                doc.setdefault("id", doc_id)
                doc.setdefault("indexed_at", datetime.now(timezone.utc).isoformat())

                if "embedding" not in doc:
                    text = doc.get("text", "")
                    doc["embedding"] = EmbeddingEngine.encode(text)

                f.write(json.dumps(doc, ensure_ascii=False) + "\n")
                self._collections[collection].append(doc)
                count += 1

        logger.info("memory_indexed", collection=collection, count=count)
        return count

    def search(self, query: str, collection: str = "default",
               top_k: int = 5, min_score: float = 0.15) -> list[dict]:
        if collection not in self._collections:
            return []

        query_vec = EmbeddingEngine.encode(query)
        docs = self._collections.get(collection, [])
        if not docs:
            return []

        scored = []
        for doc in docs:
            doc_vec = doc.get("embedding")
            if doc_vec:
                score = EmbeddingEngine.cosine_similarity(query_vec, doc_vec)
                if score >= min_score:
                    scored.append({
                        "text": doc.get("text", ""),
                        "metadata": doc.get("metadata", {}),
                        "score": round(score, 4),
                        "id": doc.get("id", ""),
                        "source": doc.get("source", collection),
                        "timestamp": doc.get("indexed_at", ""),
                    })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def delete(self, ids: list[str], collection: str = "default") -> int:
        if collection not in self._collections:
            return 0
        before = len(self._collections[collection])
        self._collections[collection] = [
            d for d in self._collections[collection] if d.get("id") not in ids
        ]
        deleted = before - len(self._collections[collection])
        path = self._collection_path(collection)
        with open(path, "w", encoding="utf-8") as f:
            for doc in self._collections[collection]:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")
        return deleted

    def count(self, collection: str = "default") -> int:
        return len(self._collections.get(collection, []))


# ═══════════════════════════════════════════════════════════════
# ChromaMemoryStore — 语义向量检索（可选 chromadb）
# ═══════════════════════════════════════════════════════════════


class ChromaMemoryStore(MemoryStore):
    """ChromaDB 后端 — 高性能语义检索

    依赖: pip install chromadb
    """

    def __init__(self, persist_dir: str | Path = "./chroma_data"):
        self._dir = Path(persist_dir)
        self._client = None
        self._collections: dict[str, Any] = {}

    def _get_client(self):
        if self._client is None:
            try:
                import chromadb
                self._client = chromadb.PersistentClient(path=str(self._dir))
                logger.info("chroma_initialized", path=str(self._dir))
            except ImportError:
                raise ImportError("chromadb 未安装。pip install chromadb")
        return self._client

    def _get_collection(self, name: str):
        if name not in self._collections:
            client = self._get_client()
            self._collections[name] = client.get_or_create_collection(name=name)
        return self._collections[name]

    def index(self, documents: list[dict], collection: str = "default") -> int:
        try:
            col = self._get_collection(collection)
            texts = [d.get("text", "") for d in documents]
            metadatas = [d.get("metadata", {}) for d in documents]
            ids = [d.get("id", f"mem-{i}") for i, d in enumerate(documents)]

            col.add(documents=texts, metadatas=metadatas, ids=ids)
            logger.info("chroma_indexed", collection=collection, count=len(documents))
            return len(documents)
        except Exception as e:
            logger.error("chroma_index_failed", error=str(e))
            return 0

    def search(self, query: str, collection: str = "default",
               top_k: int = 5, min_score: float = 0.15) -> list[dict]:
        try:
            col = self._get_collection(collection)
            results = col.query(query_texts=[query], n_results=top_k)

            return [
                {
                    "text": results["documents"][0][i] if results.get("documents") else "",
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "score": round(results["distances"][0][i], 4) if results.get("distances") else 0.0,
                    "id": results["ids"][0][i] if results.get("ids") else "",
                    "source": collection,
                }
                for i in range(len(results.get("ids", [[]])[0]))
                if results.get("distances", [[1.0]])[0][i] <= (1 - min_score)
            ]
        except Exception as e:
            logger.error("chroma_search_failed", error=str(e))
            return []

    def delete(self, ids: list[str], collection: str = "default") -> int:
        try:
            col = self._get_collection(collection)
            col.delete(ids=ids)
            return len(ids)
        except Exception:
            return 0

    def count(self, collection: str = "default") -> int:
        try:
            col = self._get_collection(collection)
            return col.count()
        except Exception:
            return 0
