import glob
import os

files = glob.glob('D:/python/rtl/*.v') + glob.glob('D:/python/monitoring/*.py') + [
    'D:/python/README.md',
    'D:/python/rtl/uwoc_qkd_receiver.qsf',
    'D:/python/rtl/uwoc_qkd_receiver.sdc'
]

for f in files:
    if os.path.exists(f):
        with open(f, 'rb') as file:
            data = file.read()
        # Force conversion to LF
        data = data.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
        # Append a dummy space so Git detects a content change!
        data += b' '
        with open(f, 'wb') as file:
            file.write(data)
