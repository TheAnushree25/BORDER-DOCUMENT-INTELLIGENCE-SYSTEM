import os
import glob
import time

uploads = sorted(glob.glob("backend/uploads/DOC-*.jpg"), key=os.path.getmtime, reverse=True)
print("Latest 15 uploads:")
for p in uploads[:15]:
    mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(p)))
    size = os.path.getsize(p)
    print(f"{p}: {size} bytes, {mtime}")
