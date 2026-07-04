from fastapi import FastAPI, Request

app = FastAPI()


@app.post("/webhook")
async def receive_webhook(request: Request) -> dict[str, str]:
    payload = await request.json()
    print(f"Received webhook payload: {payload}", flush=True)
    return {"status": "ok"}
