import os
import glob
from pathlib import Path
import numpy as np

print("================================================================================")
print("              BHARATRISK AI - APRIL 2020 DATA INTEGRITY AUDIT                   ")
print("================================================================================")

headers = ["Day", "Raw L1C (.h5)", "Proc L1C (.npz)", "Sat Feat (.npz)", "Raw QPE (.h5)", "QPE Feat (.npz)"]
print(f"{headers[0]:<8} | {headers[1]:<14} | {headers[2]:<16} | {headers[3]:<16} | {headers[4]:<14} | {headers[5]:<16}")
print("-" * 92)

tot_raw_l1c = 0
tot_proc_l1c = 0
tot_sat_feat = 0
tot_raw_qpe = 0
tot_qpe_feat = 0

days_audit = []

for day in range(1, 31):
    d_str = f"{day:02d}"
    d_iso = f"202004{d_str}"
    d_tag = f"{d_str}APR2020"
    
    raw_l1c = len(glob.glob(f"data/insat/l1c/3RIMG_L1C_ASIA_MER/2020/{d_str}APR/*.h5"))
    proc_l1c = len(glob.glob(f"data/insat/l1c/processed/*{d_tag}*.npz"))
    sat_feat = len(glob.glob(f"data/derived/satellite/{d_iso}*.npz"))
    raw_qpe = len(glob.glob(f"data/insat/qpe/3RIMG_L2B_HEM/2020/{d_str}APR/*.h5"))
    qpe_feat = len(glob.glob(f"data/derived/satellite/qpe_{d_iso}*.npz"))
    
    tot_raw_l1c += raw_l1c
    tot_proc_l1c += proc_l1c
    tot_sat_feat += sat_feat
    tot_raw_qpe += raw_qpe
    tot_qpe_feat += qpe_feat
    
    days_audit.append({
        "day": d_str,
        "raw_l1c": raw_l1c,
        "proc_l1c": proc_l1c,
        "sat_feat": sat_feat,
        "raw_qpe": raw_qpe,
        "qpe_feat": qpe_feat
    })
    
    print(f"APR {d_str:<4} | {raw_l1c:<14} | {proc_l1c:<16} | {sat_feat:<16} | {raw_qpe:<14} | {qpe_feat:<16}")

print("-" * 92)
print(f"{'TOTAL':<8} | {tot_raw_l1c:<14} | {tot_proc_l1c:<16} | {tot_sat_feat:<16} | {tot_raw_qpe:<14} | {tot_qpe_feat:<16}")
print("================================================================================")

print("\n=== RUNNING COMPLETE ARRAY INTEGRITY VERIFICATION ===")
import time
t0 = time.time()

corrupt_sat = []
sat_files = glob.glob("data/derived/satellite/202004*.npz")
for f in sat_files:
    try:
        data = np.load(f)
        # Verify required keys
        req = ["wv_radiance", "tir1_bt_c", "vis_radiance"]
        for k in req:
            if k not in data or data[k].shape != (114, 84):
                corrupt_sat.append((f, f"Missing or bad shape for {k}"))
                break
    except Exception as e:
        corrupt_sat.append((f, str(e)))

print(f"Verified {len(sat_files)} Satellite Feature files in {time.time()-t0:.2f}s. Corrupt/Invalid: {len(corrupt_sat)}")

t1 = time.time()
corrupt_qpe = []
qpe_files = glob.glob("data/derived/satellite/qpe_202004*.npz")
for f in qpe_files:
    try:
        data = np.load(f)
        req = ["qpe_rate_mm_hr", "qpe_1h_mm", "qpe_3h_mm", "qpe_6h_mm", "qpe_valid_mask"]
        for k in req:
            if k not in data or data[k].shape != (114, 84):
                corrupt_qpe.append((f, f"Missing or bad shape for {k}"))
                break
    except Exception as e:
        corrupt_qpe.append((f, str(e)))

print(f"Verified {len(qpe_files)} QPE Feature files in {time.time()-t1:.2f}s. Corrupt/Invalid: {len(corrupt_qpe)}")

# Calculate disk space usage
def get_dir_size(path_str):
    total = 0
    p = Path(path_str)
    if not p.exists():
        return 0
    for f in p.glob("**/*"):
        if f.is_file():
            total += f.stat().st_size
    return total

raw_l1c_bytes = get_dir_size("data/insat/l1c/3RIMG_L1C_ASIA_MER/2020")
raw_qpe_bytes = get_dir_size("data/insat/qpe/3RIMG_L2B_HEM/2020")
proc_l1c_bytes = sum(Path(f).stat().st_size for f in glob.glob("data/insat/l1c/processed/*APR2020*.npz"))
sat_feat_bytes = sum(Path(f).stat().st_size for f in sat_files)
qpe_feat_bytes = sum(Path(f).stat().st_size for f in qpe_files)

print("\n=== STORAGE RECLAMATION SUMMARY ===")
print(f"Raw L1C (data/insat/l1c/3RIMG_L1C_ASIA_MER/2020): {raw_l1c_bytes / (1024**3):.2f} GB ({tot_raw_l1c} files)")
print(f"Raw QPE (data/insat/qpe/3RIMG_L2B_HEM/2020):        {raw_qpe_bytes / (1024**3):.2f} GB ({tot_raw_qpe} files)")
print(f"TOTAL RAW SPACE TO RECLAIM:                       {(raw_l1c_bytes + raw_qpe_bytes) / (1024**3):.2f} GB")
print("-" * 50)
print(f"Processed L1C regional arrays (.npz):             {proc_l1c_bytes / (1024**2):.2f} MB ({tot_proc_l1c} files)")
print(f"Derived Satellite features (.npz):                {sat_feat_bytes / (1024**2):.2f} MB ({len(sat_files)} files)")
print(f"Derived QPE features (.npz):                      {qpe_feat_bytes / (1024**2):.2f} MB ({len(qpe_files)} files)")
print(f"TOTAL PRESERVED PROCESSED STORAGE:                {(proc_l1c_bytes + sat_feat_bytes + qpe_feat_bytes) / (1024**2):.2f} MB")
print(f"COMPRESSION RATIO:                                {(1 - (proc_l1c_bytes + sat_feat_bytes + qpe_feat_bytes)/(raw_l1c_bytes + raw_qpe_bytes))*100:.2f}% reduction")
