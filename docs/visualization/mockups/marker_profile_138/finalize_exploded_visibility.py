"""Final B review: avoid marker occlusion and penalize ambiguous ID leaders."""
from __future__ import annotations

import argparse
from pathlib import Path
import json

import numpy as np
from matplotlib.font_manager import FontProperties
from matplotlib.transforms import Bbox
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from compare_exploded_angles import (ConfiguredExploded, base_report, project,
    geometry, measurements, intersection_area)
from generate_reviewed_mockups import settled, capture_reviewed
from generate_preview_options import COLORS
from generate_mockups import EXPECTED_HASHES
from src.simulation.marker_fixtures import load_profile, validate_profile


def rectangle(box):
    return np.asarray([(box.x0,box.y0),(box.x1,box.y0),(box.x1,box.y1),(box.x0,box.y1)])


def leader_segment(anchor,center,box):
    anchor=np.asarray(anchor,float); center=np.asarray(center,float); v=anchor-center
    t=min([1]+[half/abs(delta) for half,delta in zip((box.width/2,box.height/2),v) if abs(delta)>1e-9])
    return anchor,center+t*v


def distance_to_segment(points,a,b):
    v=b-a; denominator=float(np.dot(v,v))
    if denominator<1e-9: return np.linalg.norm(points-a,axis=1)
    t=np.clip((points-a)@v/denominator,0,1)
    return np.linalg.norm(points-(a+t[:,None]*v),axis=1)


def segments_cross(a,b,c,d):
    def cross(v,w): return v[0]*w[1]-v[1]*w[0]
    return cross(b-a,c-a)*cross(b-a,d-a)<-1e-9 and cross(d-c,a-c)*cross(d-c,b-c)<-1e-9


def segment_box(a,b,box):
    low,high=0.,1.; v=b-a
    for start,delta,minimum,maximum in zip(a,v,(box.x0,box.y0),(box.x1,box.y1)):
        if abs(delta)<1e-9:
            if start<minimum or start>maximum: return False
        else:
            p,q=sorted(((minimum-start)/delta,(maximum-start)/delta))
            low=max(low,p); high=min(high,q)
            if low>high: return False
    return True


