"""Read-only discovery API for the operations registry."""

from fastapi import FastAPI, HTTPException

from src.actions import REGISTRY


app = FastAPI(title="SFSM Operations API")


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "ops_count": len(REGISTRY.list_ops())}


@app.get("/api/v1/ops")
def list_ops():
    return [
        {
            "name": op.name,
            "description": op.description,
            "spec_schema": op.spec_schema,
            "example": op.example,
        }
        for op in REGISTRY.list_ops()
    ]


@app.get("/api/v1/ops/{name}")
def get_op(name: str):
    op = REGISTRY.list_ops()
    match = [o for o in op if o.name == name]
    if not match:
        raise HTTPException(status_code=404, detail=f"Operation '{name}' not found")
    o = match[0]
    return {
        "name": o.name,
        "description": o.description,
        "spec_schema": o.spec_schema,
        "example": o.example,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8081)
