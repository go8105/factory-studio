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

# Modular shell: 23 x 14 m footprint matching the existing walking bounds.
concrete=mat('Concrete',(.46,.48,.46),0,.88)
cladding=mat('Ivory_panels',(.68,.7,.67),.12,.6)
glass=mat('Blue_glazing',(.13,.25,.30),.5,.2)
asphalt=mat('Asphalt',(.105,.12,.13),0,.95)
roofmat=mat('Roof_metal',(.32,.39,.41),.5,.52)
line=mat('Safety_marking',(.84,.68,.27),0,.7)
current=None
def category(name):
    global current
    current=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(current)
def b(name,p,s,m,bevel=.015):
    o=box(name,p,s,m,bevel);o.parent=current;return o
def c(name,p,r,d,m,axis='y'):
    o=cylinder(name,p,r,d,m,axis);o.parent=current;return o
category('Site')
b('Yard',(0,-.42,2),(34,.25,30),asphalt)
b('Foundation',(0,-.17,0),(23.5,.34,14.6),concrete)
b('Front_walk',(-6,-.05,9),(11,.12,3),concrete)
for x in [-15,15]:
    b('Curb',(x,-.17,0),(.2,.3,25),white)
for x in [-12,-8,-4,0,4,8,12]:
    b('Parking_line',(x,-.281,13),(.07,.012,3.5),white,0)
for x in [3.8,8.2]:
    b('Loading_lane',(x,-.281,10),(.09,.012,5),line,0)
for z in [8,9,10,11]:b('Crosswalk',(-9,-.275,z),(2,.02,.35),white,0)
category('FixedWalls')
# Back and left walls stay visible in the cutaway.
for z in [-7]:
    b('Rear_lower',(0,1.25,z),(23,2.5,.18),cladding)
    b('Rear_upper',(0,6.35,z),(23,3.7,.18),cladding)
    b('Rear_glazing',(0,3.5,z),(23,2,.10),glass)
    for x in range(-11,12,2):b('Rear_mullion',(x,3.5,z+.06),(.07,2,.14),steel)
b('West_wall',(-11.5,4.1,0),(.18,8.2,14),cladding)
for x in range(-11,12):b('Rear_seam',(x,6.35,-7.105),(.025,3.7,.015),steel,0)
category('Envelope')
# Front: separate office entrance and production loading shutter.
b('Office_front',(-7.5,4.1,7),(8,8.2,.18),cladding)
for y in [2,5.8]:
    b('Office_window',(-7.5,y,7.11),(6,1.8,.08),glass)
    for x in [-10.5,-9,-7.5,-6,-4.5]:b('Window_frame',(x,y,7.17),(.07,1.9,.09),steel)
b('Entrance',(-8,.95,7.19),(1.7,1.9,.08),dark)
b('Door_glass',(-8,1.12,7.25),(1.45,1.5,.035),glass)
b('Entrance_canopy',(-8,2.65,7.9),(3.4,.15,2.2),teal)
for x in [-9.45,-6.55]:b('Canopy_post',(x,1.25,8.8),(.08,2.5,.08),steel)
b('Front_header',(4,6.2,7),(15,4,.18),cladding)
b('Front_left_pier',(-1,2.1,7),(5,4.2,.18),cladding)
b('Front_right_pier',(10,2.1,7),(3,4.2,.18),cladding)
b('Loading_shutter',(5,2.1,7.05),(6,4.2,.12),roofmat)
for i in range(15):b('Shutter_slat',(5,.15+i*.28,7.13),(5.9,.025,.025),steel,0)
b('Loading_canopy',(5,4.5,7.8),(6.7,.16,1.8),teal)
for x in [1.7,8.3]:c('Bollard',(x,.45,8.2),.1,.9,line)
b('East_wall',(11.5,4.1,0),(.18,8.2,14),cladding)
for z in range(-6,7,2):
    b('East_window',(11.61,5.6,z),(.08,1.5,1.4),glass)
