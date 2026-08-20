#!/usr/bin/env python3
"""Extract the stock DTB segment from a boot image.

boot header v1: kernel data starts at page_size (4096), kernel size at offset 8.
Image.gz-dtb = gzip(Image) + concatenated DTBs. Bootloader selects one DTB via
androidboot.dtb_idx, so the STOCK dtb ORDER must be preserved. We emit the
stock dtb segment so CI can repack: our Image.gz + stock dtb.
"""
import struct
import sys
import zlib

path = sys.argv[1] if len(sys.argv) > 1 else 'boot_stock.img'
out = sys.argv[2] if len(sys.argv) > 2 else 'stock_dtb.bin'

d = open(path, 'rb').read()
ks = struct.unpack('<I', d[8:12])[0]
kgz = d[4096:4096 + ks]
dobj = zlib.decompressobj(16 + zlib.MAX_WBITS)
dobj.decompress(kgz)
dtb = dobj.unused_data
open(out, 'wb').write(dtb)
print('stock dtb segment:', len(dtb), 'bytes, first magic:', dtb[:4].hex())
assert dtb[:4] == b'\xd0\x0d\xfe\xed', 'no DTB magic in tail'
