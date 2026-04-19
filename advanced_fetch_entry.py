from advanced_fetch_mcp.server import cleanup, mcp
from advanced_fetch_mcp.settings import BASE_DIR, logger


def main():
    logger.info("=" * 50)
    logger.info("AdvancedFetchMCP 启动")
    logger.info("工作目录: %s", BASE_DIR)
    logger.info("=" * 50)
    try:
        mcp.run()
    finally:
        cleanup()


if __name__ == "__main__":
    main()
