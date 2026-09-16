"""Build local map paths and country lookup from Natural Earth 5.1.2 50m GeoJSON.
Usage: python scripts/build-country-map.py path/to/ne_50m_admin_0_countries.geojson
Source: https://github.com/nvkelso/natural-earth-vector/tree/v5.1.2/geojson
Natural Earth data is public domain. Coordinates use an equirectangular projection.
"""
import json,sys,re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
rename={'United States of America':'United States','Republic of Serbia':'Serbia','Czechia':'Czech Republic','United Republic of Tanzania':'Tanzania','Republic of the Congo':'Republic of Congo','Democratic Republic of the Congo':'Democratic Republic of Congo'}
shapes=[];lookup={}
def simplify(points, tolerance=.08):
 if len(points)<3:return points
 a,b=points[0],points[-1];dx=b[0]-a[0];dy=b[1]-a[1];den=dx*dx+dy*dy
 distances=[]
 for p in points[1:-1]:
  t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den)) if den else 0
  distances.append((p[0]-a[0]-t*dx)**2+(p[1]-a[1]-t*dy)**2)
 m=max(distances)
 if m<=tolerance*tolerance:return [a,b]
 i=distances.index(m)+1
 return simplify(points[:i+1])+simplify(points[i:])[1:]
for f in json.loads(Path(sys.argv[1]).read_text())['features']:
 p=f['properties']; name=rename.get(p['ADMIN'],p['ADMIN'])
 if name=='Antarctica':continue
 for key in ['ADMIN','NAME','NAME_EN','NAME_LONG','ISO_A2_EH','ISO_A3_EH','ISO_A2','ISO_A3']:
  alias=p.get(key)
  if alias and alias!='-99':lookup[alias.casefold()]=name
 lookup[name.casefold()]=name
 polygons=f['geometry']['coordinates']
 if f['geometry']['type']=='Polygon':polygons=[polygons]
 paths=[]
 for polygon in polygons:
  for ring in polygon:
   pts=simplify(ring)
   if len(pts)<4:pts=ring
   paths.append('M'+'L'.join(f'{(lon+180)*2.5:.1f},{(85-lat)*2.5:.1f}' for lon,lat in pts)+'Z')
 shapes.append({'name':name,'path':''.join(paths),'x':round((p['LABEL_X']+180)*2.5,1),'y':round((85-p['LABEL_Y'])*2.5,1)})
(root/'frontend/src/data/world-map.json').write_text(json.dumps(shapes,separators=(',',':'))+'\n')
(root/'backend/src/data/country-names.json').write_text(json.dumps(lookup,sort_keys=True,ensure_ascii=False)+'\n')
print('Generated',len(shapes),'country outlines')
