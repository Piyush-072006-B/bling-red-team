import asyncio
import httpx
from app.engines.seed_library import get_seed

async def send_payload():
    seed = get_seed('digital_arrest')
    payload = {
        "source_type": "FRAUD_DNA",
        "transaction_id": "TXN-DEBUG-001",
        "account_id": "ACC-DEBUG-001",
        "confirmed_archetype": "digital_arrest",
        "feature_vector": seed,
        "timestamp": "2026-06-21T10:00:00Z"
    }
    
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "http://localhost:8002/red-team/ingest",
            json=payload,
            headers={"X-API-Key": "changeme"}
        )
        print("Response:", r.status_code, r.text)

if __name__ == "__main__":
    asyncio.run(send_payload())
