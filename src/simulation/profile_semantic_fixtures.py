"""Independently declared counterexample, without consumer-derived expectations."""
from src.utils.marker_profile_identity import PLAN_SPEC


def ambiguous_face_profile():
    # Both identity and a +90 degree Y turn satisfy every assigned face and
    # box bound. Full local rank cannot prove this globally unique.
    points=[('F1','FRONT',[50,-20,50]),('F2','FRONT',[50,20,50]),
        ('B1','BACK',[-50,-15,-50]),('B2','BACK',[-50,15,-50]),
        ('R1','RIGHT',[50,-30,-50]),('R2','RIGHT',[50,30,-50]),
        ('L1','LEFT',[-50,-25,50]),('L2','LEFT',[-50,25,50]),
        ('T1','TOP',[-10,50,-20]),('T2','TOP',[20,50,10]),
        ('M1','BOTTOM',[-20,-50,10]),('M2','BOTTOM',[10,-50,-20])]
    return dict(schema_version=1,plan_spec=PLAN_SPEC,profile_id='public-face-constraint-ambiguity',
        profile_version='1',units='mm',origin='box-geometric-center',dimension_policy='absolute-mm',
        box_dims_mm=[100.,100.,100.],publication='public-analytical-counterexample-not-experimental-standard',
        source='Literal geometry: I and Ry(+90deg) satisfy assigned-face constraints',license='same as repository source code',
        markers=[dict(id=label,face=face,xyz_mm=xyz) for label,face,xyz in points])


def rank_deficient_face_profile():
    points=[('F1','FRONT',[0,0,40]),('B1','BACK',[0,0,-40]),
        ('R1','RIGHT',[100,0,0]),('L1','LEFT',[-100,0,0]),
        ('T1','TOP',[0,60,0]),('M1','BOTTOM',[0,-60,0])]
    return dict(schema_version=1,plan_spec=PLAN_SPEC,profile_id='public-face-centre-rank-deficiency',
        profile_version='1',units='mm',origin='box-geometric-center',dimension_policy='absolute-mm',
        box_dims_mm=[200.,120.,80.],publication='public-analytical-counterexample-not-experimental-standard',
        source='Literal six face centres: declared assigned-face rank3, noise cannot certify support',license='same as repository source code',
        markers=[dict(id=label,face=face,xyz_mm=xyz) for label,face,xyz in points])
