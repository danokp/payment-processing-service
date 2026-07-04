from fastapi import FastAPI, Request

app = FastAPI(title="Demo Webhook Receiver")


@app.post("/webhook")
async def receive_webhook(request: Request) -> dict[str, str]:
    payload = await request.json()
    print({"received_webhook": payload}, flush=True)
    return {"status": "ok"}
