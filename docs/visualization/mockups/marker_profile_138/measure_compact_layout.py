"""Measure same-fixture layout changes; this is display evidence, not physics."""
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from PySide6.QtWidgets import QApplication
from mpl_toolkits.mplot3d import proj3d
from generate_stacked_mockups import StackedPrototype
from generate_compact_mockups import CompactPrototype
from generate_mockups import PLAN_SPEC

app=QApplication.instance() or QApplication([])
records=[]
for kind,constructor in [('prior',StackedPrototype),('compact',CompactPrototype)]:
    window=constructor('32',(1920,1080))
    window.show(); app.processEvents(); window.resize(1920,1080); app.processEvents()
    window.draw(); app.processEvents()
    # Literal public-32 box dimensions define independent geometric bounds.
    corners=np.asarray(list(product((-1,1),repeat=3)))*np.array([150.,90.,45.])
    projection=np.array([proj3d.proj_transform(*p,window.axes.get_proj())[:2] for p in corners])
    pixels=window.axes.transData.transform(projection)
    ranges=np.array([np.ptp(window.axes.get_xlim()),np.ptp(window.axes.get_ylim()),np.ptp(window.axes.get_zlim())])
    scales=window.axes._roll_to_vertical(window.axes.get_box_aspect())/ranges
    ratios=scales/scales[0]
    assert np.allclose(ratios,[1,1,1],rtol=1e-12,atol=0)
    records.append(dict(layout=kind,projected_box_pixels=np.ptp(pixels,axis=0).tolist(),
        table_width_logical=window.table.width(),display_xyz_scale_ratio=ratios.tolist()))
    window.close()
report=dict(schema_version=1,plan_spec=PLAN_SPEC,object_type='ProfileLayoutComparisonEvidence',
    utc=datetime.now(timezone.utc).isoformat(),fresh=True,command=sys.argv,
    commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    dpr=app.primaryScreen().devicePixelRatio(),input=dict(example='32',box_dims_mm=[300,180,90],
        geometry_kind='public-virtual',seed=None,seed_reason='Static geometry'),
    records=records,independent_expected_scale_ratio=[1,1,1],
    relative_tolerance=1e-12,tolerance_units='dimensionless',
    tolerance_reason='Float64 aspect normalization arithmetic only; not pose accuracy',
    result='pass',native_status='not-executed')
path=Path(__file__).parent/'compact'/'layout-comparison.json'
path.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
print(json.dumps(records))
