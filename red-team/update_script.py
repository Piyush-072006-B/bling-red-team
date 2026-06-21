import json

with open('data/computed_archetype_seeds.json', 'r') as f:
    data = json.load(f)

header = '''"""
Archetype Seed Data — Realistic Feature Vectors for 16 Archetypes
==================================================================
Derived from BAF NeurIPS 2022 + PaySim fraud dataset statistics.
Each vector has all 59 Blue Team features.

This file is pure data — no functions. Import ARCHETYPE_SEEDS from here.
"""

ARCHETYPE_SEEDS: dict[str, dict[str, float]] = '''

with open('app/engines/seed_data.py', 'w', encoding='utf-8') as f:
    f.write(header + json.dumps(data, indent=4) + '\n')
