// Single sheet specification, portable ExcelJS export or Codex artifact rendering/export.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const d=JSON.parse(await fs.readFile(path.join(root,'docs/db/schema-metadata/schema.json'),'utf8'));
const modules={core:'CORE',mes:'MES',erp:'ERP',fems:'FEMS',qms:'QMS',wms:'WMS',bems:'BEMS',spc:'SPC'};
const specs=[];
function spec(name,title,heads,rows,widths){const s={name,title,heads,rows:rows.map(row=>row.map(value=>value===''?null:value)),widths,links:[]};specs.push(s);return s}
const toc=spec('00_목차','Factory Studio 모듈별 DB 명세',['모듈','테이블','컬럼','테이블 목록','컬럼 명세','참조 관계','규칙·보존'],[],[23,12,12,23,23,23,23]);
const cross=d.relations.filter(r=>r.source.split('.')[0]!==r.target.split('.')[0]);
spec('00_전체관계','모듈 간 참조 관계',['원본 테이블','컬럼','참조 테이블','참조 컬럼','설명'],cross.map(r=>[r.source,r.columns.join('\n'),r.target,r.target_columns.join('\n'),r.note]),[36,32,36,32,68]);
spec('00_변경이력','설계 변경 이력',['버전','작업','작성일','내용','검증 상태'],d.change_log.map(c=>[c.version,c.task,c.date,c.change,c.status]),[13,16,17,80,48]);
for(const [mod,prefix] of Object.entries(modules)){
 const tables=d.tables.filter(t=>t.name.startsWith(mod+'.'));const names=new Set(tables.map(t=>t.name));
 const row=[prefix,tables.length,tables.reduce((n,t)=>n+t.columns.length,0),'테이블 목록','컬럼 명세','참조 관계','규칙·보존'];toc.rows.push(row);
 ['테이블','컬럼','관계','규칙'].forEach((s,i)=>toc.links.push([toc.rows.length+5,i+3,`${prefix}_${s}`,'A1',row[i+3]]));
 spec(prefix+'_테이블',prefix+' 테이블 목록',['테이블','한글명','단계','범위','컬럼 수','설명'],tables.map(t=>[t.name,t.label,t.phase,t.scope,t.columns.length,t.note||'상세 규칙 시트 참조']),[37,25,12,18,12,65]);
 spec(prefix+'_컬럼',prefix+' 컬럼 명세',['테이블','컬럼','한글명','타입','NULL','키','기본값','설명'],tables.flatMap(t=>t.columns.map(c=>[t.name,c.name,c.label,c.type,c.nullable?'허용':'불가',[...new Set(d.constraints.filter(k=>k.table===t.name&&['PK','UK','UK_PARTIAL'].includes(k.kind)&&k.columns.includes(c.name)).map(k=>k.kind).concat(d.relations.some(r=>r.source===t.name&&r.columns.includes(c.name))?['FK']:[]))].join('/'),c.default??'—',c.rule||'규칙·관계 시트 참조'])),[36,32,25,24,10,18,35,65]);
 const rs=d.relations.filter(r=>names.has(r.source));const rel=spec(prefix+'_관계',prefix+' 외래키 관계',['원본','컬럼','참조 대상','참조 컬럼','삭제/변경','설명'],rs.map(r=>[r.source,r.columns.join('\n'),r.target,r.target_columns.join('\n'),r.on_delete+'/'+r.on_update,r.note]),[36,32,36,32,25,60]);
 rs.forEach((r,i)=>{const targetPrefix=modules[r.target.split('.')[0]],tt=d.tables.filter(t=>t.name.startsWith(r.target.split('.')[0]+'.'));rel.links.push([i+6,2,targetPrefix+'_테이블','A'+(tt.findIndex(t=>t.name===r.target)+6),r.target])});
 const rules=d.constraints.filter(c=>names.has(c.table)).map(c=>[c.table,c.kind,c.columns.join('\n'),c.expression||'—',c.reason]);
 for(const st of d.states.filter(s=>names.has(s.table)))rules.push([st.table,'STATE',st.column,st.values.join(' / '),st.transition||'상태 전이 계약 참조']);
 for(const cl of (d.code_lists||[]).filter(c=>names.has(c.target)||(mod==='core'&&c.target==='공통 단위')))rules.push([cl.target,'CODE',cl.column,cl.values.join(' / '),cl.note||'']);
 for(const t of tables)rules.push([t.name,'RETENTION','회원 / 게스트',t.retention,t.guest_cleanup]);
 spec(prefix+'_규칙',prefix+' 제약·정책·상태·보존',['테이블','종류','컬럼','정의','이유/관리 정책'],rules,[36,23,34,90,65]);
}
const out=path.join(root,'docs/db/DB설계서.xlsx'),pre=path.join(root,'work/db-design/previews-fs007b');await fs.mkdir(pre,{recursive:true});
const artifact=process.argv.includes('--artifact');let wb,SpreadsheetFile;
if(artifact){const require=createRequire(path.join(root,'work/db-design/package.json'));({SpreadsheetFile}=require('@oai/artifact-tool'));wb=require('@oai/artifact-tool').Workbook.create();for(const s of specs)wb.worksheets.add(s.name)}else{const {default:ExcelJS}=await import('exceljs');wb=new ExcelJS.Workbook();for(const s of specs)wb.addWorksheet(s.name)}
const subtitle=`v${d.version} / ${d.date} / 설계 초안 · 실제 DB 미적용`;
for(const [index,s] of specs.entries()){
 const sh=artifact?wb.worksheets.getItem(s.name):wb.getWorksheet(s.name),n=s.rows.length+5;
 const put=(r,c,value,formula=false)=>{if(artifact){const range=sh.getRangeByIndexes(r-1,c,1,1);if(formula)range.formulas=[[value]];else range.values=[[value]]}else{const cell=sh.getCell(r,c+1);cell.value=formula?{formula:value.slice(1)}:value}};
 put(2,0,s.title);put(3,0,subtitle);put(4,0,'전체 목차');
 const link=(r,c,sheet,cell,label)=>{if(artifact){put(r,c,label);sh.getRangeByIndexes(r-1,c,1,1).format.font={name:'Arial',size:11,color:'#315675'}}else sh.getCell(r,c+1).value={text:label,hyperlink:`#'${sheet}'!${cell}`}};
 link(4,0,'00_목차','A1','전체 목차');
 if(artifact){sh.showGridLines=false;sh.tabColor='#1F2D3D';sh.getRangeByIndexes(4,0,1,s.heads.length).values=[s.heads];if(s.rows.length)sh.getRangeByIndexes(5,0,s.rows.length,s.heads.length).values=s.rows;sh.getRangeByIndexes(0,0,n,s.heads.length).format.font={name:'Arial',size:11,color:'#1A1C1E'};sh.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:'#1F2D3D'};sh.getRangeByIndexes(4,0,1,s.heads.length).format={fill:'#1F2D3D',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},rowHeight:32,wrapText:true,horizontalAlignment:'center',verticalAlignment:'center'};sh.freezePanes.freezeRows(5);sh.tables.add(sh.getRangeByIndexes(4,0,s.rows.length+1,s.heads.length),true,'Module_'+index);s.widths.forEach((w,j)=>sh.getRangeByIndexes(0,j,n,1).format.columnWidth=w)}else{sh.views=[{showGridLines:false,state:'frozen',ySplit:5}];sh.properties.tabColor={argb:'FF1F2D3D'};sh.getRow(5).values=s.heads;for(const [i,r]of s.rows.entries())sh.getRow(i+6).values=r;s.widths.forEach((w,j)=>sh.getColumn(j+1).width=w);sh.eachRow(r=>r.eachCell(c=>{c.font={name:'Arial',size:11,color:{argb:'FF1A1C1E'}}}));sh.getCell('A2').font={name:'Arial',size:16,bold:true};sh.getRow(5).eachCell(c=>{c.fill={type:'pattern',pattern:'solid',fgColor:{argb:'FF1F2D3D'}};c.font={name:'Arial',size:11,bold:true,color:{argb:'FFFFFFFF'}}});sh.getRow(5).height=32;sh.autoFilter={from:{row:5,column:1},to:{row:n,column:s.heads.length}}}
 for(const [i,row] of s.rows.entries()){
  const lines=Math.max(...row.map((v,j)=>String(v??'').split('\n').reduce((a,l)=>a+Math.max(1,Math.ceil([...l].reduce((z,c)=>z+(c.charCodeAt(0)>255?1.8:1),0)/(s.widths[j]-3))),0)));const height=Math.max(32,lines*17+12);
  if(artifact){const rr=sh.getRangeByIndexes(i+5,0,1,s.heads.length);rr.format.wrapText=true;rr.format.rowHeight=height;rr.format.verticalAlignment='center';rr.format.fill=i%2?'#F7F7F6':'#FFFFFF'}else{const rr=sh.getRow(i+6);rr.height=height;rr.eachCell({includeEmpty:true},c=>{c.alignment={wrapText:true,vertical:'middle'};c.fill={type:'pattern',pattern:'solid',fgColor:{argb:i%2?'FFF7F7F6':'FFFFFFFF'}}})}
 }
 for(const l of s.links)link(...l);
 if(s.name==='00_목차'){put(15,0,'전체 규모');put(15,1,d.tables.length);put(15,2,d.tables.reduce((n,t)=>n+t.columns.length,0));put(16,0,'외래키');put(16,1,d.relations.length);put(17,0,'기준');put(17,1,d.task);put(18,0,'다음 설계');put(18,1,'FS-010 API 계약 (사용자 확인 후)');}
}
if(artifact){wb.recalculate();console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#SPILL!',options:{useRegex:true,maxResults:20},maxChars:1000})).ndjson);for(const s of specs){const end=String.fromCharCode(64+s.heads.length);const blob=await wb.render({sheetName:s.name,range:`A1:${end}${Math.min(9,s.rows.length+5)}`,scale:1,format:'png'});await fs.writeFile(path.join(pre,s.name+'.png'),new Uint8Array(await blob.arrayBuffer()))}await(await SpreadsheetFile.exportXlsx(wb)).save(out)}else await wb.xlsx.writeFile(out);
await fs.writeFile(path.join(pre,'sheet-specs.json'),JSON.stringify(specs));
if(artifact)execFileSync(process.env.FACTORY_PYTHON || 'python3',[path.join(root,'tools/add_db_links.py'),out,path.join(pre,'sheet-specs.json')]);
console.log(JSON.stringify({sheets:specs.length,tables:d.tables.length,columns:d.tables.reduce((n,t)=>n+t.columns.length,0),foreign_keys:d.relations.length,engine:artifact?'artifact-tool':'exceljs',output:out}));