for x in range(-3,12):b('Front_seam',(x,6.2,7.105),(.025,3.9,.015),steel,0)
# A small raised building identifier, geometry only.
b('Sign_board',(-.3,6.3,7.19),(3,.8,.08),teal)
bpy.ops.object.text_add(location=pos((-1.55,6.05,7.25)))
o=bpy.context.object;o.name='Factory_sign';o.parent=current;o.rotation_euler=(pi/2,0,0);o.data.body='FACTORY 01';o.data.size=.33;o.data.extrude=.002;o.data.materials.append(white)
bpy.ops.object.convert(target='MESH')
category('Structure')
for x in [-11.15,-2.85,10.95]:
    for z in [-6.65,6.75]:
        b('Steel_column',(x,4,z),(.18,8,.24),steel)
        b('Column_base',(x,.1,z),(.34,.2,.4),dark)
# Rear perimeter structure does not obstruct the central line or walking route.
for x in [-11.15,-2.85,10.95]:b('Longitudinal_beam',(x,7.7,0),(.18,.35,13.5),steel)
category('Overhead')
for z in [-5,0,5]:
    b('Roof_beam',(0,7.75,z),(22.5,.3,.18),steel)
    for x in [-7,1,7]:
        b('Light_housing',(x,6.9,z),(2,.08,.25),dark)
        b('Light_diffuser',(x,6.84,z),(1.9,.025,.21),ring)
        for dx in [-.8,.8]:b('Suspension',(x+dx,7.2,z),(.018,.6,.018),steel,0)
b('Supply_duct',(3,7.2,-3),(14,.45,.55),steel)
for x in [-2,2,6,9]:b('Duct_outlet',(x,6.95,-3),(.65,.1,.65),white)
b('Cable_tray',(3,6.8,-5.7),(14,.14,.35),dark)
category('Roof')
b('Roof_deck',(0,8.25,0),(23.6,.18,14.6),roofmat)
for x in range(-11,12):b('Standing_seam',(x,8.37,0),(.025,.07,14.5),steel,0)
for z in [-7.25,7.25]:b('Parapet',(0,8.55,z),(23.6,.45,.13),cladding)
for x in [-11.7,11.7]:b('Parapet',(x,8.55,0),(.13,.45,14.6),cladding)
for x in [-6,-1,4,9]:
    b('Skylight_curb',(x,8.43,-3),(2.4,.2,1.8),dark)
    b('Skylight',(x,8.56,-3),(2.2,.08,1.6),glass)
for x in [-5,0,5]:
    b('HVAC_base',(x,8.55,2),(3.5,.3,2.4),dark)
    b('HVAC_unit',(x,9.15,2),(3.2,.9,2.1),white)
    for dx in [-.8,.8]:
        c('Fan_grille',(x+dx,9.64,2),.59,.06,dark)
        for i in [-2,-1,0,1,2]:b('Fan_bar',(x+dx+i*.17,9.69,2),(.035,.025,1),steel,0)
    for i in range(8):b('HVAC_louver',(x,8.88+i*.08,3.065),(2.8,.025,.025),steel,0)
# Save editable components, then batch each category/material for fewer draw calls.
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/blender/factory-building.blend'))
for parent in [o for o in bpy.data.objects if o.type=='EMPTY']:
    meshes=[o for o in parent.children if o.type=='MESH']
    by_material={}
    for o in meshes:
        by_material.setdefault(o.data.materials[0].name,[]).append(o)
    for material,objects in by_material.items():
        bpy.ops.object.select_all(action='DESELECT')
        for o in objects:
            o.select_set(True);bpy.context.view_layer.objects.active=o
            for modifier in list(o.modifiers):bpy.ops.object.modifier_apply(modifier=modifier.name)
        bpy.context.view_layer.objects.active=objects[0]
        bpy.ops.object.join();bpy.context.object.name=parent.name+'_'+material
bpy.ops.export_scene.gltf(filepath=str(ROOT/'frontend/public/models/factory-building.glb'),export_format='GLB',export_apply=True)
print('FACTORY_EXPORT_OK')
