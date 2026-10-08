"""Blender batch exporter: register the supplied colored model and emit portable COLLADA.

blender -b --factory-startup --python scripts/export_mid360_blender.py -- \
  --source SOURCE.blend --output-dir meshes/mid360 --source-output meshes/mid360/source.blend
The input is never overwritten. Only the named sensor mesh and its labels are exported.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import bpy
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--source-output', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if args.source_output and args.source.resolve() == args.source_output.resolve():
        raise ValueError('Refusing to overwrite the input Blender file')
    source_sha = hashlib.sha256(args.source.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()))
    keep = {'MID360_colored', 'MID360_label_LIVOX', 'MID360_label_model', 'MID360_top_label'}
    for obj in list(bpy.data.objects):
        if obj.name not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    body = bpy.data.objects['MID360_colored']
    mesh = body.data
    # Keep the audited registration after winding repairs; face normals may change.
    saved_registration = json.loads(body['mid360_source_to_mount']) if 'mid360_source_to_mount' in body else None
    original = np.array([body.matrix_world @ vertex.co for vertex in mesh.vertices])
    if saved_registration is not None:
        transform = np.array(saved_registration, dtype=float)
        if transform.shape != (4, 4) or not np.isfinite(transform).all() or not np.allclose(transform[3], [0, 0, 0, 1]):
            raise ValueError('Invalid saved registration')
        rotation, center = transform[:3, :3], -transform[:3, 3]
    else:
        # Legacy sources: optical cap for +Z and front housing side plane for +X.
        top = max((p for p in mesh.polygons if p.center.z > .058 and p.normal.z > .99), key=lambda p: p.area)
        front = max((p for p in mesh.polygons if p.normal.x > .999 and
                     abs(p.normal.y) < .0001 and .03 < p.normal.z < .04), key=lambda p: p.area)
        z = np.array(top.normal, dtype=float)
        z /= np.linalg.norm(z)
        x = np.array(front.normal, dtype=float)
        x -= z * np.dot(x, z)
        x /= np.linalg.norm(x)
        rotation = np.stack([x, np.cross(z, x), z])
        aligned = original @ rotation.T
        bottom = aligned[aligned[:, 2] < aligned[:, 2].min() + 1e-4]
        center = (bottom.min(0) + bottom.max(0)) / 2
        center[2] = aligned[:, 2].min()
    aligned = original @ rotation.T
    canonical = aligned - center
    if not np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-7) or not np.isclose(np.linalg.det(rotation), 1):
        raise ValueError('Registration is not a rigid rotation')
    if not (.072 < np.ptp(canonical[:, 0]) < .074 and
            .064 < np.ptp(canonical[:, 1]) < .066 and .059 < np.ptp(canonical[:, 2]) < .061):
        raise ValueError('Unexpected dimensions: refusing silent rescaling')

    ns = 'http://www.collada.org/2005/11/COLLADASchema'
    ET.register_namespace('', ns)

    def sub(parent, tag, text=None, **attrs):
        element = ET.SubElement(parent, '{' + ns + '}' + tag, attrs)
        if text is not None:
            element.text = str(text)
        return element

    def numbers(array):
        return ' '.join(f'{number:.9g}' for number in np.asarray(array).flatten())

    root = ET.Element('{' + ns + '}COLLADA', version='1.4.1')
    asset = sub(root, 'asset')
    sub(asset, 'created', '2026-10-09T00:00:00Z')
    sub(asset, 'modified', '2026-10-09T00:00:00Z')
    sub(asset, 'unit', name='meter', meter='1')
    sub(asset, 'up_axis', 'Z_UP')
    effects = sub(root, 'library_effects')
    materials = sub(root, 'library_materials')
    geometries = sub(root, 'library_geometries')
    scenes = sub(root, 'library_visual_scenes')
    scene = sub(scenes, 'visual_scene', id='Scene', name='MID360')
    material_ids = {}
    material_report = []
    triangle_count = 0
    all_points = []
    for obj_index, obj in enumerate(sorted(bpy.data.objects, key=lambda o: o.name)):
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        evaluated_mesh = evaluated.to_mesh()
        evaluated_mesh.calc_loop_triangles()
        points = np.array([obj.matrix_world @ v.co for v in evaluated_mesh.vertices]) @ rotation.T - center
        all_points.append(points)
        normal_matrix = np.array(obj.matrix_world.to_3x3().inverted().transposed())
        normals = np.array([n.vector for n in evaluated_mesh.corner_normals]) @ normal_matrix.T @ rotation.T
        normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
        slots = []
        for material in evaluated_mesh.materials:
            key = material.name
            if key not in material_ids:
                mid = 'material_' + str(len(material_ids))
                material_ids[key] = mid
                shader = next((node for node in material.node_tree.nodes if node.type == 'BSDF_PRINCIPLED'), None)
                color = list(shader.inputs['Base Color'].default_value) if shader else list(material.diffuse_color)
                roughness = float(shader.inputs['Roughness'].default_value) if shader else .4
                effect = sub(effects, 'effect', id=mid + '_effect')
                phong = sub(sub(sub(effect, 'profile_COMMON'), 'technique', sid='common'), 'phong')
                sub(sub(phong, 'ambient'), 'color', numbers(color))
                sub(sub(phong, 'diffuse'), 'color', numbers(color))
                sub(sub(phong, 'specular'), 'color', '0.25 0.25 0.25 1')
                sub(sub(phong, 'shininess'), 'float', min(200, 2 / max(roughness ** 2, .01) - 2))
                sub(sub(materials, 'material', id=mid, name=key), 'instance_effect', url='#' + mid + '_effect')
                material_report.append({'name': key, 'diffuse': color, 'roughness_source': roughness})
            slots.append(material_ids[key])
        gid = 'geometry_' + str(obj_index)
        geometry = sub(geometries, 'geometry', id=gid, name=obj.name)
        mesh_xml = sub(geometry, 'mesh')
        for suffix, array in [('positions', points), ('normals', normals)]:
            sid = gid + '_' + suffix
            source = sub(mesh_xml, 'source', id=sid)
            sub(source, 'float_array', numbers(array), id=sid + '_array', count=str(array.size))
            accessor = sub(sub(source, 'technique_common'), 'accessor', source='#' + sid + '_array', count=str(len(array)), stride='3')
            for axis in 'XYZ':
                sub(accessor, 'param', name=axis, type='float')
        sub(sub(mesh_xml, 'vertices', id=gid + '_vertices'), 'input', semantic='POSITION', source='#' + gid + '_positions')
        for index, mid in enumerate(slots):
            triangles = [tri for tri in evaluated_mesh.loop_triangles if tri.material_index == index]
            if not triangles:
                continue
            triangle_count += len(triangles)
            primitive = sub(mesh_xml, 'triangles', count=str(len(triangles)), material=mid)
            sub(primitive, 'input', semantic='VERTEX', source='#' + gid + '_vertices', offset='0')
            sub(primitive, 'input', semantic='NORMAL', source='#' + gid + '_normals', offset='1')
            sub(primitive, 'p', ' '.join(str(i) for tri in triangles for pair in zip(tri.vertices, tri.loops) for i in pair))
        instance = sub(sub(scene, 'node', id='node_' + str(obj_index), name=obj.name), 'instance_geometry', url='#' + gid)
        binding = sub(sub(instance, 'bind_material'), 'technique_common')
        for mid in slots:
            sub(binding, 'instance_material', symbol=mid, target='#' + mid)
        evaluated.to_mesh_clear()
    sub(sub(root, 'scene'), 'instance_visual_scene', url='#Scene')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / 'mid360.dae'
    ET.ElementTree(root).write(target, encoding='utf-8', xml_declaration=True)
    transform = np.eye(4)
    transform[:3, :3] = rotation
    transform[:3, 3] = -center
    cloud = np.concatenate(all_points)
    report = dict(source_sha256=source_sha, source_body_triangles=len(mesh.polygons),
                  exported_triangles=triangle_count, units='meter', up_axis='Z_UP',
                  source_to_mount=transform.tolist(), registration='mesh reference planes; no scaling',
                  bounds_m=[cloud.min(0).tolist(), cloud.max(0).tolist()], materials=material_report,
                  output_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    (args.output_dir / 'geometry_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    if args.source_output:
        bpy.ops.wm.save_as_mainfile(filepath=str(args.source_output.resolve()))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
