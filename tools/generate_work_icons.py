"""코드로 그린 시계 SVG와 같은 형태의 PWA PNG 아이콘. 외부 렌더러/사진 없음."""
import math
import struct
import zlib
from pathlib import Path


def chunk(kind, data):
    return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)


def line_distance(x,y,ax,ay,bx,by):
    t=max(0,min(1,((x-ax)*(bx-ax)+(y-ay)*(by-ay))/((bx-ax)**2+(by-ay)**2)))
    return math.hypot(x-ax-t*(bx-ax),y-ay-t*(by-ay))


def make(size):
    rows=bytearray()
    for y in range(size):
        rows.append(0)
        for x in range(size):
            count=0
            for dx,dy in [(0.25,0.25),(0.75,0.25),(0.25,0.75),(0.75,0.75)]:
                sx,sy=(x+dx)*512/size,(y+dy)*512/size
                on=abs(math.hypot(sx-256,sy-256)-130)<=10 or line_distance(sx,sy,256,164,256,264)<=11 or line_distance(sx,sy,256,264,324,306)<=11
                count+=on
            rows.extend(round(a+(b-a)*count/4) for a,b in zip((31,45,61),(247,247,246)))
    data=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',size,size,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')
    (Path(__file__).resolve().parents[1]/f'frontend/public/work-icon-{size}.png').write_bytes(data)

if __name__=='__main__':
    for size in (192,512):make(size)
