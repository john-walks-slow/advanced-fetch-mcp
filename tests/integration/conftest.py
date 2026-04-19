"""集成测试 pytest 配置。

运行集成测试：
    pytest tests/integration/ -v -m integration

集成测试需要网络和浏览器环境，默认不运行。
"""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (requires network/browser)",
    )