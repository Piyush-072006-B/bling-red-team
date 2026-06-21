import sys
import os

sys.path.insert(0, os.path.abspath('d:/bling-red-team/red-team'))
from app.engines.archetype_extractor import extract_archetype
from app.engines.seed_library import get_seed

for arch in ['digital_arrest', 'bipartite_mule', 'cycle_round_trip']:
    seed = get_seed(arch)
    result = extract_archetype(seed)
    print(f'Testing {arch}: {result}')
