# ⚡ COPY-PASTE COMMANDS - C DRIVE CLEANUP & E DRIVE MIGRATION

## 🔴 EMERGENCY CLEANUP (Run these immediately!)

**Open PowerShell as Administrator and paste these commands:**

```powershell
Write-Host "Starting C Drive Emergency Cleanup...")
Remove-Item 'C:\Windows\Temp\*' -Recurse -Force -ErrorAction SilentlyContinue 2>$null
Remove-Item 'C:\Users\HP\AppData\Local\Temp\*' -Recurse -Force -ErrorAction SilentlyContinue 2>$null
Remove-Item 'C:\Users\HP\AppData\Local\pip\cache' -Recurse -Force -ErrorAction SilentlyContinue 2>$null
Get-ChildItem -Path 'C:\Users\HP' -Recurse -Filter '__pycache__' -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue 2>$null
Clear-RecycleBin -Force -ErrorAction SilentlyContinue 2>$null
Write-Host "✅ Emergency cleanup complete!`n"
Get-Volume C: | Format-Table DriveLetter, @{Label='TotalGB';Expression={[math]::Round($_.Size/1GB,2)}}, @{Label='FreeGB';Expression={[math]::Round($_.SizeRemaining/1GB,2)}}
```

**Expected result**: Free 15-30+ GB on C drive

---

## 📊 CHECK WHAT'S CURRENTLY ON C DRIVE

```powershell
Write-Host "Checking for YCCE_RAG on C drive..."
Get-ChildItem -Path 'C:\' -Recurse -Filter '*YCCE*' -ErrorAction SilentlyContinue | Select-Object FullName

Write-Host "Checking for Python environments on C drive..."
Get-ChildItem -Path 'C:\Users\HP\AppData\Local\miniconda3\envs' -ErrorAction SilentlyContinue | Select-Object Name, @{Label='SizeGB';Expression={[math]::Round((Get-ChildItem -Path $_.FullPath -Recurse | Measure-Object -Property Length -Sum).Sum/1GB,2)}}
```

---

## 🚀 AFTER CLEANUP: Verify Project on E Drive

```powershell
# Verify E:\YCCE_RAG exists and is accessible
Write-Host "Checking E:\YCCE_RAG project..."
if(Test-Path 'E:\YCCE_RAG\main_initial_crawl.py') {
    Write-Host "✅ Main project found on E drive"
    Write-Host "✅ Ready to run!"
} else {
    Write-Host "❌ Project not found - need to copy it"
}

# Check E drive space
Write-Host "`nE Drive Status:"
Get-Volume | Where-Object {$_.DriveLetter -eq 'E'} | Format-Table DriveLetter, @{Label='TotalGB';Expression={[math]::Round($_.Size/1GB,2)}}, @{Label='FreeGB';Expression={[math]::Round($_.SizeRemaining/1GB,2)}}
```

---

## 📋 VERIFY PYTHON ENVIRONMENT

```powershell
# Verify Python works
python --version
pip list | grep -E "langchain|faiss|streamlit"

# Go to project
cd E:\YCCE_RAG
python -m py_compile ingestion/ingest_pipeline.py
if ($LASTEXITCODE -eq 0) { Write-Host "✅ Project syntax OK" } else { Write-Host "❌ Syntax error" }
```

---

## 🔄 IF YOU HAVE CONDA ENVIRONMENTS ON C DRIVE

```powershell
# List all conda environments
conda env list

# If you have env on C drive, move it to E:
# Option 1: Clone to E drive (safer)
conda create --prefix E:\Python_Envs\ycce-env --clone base

# Option 2: Move entirely
# (Only if you have backup!)
```

---

## 📦 IF YOU HAVE DOWNLOADS/BACKUPS ON C DRIVE

```powershell
# Create backup folder on E drive
New-Item -ItemType Directory -Path 'E:\C_Drive_Backup' -Force

