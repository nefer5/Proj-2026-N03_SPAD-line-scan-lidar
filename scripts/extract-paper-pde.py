"""Print CSV by digitizing a checksum-pinned PDF vector curve; never edit the paper.
Usage: python scripts/extract-paper-pde.py path/to/2203.01560v1.pdf
Requires PyMuPDF only for source extraction, not simulator runtime.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import fitz
import yaml

ROOT=Path(__file__).resolve().parents[1]


def extract(path, metadata):
    data=Path(path).read_bytes()
    if sha256(data).hexdigest()!=metadata['pdf_sha256']:
        raise ValueError('PDF hash mismatch; recalibrate the correct paper version first')
    c=metadata['calibration']
    document=fitz.open(stream=data,filetype='pdf')
    page=document[metadata['page_index']]
    box=fitz.Rect(c['plot_box'])
    candidates=[]
    for drawing in page.get_drawings():
        rgb=drawing.get('color')
        if rgb is None or any(abs(a-b)>1e-7 for a,b in zip(rgb,c['curve_rgb'])):continue
        items=drawing['items']
        if len(items)!=metadata['points']-1 or not all(item[0]=='l' for item in items):continue
        points=[items[0][1]]+[item[2] for item in items]
        if all(box.contains(point) for point in points):candidates.append(points)
    if len(candidates)!=1:
        raise ValueError('Expected one matching colored polyline')
    points=candidates[0]
    (x0,w0),(x1,w1)=c['x_axis']
    (y0,p0),(y1,p1)=c['y_axis']
    rows=[]
    for point in points:
        wavelength=round(w0+(point.x-x0)*(w1-w0)/(x1-x0),c['wavelength_digits'])
        pde=round(p0+(point.y-y0)*(p1-p0)/(y1-y0),c['pde_digits'])
        if rows and wavelength<=rows[-1][0]:raise ValueError('Non-increasing curve')
        if not 0<=pde<=1:raise ValueError('Invalid extracted PDE')
        rows.append((wavelength,pde))
    return 'wavelength_nm,pde\n'+''.join(f'{w:g},{p:.4f}\n' for w,p in rows)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('pdf');args=parser.parse_args()
    metadata=yaml.safe_load((ROOT/'config/pde-datasets.yaml').read_text(encoding='utf-8'))['van_sieleghem_2022_fig7_3p5v']
    print(extract(args.pdf,metadata),end='')
