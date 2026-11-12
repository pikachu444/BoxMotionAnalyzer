"""Rebuild the public conceptual Guide figures with Matplotlib.

Run: python scripts/generate_metric_guide_diagrams.py
"""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, FancyBboxPatch
import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'src/analysis/ui/assets'


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / ('guide_' + name + '.png'), dpi=140, facecolor='white')
    plt.close(fig)


def posture():
    fig, (ax, text) = plt.subplots(1, 2, figsize=(11, 5.6), gridspec_kw={'width_ratios':[1,1.15]})
    fig.subplots_adjust(left=.05,right=.98,bottom=.10,top=.91,wspace=.20)
    fig.suptitle('Posture geometry: conceptual projection, not a trial trajectory',fontsize=13,weight='bold')
    local=np.array([[-100,-60],[100,-60],[100,60],[-100,60]],float)
    angle=np.pi/6
    matrix=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    points=local@matrix.T+[0,200]
    ring=np.vstack([points,points[0]])
    ax.plot(ring[:,0],ring[:,1],color='#555555')
    ax.plot(points[:2,0],points[:2,1],color='#175d91',linewidth=4)
    for point,label,offset in zip(points,['C1,C5','C2,C6','C3,C7','C4,C8'],[(-35,-24),(8,-16),(8,14),(-45,14)]):
        ax.annotate(label,point,xytext=offset,textcoords='offset points',fontsize=10)
    ax.axhline(0,color='black',linewidth=1)
    ax.text(-190,8,'Floor',fontsize=9)
    ax.annotate('World +Y / up',xy=(-185,150),xytext=(-185,55),arrowprops=dict(arrowstyle='->'),ha='center',fontsize=9)
    center=points[:2].mean(axis=0)
    normal=matrix@np.array([0.,-1.])
    ax.annotate('',xy=center+70*normal,xytext=center,arrowprops=dict(arrowstyle='->',color='#175d91'))
    ax.annotate('Face normal',xy=center+70*normal,xytext=(140,70),arrowprops=dict(arrowstyle='-'),ha='center',fontsize=9)
    ax.annotate('',xy=center+[0,-70],xytext=center,arrowprops=dict(arrowstyle='->',linestyle='dashed'))
    ax.annotate('World down',xy=center+[0,-70],xytext=(-30,40),arrowprops=dict(arrowstyle='-'),ha='center',fontsize=9)
    theta=np.linspace(0,angle,30)
    ax.plot(center[0]+40*np.sin(theta),center[1]-40*np.cos(theta),color='black')
    ax.text(center[0]+25,center[1]-30,'Beta',fontsize=9)
    # Axis callouts live outside the box projection to avoid corner-label collisions.
    origin=np.array([-130.,340.]);direction=matrix@np.array([45.,0.])
    ax.annotate('',xy=origin+direction,xytext=origin-direction,arrowprops=dict(arrowstyle='<->',color='#555555'))
    ax.text(*(origin+direction+[4,0]),'+X long',fontsize=9)
    ax.text(*(origin-direction+[-12,-16]),'-X',fontsize=9)
    ax.set(xlim=(-220,220),ylim=(-20,395),xlabel='World X (mm)',ylabel='World Y (mm)')
    ax.set_aspect('equal',adjustable='box')
    ax.text(-205,-13,'View from +Z: +Z toward viewer; -Z away',fontsize=8)
    text.axis('off')
    lines=[
        'Reference example: BOTTOM (C1,C2,C5,C6).',
        'Public policy selects the most down-facing of SIX faces.',
        'Beta compares outward face normal with world down.',
        'It is not an approved edge/corner target error.',
        'Long local X: negative C1,C5; positive C2,C6.',
        'Short local Z: negative C1,C2; positive C5,C6.',
        'Signed theta = asin((mean h+ - mean h-) / length).',
        'Here: long +30 deg, short 0 deg, Beta 30 deg.',
        'Face DeltaH = max h - min h = 100 mm.',
        'ALL-eight Cmin: exact tied minima C1,C5.',
        'Second-lowest gap = 0 mm; no unique-corner agreement.',
        'Fixed face stays fixed during rebound/toppling.',
    ]
    for i,line in enumerate(lines):
        text.text(0,.97-i*.079,line,va='top',fontsize=10)
    save(fig,'posture')


