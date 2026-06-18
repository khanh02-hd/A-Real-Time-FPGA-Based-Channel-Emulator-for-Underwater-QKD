import os
import subprocess

# Get all tracked files
result = subprocess.run(['git', 'ls-files'], stdout=subprocess.PIPE, text=True)
files = result.stdout.split('\n')

for f in files:
    if not f or f.endswith('.png') or f == 'fix_lines.py':
        continue
    if os.path.exists(f):
        with open(f, 'rb') as file:
            data = file.read()
        
        # Replace CRLF -> LF, CR -> LF
        data = data.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
        
        # Append space to force git to see the change
        if not data.endswith(b' '):
            data += b' '
            
        with open(f, 'wb') as file:
            file.write(data)

# Remove the fix_lines.py script
if os.path.exists('fix_lines.py'):
    os.remove('fix_lines.py')
