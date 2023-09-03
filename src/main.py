import asyncio

from fastapi import FastAPI
from uvicorn import Config
from uvicorn import Server

app = FastAPI()


@app.get("/health")
async def health() -> dict:
    return {"status": "Ok"}


async def main() -> None:  # pragma: no cover
    config = Config("src.main:app", port=80, host="0.0.0.0")
    server = Server(config)

    await server.serve()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
