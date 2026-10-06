"""User-reviewable prototype from the two Sol/xhigh advisors' design debate."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np
import PySide6
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QPushButton, QScrollArea, QSplitter, QTableWidgetItem, QVBoxLayout, QWidget)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.colors import to_rgba
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator
from matplotlib.transforms import Bbox
from mpl_toolkits.mplot3d import proj3d

from generate_mockups import Prototype, capture, EXPECTED_HASHES, PLAN_SPEC
from generate_preview_options import VisibilityPrototype, FACES, COLORS, PLANE_AXES
from src.simulation.marker_fixtures import load_profile, validate_profile

NORMALS={'FRONT':(0,0,1),'BACK':(0,0,-1),'RIGHT':(1,0,0),
         'LEFT':(-1,0,0),'TOP':(0,1,0),'BOTTOM':(0,-1,0)}


class ReviewedPrototype(Prototype):
    def __init__(self,example='32',size=(1920,1080),state='copy'):
        self.ready=False
        self.selected_row=0
        self.current_face='BACK'
        self.zoom_3d=None
        self.labels=[]; self.label_bounds=[]
        self.face_views={}
        self.selection_ring=None
        super().__init__('example32' if example=='32' else state,size)
        # Copy is an entry action in the export window; this editor already holds a copy.
        self.copy_button.hide(); self.copy_button.clicked.disconnect()
        self.setWindowTitle('Marker profile #138 — PREAPPROVAL reviewed layout')
        old=self.preview_panel.layout()
        while old.count():
            item=old.takeAt(0)
            if item.widget(): item.widget().setParent(None)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.verticalHeader().setMinimumSectionSize(26)
        for row in range(self.table.rowCount()): self.table.setRowHeight(row,26)
        for col in range(1,5):
            self.table.horizontalHeader().setSectionResizeMode(col,QHeaderView.Fixed)
            self.table.setColumnWidth(col,88 if col==1 else 72)
        self.table.setMinimumWidth(440)
        for splitter in self.findChildren(QSplitter): splitter.setSizes([480,size[0]-500])

        old.addWidget(self.preview_title)
        facebar=QHBoxLayout(); facebar.setSpacing(5)
        facebar.addWidget(QLabel('View face' if size[0]<1100 else 'View face (marker count)'))
        self.view_combo=QComboBox(); self.view_combo.addItems([f.title() for f in FACES])
        self.view_combo.setCurrentText('Back'); facebar.addWidget(self.view_combo)
        self.face_buttons={}
        for face in FACES:
            button=QPushButton(face.title()); button.setCheckable(True)
            button.clicked.connect(lambda _checked=False,f=face:self.view_combo.setCurrentText(f.title()))
            button.setStyleSheet(f'QPushButton {{ border-bottom: 2px solid {COLORS[face]}; padding: 4px 10px; }}')
            facebar.addWidget(button); self.face_buttons[face]=button
        self.view_combo.setVisible(size[0]<1100)
        for button in self.face_buttons.values(): button.setVisible(size[0]>=1100)
        facebar.addStretch(); old.addLayout(facebar)
        self.selected_readout=QLabel(); old.addWidget(self.selected_readout)

        self.plot_splitter=QSplitter(Qt.Vertical)
        self.plot_splitter.setChildrenCollapsible(False)
        self.figure3=Figure(); self.canvas3=FigureCanvasQTAgg(self.figure3)
        self.figure2=Figure(); self.canvas2=FigureCanvasQTAgg(self.figure2)
        self.canvas=self.canvas2  # Existing face-label helper uses this renderer.
        top=QWidget(); top_layout=QVBoxLayout(top); top_layout.setContentsMargins(0,0,0,0)
        topbar=QHBoxLayout(); topbar.addWidget(QLabel('3D layout')); topbar.addStretch()
        self.fit3_button=QPushButton('Fit'); topbar.addWidget(self.fit3_button)
        self.reset_view=QPushButton('Reset view'); topbar.addWidget(self.reset_view)
        top_layout.addLayout(topbar); top_layout.addWidget(self.canvas3,1)
        bottom=QWidget(); bottom_layout=QVBoxLayout(bottom); bottom_layout.setContentsMargins(0,0,0,0)
        bottom_bar=QHBoxLayout(); self.face_title=QLabel(); bottom_bar.addWidget(self.face_title)
        bottom_bar.addStretch(); bottom_bar.addWidget(QLabel('Names'))
        self.names=QComboBox(); self.names.addItems(['All','Selected']); bottom_bar.addWidget(self.names)
        self.nav=NavigationToolbar2QT(self.canvas2,self); self.nav.hide()
        self.pan_button=QPushButton('Pan'); self.pan_button.setCheckable(True)
        self.pan_button.clicked.connect(lambda:self.set_tool('pan')); bottom_bar.addWidget(self.pan_button)
        self.zoom_button=QPushButton('Zoom'); self.zoom_button.setCheckable(True)
        self.zoom_button.clicked.connect(lambda:self.set_tool('zoom')); bottom_bar.addWidget(self.zoom_button)
        self.fit2_button=QPushButton('Fit'); bottom_bar.addWidget(self.fit2_button)
        self.bottom_controls=QWidget(); self.bottom_controls.setLayout(bottom_bar)
        if size[0]<1100:
            old.addWidget(self.bottom_controls)
        else:
            bottom_layout.addWidget(self.bottom_controls)
        bottom_layout.addWidget(self.canvas2,1)
        self.plot_splitter.addWidget(top); self.plot_splitter.addWidget(bottom)
        self.plot_splitter.setSizes([550,450])
        if size[0]<1100:
            top.setMinimumHeight(355); bottom.setMinimumHeight(275)
            self.plot_scroll=QScrollArea(); self.plot_scroll.setFrameShape(QFrame.NoFrame)
            self.plot_scroll.setWidgetResizable(True); self.plot_scroll.setWidget(self.plot_splitter)
            old.addWidget(self.plot_scroll,1)
        else:
            self.plot_scroll=None; old.addWidget(self.plot_splitter,1)

        actions=self.layout().itemAt(self.layout().count()-1).layout()
        self.preview_button.setText('Preview'); actions.insertWidget(0,self.preview_button)
        self.layout_status.hide()
        self.candidates=QFrame(self.preview_panel); self.candidates.setFrameShape(QFrame.StyledPanel)
        self.candidates.setAutoFillBackground(True); self.candidates.hide()
        self.candidate_layout=QVBoxLayout(self.candidates); self.candidate_layout.setContentsMargins(5,5,5,5)
        self.candidate_indices=[]
        self.view_combo.currentTextChanged.connect(self.change_face)
        self.names.currentTextChanged.connect(lambda:self.draw())
        self.table.itemSelectionChanged.connect(self.select_row)
        self.fit3_button.clicked.connect(self.fit3)
        self.reset_view.clicked.connect(self.restore_view)
        self.fit2_button.clicked.connect(self.fit2)
        self.canvas3.mpl_connect('button_press_event',lambda event:self.pick(event,'3d'))
        self.canvas2.mpl_connect('button_press_event',lambda event:self.pick(event,'2d'))
        self.canvas3.mpl_connect('button_release_event',lambda _event:self.selection_overlay())
        self.canvas3.mpl_connect('scroll_event',self.wheel3)
        self.ready=True
        self.axes=None; self.face_axes=None
        self.selected_row=next(i for i,m in enumerate(self.valid_preview['markers']) if m['id']=='B1')
        self.table.selectRow(self.selected_row)
        self.tabs.setCurrentWidget(self.preview_panel)
        self.draw()

    def change_face(self):
        if not self.ready: return
        if self.face_axes is not None:
            self.face_views[self.current_face]=(self.face_axes.get_xlim(),self.face_axes.get_ylim())
        self.face_axes=None
        self.current_face=self.view_combo.currentText().upper(); self.draw()

    def clarify_caption(self):
        if hasattr(self,'preview_title'):
            captions={'Draft preview — not applied':'Preview — not applied',
                'Previous preview — draft changed':'Preview outdated — edits changed',
                'Last valid preview — current draft invalid':'Last valid preview — invalid edits'}
            self.preview_title.setText(captions.get(self.preview_title.text(),self.preview_title.text()))

    def preview(self):
        super().preview(); self.clarify_caption()

    def changed(self,*args):
        if not hasattr(self,'table'): return
        blocked=self.table.blockSignals(True)
        try: self.refresh_changed(*args)
        finally: self.table.blockSignals(blocked)

    def refresh_changed(self,*args):
        super().changed(*args); self.clarify_caption()
        if not hasattr(self,'status'): return
        invalid=[]
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                self.table.item(row,col).setBackground(QBrush())
            for col in (2,3,4):
                try:
                    if not np.isfinite(float(self.table.item(row,col).text())): raise ValueError()
                except (ValueError,TypeError): invalid.append((row,col))
        if invalid:
            for row,col in invalid: self.table.item(row,col).setBackground(QColor('#ffe0e0'))
            row,col=invalid[0]
            self.status.setText(f'{self.table.item(row,0).text()}: {"XYZ"[col-2]} must be a finite number.')
        elif not self.preview_button.isEnabled() and args and isinstance(args[0],QTableWidgetItem):
            args[0].setBackground(QColor('#ffe0e0'))

    def set_tool(self,tool):
        getattr(self.nav,tool)()
        self.pan_button.setChecked(str(self.nav.mode)=='pan/zoom')
        self.zoom_button.setChecked(str(self.nav.mode)=='zoom rect')

    def select_row(self):
        if not self.ready or self.table.currentRow()<0: return
        self.selected_row=self.table.currentRow()
        marker=self.valid_preview['markers'][min(self.selected_row,len(self.valid_preview['markers'])-1)]
        self.view_combo.setCurrentText(marker['face'].title()); self.draw()

    def draw(self):
        if not self.ready: return super().draw()
        self.clarify_caption()
        if self.face_axes is not None:
            self.face_views[self.current_face]=(self.face_axes.get_xlim(),self.face_axes.get_ylim())
        camera=(self.axes.elev,self.axes.azim,self.axes.roll) if self.axes is not None else (20,30,0)
        self.selected_row=min(self.selected_row,len(self.valid_preview['markers'])-1)
        marker=self.valid_preview['markers'][self.selected_row]; self.selected_id=marker['id']
        normal=', '.join(str(n) for n in NORMALS[marker['face']])
        self.selected_readout.setText(f'Selected: {marker["id"]}  {marker["face"].title()}  ('+
            ', '.join(f'{v:g}' for v in marker['xyz_mm'])+f') mm    Normal: ({normal})')
        self.selected_readout.setToolTip('Selected marker from the last valid preview; normal points outward in the box-local frame.')
        for face,button in self.face_buttons.items():
            count=sum(m['face']==face for m in self.valid_preview['markers'])
            button.setText(face.title()+f' ({count})')
            button.setToolTip(f'View {face.title()} face: {count} markers in the last preview')
            button.setChecked(face==self.current_face)
        self.render3(camera)
        self.figure2.clear(); self.face_axes=self.figure2.add_axes((.09,.14,.86,.81))
        self.labels=[]; self.label_bounds=[]
        VisibilityPrototype.draw_face(self,self.current_face)
        self.face_points=np.asarray(self.face_points).reshape(-1,2)
        self.face_axes.set_title('')
        self.face_axes.set_xlabel(self.face_axes.get_xlabel(),fontsize=9,labelpad=1)
        self.face_axes.set_ylabel(self.face_axes.get_ylabel(),fontsize=9,labelpad=1)
        self.face_axes.tick_params(labelsize=8)
        a,b=PLANE_AXES[self.current_face]; c=next(i for i in range(3) if i not in (a,b))
        value=NORMALS[self.current_face][c]*self.valid_preview['box_dims_mm'][c]/2
        self.face_title.setText(self.current_face.title()+f' / {"XYZ"[c]}={value:g} mm ({len(self.face_markers)})')
        if self.current_face in self.face_views:
            xlim,ylim=self.face_views[self.current_face]; self.face_axes.set_xlim(xlim); self.face_axes.set_ylim(ylim)
        self.canvas2.draw(); VisibilityPrototype.place_face_labels(self)
        if self.names.currentText()=='Selected':
            for label in self.labels: label.set_visible(label.get_text()==self.selected_id)
        self.canvas2.draw()

    def render3(self,camera):
        self.selection_ring=None
        self.figure3.clear(); self.axes=self.figure3.add_axes((.01,.01,.98,.98),projection='3d')
        ax=self.axes; dims=np.asarray(self.valid_preview['box_dims_mm'],float)
        self.corners=np.asarray(list(product((-1,1),repeat=3)))*dims/2
        for i,p in enumerate(self.corners):
            for q in self.corners[i+1:]:
                if np.count_nonzero(p!=q)==1:
                    ax.plot(*np.stack((p,q)).T,color='#9c9c9c',linewidth=.8,alpha=.65)
        self.xyz=np.asarray([m['xyz_mm'] for m in self.valid_preview['markers']])
        rgba=[to_rgba(COLORS[m['face']],.95 if m['face']==self.current_face else .38)
              for m in self.valid_preview['markers']]
        ax.scatter(*self.xyz.T,s=85,c=rgba,edgecolors='#333333',linewidths=.75,depthshade=False)
        ax.view_init(*camera,vertical_axis='y'); ax.set_proj_type('ortho'); ax.grid(False)
        self.ranges=dims*1.1
        for setter,dimension in zip((ax.set_xlim,ax.set_ylim,ax.set_zlim),self.ranges): setter(-dimension/2,dimension/2)
        ax.set_box_aspect(self.ranges.copy(),zoom=self.zoom_3d or 1)
        for axis in (ax.xaxis,ax.yaxis,ax.zaxis):
            axis.pane.fill=False; axis.set_major_locator(MaxNLocator(3))
        ax.set_xlabel('Local X (mm)',fontsize=9,labelpad=0)
        ax.set_ylabel('Local Y (mm)',fontsize=9,labelpad=0)
        ax.set_zlabel('Local Z (mm)',fontsize=9,labelpad=0); ax.tick_params(labelsize=8)
        # Each independent canvas is the clip boundary, not another plot's space.
        clip=Rectangle((0,0),1,1,transform=self.figure3.transFigure)
        for artist in ax.get_children():
            if isinstance(artist,Line2D) or hasattr(artist,'_offsets3d'):
                artist.set_clip_box(self.figure3.bbox); artist.set_clip_path(clip)
        self.canvas3.draw()
        if self.zoom_3d is None: self.fit3()
        else: self.selection_overlay()

    def bounds3(self):
        xy=np.array([proj3d.proj_transform(*p,self.axes.get_proj())[:2] for p in self.corners])
        pixels=self.axes.transData.transform(xy)
        return Bbox.from_extents(*pixels.min(axis=0),*pixels.max(axis=0))

    def fit3(self):
        if not self.ready or self.axes is None: return
        self.axes.set_box_aspect(self.ranges.copy(),zoom=1); self.canvas3.draw()
        box=self.bounds3(); fw,fh=self.figure3.bbox.width,self.figure3.bbox.height
        dpr=self.canvas3.devicePixelRatioF()
        self.zoom_3d=.94*min((fw-110*dpr)/box.width,(fh-115*dpr)/box.height)
        for _ in range(30):
            self.axes.set_box_aspect(self.ranges.copy(),zoom=self.zoom_3d)
            self.selection_overlay()
            if self.fit_content_inside(): break
            self.zoom_3d*=.94
        assert self.fit_content_inside(), 'Default Fit clips geometry/axis/selected annotation'

    def content_bounds3(self):
        renderer=self.canvas3.get_renderer()
        artists=list(self.axes.texts)
        for axis,limits in zip((self.axes.xaxis,self.axes.yaxis,self.axes.zaxis),
                               (self.axes.get_xlim(),self.axes.get_ylim(),self.axes.get_zlim())):
            artists.append(axis.label)
            artists.extend(tick.label1 for tick in axis.majorTicks
                           if min(limits)<=tick.get_loc()<=max(limits))
        return Bbox.union([self.bounds3()]+[artist.get_window_extent(renderer) for artist in artists
                                          if artist.get_visible() and artist.get_text()])

    def fit_content_inside(self):
        bounds=self.content_bounds3(); fw,fh=self.figure3.bbox.width,self.figure3.bbox.height
        margin=4*self.canvas3.devicePixelRatioF()
        return bounds.x0>=margin and bounds.y0>=margin and bounds.x1<=fw-margin and bounds.y1<=fh-margin

    def selection_overlay(self):
        if not self.ready or self.axes is None: return
        if self.selection_ring is not None:
            self.selection_ring.remove()
        for artist in list(self.axes.texts): artist.remove()
        marker=self.valid_preview['markers'][self.selected_row]
        x,y,_=proj3d.proj_transform(*marker['xyz_mm'],self.axes.get_proj())
        ring=Line2D([x],[y],marker='o',markersize=17,markerfacecolor='none',
                    markeredgecolor='#111111',markeredgewidth=2,linestyle='none',
                    transform=self.axes.transData,zorder=100)
        self.axes.add_artist(ring)
        self.selection_ring=ring
        self.axes.annotate(marker['id'],(x,y),xytext=(15,15),textcoords='offset points',
            fontsize=12,fontweight='bold',bbox=dict(boxstyle='round,pad=.2',fc='white',ec='#444444'),
            arrowprops=dict(arrowstyle='-',color='#444444'),zorder=101)
        self.canvas3.draw()

    def wheel3(self,event):
        self.zoom_3d=max(.15,min(8,self.zoom_3d*(1.12 if event.step>0 else 1/1.12)))
        self.axes.set_box_aspect(self.ranges.copy(),zoom=self.zoom_3d); self.selection_overlay()

    def restore_view(self):
        self.axes.view_init(20,30,0,vertical_axis='y'); self.fit3()

    def fit2(self):
        if self.face_axes is not None:
            self.face_axes=None
        self.face_views.pop(self.current_face,None); self.draw()

    def hit_rows(self,x,y,kind):
        if kind=='3d':
            xy=np.asarray([proj3d.proj_transform(*p,self.axes.get_proj())[:2] for p in self.xyz])
            pixels=self.axes.transData.transform(xy); indices=list(range(len(self.xyz)))
        else:
            pixels=self.face_axes.transData.transform(self.face_points)
            indices=[next(i for i,m in enumerate(self.valid_preview['markers']) if m['id']==f['id']) for f in self.face_markers]
        return [row for row,p in zip(indices,pixels) if np.linalg.norm(p-[x,y])<=12*self.canvas3.devicePixelRatioF()]

    def pick(self,event,kind):
        if event.button!=1 or event.x is None or event.y is None: return
        if kind=='2d' and self.nav.mode: return
        rows=self.hit_rows(event.x,event.y,kind)
        if kind=='2d' and not rows:
            renderer=self.canvas2.get_renderer()
            for label in self.labels:
                if label.get_visible() and label.get_bbox_patch().get_window_extent(renderer).contains(event.x,event.y):
                    rows=[next(i for i,m in enumerate(self.valid_preview['markers']) if m['id']==label.get_text())]
        self.show_candidates(rows,event.x,event.y,self.canvas3 if kind=='3d' else self.canvas2)

    def show_candidates(self,rows,x,y,canvas):
        self.candidates.hide(); self.candidate_indices=rows
        if len(rows)==1:
            self.table.selectRow(rows[0]); return
        if not rows: return
        while self.candidate_layout.count():
            item=self.candidate_layout.takeAt(0); item.widget().deleteLater()
        self.candidate_layout.addWidget(QLabel('Select marker'))
        for row in rows:
            marker=self.valid_preview['markers'][row]
            button=QPushButton(marker['id']+'  '+marker['face'].title())
            button.clicked.connect(lambda _checked=False,r=row:(self.candidates.hide(),self.table.selectRow(r)))
            self.candidate_layout.addWidget(button)
        self.candidates.adjustSize()
        dpr=canvas.devicePixelRatioF()
        point=canvas.mapTo(self.preview_panel,QPoint(int(x/dpr),canvas.height()-int(y/dpr)))
        self.candidates.move(min(point.x()+10,self.preview_panel.width()-self.candidates.width()),
                             min(point.y()+10,self.preview_panel.height()-self.candidates.height()))
        self.candidates.show(); self.candidates.raise_()


def settled(window,app,size):
    window.show(); app.processEvents(); window.resize(*size); app.processEvents()
    window.plot_splitter.setSizes([550,450]); app.processEvents()
    window.zoom_3d=None; window.draw(); app.processEvents()


def capture_reviewed(window,out,name,size):
    window.show(); QApplication.processEvents(); window.resize(*size); QApplication.processEvents()
    assert [window.width(),window.height()]==list(size)
    pixmap=window.grab(); assert pixmap.save(str(out/name))
    visible=[]; scrollable=[]
    for button in window.findChildren(QPushButton):
        if not button.isVisible(): continue
        corners=[button.mapTo(window,p) for p in (button.rect().topLeft(),button.rect().bottomRight())]
        if all(window.rect().contains(p) for p in corners): visible.append(button.text())
        else:
            assert window.plot_scroll is not None and window.plot_splitter.isAncestorOf(button),button.text()
            scrollable.append(button.text())
    for button in (window.preview_button,window.reset_button,window.save_button,window.apply_button,window.cancel_button):
        assert button.text() in visible
    if window.plot_scroll is not None and window.tabs.currentWidget()==window.preview_panel:
        for button in (window.pan_button,window.zoom_button,window.fit2_button):
            assert button.text() in visible
        assert window.rect().contains(window.face_title.mapTo(window,window.face_title.rect().bottomRight()))
        if window.plot_scroll.verticalScrollBar().value()==window.plot_scroll.verticalScrollBar().maximum():
            viewport=window.plot_scroll.viewport()
            assert viewport.rect().contains(window.canvas2.mapTo(viewport,window.canvas2.rect().topLeft()))
            assert viewport.rect().contains(window.canvas2.mapTo(viewport,window.canvas2.rect().bottomRight()))
    return dict(screenshot=name,logical_size=list(size),pixel_size=[pixmap.width(),pixmap.height()],
        dpr=window.devicePixelRatioF(),visible_buttons=visible,scrolled_plot_buttons=scrollable,
        evidence_kind='Qt-widget-render-preapproval',fresh=True)


def check_interaction(app):
    window=ReviewedPrototype('18',(1280,960)); settled(window,app,(1280,960))
    before=copy.deepcopy(window.applied)
    window.table.selectRow(17); assert window.selected_id=='M2' and window.current_face=='BOTTOM'
    assert '(38, -60, -18) mm' in window.selected_readout.text() and 'Normal: (0, -1, 0)' in window.selected_readout.text()
    assert not window.copy_button.isVisible()
    QTest.mouseClick(window.pan_button,Qt.LeftButton)
    assert window.pan_button.isChecked() and not window.zoom_button.isChecked()
    QTest.mouseClick(window.zoom_button,Qt.LeftButton)
    assert window.zoom_button.isChecked() and not window.pan_button.isChecked()
    QTest.mouseClick(window.zoom_button,Qt.LeftButton)
    assert not window.zoom_button.isChecked() and not window.pan_button.isChecked()
    window.face_axes.set_xlim(-9,9); window.face_axes.set_ylim(-7,7)
    window.view_combo.setCurrentText('Front')
    assert window.face_axes.get_xlim()[1]>9
    assert window.selected_id=='M2' and 'Normal: (0, -1, 0)' in window.selected_readout.text()
    window.view_combo.setCurrentText('Bottom')
    assert window.face_axes.get_xlim()==(-9,9) and window.face_axes.get_ylim()==(-7,7)
    window.axes.view_init(25,40,0,vertical_axis='y'); window.zoom_3d*=1.1
    window.table.item(17,0).setText('M9')
    assert window.valid_preview['markers'][17]['id']=='M2'
    QTest.mouseClick(window.preview_button,Qt.LeftButton)
    assert window.selected_id=='M9' and window.applied==before
    assert (window.axes.elev,window.axes.azim)==(25,40)
    window.table.item(0,2).setText('22'); QTest.mouseClick(window.preview_button,Qt.LeftButton)
    assert window.valid_preview['markers'][0]['xyz_mm']==[22.,12.,40.] and window.applied==before
    QTest.mouseClick(window.reset_button,Qt.LeftButton)
    assert window.valid_preview['markers'][0]['xyz_mm']==[21,12,40]
    row=next(i for i,m in enumerate(window.valid_preview['markers']) if m['id']=='B2')
    window.table.item(row,3).setText('bad')
    assert window.status.text()=='B2: Y must be a finite number.'
    assert window.table.item(row,3).background().color()==QColor('#ffe0e0')
    assert window.table.item(0,2).background().style()==Qt.NoBrush
    assert not window.preview_button.isEnabled() and not window.save_button.isEnabled() and not window.apply_button.isEnabled()
    window.table.item(row,3).setText('23')
    assert window.table.item(row,3).background().style()==Qt.NoBrush and window.preview_button.isEnabled()
    window.table.item(0,2).setText('bad'); assert not window.apply_button.isEnabled()
    window.close()
    return dict(status='pass',kind='prototype-QTest-only',
        oracle='M2=[38,-60,-18]/BOTTOM normal=[0,-1,0]; rename preserves row/camera; F1 21->22 Preview retains applied; Reset restores21; B2/Y bad marks only B2/Y, repair clears; Pan/Zoom exclusive; redundant copy hidden; invalid blocks Preview/Save/Apply')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'reviewed')
    args=parser.parse_args(); app=QApplication.instance() or QApplication([])
    args.output.mkdir(parents=True,exist_ok=True); entries=[]
    for example in ('18','32'):
        assert validate_profile(load_profile(example=example))==EXPECTED_HASHES[example]
        for size in ((1920,1080),(1280,960),(820,600)):
            window=ReviewedPrototype(example,size); settled(window,app,size)
            for position in (('both',) if window.plot_scroll is None else ('top','bottom')):
                if window.plot_scroll:
                    bar=window.plot_scroll.verticalScrollBar(); bar.setValue(bar.maximum() if position=='bottom' else 0); app.processEvents()
                entry=capture_reviewed(window,args.output,f'reviewed-{example}-{size[0]}x{size[1]}-{position}.png',size)
                entry.update(example=example,scroll_position=position,selected=window.selected_id,
                    projected_box_pixels=list(window.bounds3().size),camera=[window.axes.elev,window.axes.azim],
                    canvas3_logical=[window.canvas3.width(),window.canvas3.height()],
                    canvas2_logical=[window.canvas2.width(),window.canvas2.height()],
                    table_width=window.table.width(),row_height=window.table.rowHeight(0))
                entries.append(entry)
            if size in ((1280,960),(820,600)):
                window.tabs.setCurrentWidget(window.rules_panel); app.processEvents()
                entries.append(capture_reviewed(window,args.output,f'reviewed-{example}-{size[0]}x{size[1]}-rules.png',size))
                if size==(820,600):
                    window.tabs.setCurrentWidget(window.table); app.processEvents()
                    entries.append(capture_reviewed(window,args.output,f'reviewed-{example}-820x600-markers.png',size))
                window.tabs.setCurrentWidget(window.preview_panel); app.processEvents()
            if example=='32' and size==(1920,1080):
                ids=[m['id'] for m in window.valid_preview['markers']]
                pair=[ids.index('F3'),ids.index('B2')]
                xy=np.array([proj3d.proj_transform(*window.xyz[i],window.axes.get_proj())[:2] for i in pair])
                midpoint=window.axes.transData.transform(xy).mean(axis=0)
                rows=window.hit_rows(*midpoint,'3d')
                assert set(pair).issubset(rows) and len(rows)>=2
                window.show_candidates(rows,*midpoint,window.canvas3); app.processEvents()
                assert window.candidates.isVisible()
                entries.append(capture_reviewed(window,args.output,'reviewed-overlap-1920x1080.png',size))
                button=next(b for b in window.candidates.findChildren(QPushButton) if b.text()=='F3  Front')
                QTest.mouseClick(button,Qt.LeftButton)
                assert window.selected_id=='F3' and window.current_face=='FRONT' and not window.candidates.isVisible()
                window.candidates.hide()
                window.table.selectRow(31); app.processEvents()
                assert window.selected_id=='T3' and window.current_face=='TOP'
                entries.append(capture_reviewed(window,args.output,'reviewed-last-row-1920x1080.png',size))
                window.view_combo.setCurrentText('Bottom')
                assert window.hit_rows(0,0,'2d')==[]
            assert window.valid_preview['markers']==load_profile(example=example)['markers']
            window.close()
    for state in ('invalid','legacy','incompatible'):
        window=ReviewedPrototype('18',(1920,1080),state); settled(window,app,(1920,1080))
        entries.append(capture_reviewed(window,args.output,f'reviewed-{state}-1920x1080.png',(1920,1080))); window.close()
    window=ReviewedPrototype('18',(1920,1080)); settled(window,app,(1920,1080))
    row=next(i for i,m in enumerate(window.valid_preview['markers']) if m['id']=='B2')
    window.table.selectRow(row); window.table.item(row,3).setText('bad'); app.processEvents()
    entries.append(capture_reviewed(window,args.output,'reviewed-invalid-B2-1920x1080.png',(1920,1080))); window.close()
    screen=app.primaryScreen(); script=Path(__file__)
    report=dict(schema_version=1,plan_spec=PLAN_SPEC,object_type='ProfileReviewedMockupEvidence',
        utc=datetime.now(timezone.utc).isoformat(),run_id='reviewed-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),command=sys.argv,
        source_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
        environment=dict(platform=platform.platform(),python=platform.python_version(),pyside=PySide6.__version__,
            qt_platform=app.platformName(),dpr=screen.devicePixelRatio(),windows_scale_percent=100,
            qt_process_scale_percent=screen.devicePixelRatio()*100),
        input=dict(profile_hashes=EXPECTED_HASHES,kind='public-synthetic-static-geometry',seed=None,
            seed_reason='Static geometry',tolerance=None,tolerance_reason='Exact geometry invariance; not physical accuracy'),
        states=entries,interaction=check_interaction(app),approval_status='pending',production_changed=False,
        native_status='not-executed-existing-capture-activation-failure',experimental_status='unavailable',
        limitations=['Save/export/worker production contracts are not implemented in this prototype.',
            'Fit/pick and snapshots demonstrate interaction; GUI acceptance requires user review and native follow-up.',
            'Compatibility/error text is a UI fixture, not completed production compatibility verification.'],
        prior_attempts=[dict(status='failed',boundary='prototype-axis-fit-correction',
            diagnostic='Reading get_ticklabels after draw reset 3D projected tick positions; extent assertion failed.',
            correction='Read already-rendered majorTicks label1 extents and fit within DPR-aware canvas margins.'),
            dict(status='failed',boundary='prototype-invalid-cell-correction',
            diagnostic='Background updates emitted itemChanged recursively; generation stopped.',
            correction='Block table signals while clearing/setting validation backgrounds; bounded QTest passed.'),
            dict(status='failed',boundary='prototype-scroll-accessibility-check',
            diagnostic='Inherited capture treated scrolled-away per-plot Fit controls as fixed actions.',
            correction='Record scrolled plot controls separately; still require all fixed actions in view.')])
    (args.output/'evidence.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(states=len(entries),dpr=screen.devicePixelRatio(),interaction=report['interaction'])))


if __name__=='__main__':
    main()
