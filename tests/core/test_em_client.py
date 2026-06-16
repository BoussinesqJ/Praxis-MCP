"""东财基类单元测试

测试统一的东财 API 客户端基类
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from praxis.core.em_client import EMClient, EMClientConfig


class TestEMClient:
    """东财基类测试"""

    def test_default_config(self):
        """测试默认配置"""
        client = EMClient()
        assert client.config.min_interval == 1.0
        assert client.config.jitter_max == 0.5
        assert client.config.timeout == 10
        assert client.config.max_retries == 3

    def test_custom_config(self):
        """测试自定义配置"""
        config = EMClientConfig(
            min_interval=2.0,
            jitter_max=1.0,
            timeout=15,
            max_retries=5
        )
        client = EMClient(config)
        assert client.config.min_interval == 2.0
        assert client.config.jitter_max == 1.0
        assert client.config.timeout == 15
        assert client.config.max_retries == 5

    def test_user_agent(self):
        """测试 User-Agent 伪装"""
        client = EMClient()
        ua = client._get_user_agent()
        assert "Mozilla" in ua
        assert "Windows" in ua or "Mac" in ua

    def test_session_creation(self):
        """测试 Session 创建"""
        client = EMClient()
        session = client._get_session()
        assert session is not None
        assert session.headers.get("User-Agent") is not None

    def test_session_reuse(self):
        """测试 Session 复用"""
        client = EMClient()
        session1 = client._get_session()
        session2 = client._get_session()
        assert session1 is session2

    @pytest.mark.asyncio
    async def test_get_success(self):
        """测试 GET 请求成功"""
        client = EMClient()

        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "test"}
        mock_response.raise_for_status = MagicMock()

        # 先初始化 session
        client._get_session()
        with patch.object(client._session, 'get', return_value=mock_response):
            result = await client.get("http://example.com")

        assert result == {"data": "test"}

    @pytest.mark.asyncio
    async def test_get_with_params(self):
        """测试带参数的 GET 请求"""
        client = EMClient()

        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "test"}
        mock_response.raise_for_status = MagicMock()

        # 先初始化 session
        client._get_session()
        with patch.object(client._session, 'get', return_value=mock_response) as mock_get:
            result = await client.get(
                "http://example.com",
                params={"key": "value"}
            )

        assert result == {"data": "test"}

    @pytest.mark.asyncio
    async def test_get_failure_retry(self):
        """测试失败重试"""
        config = EMClientConfig(max_retries=3, min_interval=0.0)
        client = EMClient(config)

        # Mock response that fails twice then succeeds
        mock_response_fail = MagicMock()
        mock_response_fail.raise_for_status.side_effect = Exception("Network error")

        mock_response_success = MagicMock()
        mock_response_success.json.return_value = {"data": "test"}
        mock_response_success.raise_for_status = MagicMock()

        call_count = 0

        def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return mock_response_fail
            return mock_response_success

        # 先初始化 session
        client._get_session()
        with patch.object(client._session, 'get', side_effect=mock_get):
            result = await client.get("http://example.com")

        assert result == {"data": "test"}
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_get_failure_max_retries(self):
        """测试超过最大重试次数"""
        config = EMClientConfig(max_retries=2, min_interval=0.0)
        client = EMClient(config)

        # Mock response that always fails
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("Network error")

        # 先初始化 session
        client._get_session()
        with patch.object(client._session, 'get', return_value=mock_response):
            with pytest.raises(Exception) as exc_info:
                await client.get("http://example.com")
            assert "Network error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_text_success(self):
        """测试获取文本响应"""
        client = EMClient()

        # Mock response
        mock_response = MagicMock()
        mock_response.text = "test content"
        mock_response.raise_for_status = MagicMock()

        # 先初始化 session
        client._get_session()
        with patch.object(client._session, 'get', return_value=mock_response):
            result = await client.get_text("http://example.com")

        assert result == "test content"

    def test_cache_integration(self):
        """测试缓存集成"""
        client = EMClient()
        assert client._cache is not None

    @pytest.mark.asyncio
    async def test_get_with_cache(self):
        """测试带缓存的 GET 请求"""
        client = EMClient()

        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "test"}
        mock_response.raise_for_status = MagicMock()

        # 先初始化 session
        client._get_session()

        # 第一次请求
        with patch.object(client._session, 'get', return_value=mock_response):
            result1 = await client.get("http://example.com", cache_key="test_key")

        # 第二次请求应该使用缓存
        result2 = await client.get("http://example.com", cache_key="test_key")

        assert result1 == result2

    def test_close(self):
        """测试关闭"""
        client = EMClient()
        client._get_session()  # 创建 session
        client.close()
        # 关闭不应抛出异常


class TestEMClientSingleton:
    """测试全局单例"""

    def test_singleton(self):
        """测试全局单例"""
        from praxis.core.em_client import get_em_client, reset_em_client

        reset_em_client()
        client1 = get_em_client()
        client2 = get_em_client()

        assert client1 is client2
        reset_em_client()
