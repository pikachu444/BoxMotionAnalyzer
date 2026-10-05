"""Bounded interactive marker display. Canonical profiles never move with the view."""
from __future__ import annotations

from collections import OrderedDict, deque
import copy
import hashlib
from itertools import product
import json
from time import perf_counter_ns

import numpy as np
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import proj3d
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QApplication, QWidget

from src.utils.marker_profile_identity import PLAN_SPEC
from src.config.marker_semantics import FACE_NORMALS as NORMALS
from src.simulation.marker_fixtures import validate_profile

FACES = ('FRONT', 'BACK', 'RIGHT', 'LEFT', 'TOP', 'BOTTOM')
COLORS = dict(zip(FACES, ('#0072B2', '#D55E00', '#009E73', '#CC79A7', '#6C51A3', '#8C564B')))
PLANE_AXES = {'FRONT': (0, 1), 'BACK': (0, 1), 'RIGHT': (2, 1),
              'LEFT': (2, 1), 'TOP': (0, 2), 'BOTTOM': (0, 2)}


# This binds saved *display state* only; it does not certify legacy result semantics.
DISPLAY_RULE = dict(schema_version=1, plan_spec=PLAN_SPEC, rule_version=1,
                    origin='box-geometric-center', source_units='mm',
                    axes={'X': 'Right', 'Y': 'Top', 'Z': 'Front'}, normals=NORMALS,
                    projection='orthographic-y-up', offset_operation='declared-normal-times-view-ratio-times-largest-box-dimension')
