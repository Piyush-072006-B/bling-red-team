import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath('d:/bling-red-team/red-team'))
from app.engines.seed_library import get_seed
from app.engines.mutation_engine import generate_mutations
from app.sandbox.shadow_scorer import get_shadow_score

async def run():
    seed = get_seed("digital_arrest")
    print(f"Seed keys count: {len(seed)}")
    try:
        mutations = await generate_mutations(seed, original_score=0.9, n=22, shadow_scorer=get_shadow_score, current_tier=1)
        print(f"Produced: {len(mutations)}")
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(run())
