from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import hashlib
import numpy as np
import pytest
from plyfile import PlyData
from inspection_replay import Host
from test_live_inspection import inspected

spec=spec_from_file_location('visual_fixture_generator',Path(__file__).resolve().parents[1]/'scripts/generate_visual_inspection_fixtures.py')
generator=module_from_spec(spec);spec.loader.exec_module(generator)

@pytest.fixture(scope='module')
def files(tmp_path_factory):
    root=tmp_path_factory.mktemp('visual-exact-files');manifest=generator.generate(root)
    assert manifest==generator.generate(root)
    return root,manifest

@pytest.mark.parametrize('index',range(9))
def test_exact_hashed_ply_bytes_through_actual_fitting_and_inspection(files,index):
    root,manifest=files;entry=manifest['fixtures'][index];path=root/entry['file']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256']
    data=PlyData.read(path)['vertex'];points=np.column_stack([data[k] for k in ('x','y','z')])
    assert len(points)==entry['point_count']
    h,s,p,_=inspected(Host(points,entry['global_shift'],entry['global_scale']),kinds=entry['kinds'],sample_limit=512)
    assert p['candidates'] and p['camera_recovery']['status']=='restored' and h.query_count==2
    assert p['query']['region']['min']==points.min(axis=0).tolist()
    if entry['name']=='parallel_planes':assert len(p['candidates'])==2


def test_generator_never_overwrites_unexpected_work(tmp_path):
    (tmp_path/'plane.ply').write_text('unexpected prior work')
    with pytest.raises(FileExistsError):generator.generate(tmp_path)
    assert (tmp_path/'plane.ply').read_text()=='unexpected prior work'
