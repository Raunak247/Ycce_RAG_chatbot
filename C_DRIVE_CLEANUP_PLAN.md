# 🚨 C DRIVE FULL - CLEANUP & MIGRATION PLAN

## Current Status
- **C Drive**: 161 GB TOTAL | 0 GB FREE ❌ CRITICAL
- **E Drive**: ~160 GB TOTAL | 83 GB FREE ✅ AVAILABLE

## Space Consumers on C Drive
- C:\Windows: 28.97 GB
- C:\Program Files: 11.33 GB
- C:\Program Files (x86): 5.43 GB
- C:\ProgramData: 1.53 GB
- C:\Users\HP\...: ~114 GB (user files, caches, temp)

---

## PHASE 1: EMERGENCY CLEANUP (Free up ~10-20 GB immediately)

### Step 1: Clear Windows Temporary Files
```powershell
# As Administrator
Remove-Item 'C:\Windows\Temp\*' -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "✅ Cleaned C:\Windows\Temp"
```

### Step 2: Clear User Temporary Files
```powershell
Remove-Item 'C:\Users\HP\AppData\Local\Temp\*' -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "✅ Cleaned C:\Users\HP\AppData\Local\Temp"
```

### Step 3: Clear Python Cache
```powershell
# Pip cache
Remove-Item 'C:\Users\HP\AppData\Local\pip\cache' -Recurse -Force -ErrorAction SilentlyContinue

# Conda cache
Remove-Item 'C:\Users\HP\AppData\Local\.conda\pkgs' -Recurse -Force -ErrorAction SilentlyContinue

# Python pycache
Get-ChildItem -Path 'C:\Users\HP' -Recurse -Filter '__pycache__' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "✅ Cleared all Python caches"
```

### Step 4: Check Freed Space
```powershell
Get-Volume | Where-Object {$_.DriveLetter -eq 'C'} | Format-Table DriveLetter, Size, SizeRemaining
```

**Expected Result**: Should free 10-20+ GB

---

## PHASE 2: IDENTIFY PROJECT FILES ON C DRIVE

### Check if YCCE_RAG backup exists on C drive
```powershell
Get-ChildItem -Path 'C:\' -Recurse -Filter '*YCCE*' -ErrorAction SilentlyContinue
```

### Check for conda environments, venv, or virtualenv on C drive
```powershell
Get-ChildItem -Path 'C:\Users\HP\AppData\Local\conda\envs' -ErrorAction SilentlyContinue
Get-ChildItem -Path 'C:\Users\HP\AppData\Local\miniconda3\envs' -ErrorAction SilentlyContinue
```

---

## PHASE 3: MOVE PROJECT DATA TO E DRIVE

### Option A: If project is completely on C drive
```powershell
# Create backup location on E drive
New-Item -ItemType Directory -Path 'E:\Python_Envs' -Force
New-Item -ItemType Directory -Path 'E:\Projects_Backup' -Force

# Move Python environment if needed
Move-Item -Path 'C:\path\to\environment' -Destination 'E:\Python_Envs'

# Move any YCCE_RAG project copies
Move-Item -Path 'C:\path\to\YCCE_RAG' -Destination 'E:\Projects_Backup\YCCE_RAG'
```

### Option B: If only config/data needs moving
```powershell
# Move any downloaded data
Move-Item -Path 'C:\Users\HP\Downloads\*' -Destination 'E:\Downloads' -Force

# Move any project cache
Move-Item -Path 'C:\Users\HP\AppData\Local\YCCE*' -Destination 'E:\AppData_Backup' -Force
```

---

## PHASE 4: RECONFIGURE PATHS IN MAIN PROJECT (E:\YCCE_RAG)

After cleanup, verify the main project is working:

```bash
cd E:\YCCE_RAG
python -m py_compile ingestion/ingest_pipeline.py
python main_initial_crawl.py --help
```

---

## SUMMARY OF ACTION ITEMS

| Step | Action | Impact | Time |
|------|--------|--------|------|
| **1** | Clean Windows Temp | Free ~2-5 GB | 2 min |
| **2** | Clean User Temp | Free ~5-10 GB | 2 min |
| **3** | Clear Python Cache | Free ~3-8 GB | 1 min |
| **4** | Check freed space | Verify progress | 1 min |
| **5** | Identify C-drive files | Plan migration | 2 min |
| **6** | Move project files | Finalize migration | 5 min |
| **7** | Update paths | Verify functionality | 5 min |
| **8** | Resume pipeline | Start fresh | 2 min |

**Total Time**: ~20 minutes

---

## BEFORE YOU PROCEED

⚠️ **IMPORTANT**:
1. ✅ E:\YCCE_RAG is your main project (already on E drive - GOOD!)
2. ✅ E drive has 83 GB free (more than enough)
3. ⚠️ Some C drive items cannot be moved (Windows system files)
4. ⚠️ Do NOT move Windows\System32 or critical OS files
5. ✅ Safe to delete: Temp, Cache, Old backups

---

## RECOMMENDED DISK CLEANUP TOOL (Alternative)

If manual cleanup is risky, use Windows built-in tool:
```powershell
# Open Storage Sense
Start-Process ms-settings:storagesense

# Or use Disk Cleanup utility
cleanmgr
```

---

## DO THIS FIRST (Emergency Action)

Run these commands NOW to free immediate space:

```powershell
# 1. Clean Windows Update Cache (very large!)
Rename-Item -Path 'C:\Windows\SoftwareDistribution\Download' -NewName 'Download.old'
New-Item -ItemType Directory -Path 'C:\Windows\SoftwareDistribution\Download'

# 2. Clean Recycle Bin
Clear-RecycleBin -Force -ErrorAction SilentlyContinue

# 3. Remove old Windows installation backup (if exists)
Remove-Item 'C:\Windows.old' -Recurse -Force -ErrorAction SilentlyContinue

# 4. Check freed space
Get-Volume C: | Format-Table DriveLetter, SizeRemaining
```

**Expected Result**: Free 15-40+ GB

---

## NEXT: Tell Me...

1. ✅ Can you run the emergency cleanup commands above?
2. ❓ Do you have any programs in C:\Program Files you don't use?
3. ❓ Do you have old backups or Downloads that can be moved?
4. ❓ After cleanup, how much free space appears on C drive?

Once I know, I can give exact commands to:
- Move remaining project files to E drive
- Update all paths in the code
- Verify everything works from E drive only