class FinalVisibilityPrototype(ConfiguredExploded):
    def __init__(self,example='32',size=(1280,960)):
        self.enforce_readability=False
        self.layout_cache={}; self.active_layout=None
        self.label_leaders=[]; self.title_annotations=[]; self.readability_metrics={}
        super().__init__(example,size,(25,50,30),1)
        self.enforce_readability=True
        bar=self.plot_splitter.widget(0).layout().itemAt(0).layout()
        bar.itemAt(3).widget().setToolTip('Separated faces are a display aid. Table, selected coordinates and saved profile keep original positions.')

    def record_label_position(self,row,anchor,center,box):
        self.label_leaders.append((row,*leader_segment(anchor,center,box),box))

    def fit3(self):
        if self.display_mode=='Box': return super().fit3()
        self.axes.set_box_aspect(self.ranges.copy(),zoom=1); self.canvas3.draw()
        bounds=self.bounds3(); fw,fh=self.figure3.bbox.width,self.figure3.bbox.height
        margin=16*self.canvas3.devicePixelRatioF()
        self.zoom_3d=.94*min((fw-2*margin)/bounds.width,(fh-2*margin)/bounds.height)
        self.axes.set_box_aspect(self.ranges.copy(),zoom=self.zoom_3d); self.selection_overlay()
        assert self.fit_content_inside()

    def label_rows(self,pixels):
        if self.display_mode=='Box' or not self.enforce_readability: return super().label_rows(pixels)
        distances=np.linalg.norm(pixels[:,None]-pixels[None,:],axis=2)
        dpr=self.canvas3.devicePixelRatioF(); renderer=self.canvas3.get_renderer()
        fw,fh=self.figure3.bbox.width,self.figure3.bbox.height
        point_boxes=[Bbox.from_bounds(x-7*dpr,y-7*dpr,14*dpr,14*dpr) for x,y in pixels]
        obstacles=point_boxes+self.extra_label_obstacles()
        scarcity={}
        for row,marker in enumerate(self.valid_preview['markers']):
            width,height,_=renderer.get_text_width_height_descent(marker['id'],FontProperties(size=10),False)
            width+=8*dpr; height+=8*dpr; legal=0
            for radius in (16,24,32):
                for angle in np.arange(0,2*np.pi,np.pi/8):
                    x,y=pixels[row]+radius*dpr*np.asarray([np.cos(angle),np.sin(angle)])
                    box=Bbox.from_bounds(x-width/2,y-height/2,width,height)
                    if box.x0<6*dpr or box.y0<6*dpr or box.x1>fw-6*dpr or box.y1>fh-6*dpr: continue
                    if any(box.overlaps(p) for p in obstacles): continue
                    legal+=1
            scarcity[row]=legal
        # Boundary/crowding constraints first; no ID-specific priority.
        return sorted(range(len(pixels)),key=lambda r:(scarcity[r],-int(np.count_nonzero(distances[r]<42*dpr)),r))

    def label_candidate_score(self,row,box,anchor,center,pixels):
        if self.display_mode=='Box' or not self.enforce_readability: return 0
        a,b=leader_segment(anchor,center,box); dpr=self.canvas3.devicePixelRatioF()
        faces=[m['face'] for m in self.valid_preview['markers']]
        others=np.asarray([i for i in range(len(pixels)) if i!=row])
        hits=int(np.count_nonzero(distance_to_segment(pixels[others],a,b)<7*dpr))
        crossings=sum(segments_cross(a,b,c,d) for _,c,d,_ in self.label_leaders)
        badge_hits=sum(segment_box(a,b,other_box) or segment_box(c,d,box) for _,c,d,other_box in self.label_leaders)
        wrong_face=sum(self.frame_bounds[f].overlaps(box) and intersection_area(rectangle(box),frame)>1e-6
            for f,frame in self.projected_frames.items() if f!=faces[row])
        # Shortest unobstructed leaders first; all distances are display pixels.
        return float(np.linalg.norm(b-a)/dpr+1000000*(hits+crossings+badge_hits)+10000*wrong_face)

    def draw_selected_overlay(self):
        if self.display_mode=='Box': return super().draw_selected_overlay()
        super().draw_selected_overlay()
        self.selection_ring.set_markersize(9); self.selection_ring.set_markeredgewidth(1)
        for text in list(self.axes.texts): text.remove()
        self.label_leaders=[]; self.title_annotations=[]
        renderer=self.canvas3.get_renderer(); dpr=self.canvas3.devicePixelRatioF()
        pixels=project(self.axes,self.display_xyz)
        self.projected_frames={f:project(self.axes,p) for f,p in self.face_vertices.items()}
        self.frame_bounds={f:Bbox.from_extents(*np.min(p,axis=0),*np.max(p,axis=0)) for f,p in self.projected_frames.items()}
        fw,fh=self.figure3.bbox.width,self.figure3.bbox.height
        available=Bbox.from_extents(6*dpr,6*dpr,fw-6*dpr,fh-6*dpr)
        obstacles=[Bbox.from_bounds(x-7*dpr,y-7*dpr,14*dpr,14*dpr) for x,y in pixels]
        selected=pixels[self.selected_row]
        obstacles[self.selected_row]=Bbox.from_bounds(selected[0]-13*dpr,selected[1]-13*dpr,26*dpr,26*dpr)
        marker=self.valid_preview['markers'][self.selected_row]
        width,height,_=renderer.get_text_width_height_descent(marker['id'],FontProperties(size=10),False)
        width+=10*dpr; height+=10*dpr; candidates=[]
        for distance in (20,28,40,55,75,100):
            for dx,dy in ((1,1),(-1,1),(1,-1),(-1,-1),(1,0),(-1,0),(0,1),(0,-1)):
                x,y=selected+np.asarray([dx,dy])*distance*dpr
                box=Bbox.from_bounds(x-width/2,y-height/2,width,height)
                if not (available.contains(box.x0,box.y0) and available.contains(box.x1,box.y1)): continue
                if any(box.overlaps(other) for other in obstacles): continue
                candidates.append((self.label_candidate_score(self.selected_row,box,selected,(x,y),pixels),x,y,box))
        assert candidates,'No readable selected badge position'
        _,x,y,box=min(candidates,key=lambda p:p[0])
        if self.active_layout is not None: x,y=self.active_layout['ids'][self.selected_row]
        xy=self.axes.transData.inverted().transform(selected)
        self.axes.annotate(marker['id'],xy,xycoords=self.axes.transData,
            xytext=(x,y),textcoords='figure pixels',ha='center',va='center',fontsize=10,
            bbox=dict(boxstyle='round,pad=.12',fc='white',ec='#111111'),
            arrowprops=dict(arrowstyle='-',color='#444444',linewidth=.6),zorder=101)
        self.record_label_position(self.selected_row,selected,(x,y),box)
        length=max(self.valid_preview['box_dims_mm'])*.12
        for axis,color in enumerate(('#b33','#386b36','#376fa8')):
            endpoint=np.zeros(3); endpoint[axis]=length
            end=self.axes.transData.inverted().transform(project(self.axes,[endpoint])[0])
            self.axes.annotate('XYZ'[axis],end,xycoords=self.axes.transData,
                xytext=(4,4),textcoords='offset points',fontsize=9,color=color,zorder=104)
        self.canvas3.draw(); renderer=self.canvas3.get_renderer()
        occupied=[text.get_bbox_patch().get_window_extent(renderer) if text.get_bbox_patch() else text.get_window_extent(renderer) for text in self.axes.texts]
        for face,frame in self.projected_frames.items():
            title=face.title()+f' ({sum(m["face"]==face for m in self.valid_preview["markers"])})'
            width,height,_=renderer.get_text_width_height_descent(title,FontProperties(size=9,weight='bold'),False)
            width+=8*dpr; height+=8*dpr; proposals=[]
            cx,cy=np.mean(frame,axis=0)
            for gap in (16,28,42,60):
                proposals.extend([(cx,np.max(frame[:,1])+gap*dpr),(cx,np.min(frame[:,1])-gap*dpr),
                    (np.min(frame[:,0])-width/2-gap*dpr,cy),(np.max(frame[:,0])+width/2+gap*dpr,cy)])
            chosen=None
            if self.active_layout is not None:
                x,y=self.active_layout['titles'][face]
                chosen=(x,y,Bbox.from_bounds(x-width/2,y-height/2,width,height))
            for x,y in proposals:
                if chosen is not None: break
                box=Bbox.from_bounds(x-width/2,y-height/2,width,height)
                if not (available.contains(box.x0,box.y0) and available.contains(box.x1,box.y1)): continue
                if any(box.overlaps(other) for other in obstacles+occupied): continue
                if any(self.frame_bounds[f].overlaps(box) and intersection_area(rectangle(box),p)>1e-6 for f,p in self.projected_frames.items() if f!=face): continue
                chosen=(x,y,box); break
            assert chosen is not None,f'No unoccluded title for {face}'
            x,y,box=chosen
            annotation=self.axes.annotate(title,(x,y),xycoords='figure pixels',ha='center',va='center',
                fontsize=9,color=COLORS[face],fontweight='bold',
                bbox=dict(boxstyle='round,pad=.15',fc='white',ec='none',alpha=.94),zorder=103)
            self.title_annotations.append(annotation); occupied.append(box)
        self.canvas3.draw()

    def selection_overlay(self):
        key=(tuple(self.source_xyz.ravel()),tuple(self.valid_preview['box_dims_mm']),self.valid_preview.get('version'),
            tuple(self.display_xyz.ravel()),tuple((m['id'],m['face']) for m in self.valid_preview['markers']),self.name_mode,
            tuple(self.axes.get_proj().ravel()),tuple(self.figure3.bbox.bounds),self.canvas3.devicePixelRatioF()) if self.display_mode!='Box' else None
        self.active_layout=self.layout_cache.get(key) if self.enforce_readability and self.name_mode=='All' else None
        reused=self.active_layout is not None
        if not reused:
            super().selection_overlay()
            if self.display_mode=='Box' or not self.enforce_readability: return
            self.untangle_ids()
        else:
            self.draw_selected_overlay(); self.id_annotations=[(self.selected_row,self.axes.texts[0])]
            for row,marker in enumerate(self.valid_preview['markers']):
                if row==self.selected_row: continue
                xy=self.axes.transData.inverted().transform(project(self.axes,[self.display_xyz[row]])[0])
                annotation=self.axes.annotate(marker['id'],xy,xycoords=self.axes.transData,
                    xytext=self.active_layout['ids'][row],textcoords='figure pixels',ha='center',va='center',fontsize=10,
                    bbox=dict(boxstyle='round,pad=.12',fc='white',ec='none',alpha=.94),
                    arrowprops=dict(arrowstyle='-',color='#666666',linewidth=.6),zorder=102)
                self.id_annotations.append((row,annotation))
            self.canvas3.draw()
        renderer=self.canvas3.get_renderer(); pixels=project(self.axes,self.display_xyz); dpr=self.canvas3.devicePixelRatioF()
        point_boxes=[Bbox.from_bounds(x-7*dpr,y-7*dpr,14*dpr,14*dpr) for x,y in pixels]
        title_boxes=[a.get_bbox_patch().get_window_extent(renderer) for a in self.title_annotations]
        selected_box=self.id_annotations[0][1].get_bbox_patch().get_window_extent(renderer)
        selected_ring=self.selection_ring.get_window_extent(renderer)
        point_diameter=(np.sqrt(85)+.75)*renderer.points_to_pixels(1)
        distances=np.linalg.norm(pixels[:,None]-pixels[None,:],axis=2)
        disk_hits=np.argwhere(np.triu(distances<point_diameter,1))
        ring_radius=(selected_ring.width+self.selection_ring.get_markeredgewidth()*renderer.points_to_pixels(1))/2
        ring_hits=[i for i in range(len(pixels)) if i!=self.selected_row and distances[self.selected_row,i]<ring_radius+point_diameter/2]
        title_hits=sum(b.overlaps(p) for b in title_boxes for p in point_boxes+[selected_ring,selected_box])
        title_collisions=sum(a.overlaps(b) for i,a in enumerate(title_boxes) for b in title_boxes[i+1:])
        selected_hits=sum(selected_box.overlaps(p) for p in point_boxes+[selected_ring])
        leader_hits=[]; leader_crossings=[]; badge_leader_hits=[]; lengths=[]; actual_leaders=[]
        badge_boxes=[(r,a.get_bbox_patch().get_window_extent(renderer)) for r,a in self.id_annotations]
        badge_collisions=sum(a.overlaps(b) for i,(_,a) in enumerate(badge_boxes) for _,b in badge_boxes[i+1:])
        for row,annotation in self.id_annotations:
            patch=annotation.arrow_patch
            if patch is None: continue
            path=patch.get_path().transformed(patch.get_transform()); vertices=path.vertices
            actual_leaders.append((row,vertices[0],vertices[-1]))
            lengths.append(float(np.linalg.norm(vertices[0]-vertices[-1])/dpr))
            for other,box in enumerate(point_boxes):
                if other!=row and path.intersects_bbox(box,filled=False): leader_hits.append([row,other])
            for other,box in badge_boxes:
                if other!=row and path.intersects_bbox(box,filled=False): badge_leader_hits.append([row,other])
        for i,(row,a,b) in enumerate(actual_leaders):
            for other,c,d in actual_leaders[i+1:]:
                if segments_cross(a,b,c,d): leader_crossings.append([row,other])
        self.readability_metrics=dict(selected_id=self.valid_preview['markers'][self.selected_row]['id'],layout_reused=reused,id_badge_collisions=int(badge_collisions),title_marker_or_selected_occlusions=int(title_hits),title_bbox_collisions=int(title_collisions),
            marker_disk_overlap_pairs=disk_hits.tolist(),selected_ring_other_marker_intersections=ring_hits,
            selected_badge_marker_or_ring_occlusions=int(selected_hits),leader_marker_intersections=leader_hits,
            leader_badge_intersections=badge_leader_hits,leader_crossings=leader_crossings,
            maximum_leader_logical_px=round(max(lengths,default=0),2),
            note='Actual rendered extents/arrow paths; display diagnostics, not physical tolerance or native acceptance.')
        assert title_hits==0 and title_collisions==0 and selected_hits==0,self.readability_metrics
        assert badge_collisions==0,self.readability_metrics
        assert not len(disk_hits) and not ring_hits,self.readability_metrics
        assert not leader_hits and not badge_leader_hits and not leader_crossings,self.readability_metrics
        if not reused and self.name_mode=='All':
            self.layout_cache[key]=dict(ids={r:tuple(a.get_position()) for r,a in self.id_annotations},
                titles={face:tuple(a.get_position()) for face,a in zip(self.projected_frames,self.title_annotations)})

    def untangle_ids(self):
        """Coordinate descent against every existing badge/leader, using actual sizes."""
        dpr=self.canvas3.devicePixelRatioF(); pixels=project(self.axes,self.display_xyz)
        fw,fh=self.figure3.bbox.width,self.figure3.bbox.height
        inset=6*dpr; available=Bbox.from_extents(inset,inset,fw-inset,fh-inset)
        point_boxes=[Bbox.from_bounds(x-7*dpr,y-7*dpr,14*dpr,14*dpr) for x,y in pixels]
        ring=self.selection_ring.get_window_extent(self.canvas3.get_renderer())
        offsets=[np.asarray([np.cos(a),np.sin(a)])*r*dpr for r in (16,24,32,44,60,80,110)
            for a in np.arange(0,2*np.pi,np.pi/8)]
        annotations=dict(self.id_annotations)
        for iteration in range(10):
            renderer=self.canvas3.get_renderer()
            boxes={row:a.get_bbox_patch().get_window_extent(renderer) for row,a in self.id_annotations}
            segments={}
            for row,a in self.id_annotations:
                path=a.arrow_patch.get_path().transformed(a.arrow_patch.get_transform())
                segments[row]=(path.vertices[0],path.vertices[-1])
            reserved=[a.get_bbox_patch().get_window_extent(renderer) if a.get_bbox_patch() else a.get_window_extent(renderer)
                for a in self.axes.texts if a not in annotations.values()]
            def badness(row,box,segment):
                a,b=segment; other_rows=[r for r in boxes if r!=row]
                hits=sum(segment_box(a,b,p) for i,p in enumerate(point_boxes) if i!=row)
                hits+=int(row!=self.selected_row and segment_box(a,b,ring))
                hits+=sum(segment_box(a,b,boxes[r]) or segment_box(*segments[r],box) for r in other_rows)
                hits+=sum(segments_cross(a,b,*segments[r]) for r in other_rows)
                return hits
            def actual(row,position):
                annotation=annotations[row]; annotation.set_position(tuple(position))
                annotation.update_positions(renderer); annotation.update_bbox_position_size(renderer)
                box=annotation.get_bbox_patch().get_window_extent(renderer)
                path=annotation.arrow_patch.get_path().transformed(annotation.arrow_patch.get_transform())
                return box,(path.vertices[0],path.vertices[-1])
            def legal(box,excluded):
                return (available.contains(box.x0,box.y0) and available.contains(box.x1,box.y1)
                    and not any(box.overlaps(p) for p in point_boxes+reserved+[ring]+[p for r,p in boxes.items() if r not in excluded]))
            def resolve_pair():
                # A clear neighboring label may need to move to free a clean slot.
                for row in sorted(boxes,key=lambda r:-badness(r,boxes[r],segments[r])):
                    if badness(row,boxes[row],segments[row])==0: continue
                    position_a=annotations[row].get_position(); box_a,seg_a=boxes[row],segments[row]
                    for offset in offsets:
                        center_a=pixels[row]+offset; box,segment=actual(row,center_a)
                        blockers=[r for r,p in boxes.items() if r!=row and
                            (box.overlaps(p) or segment_box(*segment,p) or segment_box(*segments[r],box) or segments_cross(*segment,*segments[r]))]
                        if len(blockers)!=1 or not legal(box,{row,blockers[0]}): continue
                        other=blockers[0]
                        if other==self.selected_row: continue
                        position_b=annotations[other].get_position(); box_b,seg_b=boxes[other],segments[other]
                        boxes[row]=box; segments[row]=segment
                        a,b=segment
                        impossible=sum(segment_box(a,b,p) for i,p in enumerate(point_boxes) if i!=row)
                        impossible+=int(row!=self.selected_row and segment_box(a,b,ring))
                        unrelated=[r for r in boxes if r not in (row,other)]
                        impossible+=sum(segment_box(a,b,boxes[r]) or segment_box(*segments[r],box) or segments_cross(a,b,*segments[r]) for r in unrelated)
                        if impossible:
                            boxes[row]=box_a; segments[row]=seg_a; continue
                        for next_offset in offsets:
                            center_b=pixels[other]+next_offset; new_box,new_segment=actual(other,center_b)
                            if not legal(new_box,{other}): continue
                            boxes[other]=new_box; segments[other]=new_segment
                            if badness(row,boxes[row],segments[row])==0 and badness(other,new_box,new_segment)==0:
                                return True
                            boxes[other]=box_b; segments[other]=seg_b
                        annotations[other].set_position(position_b); boxes[other]=box_b; segments[other]=seg_b
                        boxes[row]=box_a; segments[row]=seg_a
                    annotations[row].set_position(position_a); boxes[row]=box_a; segments[row]=seg_a
                return False
            troublesome=sorted(boxes,key=lambda r:-badness(r,boxes[r],segments[r]))
            changed=False
            for row in troublesome:
                original=boxes[row]; old_segment=segments[row]; old_hits=badness(row,original,old_segment)
                if old_hits==0: continue
                annotation=annotations[row]; original_position=annotation.get_position()
                best=None; best_score=(old_hits,float('inf'))
                for offset in offsets:
                    center=pixels[row]+offset; x,y=center
                    annotation.set_position(tuple(center))
                    annotation.update_positions(renderer); annotation.update_bbox_position_size(renderer)
                    box=annotation.get_bbox_patch().get_window_extent(renderer)
                    if not (available.contains(box.x0,box.y0) and available.contains(box.x1,box.y1)): continue
                    if any(box.overlaps(p) for p in point_boxes+reserved+[ring]+[p for r,p in boxes.items() if r!=row]): continue
                    path=annotation.arrow_patch.get_path().transformed(annotation.arrow_patch.get_transform())
                    segment=(path.vertices[0],path.vertices[-1])
                    hits=badness(row,box,segment)
                    # Keep badge association with its source face when possible.
                    face=self.valid_preview['markers'][row]['face']
                    wrong=sum(self.frame_bounds[f].overlaps(box) and intersection_area(rectangle(box),p)>1e-6
                        for f,p in self.projected_frames.items() if f!=face)
                    score=(hits,wrong*1000+float(np.linalg.norm(segment[1]-segment[0])/dpr))
                    if score<best_score: best_score=score; best=(center,box,segment)
                if best is not None and best_score[0]<old_hits:
                    center,box,segment=best; annotations[row].set_position(tuple(center))
                    boxes[row]=box; segments[row]=segment; changed=True
                else: annotation.set_position(original_position)
            self.canvas3.draw()
            if not changed:
                changed=resolve_pair(); self.canvas3.draw()
                if not changed: break


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--selection-sweep',action='store_true'); args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True); app=QApplication.instance() or QApplication([]); states=[]; sweep=[]
    for example in ('32','18'):
        source=load_profile(example=example)
        assert validate_profile(source)==EXPECTED_HASHES[example]
        for size in ((1280,960),(1920,1080),(820,600)):
            window=FinalVisibilityPrototype(example,size); settled(window,app,size)
            for position in ('top','bottom') if window.plot_scroll else ('both',):
                if window.plot_scroll:
                    bar=window.plot_scroll.verticalScrollBar(); bar.setValue(bar.maximum() if position=='bottom' else 0); app.processEvents()
                entry=capture_reviewed(window,args.output,f'final-{example}-{size[0]}x{size[1]}-{position}.png',size)
                _,_,center=geometry(source,1); dpr=window.canvas3.devicePixelRatioF()
                entry.update(example=example,camera=[window.axes.elev,window.axes.azim,window.axes.roll],radius_ratio=1,
                    scroll_position=position,source_hash=EXPECTED_HASHES[example],labels=window.label_metrics,readability=window.readability_metrics,
                    metrics=measurements(source,{f:p/dpr for f,p in window.projected_frames.items()},project(window.axes,window.display_xyz)/dpr,project(window.axes,center)/dpr))
                states.append(entry)
                print(json.dumps(dict(captured=entry['screenshot'],readability=window.readability_metrics)),flush=True)
            if size==(1280,960):
                for marker_id in ('B3','B10') if example=='32' else ('F1','M2'):
                    row,annotation=next((r,a) for r,a in window.id_annotations if source['markers'][r]['id']==marker_id)
                    box=annotation.get_bbox_patch().get_window_extent(window.canvas3.get_renderer()); dpr=window.canvas3.devicePixelRatioF()
                    p=window.canvas3.rect().topLeft(); p.setX(round((box.x0+box.x1)/2/dpr))
                    p.setY(window.canvas3.height()-round((box.y0+box.y1)/2/dpr))
                    QTest.mouseClick(window.canvas3,Qt.LeftButton,pos=p); app.processEvents()
                    assert window.selected_id==marker_id and window.table.currentRow()==row
                    assert window.valid_preview['markers']==source['markers']
                rows=range(len(source['markers'])) if args.selection_sweep else [0,window.selected_row]
                for row in rows:
                    window.selected_row=row; window.selection_overlay(); app.processEvents()
                    sweep.append(dict(example=example,selected=source['markers'][row]['id'],kind='actual-selected-layout-render',readability=window.readability_metrics,labels=window.label_metrics))
                    assert window.valid_preview['markers']==source['markers']
                    if row%8==0: print(json.dumps(dict(selection=source['markers'][row]['id'],example=example,status='pass')),flush=True)
                window.table.selectRow(0); app.processEvents()
                assert window.selected_id=='F1' and 'Selected: F1' in window.selected_readout.text()
                window.axes.view_init(10,15,5,vertical_axis='y'); QTest.mouseClick(window.reset_view,Qt.LeftButton)
                assert (window.axes.elev,window.axes.azim,window.axes.roll)==(25,50,30)
                if example=='18':
                    window.table.selectRow(17); app.processEvents()
                    assert '(38, -60, -18) mm' in window.selected_readout.text()
                    assert np.array_equal(window.display_xyz[17],[38,-200,-18])
                for mode in ('Box','Exploded faces'):
                    window.mode_combo.setCurrentText(mode); app.processEvents()
                    assert window.valid_preview['markers']==source['markers']
                assert (window.axes.elev,window.axes.azim,window.axes.roll)==(25,50,30)
                for mode in ('Selected','View face','All'):
                    window.names3.setCurrentText(mode); app.processEvents()
                    expected=1 if mode=='Selected' else len(source['markers']) if mode=='All' else sum(m['face']==window.current_face for m in source['markers'])
                    assert len(window.id_annotations)==expected
                if example=='18':
                    before=set(window.layout_cache); applied=__import__('copy').deepcopy(window.applied)
                    window.table.item(0,2).setText('22'); QTest.mouseClick(window.preview_button,Qt.LeftButton)
                    assert window.valid_preview['markers'][0]['xyz_mm']==[22.,12.,40.]
                    assert set(window.layout_cache)!=before and window.applied==applied
                    before=set(window.layout_cache); window.table.item(0,0).setText('F9')
                    QTest.mouseClick(window.preview_button,Qt.LeftButton)
                    assert window.valid_preview['markers'][0]['id']=='F9' and set(window.layout_cache)!=before
                    QTest.mouseClick(window.reset_button,Qt.LeftButton)
                    assert window.valid_preview['markers']==source['markers'] and window.applied==applied
            if size==(820,600):
                window.tabs.setCurrentWidget(window.table); row=next(i for i,m in enumerate(source['markers']) if m['id']=='B2')
                window.table.item(row,3).setText('bad'); app.processEvents()
                assert window.status.text()=='B2: Y must be a finite number.'
                assert not any(b.isEnabled() for b in (window.preview_button,window.save_button,window.apply_button))
                states.append(capture_reviewed(window,args.output,f'final-{example}-820x600-invalid.png',size))
                window.table.item(row,3).setText(str(source['markers'][row]['xyz_mm'][1])); assert window.preview_button.isEnabled()
            assert window.valid_preview['markers']==source['markers']; window.close()
    report=base_report('FinalExplodedVisibilityEvidence')
    report['dependency_sha256']['compare_exploded_angles.py']=__import__('hashlib').sha256(Path(__file__).with_name('compare_exploded_angles.py').read_bytes()).hexdigest()
    report.update(source_sha256=__import__('hashlib').sha256(Path(__file__).read_bytes()).hexdigest(),states=states,selection_sweep=sweep,
        environment=dict(qt_platform=app.platformName(),dpr=app.primaryScreen().devicePixelRatio(),windows_scale_percent=100,
            qt_process_scale_percent=100*app.primaryScreen().devicePixelRatio()),result='pass',fresh=True,
        independent_expected='Exact literal source18/32 hashes/marker arrays; zero marker/ring occlusion by selected badge or face titles; zero title/ID badge overlaps and actual leader intersections; direct B3/B10 or F1/M2 ID clicks select canonical rows; M2 original[38,-60,-18]/display[38,-200,-18]; Reset view25/50/30; Names mode counts1/face/total;18 F1 X21->22 and F1->F9 Preview invalidate layout and retain applied; Reset source restores canonical fixture.',
        limitations=['Arrow diagnostics supplement human inspection; arbitrary camera angles and imported layouts are not universally occlusion-free.',
            'Qt widget render/QTest; native Windows input/capture unavailable. Production paths remain unimplemented.'],
        prior_attempts=[dict(status='failed',command='compare_exploded_angles.py --small B-balanced',
            cause='Summary print expected source_hash on bottom/invalid screenshot records; KeyError after evidence and assertions completed.',
            correction='Use optional-key lookup; final visibility harness has a separate summary.'),
            dict(status='interrupted',command='finalize_exploded_visibility.py initial selection sweep',
                cause='First valid screenshot produced; stopped Main-owned process to avoid redundant polygon clipping and penalize leader/badge intersections.',
                correction='Cached frame bounding boxes, density-first label ordering, bidirectional leader/badge checks; no prior attempt declared passed.')])
    (args.output/'evidence.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(states=len(states),selection_checks=len(sweep),dpr=app.primaryScreen().devicePixelRatio(),readability=[s['readability'] for s in states if 'readability' in s])))


if __name__=='__main__': main()
