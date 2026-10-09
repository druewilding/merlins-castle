# Extract files from an Acorn DFS .ssd disk image.
import sys, os
img = open(sys.argv[1], 'rb').read()
s0, s1 = img[0:256], img[256:512]
n = s1[5] // 8
os.makedirs('files', exist_ok=True)
for i in range(n):
    e = s0[8 + i*8: 16 + i*8]
    name = e[:7].decode('ascii').rstrip()
    d = chr(e[7] & 0x7f)
    m = s1[8 + i*8: 16 + i*8]
    mixed = m[6]
    length = m[4] | (m[5] << 8) | (((mixed >> 4) & 3) << 16)
    start = m[7] | ((mixed & 3) << 8)
    load = m[0] | (m[1] << 8)
    data = img[start*256: start*256 + length]
    fn = f"{d}.{name}"
    open(os.path.join('files', fn), 'wb').write(data)
    print(f"{fn:12} len={length:6} load={load:04x} start={start}")
