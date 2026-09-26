"""Rebuild the original Factory Studio vision cell with Blender --background --python."""
import bpy
from pathlib import Path
from math import pi
ROOT = Path(__file__).resolve().parents[2]
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
def mat(name, color, metal=0, rough=.4, emission=0):
    m=bpy.data.materials.new(name); m.use_nodes=True
    p=next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'); p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough
    p.inputs['Emission Color'].default_value=(*color,1); p.inputs['Emission Strength'].default_value=emission
    return m
white=mat('Porcelain',(.73,.76,.74)); dark=mat('Graphite',(.035,.055,.065)); steel=mat('Brushed_aluminium',(.43,.49,.52),.7)
teal=mat('Indigo',(.08,.17,.22)); belt=mat('Conveyor_rubber',(.025,.035,.035),0,.8)
ring=mat('Inspection_light',(.65,.88,1),0,.3,.1)
red=mat('Lamp_red',(.8,.07,.035)); amber=mat('Lamp_amber',(.95,.48,.025)); green=mat('Lamp_green',(.08,.62,.32))
# Author coordinates are web x,y,z (y up); Blender uses x,-z,y.
def pos(p): return (p[0],-p[2],p[1])
def box(name,p,s,m,bevel=.025):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos(p)); o=bpy.context.object; o.name=name
    o.dimensions=(s[0],s[2],s[1]); bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(m)
    if bevel:
        b=o.modifiers.new('Machined_edges','BEVEL'); b.width=bevel;b.segments=2
        o.modifiers.new('Weighted_normals','WEIGHTED_NORMAL')
    return o
def cylinder(name,p,r,depth,m,axis='y'):
    bpy.ops.mesh.primitive_cylinder_add(vertices=20,radius=r,depth=depth,location=pos(p));o=bpy.context.object;o.name=name
    if axis=='z':o.rotation_euler[0]=pi/2
    o.data.materials.append(m);return o

for kind in ['assembly','packaging']:
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    box('Cabinet',(0,.67,0),(2.5,1.22,2.05),white)
    box('Door_panel',(0,.7,1.04),(2.26,.92,.045),teal)
    for x in [-1,1]:
        box('Handle',(x,.84,1.09),(.045,.27,.055),steel)
        for z in [-.8,.8]:cylinder('Foot',(x,.08,z),.1,.15,dark)
    box('Conveyor',(0,1.36,0),(2.8,.12,.95),belt)
    for z in [-.54,.54]:box('Guide_rail',(0,1.43,z),(2.8,.1,.07),steel)
    for x in [-1.15,1.15]:
        for z in [-.8,.8]:box('Frame',(x,2.03,z),(.09,1.35,.09),steel)
    for z in [-.8,.8]:box('Top_rail',(0,2.7,z),(2.4,.1,.1),steel)
    box('Back_panel',(0,2,-.88),(2.4,1.35,.04),white)
    box('Header',(0,2.58,.85),(2.4,.22,.065),teal)
    box('Electrical_box',(.83,1.8,.89),(.42,.42,.1),dark)
    box('Display',(.83,1.88,.95),(.3,.16,.02),ring)
    cylinder('Emergency',(.83,1.66,.97),.05,.04,red,'z')
    cylinder('Tower',(1.07,2.96,-.8),.075,.4,green)
    if kind=='assembly':
        box('Press_bridge',(0,2.48,0),(1.8,.18,.6),steel)
        for x in [-.55,.55]:cylinder('Guide_rod',(x,2,0),.055,.85,steel)
        cylinder('Cylinder',(0,2.6,0),.18,.36,teal)
        head=box('PressHead',(0,2.05,0),(1.15,.18,.6),dark)
        box('Fixture',(0,1.51,0),(.85,.18,.65),steel)
        box('Workpiece',(0,1.64,0),(.55,.09,.4),teal)
    else:
        box('Sealer_bridge',(0,2.46,0),(1.8,.16,.55),steel)
        for x in [-.72,.72]:cylinder('Sealer_rod',(x,2.1,0),.05,.6,steel)
        box('Sealer',(0,2.08,0),(1.6,.12,.4),dark)
        cardboard=mat('Cardboard',(.48,.32,.16),0,.9)
        box('Carton',(0,1.67,0),(.85,.48,.65),cardboard)
        box('Tape',(0,1.92,0),(.13,.012,.64),white,.002)
        cylinder('Tape_roll',(0,2.75,0),.23,.2,white,'z')
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/('assets/blender/'+kind+'-cell.blend')))
    bpy.ops.export_scene.gltf(filepath=str(ROOT/('frontend/public/models/'+kind+'-cell.glb')),export_format='GLB',export_apply=True)
print('LINE_EXPORT_OK')
