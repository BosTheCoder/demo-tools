from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "api", "hello": "world"}


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}