# Move Downloads
if(Test-Path 'C:\Users\HP\Downloads') {
    Move-Item -Path 'C:\Users\HP\Downloads\*' -Destination 'E:\C_Drive_Backup\Downloads' -Force -ErrorAction SilentlyContinue
    Write-Host "✅ Moved Downloads to E drive"
}

# Move Desktop files (if many)
if(Test-Path 'C:\Users\HP\Desktop') {
    $desktopSize = (Get-ChildItem -Path 'C:\Users\HP\Desktop' -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    if($desktopSize -gt 1GB) {
        Write-Host "⚠️ Desktop has $(([math]::Round($desktopSize/1GB,2))) GB - consider moving large files to E drive"
    }
}
```

---

## 🎯 FINAL STEPS (After C Drive has free space)

### Step 1: Run the project from E drive
```bash
cd E:\YCCE_RAG
python main_initial_crawl.py
```

### Step 2: Monitor progress
Open another PowerShell and watch:
```powershell
# Watch ingestion progress
while($true) {
    Get-Volume | Where-Object {$_.DriveLetter -eq 'E'} | Format-Table DriveLetter, @{Label='FreeGB';Expression={[math]::Round($_.SizeRemaining/1GB,2)}}
    Start-Sleep -Seconds 10
}
```

### Step 3: Verify FAISS index created
```bash
ls E:\YCCE_RAG\chatbot\faiss_index
ls E:\YCCE_RAG\data\
```

---

## ⚠️ WHAT NOT TO DELETE

❌ DO NOT DELETE:
- C:\Windows (system files - CRITICAL)
- C:\Windows\System32
- C:\Program Files (unless you don't use programs)
- C:\Program Files (x86) (unless you don't use programs)
- C:\ProgramData (program data - CRITICAL)

✅ SAFE TO DELETE:
- C:\Windows\Temp\* (temporary files)
- C:\Users\HP\AppData\Local\Temp\* (user temp files)
- C:\Users\HP\AppData\Local\pip\cache (pip package cache)
- Recycle Bin files
- Old downloads

---

## 📊 DISK SPACE SUMMARY

### Before Cleanup:
- C Drive: 161 GB | **0 GB Free** ❌
- E Drive: ~160 GB | **83 GB Free** ✅

### After Cleanup (Expected):
- C Drive: 161 GB | **15-30 GB Free** ✅
- E Drive: ~160 GB | **83 GB Free** ✅

### After Project Migration (Expected):
- C Drive: 161 GB | **15-20 GB Free** ✅
- E Drive: ~160 GB | **60-70 GB Free** ✅

---

## 🆘 TROUBLESHOOTING

### If cleanup stuck on file:
```powershell
# Try force delete specific folder
takeown /F "C:\path\to\folder" /R /D Y
icacls "C:\path\to\folder" /grant Everyone:F /T
Remove-Item "C:\path\to\folder" -Recurse -Force
```

### If free space still 0:
1. Restart computer
2. Run cleanup again
3. Check Windows\SoftwareDistribution\Download (Windows Updates - can be 5-20GB)
4. Run disk cleanup utility: `cleanmgr`

### If project won't start:
```powershell
cd E:\YCCE_RAG
python -m pip install -r requirements.txt --upgrade
python main_initial_crawl.py --help
```

---

## ✅ EXECUTION CHECKLIST

Run in order:

- [ ] **Step 1**: Copy-paste cleanup commands (runs in 2-3 min)
- [ ] **Step 2**: Check freed space (should see 15-30+ GB free on C)
- [ ] **Step 3**: Verify Python environment works
- [ ] **Step 4**: Check E:\YCCE_RAG is accessible
- [ ] **Step 5**: Run `python main_initial_crawl.py` from E:\YCCE_RAG
- [ ] **Step 6**: Monitor batch ingestion progress
- [ ] **Step 7**: Verify FAISS index created (should be ~500MB)
- [ ] **Step 8**: Test chatbot: `streamlit run chatbot/streamlit_app.py`

---

Let me know when you've run the cleanup so I can help verify everything works! 🚀
