#!/usr/bin/env python3
"""
Comprehensive FAISS index.pkl Status Diagnostic Report
========================================================
Checks: 1) File sizes, 2) Loadability, 3) Cache status
"""

import os
import pickle
import time
from datetime import datetime

PRIMARY_PKL = 'data/faiss_index/index.pkl'
BACKUP_PKL = 'data/faiss_index/index.pkl.bak'
FAISS_INDEX = 'data/faiss_index/index.faiss'

print("=" * 70)
print("FAISS INDEX DIAGNOSTIC REPORT")
print("=" * 70)
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# ============================================================================
# 1. FILE STATUS
# ============================================================================
print("1. FILE STATUS")
print("-" * 70)

files_to_check = {
    'Primary Metadata': PRIMARY_PKL,
    'Backup Metadata': BACKUP_PKL,
    'FAISS Index': FAISS_INDEX,
}

for label, path in files_to_check.items():
    if os.path.exists(path):
        size = os.path.getsize(path)
        mtime = os.path.getmtime(path)
        dt = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        size_mb = size / 1024 / 1024
        print(f"  ✓ {label}: {size:,} bytes ({size_mb:.1f} MB) - Modified: {dt}")
    else:
        print(f"  ✗ {label}: NOT FOUND")

print()

# ============================================================================
# 2. PICKLE LOADABILITY TEST
# ============================================================================
print("2. PICKLE LOADABILITY TEST")
print("-" * 70)

for label, path in [('Primary', PRIMARY_PKL), ('Backup', BACKUP_PKL)]:
    try:
        with open(path, 'rb') as f:
            data = pickle.load(f)
        print(f"  ✓ {label} ({path}):")
        print(f"      Type: {type(data).__name__}")
        if isinstance(data, dict):
            print(f"      Keys: {list(data.keys())}")
            for k in data.keys():
                v = data[k]
                if isinstance(v, dict):
                    print(f"        - {k}: dict({len(v)} items)")
                elif isinstance(v, (list, tuple)):
                    print(f"        - {k}: {type(v).__name__}({len(v)} items)")
                else:
                    print(f"        - {k}: {type(v).__name__}")
    except Exception as e:
        print(f"  ✗ {label} ({path}):")
        print(f"      ERROR: {type(e).__name__}: {str(e)[:80]}")

print()

# ============================================================================
# 3. RECOMMENDATIONS
# ============================================================================
print("3. RECOMMENDATIONS")
print("-" * 70)

primary_ok = False
backup_ok = False

# Check primary
try:
    with open(PRIMARY_PKL, 'rb') as f:
        pickle.load(f)
    primary_ok = True
except:
    primary_ok = False

# Check backup
try:
    with open(BACKUP_PKL, 'rb') as f:
        pickle.load(f)
    backup_ok = True
except:
    backup_ok = False

if primary_ok:
    print("  ✓ PRIMARY index.pkl is GOOD - No action needed")
elif backup_ok and not primary_ok:
    print("  ⚠️  PRIMARY index.pkl is CORRUPTED")
    print("  ✓ BACKUP index.pkl.bak is GOOD - Can restore")
    print()
    print("  RECOMMENDED ACTIONS:")
    print("    1. Backup the corrupted primary file:")
    print(f"       cp {PRIMARY_PKL} {PRIMARY_PKL}.corrupt")
    print()
    print("    2. Restore from backup:")
    print(f"       cp {BACKUP_PKL} {PRIMARY_PKL}")
    print()
    print("    3. Verify restoration:")
    print("       python check_balance.py")
    print()
    print("  WHY THIS HAPPENED:")
    print("    - index.pkl is likely truncated from a failed save during ingestion")
    print("    - The backup is larger (814MB vs 167MB), indicating rollback to earlier state")
    print("    - Next ingestion run will continue and update the pickle incrementally")
else:
    print("  ✗ Both primary and backup are CORRUPTED")
    print("  ⚠️  SEVERE: You may need to:")
    print("    1. Rebuild FAISS index from scratch (recreate index.faiss)")
    print("    2. Re-run full ingestion pipeline")

print()
print("=" * 70)
