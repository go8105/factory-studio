await figma.setCurrentPageAsync(figma.root.children[0]);
await Promise.all(["Regular","Medium","Bold"].map(style=>figma.loadFontAsync({family:"Noto Sans KR",style})));
const ids=[], vars={},families={},styles={};
function track(n){ids.push(n.id);return n}
function hex(h){return {r:parseInt(h.slice(1,3),16)/255,g:parseInt(h.slice(3,5),16)/255,b:parseInt(h.slice(5,7),16)/255}}
const primitives=figma.variables.createVariableCollection("FS / Primitives"),semantic=figma.variables.createVariableCollection("FS / Workspace");const variableIds=[];
for(const [name,value,scope] of [["canvas","#F7F7F6","FRAME_FILL"],["surface","#FFFFFF","FRAME_FILL"],["ink","#1A1C1E","TEXT_FILL"],["muted","#59636C","TEXT_FILL"],["navy","#1F2D3D","FRAME_FILL"],["line","#D4D8DB","STROKE_COLOR"],["soft","#EDF2F1","FRAME_FILL"],["accent","#2D6257","TEXT_FILL"]]){
 const p=figma.variables.createVariable("base/"+name,primitives,"COLOR");p.scopes=[];p.setValueForMode(primitives.modes[0].modeId,hex(value));
 const v=figma.variables.createVariable("color/"+name,semantic,"COLOR");v.scopes=[scope,...(scope==="FRAME_FILL"?["SHAPE_FILL"]:[])];v.setValueForMode(semantic.modes[0].modeId,{type:"VARIABLE_ALIAS",id:p.id});v.setVariableCodeSyntax("WEB","var(--fs-"+name+")");vars[name]=v;variableIds.push(p.id,v.id);
}
for(const [name,value,scope] of [["space/8",8,"GAP"],["space/16",16,"GAP"],["space/24",24,"GAP"],["radius/6",6,"CORNER_RADIUS"]]){const v=figma.variables.createVariable(name,semantic,"FLOAT");v.scopes=[scope];v.setValueForMode(semantic.modes[0].modeId,value);v.setVariableCodeSyntax("WEB","var(--fs-"+name.replace("/","-")+")");vars[name]=v;variableIds.push(v.id)}
function paint(key){return figma.variables.setBoundVariableForPaint({type:"SOLID",color:hex("#FFFFFF")},"color",vars[key])}
for(const [name,size,font] of [["Body",14,"Regular"],["Label",13,"Medium"],["Title",22,"Bold"]]){const s=figma.createTextStyle();s.name="FS/"+name;s.fontName={family:"Noto Sans KR",style:font};s.fontSize=size;s.lineHeight={unit:"PIXELS",value:Math.round(size*1.6)};styles[name]=s.id}
function text(label,color="ink"){const t=track(figma.createText());t.fontName={family:"Noto Sans KR",style:"Medium"};t.characters=label;t.textStyleId=styles.Label;t.fills=[paint(color)];return t}
function family(name,states,w,h){const cs=states.map(state=>{const c=track(figma.createComponent());c.name="State="+state;c.resize(w,h);c.layoutMode="HORIZONTAL";c.primaryAxisAlignItems="CENTER";c.counterAxisAlignItems="CENTER";c.paddingLeft=c.paddingRight=16;c.itemSpacing=8;c.setBoundVariable("cornerRadius",vars["radius/6"]);c.fills=[paint(state==="Primary"?"navy":state==="Complete"?"soft":"surface")];c.strokes=[paint("line")];const t=text(name+" · "+state,state==="Primary"?"surface":"ink");t.name="Label";c.appendChild(t);const prop=c.addComponentProperty("Label","TEXT",t.characters);t.componentPropertyReferences={characters:prop};return c});
 const set=track(figma.combineAsVariants(cs,figma.currentPage));set.name="FS/"+name;set.description="Workspace "+name+" with editable label and explicit states.";cs.forEach((c,i)=>{c.x=i*(w+16);c.y=0});set.x=100;set.y=2400+Object.keys(families).length*130;set.resize(states.length*(w+16),h+16);families[name]={setId:set.id,states:Object.fromEntries(cs.map(c=>[c.name.split("=")[1],c.id]))};
}
family("Button",["Default","Primary","Disabled"],160,40);
family("Step",["Pending","Active","Complete","Blocked"],196,48);
family("Field",["Default","Disabled"],232,56);
family("YC",["Off","Listening","Working","Reply","Error"],232,48);
family("Proposal",["Paused","Selected","Blocked"],240,48);
return {createdNodeIds:ids,pageId:figma.currentPage.id,variableIds,collections:[primitives.id,semantic.id],families,styles,fonts:["Noto Sans KR"],counts:{families:5,variants:17}};