DISPLAY_RULE_HASH = hashlib.sha256(json.dumps(DISPLAY_RULE, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def box_at(center, size):
    return np.asarray([center[0]-size[0]/2, center[1]-size[1]/2,
                       center[0]+size[0]/2, center[1]+size[1]/2])


def intersects(box, others):
    return (box[0] < others[:, 2]) & (box[2] > others[:, 0]) & (box[1] < others[:, 3]) & (box[3] > others[:, 1])


def segment_boxes(a, b, boxes):
    if len(boxes) == 0:
        return False
    lo = np.zeros(len(boxes)); hi = np.ones(len(boxes)); delta = b-a
    for axis in range(2):
        if abs(delta[axis]) < 1e-9:
            outside = (a[axis] < boxes[:, axis]) | (a[axis] > boxes[:, axis+2])
            lo[outside] = 2
        else:
            t = (boxes[:, [axis, axis+2]]-a[axis])/delta[axis]
            lo = np.maximum(lo, np.min(t, axis=1)); hi = np.minimum(hi, np.max(t, axis=1))
    return bool(np.any(lo <= hi))


def crossing(a, b, c, d):
    def cross(u, v):
        return u[0]*v[1]-u[1]*v[0]
    return cross(b-a, c-a)*cross(b-a, d-a) < -1e-9 and cross(d-c, a-c)*cross(d-c, b-c) < -1e-9


def leader(anchor, center, size):
    delta = anchor-center
    t = min([1]+[half/abs(value) for half, value in zip(size/2, delta) if abs(value) > 1e-9])
    return anchor, center+t*delta


def segment_matrix(a, b, boxes):
    """Bounded candidate batch versus rectangles; no Artist creation per trial."""
    a = np.atleast_2d(a); b = np.atleast_2d(b)
    if len(boxes) == 0:
        return np.zeros((len(a), 0), dtype=bool)
    lo = np.zeros((len(a), len(boxes))); hi = np.ones_like(lo)
    delta = b-a
    for axis in range(2):
        parallel = np.abs(delta[:, axis]) < 1e-9
        denominator = np.where(parallel, 1., delta[:, axis])
        p = (boxes[None, :, axis]-a[:, None, axis])/denominator[:, None]
        q = (boxes[None, :, axis+2]-a[:, None, axis])/denominator[:, None]
        lo = np.maximum(lo, np.where(parallel[:, None], 0, np.minimum(p, q)))
        hi = np.minimum(hi, np.where(parallel[:, None], 1, np.maximum(p, q)))
        outside = (a[:, None, axis] < boxes[None, :, axis]) | (a[:, None, axis] > boxes[None, :, axis+2])
        lo[parallel[:, None] & outside] = 2
    return lo <= hi


class ProfilePreviewNavigation(QWidget):
    """One gesture owner; Qt paints the existing orthographic box-local projection."""
    markerSelected = Signal(int)
    layoutFinished = Signal()
    MAX_CACHE = 8
    SLICE_NS = 8_000_000
    TOTAL_NS = 100_000_000

    def __init__(self, profile, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True); self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(200, 180)
        self.font_ids = QFont('DejaVu Sans', 10)
        self.font_titles = QFont('DejaVu Sans', 9); self.font_titles.setBold(True)
        angles = np.arange(0, 2*np.pi, np.pi/8)
        self.candidate_offsets = np.vstack([r*np.column_stack((np.cos(angles), np.sin(angles)))
                                           for r in (16, 24, 32, 44, 60, 80, 110, 140)])
        self.figure = Figure(figsize=(6.8, 3.55), dpi=100)
        self.axes = self.figure.add_axes((.01, .01, .98, .98), projection='3d')
        self.axes.disable_mouse_rotation(); self.axes.set_proj_type('ortho')
        self.mode = 'Exploded faces'; self.names = 'All'; self.current_face = 'BACK'
        self.selected = 0; self.profile_revision = 0; self.view_revision = 0
        self.gesture = None; self.layout = {}; self.title_boxes = {}; self.limited = False
        self.pick_menu = None
        self.cache = OrderedDict(); self.solver = None; self.solve_token = 0
        self.layout_timer = QTimer(self); self.layout_timer.setSingleShot(True)
        self.layout_timer.timeout.connect(self._solve_slice)
        self.idle_timer = QTimer(self); self.idle_timer.setSingleShot(True)
        self.idle_timer.timeout.connect(self._settle)
        self.stats = dict(paints=0, solve_starts=0, cancelled_solves=0, stale_results=0,
                          max_slice_ms=0., max_cache_entries=0, pending_jobs_max=1)
        self.paint_ms = deque(maxlen=256); self.input_to_paint_ms = deque(maxlen=256); self.input_time = None
        self._projection_key = None; self._matrix = None
        self.view = {}; self.saved_views = {}; self.point_pixels = np.empty((0, 2))
        self.set_profile(profile)

    def _default_view(self, mode=None):
        mode = mode or self.mode
        return dict(schema_version=1, plan_spec=PLAN_SPEC, object_type='ProfilePreviewViewState',
                    source_profile_hash=self.profile_hash, display_only=True,
                    display_rule_version=1, display_rule_hash=DISPLAY_RULE_HASH,
                    offset_units='ratio-of-largest-box-dimension', projection='orthographic-y-up',
                    time_semantics='view-state-no-recorded-time',
                    camera=[25., 50., 30.] if mode == 'Exploded faces' else [20., 30., 0.],
                    zoom=1., pan=[0., 0.], extent=float(max(self.dims)*2.12),
                    offsets={f:float(1-self.dims[np.flatnonzero(NORMALS[f])[0]]/(2*max(self.dims))) for f in FACES})

    def set_profile(self, profile):
        profile_hash = validate_profile(profile)
        if getattr(self, 'profile_hash', None) == profile_hash:
            return
        self.cancel_gesture(); previous_view = self.snapshot_view() if self.view else None
        previous_dims = getattr(self, 'dims', None)
        self._cancel_solver(); self.cache.clear()
        if self.pick_menu is not None:
            self.pick_menu.close(); self.pick_menu = None
        self.profile = copy.deepcopy(profile); self.profile_hash = profile_hash
        self.dims = np.asarray(profile['box_dims_mm'], dtype=float)
        self.source_xyz = np.asarray([m['xyz_mm'] for m in profile['markers']], dtype=float)
        self.source_xyz.setflags(write=False)
        self.ids = tuple(m['id'] for m in profile['markers'])
        self.faces = tuple(m['face'] for m in profile['markers'])
        metric = QFontMetricsF(self.font_ids)
        self.id_sizes = np.array([[metric.horizontalAdvance(name)+4, metric.height()+2] for name in self.ids])
        self._normal_rows = np.asarray([NORMALS[f] for f in self.faces], dtype=float)
        self._face_indices = np.asarray([FACES.index(f) for f in self.faces])
        self._display_points = np.empty_like(self.source_xyz); self._display_frames = {}
        self._geometry_key = None; self._scene_projection_key = None
        self.box = np.asarray(list(product((-1, 1), repeat=3)))*self.dims/2
        self.edges = [(i, j) for i in range(8) for j in range(i+1, 8) if np.count_nonzero(self.box[i] != self.box[j]) == 1]
        self.face_source = {}
        for face in FACES:
            normal = np.asarray(NORMALS[face], dtype=float); axis = int(np.flatnonzero(normal)[0])
            free = [i for i in range(3) if i != axis]; vertices = []
            for a, b in ((-1, -1), (-1, 1), (1, 1), (1, -1)):
                p = normal*self.dims[axis]/2
                p[free[0]] = a*self.dims[free[0]]/2; p[free[1]] = b*self.dims[free[1]]/2
                vertices.append(p)
            self.face_source[face] = np.asarray(vertices)
            self._display_frames[face] = np.empty((4, 3))
        n = len(self.ids)
        self._world_scene = np.empty((n+8+24+12+4, 3))
        self._world_scene[n:n+8] = self.box
        triad = np.vstack([np.zeros(3), np.eye(3)*max(self.dims)*.12])
        self._world_scene[-4:] = triad
        self.profile_revision += 1; self.selected = min(self.selected, len(self.ids)-1)
        self.view = previous_view if previous_dims is not None and np.array_equal(previous_dims, self.dims) else self._default_view()
        self.view['source_profile_hash'] = profile_hash; self.saved_views = {}
        self._changed(settle=True)

    def _cancel_solver(self):
        if self.solver is not None:
            self.stats['cancelled_solves'] += 1
        self.solve_token += 1; self.solver = None; self.layout_timer.stop(); self.idle_timer.stop()

    def _changed(self, settle=False):
        self._cancel_solver(); self.view_revision += 1; self.layout = {}
        self.input_time = perf_counter_ns(); self.update()
        if settle and self.gesture is None:
            self.idle_timer.start(0)

    def snapshot_view(self):
        return copy.deepcopy(self.view)

    def load_view_state(self, state):
        if type(state.get('schema_version')) is not int or state['schema_version'] != 1 or state.get('plan_spec') != PLAN_SPEC or state.get('object_type') != 'ProfilePreviewViewState':
            raise ValueError('Unsupported preview view contract')
        if state.get('source_profile_hash') != self.profile_hash:
            raise ValueError('Stale preview source identity')
        if type(state.get('display_rule_version')) is not int or state['display_rule_version'] != 1 or state.get('display_rule_hash') != DISPLAY_RULE_HASH:
            raise ValueError('Unsupported or stale display interpretation')
        if state.get('display_only') is not True or state.get('offset_units') != 'ratio-of-largest-box-dimension' or state.get('projection') != 'orthographic-y-up' or state.get('time_semantics') != 'view-state-no-recorded-time':
            raise ValueError('Unsupported preview coordinates or units')
        def finite_number(value):
            return isinstance(value, (int, float)) and not isinstance(value, bool) and np.isfinite(value)
        offsets = state.get('offsets', {})
        if not isinstance(offsets, dict) or set(offsets) != set(FACES) or any(not finite_number(v) or v < 0 or v > 3 for v in offsets.values()):
            raise ValueError('Invalid display spacing')
        for field, length in (('camera', 3), ('pan', 2)):
            values = state.get(field, [])
            if not isinstance(values, (list, tuple)) or len(values) != length or not all(finite_number(v) for v in values):
                raise ValueError('Invalid preview view')
        if not finite_number(state.get('zoom')) or not .15 <= state['zoom'] <= 8 or not finite_number(state.get('extent')) or state['extent'] <= 0:
            raise ValueError('Invalid preview scale')
        self.cancel_gesture(); self.view = copy.deepcopy(state); self._changed(settle=True)

    def set_selected(self, row, face=None):
        if isinstance(row, bool) or not isinstance(row, (int, np.integer)) or not 0 <= row < len(self.ids) or (face is not None and face not in FACES):
            raise ValueError('Unsupported marker selection')
        self.selected = int(row)
        if face is not None:
            self.current_face = face
        if self.names != 'All':
            self._changed(settle=True)
        else:
            self.update()

    def set_names(self, names):
        if names not in ('All', 'View face', 'Selected'):
            raise ValueError('Unsupported name display')
        self.cancel_gesture(); self.names = names; self._changed(settle=True)

    def set_mode(self, mode):
        if mode not in ('Box', 'Exploded faces'):
            raise ValueError('Unsupported preview mode')
        self.cancel_gesture(); self.saved_views[self.mode] = self.snapshot_view()
        self.mode = mode; self.view = copy.deepcopy(self.saved_views.get(mode, self._default_view(mode)))
        self._changed(settle=True)

    def reset_view(self):
        self.cancel_gesture(); self.cache.clear(); self.view = self._default_view(); self.fit()

    def display_geometry(self):
        ratios = tuple(self.view['offsets'][f] if self.mode == 'Exploded faces' else 0. for f in FACES)
        key = (self.profile_revision, ratios)
        if key != self._geometry_key:
            distances = np.asarray(ratios)*max(self.dims)
            np.multiply(self._normal_rows, distances[self._face_indices, None], out=self._display_points)
            self._display_points += self.source_xyz
            n = len(self.ids); self._world_scene[:n] = self._display_points
            for i, face in enumerate(FACES):
                offset = np.asarray(NORMALS[face])*distances[i]
                np.add(self.face_source[face], offset, out=self._display_frames[face])
                self._world_scene[n+8+i*4:n+8+(i+1)*4] = self._display_frames[face]
                center = np.mean(self.face_source[face], axis=0)
                self._world_scene[n+32+i*2:n+34+i*2] = [center, center+offset]
            self._geometry_key = key
        return self._display_points, self._display_frames

    def _project_scene(self):
        self.display_geometry()
        key = (self._geometry_key, self.width(), self.height(), tuple(self.view['camera']),
               self.view['extent'], self.view['zoom'], tuple(self.view['pan']))
        if key != self._scene_projection_key:
            self._scene_pixels, self._scene_depth = self.project(self._world_scene)
            self._scene_projection_key = key
        n = len(self.ids)
        self.point_pixels = self._scene_pixels[:n]
        self.projected_frames = {f:self._scene_pixels[n+8+i*4:n+8+(i+1)*4] for i, f in enumerate(FACES)}
        return self._scene_pixels[n:n+8], self._scene_pixels[n+32:n+44].reshape(6, 2, 2), self._scene_pixels[-4:]

    def project(self, points):
        key = (self.width(), self.height(), tuple(self.view['camera']), self.view['extent'], self.view['zoom'])
        if key != self._projection_key:
            self.figure.set_size_inches(max(1, self.width())/100, max(1, self.height())/100, forward=False)
            self.axes.view_init(*self.view['camera'], vertical_axis='y')
            extent = self.view['extent']
            for setter in (self.axes.set_xlim, self.axes.set_ylim, self.axes.set_zlim):
                setter(-extent/2, extent/2)
            self.axes.set_box_aspect((1, 1, 1), zoom=self.view['zoom'])
            self.axes.apply_aspect()  # Same square 3D projection viewport as Matplotlib.draw.
            self._matrix = self.axes.get_proj(); self._projection_key = key
        x, y, z = proj3d.proj_transform(*np.asarray(points).T, self._matrix)
        screen = self.axes.transData.transform(np.column_stack((x, y)))
        screen[:, 1] = self.height()-screen[:, 1]
        return screen+np.asarray(self.view['pan']), np.asarray(z)

    def fit(self):
        self.cancel_gesture(); points, frames = self.display_geometry()
        geometry = np.vstack([self.box, points, *frames.values()])
        self.view['extent'] = float(max(np.max(np.abs(geometry), axis=0))*2.12)
        self.view['zoom'] = 1.; self.view['pan'] = [0., 0.]
        pixels, _ = self.project(geometry); span = np.ptp(pixels, axis=0)
        self.view['zoom'] = float(np.clip(.94*min(max(1, self.width()-32)/max(1, span[0]),
                                                max(1, self.height()-32)/max(1, span[1])), .15, 8))
        pixels, _ = self.project(geometry)
        self.view['pan'] = (np.asarray([self.width()/2, self.height()/2])-np.mean([pixels.min(axis=0), pixels.max(axis=0)], axis=0)).tolist()
        self._changed(settle=True)

    def _key(self):
        return (self.profile_revision, self.width(), self.height(), self.devicePixelRatioF(), self.mode,
                self.names, self.current_face if self.names == 'View face' else None,
                self.selected if self.names != 'All' else None,
                tuple(self.view['camera']), self.view['zoom'], tuple(self.view['pan']),
                self.view['extent'], tuple(self.view['offsets'][f] for f in FACES))

    def _titles(self, point_pixels, frames):
        metric = QFontMetricsF(self.font_titles); obstacles = np.array([box_at(p, np.array([14., 14.])) for p in point_pixels])
        result = {}; occupied = []
        for face, frame in frames.items():
            title = f'{face.title()} ({self.faces.count(face)})'
            size = np.array([metric.horizontalAdvance(title)+6, metric.height()+4])
            center = frame.mean(axis=0); proposals = []
            for gap in (16, 28, 42, 60):
                proposals.extend([(center[0], frame[:, 1].min()-gap), (center[0], frame[:, 1].max()+gap),
                                  (frame[:, 0].min()-size[0]/2-gap, center[1]),
                                  (frame[:, 0].max()+size[0]/2+gap, center[1])])
            for p in proposals:
                box = box_at(p, size)
                if box[0] < 4 or box[1] < 4 or box[2] > self.width()-4 or box[3] > self.height()-4:
                    continue
                if np.any(intersects(box, obstacles)) or (occupied and np.any(intersects(box, np.array(occupied)))):
                    continue
                result[face] = (np.asarray(p), size, title); occupied.append(box); break
        return result

    def _settle(self):
        if self.gesture is not None:
            return
        key = self._key()
        if key in self.cache:
            self.layout = self.cache.pop(key); self.cache[key] = self.layout; self.limited = False; self.update()
            self.layoutFinished.emit(); return
        self._project_scene(); pixels = self.point_pixels.copy()
        frame_pixels = self.projected_frames
        titles = self._titles(pixels, frame_pixels)
        sizes = self.id_sizes
        rows = [i for i, f in enumerate(self.faces) if self.names == 'All' or
                (self.names == 'View face' and f == self.current_face) or i == self.selected]
        # Constrained dense points first. Cache is selection-independent for All.
        obstacles = np.vstack([np.column_stack((pixels-7, pixels+7)),
                               np.asarray([box_at(p, s) for p, s, _ in titles.values()]).reshape(-1, 4)])
        scarcity = {}
        for row in rows:
            centers = pixels[row]+self.candidate_offsets[:48]
            boxes = np.column_stack((centers-sizes[row]/2, centers+sizes[row]/2))
            legal = (boxes[:, 0] >= 6) & (boxes[:, 1] >= 6) & (boxes[:, 2] <= self.width()-6) & (boxes[:, 3] <= self.height()-6)
            hit = (boxes[:, None, 0] < obstacles[None, :, 2]) & (boxes[:, None, 2] > obstacles[None, :, 0]) & (boxes[:, None, 1] < obstacles[None, :, 3]) & (boxes[:, None, 3] > obstacles[None, :, 1])
            scarcity[row] = int(np.count_nonzero(legal & ~hit.any(axis=1)))
        rows.sort(key=lambda i: (scarcity[i], -np.count_nonzero(np.linalg.norm(pixels-pixels[i], axis=1) < 42), i))
        self.stats['solve_starts'] += 1
        self.solver = dict(token=self.solve_token, key=key, rows=rows, pixels=pixels,
                           sizes=sizes, titles=titles, placed={}, leaders=[], elapsed_ns=0, steps=0, current=None,
                           failed=[], repairs=[], repair_index=0)
        self.layout_timer.start(0)

    def _candidates(self, row, job, placed):
        pixels = job['pixels']; size = job['sizes'][row]; anchor = pixels[row]
        centers = anchor+self.candidate_offsets
        boxes = np.column_stack((centers-size/2, centers+size/2))
        legal = (boxes[:, 0] >= 6) & (boxes[:, 1] >= 6) & (boxes[:, 2] <= self.width()-6) & (boxes[:, 3] <= self.height()-6)
        marker_boxes = np.column_stack((pixels-7, pixels+7))
        title_boxes = [box_at(p, s) for p, s, _ in job['titles'].values()]
        occupied = title_boxes+[box_at(p, job['sizes'][r]) for r, p in placed.items()]
        obstacles = np.vstack([marker_boxes, np.asarray(occupied).reshape(-1, 4)])
        hit = (boxes[:, None, 0] < obstacles[None, :, 2]) & (boxes[:, None, 2] > obstacles[None, :, 0]) & (boxes[:, None, 1] < obstacles[None, :, 3]) & (boxes[:, None, 3] > obstacles[None, :, 1])
        legal &= ~hit.any(axis=1)
        delta = anchor-centers
        with np.errstate(divide='ignore'):
            t = np.minimum(1., np.min(np.where(np.abs(delta) > 1e-9, size/2/np.abs(delta), np.inf), axis=1))
        endpoints = centers+delta*t[:, None]; starts = np.broadcast_to(anchor, endpoints.shape)
        other_markers = marker_boxes[np.arange(len(pixels)) != row]
        arrow_obstacles = np.vstack([other_markers, np.asarray(occupied).reshape(-1, 4)])
        legal &= ~segment_matrix(starts, endpoints, arrow_obstacles).any(axis=1)
        old = [leader(pixels[r], p, job['sizes'][r]) for r, p in placed.items()]
        if old:
            c = np.array([a for a, b in old]); d = np.array([b for a, b in old])
            def cross(u, v):
                return u[..., 0]*v[..., 1]-u[..., 1]*v[..., 0]
            ab = (endpoints-starts)[:, None]; cd = (d-c)[None]
            intersects_leader = (cross(ab, c[None]-starts[:, None])*cross(ab, d[None]-starts[:, None]) < -1e-9) & (cross(cd, starts[:, None]-c[None])*cross(cd, endpoints[:, None]-c[None]) < -1e-9)
            legal &= ~intersects_leader.any(axis=1)
            legal &= ~segment_matrix(c, d, boxes).any(axis=0)
        job['steps'] += len(centers)
        return centers[legal]

    def _solve_slice(self):
        job = self.solver
        if job is None or self.gesture is not None or job['token'] != self.solve_token:
            return
        start = perf_counter_ns(); pixels = job['pixels']
        while job['rows'] and perf_counter_ns()-start < self.SLICE_NS and job['elapsed_ns']+perf_counter_ns()-start < self.TOTAL_NS:
            row = job['rows'].pop(0); candidates = self._candidates(row, job, job['placed'])
            if len(candidates):
                job['placed'][row] = candidates[0]
            else:
                job['failed'].append(row)
        # Bounded local repair moves one blocking name, using the same generic candidates.
        if not job['rows'] and not job['repairs']:
            job['repairs'] = [(row, victim) for row in job['failed'] for victim in
                              sorted(job['placed'], key=lambda r:np.linalg.norm(pixels[r]-pixels[row]))[:4]]
        while job['repair_index'] < len(job['repairs']) and perf_counter_ns()-start < self.SLICE_NS and job['elapsed_ns']+perf_counter_ns()-start < self.TOTAL_NS:
            row, victim = job['repairs'][job['repair_index']]; job['repair_index'] += 1
            if row in job['placed']:
                continue
            others = {r:p for r, p in job['placed'].items() if r != victim}
            for candidate in self._candidates(row, job, others)[:4]:
                proposed = dict(others); proposed[row] = candidate
                replacement = self._candidates(victim, job, proposed)
                if len(replacement):
                    proposed[victim] = replacement[0]; job['placed'] = proposed; break
        elapsed = perf_counter_ns()-start; job['elapsed_ns'] += elapsed
        self.stats['max_slice_ms'] = max(self.stats['max_slice_ms'], elapsed/1e6)
        if (job['rows'] or job['repair_index'] < len(job['repairs'])) and job['elapsed_ns'] < self.TOTAL_NS:
            self.layout_timer.start(0); return
        if job['token'] != self.solve_token or job['key'] != self._key() or self.gesture is not None:
            self.stats['stale_results'] += 1; self.solver = None; return
        requested = len(self.ids) if self.names == 'All' else sum(f == self.current_face for f in self.faces)
        self.layout = job['placed']; self.limited = len(self.layout) < (requested if self.names != 'Selected' else 1)
        self.stats['last_solve_ms'] = job['elapsed_ns']/1e6
        self.stats['last_missing_ids'] = [self.ids[r] for r in range(len(self.ids)) if r not in self.layout] if self.names == 'All' else []
        self.title_boxes = job['titles']; self.solver = None
        if not self.limited:
            self.cache[job['key']] = copy.deepcopy(self.layout)
            while len(self.cache) > self.MAX_CACHE:
                self.cache.popitem(last=False)
        self.stats['max_cache_entries'] = max(self.stats['max_cache_entries'], len(self.cache))
        self.update(); self.layoutFinished.emit()

    def paintEvent(self, event):
        start = perf_counter_ns(); painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing); painter.fillRect(self.rect(), Qt.white)
        boxes, links, triad = self._project_scene(); depth = self._scene_depth[:len(self.ids)]
        painter.setPen(QPen(QColor('#999999'), .8))
        for i, j in self.edges:
            painter.drawLine(QPointF(*boxes[i]), QPointF(*boxes[j]))
        for i, (face, frame) in enumerate(self.projected_frames.items()):
            color = QColor(COLORS[face]); fill = QColor(color); fill.setAlpha(12)
            painter.setPen(QPen(color, .9)); painter.setBrush(fill)
            painter.drawPolygon(QPolygonF([QPointF(*p) for p in frame]))
            color.setAlpha(100)
            painter.setPen(QPen(color, .6, Qt.DashLine)); painter.drawLine(QPointF(*links[i, 0]), QPointF(*links[i, 1]))
        for row in np.argsort(depth)[::-1]:
            color = QColor(COLORS[self.faces[row]])
            color.setAlpha(240 if self.faces[row] == self.current_face else 180)
            painter.setPen(QPen(QColor('#333333'), .75)); painter.setBrush(color)
            painter.drawEllipse(QPointF(*self.point_pixels[row]), 6.3, 6.3)
        painter.setPen(QPen(QColor('#111111'), 1.3)); painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(*self.point_pixels[self.selected]), 6.3, 6.3)
        self.title_boxes = self._titles(self.point_pixels, self.projected_frames)
        painter.setFont(self.font_titles)
        for face, (center, size, title) in self.title_boxes.items():
            self._badge(painter, center, size, title, COLORS[face], False)
        self.badge_boxes = {}
        if self.gesture is None:
            painter.setFont(self.font_ids)
            for row, center in self.layout.items():
                size = self.id_sizes[row]
                a, b = leader(self.point_pixels[row], center, size)
                painter.setPen(QPen(QColor('#777777'), .6)); painter.drawLine(QPointF(*a), QPointF(*b))
                self._badge(painter, center, size, self.ids[row], '#222222', row == self.selected)
                self.badge_boxes[row] = box_at(center, size)
        # Moving overlays follow the projected selected point; no stale screen anchor.
        if self.selected not in self.badge_boxes:
            painter.setFont(self.font_ids); size = self.id_sizes[self.selected]
            anchor = self.point_pixels[self.selected]; centers = anchor+self.candidate_offsets
            boxes = np.column_stack((centers-size/2, centers+size/2))
            obstacles = np.vstack([np.column_stack((self.point_pixels-7, self.point_pixels+7)),
                                   np.asarray([box_at(p, s) for p, s, _ in self.title_boxes.values()]).reshape(-1, 4),
                                   np.asarray(list(self.badge_boxes.values())).reshape(-1, 4)])
            hit = (boxes[:, None, 0] < obstacles[None, :, 2]) & (boxes[:, None, 2] > obstacles[None, :, 0]) & (boxes[:, None, 1] < obstacles[None, :, 3]) & (boxes[:, None, 3] > obstacles[None, :, 1])
            legal = (boxes[:, 0] >= 6) & (boxes[:, 1] >= 6) & (boxes[:, 2] <= self.width()-6) & (boxes[:, 3] <= self.height()-6) & ~hit.any(axis=1)
            if self.badge_boxes:
                old = [leader(self.point_pixels[r], self.layout[r], self.id_sizes[r]) for r in self.badge_boxes]
                legal &= ~segment_matrix(np.array([a for a, b in old]), np.array([b for a, b in old]), boxes).any(axis=0)
            if np.any(legal):
                center = centers[np.flatnonzero(legal)[0]]
                self._badge(painter, center, size, self.ids[self.selected], '#222222', True)
                self.badge_boxes[self.selected] = box_at(center, size)
        origin = triad[0]
        painter.setFont(QFont('DejaVu Sans', 9))
        for axis, color in enumerate(('#b33', '#386b36', '#376fa8')):
            end = triad[axis+1]; painter.setPen(QPen(QColor(color), 1))
            painter.drawLine(QPointF(*origin), QPointF(*end)); painter.drawText(QPointF(*(end+[4, -4])), 'XYZ'[axis])
        if self.limited and self.gesture is None:
            painter.setPen(QColor('#666666')); painter.drawText(QPointF(6, self.height()-6), 'Names limited — use face view')
        painter.end(); self.stats['paints'] += 1
        self.paint_ms.append((perf_counter_ns()-start)/1e6)
        if self.input_time is not None:
            self.input_to_paint_ms.append((perf_counter_ns()-self.input_time)/1e6); self.input_time = None

    @staticmethod
    def _badge(painter, center, size, text, color, selected):
        rect = QRectF(center[0]-size[0]/2, center[1]-size[1]/2, *size)
        painter.setPen(QPen(QColor('#111111') if selected else QColor('white'), .8))
        painter.setBrush(QColor('white')); painter.drawRoundedRect(rect, 2, 2)
        painter.setPen(QColor(color)); painter.drawText(rect, Qt.AlignCenter, text)

    def _hit(self, position):
        p = np.array([position.x(), position.y()])
        if self.mode == 'Exploded faces':
            for face, (center, size, _) in self.title_boxes.items():
                box = box_at(center, size)
                if box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]:
                    normal = np.asarray(NORMALS[face])*max(self.dims)
                    direction = self.project([np.zeros(3), normal])[0]
                    axis = direction[1]-direction[0]
                    if np.linalg.norm(axis) < QApplication.styleHints().startDragDistance():
                        return 'disabled-face', face
                    return 'face', (face, axis)
        hits = [i for i, pixel in enumerate(self.point_pixels) if np.linalg.norm(pixel-p) <= 9]
        for row, box in self.badge_boxes.items():
            if box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3] and row not in hits:
                hits.append(row)
        return 'marker' if hits else 'background', hits

    def mousePressEvent(self, event):
        if self.gesture is not None or event.button() not in (Qt.LeftButton, Qt.MiddleButton):
            return
        self.setFocus(); self._cancel_solver()
        kind, target = self._hit(event.position())
        self.gesture = dict(kind=kind, target=target, button=event.button(), start=event.position(),
                            view=self.snapshot_view(), dragging=False)
        self.grabMouse(); event.accept()

    def mouseMoveEvent(self, event):
        if self.gesture is None:
            kind, _ = self._hit(event.position())
            self.setCursor(Qt.SizeAllCursor if kind == 'face' else Qt.ForbiddenCursor if kind == 'disabled-face' else Qt.ArrowCursor)
            self.setToolTip('Drag face name to adjust display spacing' if kind == 'face' else
                            'Rotate view to adjust spacing' if kind == 'disabled-face' else
                            'Drag background to rotate; middle-drag to pan; wheel to zoom')
            return
        drag = self.gesture; delta = event.position()-drag['start']
        movement = np.array([delta.x(), delta.y()])
        if not drag['dragging'] and np.linalg.norm(movement) < QApplication.styleHints().startDragDistance():
            return
        drag['dragging'] = True; initial = drag['view']
        if drag['button'] == Qt.MiddleButton:
            self.view['pan'] = (np.asarray(initial['pan'])+movement).tolist()
        elif drag['kind'] == 'face':
            face, axis = drag['target']
            self.view['offsets'][face] = float(np.clip(initial['offsets'][face]+movement@axis/(axis@axis), 0, 3))
        elif drag['kind'] in ('background', 'marker'):
            self.view['camera'] = [float(np.clip(initial['camera'][0]+movement[1]*.35, -89, 89)),
                                   float((initial['camera'][1]-movement[0]*.35)%360), initial['camera'][2]]
        self._changed(); event.accept()

    def mouseReleaseEvent(self, event):
        drag = self.gesture
        if drag is None or event.button() != drag['button']:
            return
        self.gesture = None; self.releaseMouse()
        if drag['button'] == Qt.LeftButton and not drag['dragging'] and drag['kind'] == 'marker':
            rows = drag['target']
            if len(rows) == 1:
                self.markerSelected.emit(rows[0])
            elif rows:
                from PySide6.QtWidgets import QMenu
                menu = QMenu(self)
                self.pick_menu = menu; revision = self.profile_revision
                def clear_menu():
                    if self.pick_menu is menu:
                        self.pick_menu = None
                    menu.deleteLater()
                menu.aboutToHide.connect(clear_menu)
                for row in rows:
                    action = menu.addAction(f'{self.ids[row]}  {self.faces[row].title()}')
                    action.triggered.connect(lambda checked=False, r=row, rev=revision:
                                             self.markerSelected.emit(r) if self.profile_revision == rev else None)
                menu.popup(event.globalPosition().toPoint())
        self._changed(settle=True); event.accept()

    def wheelEvent(self, event):
        self.cancel_gesture(); self.view['zoom'] = float(np.clip(self.view['zoom']*1.12**(event.angleDelta().y()/120), .15, 8))
        self._changed(); self.idle_timer.start(80); event.accept()

    def cancel_gesture(self):
        if self.gesture is not None:
            self.view = self.gesture['view']; self.gesture = None; self.releaseMouse()
            self._changed(settle=True)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.gesture is not None:
            self.cancel_gesture(); event.accept()
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event):
        self.cancel_gesture(); super().focusOutEvent(event)

    def resizeEvent(self, event):
        self.cancel_gesture(); self.cache.clear(); self._changed(settle=True)
        super().resizeEvent(event)

    def hideEvent(self, event):
        if self.pick_menu is not None:
            self.pick_menu.close(); self.pick_menu = None
        self.cancel_gesture(); self._cancel_solver(); super().hideEvent(event)

    def showEvent(self, event):
        self._changed(settle=True); super().showEvent(event)
