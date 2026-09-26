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
box('Cabinet',(0,.72,0),(2.55,1.18,2.05),white)
box('Front_panel',(0,.76,1.04),(2.25,.87,.04),teal)
for x in [-1.03,1.03]:
    box('Door_handle',(x,.85,1.08),(.045,.29,.055),steel)
    for z in [-.78,.78]:
        cylinder('Leveling_foot',(x,.12,z),.11,.18,dark)
for i in range(7):box('Vent',(-.55+i*.16,.5,1.071),(.075,.18,.018),dark,.005)
box('Belt',(0,1.38,0),(2.8,.11,1.02),belt)
for z in [-.58,.58]:box('Conveyor_rail',(0,1.4,z),(2.8,.16,.1),steel)
for x in [-1.14,1.14]:
    for z in [-.87,.87]:box('Frame_post',(x,2.1,z),(.085,1.35,.085),steel)
for z in [-.87,.87]:box('Frame_top',(0,2.81,z),(2.4,.1,.1),steel)
for x in [-1.14,1.14]:box('Frame_cross',(x,2.81,0),(.1,.1,1.8),steel)
box('Rear_guard',(0,2.05,-.92),(2.35,1.35,.045),teal)
# Open front viewing aperture makes the inspection mechanism visible without costly glass.
box('Safety_header',(0,2.69,.92),(2.35,.18,.06),white)
box('Camera_bridge',(0,2.63,0),(.17,.12,1.75),dark)
box('Camera_body',(0,2.4,0),(.42,.32,.42),teal)
cylinder('Camera_lens',(0,2.18,0),.12,.18,dark)
bpy.ops.mesh.primitive_torus_add(major_radius=.25,minor_radius=.035,major_segments=32,minor_segments=8,location=pos((0,2.06,0)))
bpy.context.object.name='Inspection_ring';bpy.context.object.data.materials.append(ring)
box('Sensor_body',(-.7,1.65,-.67),(.15,.2,.18),dark)
box('Sensor_face',(-.7,1.65,-.565),(.09,.1,.02),red)
box('Stopper',(0.38,1.53,0),(.055,.19,.8),steel)
cylinder('Tower_stem',(1.05,2.96,-.78),.04,.25,steel)
for name,y,m in [('Lamp_green',3.12,green),('Lamp_amber',3.26,amber),('Lamp_red',3.4,red)]:cylinder(name,(1.05,y,-.78),.085,.12,m)
cylinder('Tower_cap',(1.05,3.49,-.78),.09,.04,dark)
box('Control_arm',(1.22,2,.8),(.35,.08,.08),steel)
box('Control_screen',(1.32,2.12,.9),(.35,.34,.1),dark)
box('Screen_face',(1.32,2.14,.958),(.27,.22,.014),teal)
cylinder('Emergency_stop',(1.32,1.93,.97),.055,.045,red,'z')
# Apply modifiers at export; keep the editable source.
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/blender/vision-cell.blend'))
bpy.ops.export_scene.gltf(filepath=str(ROOT/'frontend/public/models/vision-cell.glb'),export_format='GLB',export_apply=True)
print('VISION_EXPORT_OK')
