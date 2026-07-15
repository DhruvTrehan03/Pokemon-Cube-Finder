from fastapi import FastAPI


app = FastAPI(title="Pokemon Cube Finder")


@app.get("/")
def dashboard() -> dict[str, str]:
    return {"status": "Pokemon Cube Finder is ready for implementation"}
