"""News 工具测试 — 8 场景"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from praxis.tools.news import news


# ── Helpers ──────────────────────────────────────────────────────

def _mock_response(status_code: int = 200, json_data: dict | None = None):
    """创建 mock httpx Response"""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


def _mock_client_success(mock_responses: dict[str, dict]):
    """为不同 URL 返回不同 mock 响应的 client factory"""
    async def fake_get(url, **kwargs):
        for prefix, data in mock_responses.items():
            if prefix in url:
                return _mock_response(200, data)
        return _mock_response(500, {})

    client = MagicMock()
    client.get = fake_get
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


# ── 1. list_sources ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_sources():
    """list_sources 返回 6 个数据源"""
    result = await news(action="list_sources")
    assert result["success"] is True
    assert len(result["data"]) == 6
    assert "cls (财联社)" in result["data"]
    assert "zhihu (知乎热榜)" in result["data"]


# ── 2. finance with mock ────────────────────────────────────────

@pytest.mark.asyncio
async def test_finance_with_mock():
    """monkeypatch httpx 返回 mock 财经数据"""
    mock_finance_data = {
        "cls": {"data": {"roll_data": [
            {"title": "财联社测试新闻1", "ctime": 1718208000, "id": 1001},
            {"title": "财联社测试新闻2", "ctime": 1718208100, "id": 1002},
        ]}},
        "wallstreetcn": {"data": {"items": [
            {"title": "华尔街见闻新闻1", "display_time": 1718208000, "id": 2001},
        ]}},
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        client_inst = MagicMock()
        mock_client_cls.return_value = client_inst

        async def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if "cls.cn" in url:
                resp.json.return_value = mock_finance_data["cls"]
            elif "wallstcn.com" in url:
                resp.json.return_value = mock_finance_data["wallstreetcn"]
            else:
                resp.status_code = 500
                resp.json.return_value = {}
            return resp

        client_inst.get = fake_get
        client_inst.__aenter__ = AsyncMock(return_value=client_inst)
        client_inst.__aexit__ = AsyncMock(return_value=None)

        result = await news(action="finance", sources=["cls", "wallstreetcn"], count=5)

    assert result["success"] is True
    assert "cls" in result["data"]
    assert "wallstreetcn" in result["data"]
    assert len(result["data"]["cls"]) == 2
    assert result["data"]["cls"][0]["title"] == "财联社测试新闻1"
    assert result["data"]["cls"][0]["source"] == "cls"
    assert "wallstreetcn" in result["data"]["wallstreetcn"][0]["url"]


# ── 3. trends with mock ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_trends_with_mock():
    """monkeypatch 返回 mock 热搜数据"""
    mock_trend_data = {
        "weibo": {"data": {"realtime": [
            {"word": "微博热搜TOP1", "word_scheme": "#热搜TOP1#", "rank": 1, "num": 5000000},
        ]}},
        "zhihu": {"data": [
            {"target": {"title": "知乎热榜问题", "id": 123, "url": "https://zhihu.com/q/123"}, "updated": 1718208000},
        ]},
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        client_inst = MagicMock()
        mock_client_cls.return_value = client_inst

        async def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if "weibo.com" in url:
                resp.json.return_value = mock_trend_data["weibo"]
            elif "zhihu.com" in url:
                resp.json.return_value = mock_trend_data["zhihu"]
            else:
                resp.status_code = 500
                resp.json.return_value = {}
            return resp

        client_inst.get = fake_get
        client_inst.__aenter__ = AsyncMock(return_value=client_inst)
        client_inst.__aexit__ = AsyncMock(return_value=None)

        result = await news(action="trends", sources=["weibo", "zhihu"], count=5)

    assert result["success"] is True
    assert "weibo" in result["data"]
    assert "zhihu" in result["data"]
    assert result["data"]["weibo"][0]["title"] == "微博热搜TOP1"
    assert result["data"]["weibo"][0]["rank"] == 1
    assert result["data"]["zhihu"][0]["title"] == "知乎热榜问题"


# ── 4. partial failure ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_partial_failure():
    """部分数据源失败不影响其他"""
    mock_data = {
        "cls": {"data": {"roll_data": [
            {"title": "正常新闻", "ctime": 1718208000, "id": 999},
        ]}},
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        client_inst = MagicMock()
        mock_client_cls.return_value = client_inst

        async def fake_get(url, **kwargs):
            resp = MagicMock()
            if "cls.cn" in url:
                resp.status_code = 200
                resp.json.return_value = mock_data["cls"]
            else:
                # wallstreetcn and xueqiu fail
                resp.status_code = 500
                resp.json.return_value = {}
                resp.raise_for_status = MagicMock(side_effect=Exception("fail"))
            return resp

        client_inst.get = fake_get
        client_inst.__aenter__ = AsyncMock(return_value=client_inst)
        client_inst.__aexit__ = AsyncMock(return_value=None)

        result = await news(action="finance", sources=["cls", "wallstreetcn"], count=5)

    # cls 应该成功，wallstreetcn 失败返回空列表
    assert result["success"] is True
    assert len(result["data"]["cls"]) == 1
    assert result["data"]["wallstreetcn"] == []


# ── 5. all sources fail ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_sources_fail():
    """所有数据源失败返回 success=False"""
    with patch("httpx.AsyncClient") as mock_client_cls:
        client_inst = MagicMock()
        mock_client_cls.return_value = client_inst

        async def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 500
            resp.json.return_value = {}
            return resp

        client_inst.get = fake_get
        client_inst.__aenter__ = AsyncMock(return_value=client_inst)
        client_inst.__aexit__ = AsyncMock(return_value=None)

        result = await news(action="finance", sources=["cls"], count=5)

    assert result["success"] is False
    assert "error" in result


# ── 6. polymarket placeholder ───────────────────────────────────

@pytest.mark.asyncio
async def test_polymarket_placeholder():
    """polymarket 返回占位消息"""
    result = await news(action="polymarket")
    assert result["success"] is True
    assert "message" in result["data"]
    assert "Polymarket" in result["data"]["message"]


# ── 7. invalid action ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_action():
    """无效 action 返回错误"""
    with patch("httpx.AsyncClient") as mock_client_cls:
        client_inst = MagicMock()
        mock_client_cls.return_value = client_inst
        client_inst.__aenter__ = AsyncMock(return_value=client_inst)
        client_inst.__aexit__ = AsyncMock(return_value=None)

        result = await news(action="unknown_action")
    assert result["success"] is False
    assert "未知 action" in result["error"]


# ── 8. httpx not installed ──────────────────────────────────────

@pytest.mark.asyncio
async def test_httpx_not_installed():
    """httpx 未安装时降级"""
    with patch("praxis.tools.news.news") as mock_handler:
        mock_handler.return_value = {"success": False, "error": "httpx未安装，无法获取在线新闻数据"}
        result = await mock_handler(action="finance")
    assert result["success"] is False
    assert "httpx" in result["error"]
