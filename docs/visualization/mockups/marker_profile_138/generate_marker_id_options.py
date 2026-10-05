"""Read-only geometry, interactive preapproval 3D name-display alternatives."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QLabel
from matplotlib.colors import to_rgba
from matplotlib.font_manager import FontProperties
from matplotlib.transforms import Bbox
from mpl_toolkits.mplot3d import proj3d

from generate_reviewed_mockups import ReviewedPrototype, settled, capture_reviewed
from generate_preview_options import COLORS
from generate_mockups import EXPECTED_HASHES, PLAN_SPEC
from src.simulation.marker_fixtures import load_profile, validate_profile


class MarkerIdPrototype(ReviewedPrototype):
    def __init__(self,example='32',size=(1280,960),mode='View face'):
        self.name_mode=mode
        self.id_annotations=[]
        self.label_metrics={}
        super().__init__(example,size)
        bar=self.plot_splitter.widget(0).layout().itemAt(0).layout()
        bar.insertWidget(1,QLabel('Names'))
        self.names3=QComboBox(); self.names3.addItems(['View face','All','Selected'])
        self.names3.setCurrentText(mode)
        self.names3.setToolTip('3D marker names; View face names the face chosen above and the selected marker.')
        bar.insertWidget(2,self.names3)
        self.names3.currentTextChanged.connect(self.change_names)
        self.setWindowTitle('Marker profile #138 — PREAPPROVAL 3D names: '+mode)

    def change_names(self,mode):
        self.name_mode=mode; self.selection_overlay()

    def render3(self,camera):
        super().render3(camera)
        colors=[to_rgba(COLORS[m['face']],.95 if m['face']==self.current_face else .65)
                for m in self.valid_preview['markers']]
        self.axes.collections[0].set_facecolor(colors)
        self.canvas3.draw()

    def draw_selected_overlay(self):
        super().selection_overlay()

    def extra_label_obstacles(self):
        return []

    def label_candidate_score(self,row,box,anchor,center,pixels):
        return 0  # Preserve this prototype's historical first-valid placement.

    def record_label_position(self,row,anchor,center,box):
        pass

    def label_rows(self,pixels):
        return range(len(self.valid_preview['markers']))

    def selection_overlay(self):
        self.draw_selected_overlay()
        renderer=self.canvas3.get_renderer(); dpr=self.canvas3.devicePixelRatioF()
        self.id_annotations=[(self.selected_row,self.axes.texts[0])]
        selected_box=self.axes.texts[0].get_bbox_patch().get_window_extent(renderer)
        occupied=[selected_box.expanded(1.1,1.1)]
        # Read already-rendered tick positions; get_ticklabels would reset 3D projections.
        reserved=self.extra_label_obstacles()
        for axis,limits in zip((self.axes.xaxis,self.axes.yaxis,self.axes.zaxis),
                               (self.axes.get_xlim(),self.axes.get_ylim(),self.axes.get_zlim())):
            reserved.append(axis.label.get_window_extent(renderer))
            reserved.extend(tick.label1.get_window_extent(renderer) for tick in axis.majorTicks
                            if min(limits)<=tick.get_loc()<=max(limits) and tick.label1.get_visible())
        xy=np.asarray([proj3d.proj_transform(*p,self.axes.get_proj())[:2] for p in self.xyz])
        pixels=self.axes.transData.transform(xy)
        markers=[Bbox.from_bounds(x-7*dpr,y-7*dpr,14*dpr,14*dpr) for x,y in pixels]
        fw,fh=self.figure3.bbox.width,self.figure3.bbox.height
        inset=6*dpr; available=Bbox.from_extents(inset,inset,fw-inset,fh-inset)
        offsets=[]
        for distance in (16,24,34,46,60,80,110):
            offsets.extend((dx*distance*dpr,dy*distance*dpr) for dx,dy in
                           ((1,1),(-1,1),(1,-1),(-1,-1),(1,0),(-1,0),(0,1),(0,-1)))
        fallback=0
        for row in self.label_rows(pixels):
            marker=self.valid_preview['markers'][row]
            if row==self.selected_row: continue
            if self.name_mode=='Selected': continue
            if self.name_mode=='View face' and marker['face']!=self.current_face: continue
            width,height,_=renderer.get_text_width_height_descent(marker['id'],FontProperties(size=10),False)
            width+=8*dpr; height+=8*dpr
            px,py=pixels[row]; chosen=None; best_score=float('inf')
            for dx,dy in offsets:
                x,y=px+dx,py+dy
                box=Bbox.from_bounds(x-width/2,y-height/2,width,height)
                if not (available.contains(box.x0,box.y0) and available.contains(box.x1,box.y1)): continue
                if any(box.overlaps(other) for other in occupied+reserved+markers): continue
                score=self.label_candidate_score(row,box,(px,py),(x,y),pixels)
                if score<best_score:
                    chosen=(x,y,box); best_score=score
                if score==0: break
            if chosen is None:
                # Screen-space side whitespace, never displacement of a marker.
                for y in np.arange(available.y1-height/2,available.y0+height/2,-(height+3*dpr)):
                    for x in np.arange(available.x0+width/2,available.x1-width/2,width+4*dpr):
                        box=Bbox.from_bounds(x-width/2,y-height/2,width,height)
                        if not any(box.overlaps(other) for other in occupied+reserved+markers):
                            chosen=(x,y,box); break
                    if chosen is not None: break
                fallback+=1
            assert chosen is not None, f'No unclipped label position for {marker["id"]}'
            x,y,box=chosen
            annotation=self.axes.annotate(marker['id'],xy[row],xycoords=self.axes.transData,
                xytext=(x,y),textcoords='figure pixels',ha='center',va='center',
                fontsize=10,color='#222222',bbox=dict(boxstyle='round,pad=.12',fc='white',ec='none',alpha=.94),
                arrowprops=dict(arrowstyle='-',color='#666666',linewidth=.6),zorder=102)
            self.id_annotations.append((row,annotation)); occupied.append(box)
            self.record_label_position(row,(px,py),(x,y),box)
        self.canvas3.draw()
        boxes=[annotation.get_bbox_patch().get_window_extent(self.canvas3.get_renderer())
               for _,annotation in self.id_annotations]
        collisions=sum(a.overlaps(b) for i,a in enumerate(boxes) for b in boxes[i+1:])
        clipping=sum(not(available.contains(b.x0,b.y0) and available.contains(b.x1,b.y1)) for b in boxes)
        self.label_metrics=dict(mode=self.name_mode,label_count=len(boxes),
            label_ids=[self.valid_preview['markers'][row]['id'] for row,_ in self.id_annotations],
            label_bbox_collisions=int(collisions),label_badges_clipped=int(clipping),side_fallbacks=fallback,
            note='Measured bbox checks are not a human readability/leader-line-crossing acceptance.')
        assert collisions==0 and clipping==0,self.label_metrics

    def pick(self,event,kind):
        if kind=='3d' and event.button==1 and event.x is not None and event.y is not None:
            renderer=self.canvas3.get_renderer()
            for row,annotation in self.id_annotations:
                if annotation.get_bbox_patch().get_window_extent(renderer).contains(event.x,event.y):
                    self.table.selectRow(row); return
        super().pick(event,kind)


def check_names(app):
    window=MarkerIdPrototype('32',(1280,960),'All'); settled(window,app,(1280,960))
    assert window.label_metrics['label_count']==32
    for marker_id in ('F3','B2'):
        row,annotation=next((r,a) for r,a in window.id_annotations if window.valid_preview['markers'][r]['id']==marker_id)
        box=annotation.get_bbox_patch().get_window_extent(window.canvas3.get_renderer())
        point=window.canvas3.rect().topLeft()
        point.setX(round((box.x0+box.x1)/2/window.canvas3.devicePixelRatioF()))
        point.setY(window.canvas3.height()-round((box.y0+box.y1)/2/window.canvas3.devicePixelRatioF()))
        QTest.mouseClick(window.canvas3,Qt.LeftButton,pos=point)
        assert window.selected_id==marker_id and window.table.currentRow()==row
    window.names3.setCurrentText('View face'); window.view_combo.setCurrentText('Back')
    assert window.label_metrics['label_count']==12
    window.names3.setCurrentText('Selected'); assert window.label_metrics['label_ids']==['B2']
    assert window.valid_preview['markers']==load_profile(example='32')['markers']
    window.close()
    return dict(status='pass',kind='prototype-QTest',expected='All32; exact F3/B2 label click selects ID; Back12; SelectedB2; original marker coordinates unchanged')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'marker_ids')
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([]); entries=[]
    for example in ('18','32'):
        assert validate_profile(load_profile(example=example))==EXPECTED_HASHES[example]
        for mode in ('View face','All'):
            for size in ((1280,960),(1920,1080),(820,600)):
                window=MarkerIdPrototype(example,size,mode); settled(window,app,size)
                name=f'{example}-{mode.replace(" ","-").lower()}-{size[0]}x{size[1]}.png'
                entry=capture_reviewed(window,args.output,name,size)
                entry.update(example=example,labels=window.label_metrics,
                    camera=[window.axes.elev,window.axes.azim],projected_box_pixels=list(window.bounds3().size),
                    marker_area_points_squared=85,other_face_alpha=.65)
                entries.append(entry)
                assert window.valid_preview['markers']==load_profile(example=example)['markers']
                window.close()
    report=dict(schema_version=1,plan_spec=PLAN_SPEC,object_type='MarkerIdDisplayMockupEvidence',
        utc=datetime.now(timezone.utc).isoformat(),command=__import__('sys').argv,
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        input=dict(profile_hashes=EXPECTED_HASHES,kind='public-synthetic-static-geometry',seed=None,
            seed_reason='No random observations; static geometry',tolerance=None,tolerance_reason='Exact fixture invariance, not physical accuracy'),
        environment=dict(qt_platform=app.platformName(),dpr=app.primaryScreen().devicePixelRatio(),
            windows_scale_percent=100,qt_process_scale_percent=app.primaryScreen().devicePixelRatio()*100),
        states=entries,interaction=check_names(app),user_approval='pending',independent_review='not-yet-reviewed-new-variants',
        native_status='not-executed-existing-activation-capture-failure',production_changed=False,
        prior_attempts=[dict(status='failed',boundary='evidence-serialization',
            diagnostic='NumPy int64 bbox counts were not JSON serializable after captures/QTest.',
            correction='Convert counts to builtin int and rerun; failed manifest was not acceptance.')],
        limitations=['Label bbox tests do not certify human legibility or leader-line crossings.',
            'View face leaves other faces unnamed unless selected; All provides all IDs.',
            'Previous independent approval covered audited prototype, not these new variants.'])
    (args.output/'evidence.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(states=len(entries),dpr=app.primaryScreen().devicePixelRatio(),interaction=report['interaction'])))


if __name__=='__main__': main()
