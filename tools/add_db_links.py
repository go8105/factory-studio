"""Add native internal links only: artifact tool cannot render HYPERLINK formulas.
All sheet data and formatting are authored by artifact-tool. No values modified here.
"""
import json,sys,zipfile,xml.etree.ElementTree as E
from pathlib import Path
p=Path(sys.argv[1]);specs=json.loads(Path(sys.argv[2]).read_text());ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
E.register_namespace('',ns)
with zipfile.ZipFile(p) as z:entries={n:z.read(n) for n in z.namelist()}
for i,s in enumerate(specs,1):
 name=f'xl/worksheets/sheet{i}.xml';root=E.fromstring(entries[name]);links=E.Element('{'+ns+'}hyperlinks')
 for row,col,target,cell,label in [[4,0,'00_목차','A1','전체 목차'],*s['links']]:
  E.SubElement(links,'{'+ns+'}hyperlink',{'ref':chr(65+col)+str(row),'location':"'"+target+"'!"+cell,'display':label})
 # CT_Worksheet: hyperlinks follow validations and precede print/page/drawing elements.
 after={'sheetPr','dimension','sheetViews','sheetFormatPr','cols','sheetData','sheetCalcPr','sheetProtection','protectedRanges','scenarios','autoFilter','sortState','dataConsolidate','customSheetViews','mergeCells','phoneticPr','conditionalFormatting','dataValidations'}
 index=0
 for j,child in enumerate(root):
  if child.tag.split('}')[-1] in after:index=j+1
 root.insert(index,links);entries[name]=E.tostring(root,encoding='utf-8',xml_declaration=True)
with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
 for n,b in entries.items():z.writestr(n,b)
