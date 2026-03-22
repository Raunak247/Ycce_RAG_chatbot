#!/usr/bin/env python3
"""Check primary and backup pickle file status"""

import pickle
import os

primary_path = 'data/faiss_index/index.pkl'
backup_path = 'data/faiss_index/index.pkl.bak'

print("=" * 60)
print("PRIMARY index.pkl")
print("=" * 60)

try:
    size = os.path.getsize(primary_path)
    with open(primary_path, 'rb') as f:
        data = pickle.load(f)
    print(f"✓ Loaded successfully")
    print(f"  File size: {size:,} bytes ({size/1024/1024:.1f} MB)")
    print(f"  Type: {type(data)}")
    if isinstance(data, dict):
        print(f"  Keys: {list(data.keys())}")
        for k, v in data.items():
            if isinstance(v, dict):
                print(f"    {k}: dict({len(v)} items)")
            elif isinstance(v, list):
                print(f"    {k}: list({len(v)} items)")
            else:
                print(f"    {k}: {type(v).__name__}")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {str(e)[:100]}")

print("\n" + "=" * 60)
print("BACKUP index.pkl.bak")
print("=" * 60)

try:
    size = os.path.getsize(backup_path)
    with open(backup_path, 'rb') as f:
        data = pickle.load(f)
    print(f"✓ Loaded successfully")
    print(f"  File size: {size:,} bytes ({size/1024/1024:.1f} MB)")
    print(f"  Type: {type(data)}")
    if isinstance(data, dict):
        print(f"  Keys: {list(data.keys())}")
        for k, v in data.items():
            if isinstance(v, dict):
                print(f"    {k}: dict({len(v)} items)")
            elif isinstance(v, list):
                print(f"    {k}: list({len(v)} items)")
            else:
                print(f"    {k}: {type(v).__name__}")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {str(e)[:100]}")
