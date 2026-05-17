"""启动 Web 服务。"""

import uvicorn

from config.settings import get_settings


def main() -> None:
    settings = get_settings()
    print("\n" + "=" * 50)
    print("  服务启动后，请在浏览器打开：")
    print(f"  http://localhost:{settings.api_port}")
    print("  （不要用 0.0.0.0，浏览器无法访问该地址）")
    print(f"  图谱模式配置: {settings.graph_mode}（Neo4j 未启动时将自动回退 local）")
    print("=" * 50 + "\n")
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