def impact():
    fig,ax=plt.subplots(figsize=(10,5),layout='constrained')
    ax.set(xlim=(-.5,7.5),ylim=(-2.7,3.7))
    ax.axis('off')
    ax.text(-.4,3.4,'Recorded times and methods — conceptual examples',fontsize=13,weight='bold')
    ax.annotate('',xy=(7.3,1.4),xytext=(-.3,1.4),arrowprops=dict(arrowstyle='->',color='black'))
    positions=[0,1,2,3,4,5,6.5]
    labels=['Approach','Actual t1-\nprior sample','Detector onset\ntransient set','Empty interval','First accepted\n>=2 same sets','Later contact','Rebound /\nstable tail']
    for x,label in zip(positions,labels):
        ax.plot(x,1.4,'o',color='black')
        y=2.1 if int(x)%2==0 else .2
        ax.annotate(label,xy=(x,1.4),xytext=(x,y),ha='center',fontsize=10,
                    arrowprops=dict(arrowstyle='-',color='gray'))
    notes=[
        'Detector onset can precede the first accepted persistent contact.',
        'First-row onset: no actual prior sample, so t1- is unavailable.',
        'Saved geometric-centre snapshot: vertical / horizontal mm/s; angular norm rad/s.',
        'Compare: one-sided pose endpoint fits m/s and rad/s; registered COM fit height already mm.',
        'Absolute seconds are preserved. Playback may show time relative to t1-.',
        'No force, release-height or shared-estimator claim is implied by this diagram.',
    ]
    for i,line in enumerate(notes):
        ax.text(-.4,-.65-i*.34,line,fontsize=10)
    save(fig,'impact')


def contact():
    fig,ax=plt.subplots(figsize=(10,5),layout='constrained')
    ax.set(xlim=(0,10),ylim=(0,6))
    ax.axis('off')
    ax.text(.1,5.65,'Separate evidence, intent, and stable-tail diagnostics',weight='bold',fontsize=13)
    def box(x,y,text,width=2.7):
        ax.add_patch(FancyBboxPatch((x,y),width,.75,boxstyle='round,pad=.08',facecolor='#f2f5f7',edgecolor='#333333'))
        ax.text(x+width/2,y+.375,text,ha='center',va='center',fontsize=10)
    def arrow(a,b):
        ax.annotate('',xy=b,xytext=a,arrowprops=dict(arrowstyle='->',color='#333333'))
    box(.2,4.3,'Geometry / time checks')
    box(3.6,4.3,'Contact evidence')
    box(7,4.3,'Accepted events / score')
    arrow((2.95,4.67),(3.5,4.67));arrow((6.35,4.67),(6.9,4.67))
    box(.2,2.75,'Invalid / missing evidence')
    box(3.6,2.75,'Unavailable / Unknown')
    arrow((1.55,4.2),(1.55,3.6));arrow((2.95,3.12),(3.5,3.12))
    box(.2,1.2,'Independent approved intent')
    box(3.6,1.2,'Existing contact owner')
    box(7,1.2,'Match / Mismatch / Unknown')
    arrow((2.95,1.57),(3.5,1.57));arrow((6.35,1.57),(6.9,1.57))
    arrow((8.35,4.2),(8.35,2.3));arrow((8.35,2.3),(6.35,1.9))
    ax.text(.1,.55,'FinalFace: separate stable-height tail + equal-weight rotation mean over all six faces.',fontsize=10)
    ax.text(.1,.15,'Score is not probability. Unknown is not 0/Match. Mismatch is not an automatic failure.',fontsize=10)
    save(fig,'contact')


if __name__ == '__main__':
    posture()
    impact()
    contact()
