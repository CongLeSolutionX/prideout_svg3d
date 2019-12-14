#!/usr/bin/env python3

"""
TODO
- move to /extras in svg3d
- parameterize properly, create filmstrip test with various cam angles, pre-alloc all numpy arrays
"""

import numpy as np
import pyrr

from math import *

quaternion = pyrr.quaternion

def octasphere(ndivisions: int, radius: float, explosion: float):
    "Returns a vertex and index array for a subdivided octahedron."
    n = 2**ndivisions + 1
    num_verts = n * (n + 1) // 2
    verts = []
    translation = np.float32([explosion, explosion, explosion])
    for i in range(n):
        theta = pi * 0.5 * i / (n - 1)
        point_a = [0, sin(theta), cos(theta)]
        point_b = [cos(theta), sin(theta), 0]
        num_segments = n - 1 - i
        geodesic_verts = compute_geodesic(point_a, point_b, num_segments)
        geodesic_verts = geodesic_verts * radius + translation
        verts = verts + [v for v in geodesic_verts]
    assert len(verts) == num_verts

    num_faces = (n - 2) * (n - 1) + n - 1
    faces = []
    j0 = 0
    for col_index in range(n-1):
        col_height = n - 1 - col_index
        col = []
        j1 = j0 + 1
        j2 = j0 + col_height + 1
        j3 = j0 + col_height + 2
        for row in range(col_height - 1):
            col.append([j0 + row, j1 + row, j2 + row])
            col.append([j2 + row, j1 + row, j3 + row])
        row = col_height - 1
        col.append([j0 + row, j1 + row, j2 + row])
        j0 = j2
        faces = faces + col
    assert len(faces) == num_faces
    faces = np.int32(faces)

    euler_angles = np.float32([
        [0, 0, 0], [0, 1, 0], [0, 2, 0], [0, 3, 0],
        [1, 0, 0], [1, 0, 1], [1, 0, 2], [1, 0, 3],
    ]) * pi * 0.5
    quats = (quaternion.create_from_eulers(e) for e in euler_angles)

    offset, combined_verts, combined_faces = 0, [], []
    for quat in quats:
        rotated_verts = [quaternion.apply_to_vector(quat, v) for v in verts]
        rotated_faces = faces + offset
        combined_verts.append(rotated_verts)
        combined_faces.append(rotated_faces)
        offset = offset + len(verts)

    if explosion > 0.0:
        boundaries = get_boundary_indices(ndivisions)
        connectors = []

        # Top half
        for patch in range(4):
            next_patch = (patch + 1) % 4
            boundary_a = boundaries[1] + num_verts * patch
            boundary_b = boundaries[0] + num_verts * next_patch
            for i in range(n-1):
                a = boundary_a[i]
                b = boundary_b[i]
                c = boundary_a[i+1]
                d = boundary_b[i+1]
                connectors.append([a, b, d])
                connectors.append([d, c, a])

        # Top hole
        a = boundaries[0][-1]
        b = a + num_verts
        c = b + num_verts
        d = c + num_verts
        connectors.append([a, b, c])
        connectors.append([c, d, a])

        # Bottom half
        for patch in range(4,8):
            next_patch = 4 + (patch + 1) % 4
            boundary_a = boundaries[0] + num_verts * patch
            boundary_b = boundaries[2] + num_verts * next_patch
            for i in range(n-1):
                a = boundary_a[i]
                b = boundary_b[i]
                c = boundary_a[i+1]
                d = boundary_b[i+1]
                connectors.append([d, b, a])
                connectors.append([a, c, d])

        # Bottom hole
        a = boundaries[2][0] + num_verts * 4
        b = a + num_verts
        c = b + num_verts
        d = c + num_verts
        connectors.append([a, b, c])
        connectors.append([c, d, a])

        # Connect top patch to bottom patch
        squares = []
        for patch in range(4):
            next_patch = 4 + (4 - patch) % 4
            boundary_a = boundaries[2] + num_verts * patch
            boundary_b = boundaries[1] + num_verts * next_patch
            for i in range(n-1):
                a = boundary_a[i]
                b = boundary_b[n-1-i]
                c = boundary_a[i+1]
                d = boundary_b[n-1-i-1]
                connectors.append([a, b, d])
                connectors.append([d, c, a])
            a = boundary_a[0]
            b = boundary_b[n-1]
            squares.append([a, b])
            a = boundary_a[n-1]
            b = boundary_b[0]
            squares.append([a, b])

        def emit_square(i, j):
            a, b = squares[i]
            c, d = squares[j]
            connectors.append([a, b, d])
            connectors.append([d, c, a])

        emit_square(7, 0)
        emit_square(1, 2)
        emit_square(3, 4)
        emit_square(5, 6)

        combined_faces.append(connectors)

    verts, faces = np.vstack(combined_verts), np.vstack(combined_faces)
    return verts, faces


