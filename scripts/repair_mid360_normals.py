"""Repair consistently inverted connected shells without moving or filling geometry.

Run in a separate Blender process; input and output must be different paths.
Registration is retained because orientation repair changes reference-face normals.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import bmesh
import bpy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--registration', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if args.source.resolve() == args.output.resolve():
        raise ValueError('Input must not be overwritten')
    source_sha = hashlib.sha256(args.source.read_bytes()).hexdigest()
    registration = json.loads(args.registration.read_text())['source_to_mount']
    bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()))
    obj = bpy.data.objects['MID360_colored']
    mesh = obj.data
    positions_before = [tuple(vertex.co) for vertex in mesh.vertices]
    bm = bmesh.new()
    bm.from_mesh(mesh)
    boundary_before = sum(edge.is_boundary for edge in bm.edges)
    unseen = set(bm.faces)
    components = []
    while unseen:
        face = unseen.pop()
        faces, todo = {face}, [face]
        while todo:
            for edge in todo.pop().edges:
                for neighbour in edge.link_faces:
                    if neighbour in unseen:
                        unseen.remove(neighbour)
                        faces.add(neighbour)
                        todo.append(neighbour)
        edges = {edge for face in faces for edge in face.edges}
        volume = sum(face.calc_area() * face.calc_center_median().dot(face.normal) / 3 for face in faces)
        # The supplied part has consistently oriented components (no winding seams).
        # Only invert a significant negative-volume shell, retaining all boundaries.
        if any(edge.is_manifold and not edge.is_contiguous for edge in edges):
            raise ValueError('Inconsistent winding needs manual review')
        flipped = volume < -1e-10
        if flipped:
            bmesh.ops.reverse_faces(bm, faces=list(faces))
        components.append(dict(faces=len(faces), boundary_edges=sum(e.is_boundary for e in edges),
                               signed_volume_before=volume, flipped=flipped))
    bm.normal_update()
    boundary_after = sum(edge.is_boundary for edge in bm.edges)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    assert positions_before == [tuple(vertex.co) for vertex in mesh.vertices]
    assert boundary_before == boundary_after
    obj['mid360_source_to_mount'] = json.dumps(registration)
    obj['normal_repair'] = '2026-10-09: reversed negative-volume shells; no vertex movement or hole filling'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    report = dict(source_sha256=source_sha, repaired_source_sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),
                  vertices_unchanged=True, boundary_edges_before=boundary_before,
                  boundary_edges_after=boundary_after, faces=len(mesh.polygons),
                  components=sorted(components, key=lambda item: -item['faces']),
                  flipped_faces=sum(item['faces'] for item in components if item['flipped']))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