def compute_geodesic(point_a, point_b, num_segments):
    """Given two points on a unit sphere, returns a sequence of surface
    points that lie between them along a geodesic curve."""
    angle_between_endpoints = acos(np.dot(point_a, point_b))
    rotation_axis = np.cross(point_a, point_b)
    point_list = [point_a]
    if num_segments == 0:
        return np.float32(point_list)
    dtheta = angle_between_endpoints / num_segments
    for point_index in range(1, num_segments):
        theta = point_index * dtheta
        q = quaternion.create_from_axis_rotation(rotation_axis, theta)
        point_list.append(quaternion.apply_to_vector(q, point_a))
    point_list.append(point_b)
    return np.float32(point_list)


def get_boundary_indices(ndivisions):
    "Generates the list of vertex indices for all three patch edges."
    n = 2**ndivisions + 1
    boundaries = [[], [], []]
    j0 = 0
    for col_index in range(n-1):
        col_height = n - 1 - col_index
        col = []
        j1 = j0 + 1
        j2 = j0 + col_height + 1
        j3 = j0 + col_height + 2
        boundaries[0].append(j0)
        for row in range(col_height - 1):
            if col_height == n - 1:
                boundaries[2].append(j0 + row)
            col.append([j0 + row, j1 + row, j2 + row])
            col.append([j2 + row, j1 + row, j3 + row])
        row = col_height - 1
        if col_height == n - 1:
            boundaries[2].append(j0 + row)
            boundaries[2].append(j1 + row)
        boundaries[1].append(j1 + row)
        col.append([j0 + row, j1 + row, j2 + row])
        j0 = j2
    boundaries[0].append(j0 + row)
    boundaries[1].append(j0 + row)
    return np.int32(boundaries)


if __name__ == "__main__":
    from parent_folder import svg3d
    import svgwrite.utils

    create_ortho = pyrr.matrix44.create_orthogonal_projection
    create_perspective = pyrr.matrix44.create_perspective_projection
    create_lookat = pyrr.matrix44.create_look_at

    np.set_printoptions(formatter={'float': lambda x: "{0:+0.3f}".format(x)})

    SHININESS = 100
    DIFFUSE = np.float32([1.0, 0.8, 0.2])
    SPECULAR = np.float32([0.5, 0.5, 0.5])
    SIZE = (512, 256)

    def rgb(r, g, b):
        r = max(0.0, min(r, 1.0))
        g = max(0.0, min(g, 1.0))
        b = max(0.0, min(b, 1.0))
        return svgwrite.utils.rgb(r * 255, g * 255, b * 255)

    def rotate_faces(faces):
        q = quaternion.create_from_eulers([pi * -0.4, pi * 0.9, 0])
        new_faces = []
        for f in faces:
            verts = [quaternion.apply_to_vector(q, v) for v in f]
            new_faces.append(verts)
        return np.float32(new_faces)

    def translate_faces(faces, offset):
        return faces + np.float32(offset)

    def merge_faces(faces0, faces1):
        return np.vstack([faces0, faces1])

    verts, indices = octasphere(3, 7, 3.0)
    faces = verts[indices]

    left = translate_faces(faces, [ -12, 0, 0])
    right = translate_faces(rotate_faces(faces), [ 12, 0, 0])
    faces = merge_faces(left, right)

    projection = create_perspective(fovy=25, aspect=2, near=10, far=200)
    view = create_lookat(eye=[25, 20, 60], target=[0, 0, 0], up=[0, 1, 0])
    camera = svg3d.Camera(view, projection)

    ones = np.ones(faces.shape[:2] + (1,))
    eyespace_faces = np.dstack([faces, ones])
    eyespace_faces = np.dot(eyespace_faces, view)[:, :, :3]
    L = pyrr.vector.normalize(np.float32([20, 20, 50]))
    E = np.float32([0, 0, 1])
    H = pyrr.vector.normalize(L + E)

    def frontface_shader(face_index, winding):
        if winding < 0:
            return None
        face = eyespace_faces[face_index]
        p0, p1, p2 = face[0], face[1], face[2]
        N = pyrr.vector.normalize(pyrr.vector3.cross(p1 - p0, p2 - p0))
        df = max(0, np.dot(N, L))
        sf = pow(max(0, np.dot(N, H)), SHININESS)
        color = df * DIFFUSE + sf * SPECULAR
        color = np.power(color, 1.0 / 2.2)
        return dict(fill=rgb(*color), stroke="black", stroke_width="0.001")

    meshes = [svg3d.Mesh(faces, frontface_shader)]
    scene = svg3d.Scene(meshes)
    vp = svg3d.Viewport(-1, -.5, 2, 1)
    engine = svg3d.Engine([svg3d.View(camera, scene, vp)])
    engine.render("octasphere.svg", size=SIZE)