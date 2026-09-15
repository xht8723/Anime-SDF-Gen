"""Inspect a saved validation file in a separate process, without the add-on."""
from pathlib import Path
import hashlib
import json
import bpy

ROOT=Path(__file__).resolve().parents[1]
KINDS=('objects','meshes','materials','images','scenes','worlds','collections','node_groups','screens','workspaces')
owned=[(kind,block.name) for kind in KINDS for block in getattr(bpy.data,kind)
       if 'anime_sdf_gen_session' in block]
assert not owned,owned
baseline=json.loads((ROOT/'build/validation/v014/blender_integration.json').read_text())
assert {k:len(getattr(bpy.data,k)) for k in KINDS}==baseline['original_counts']
assert all('Anime SDF Gen' not in block.name for kind in KINDS for block in getattr(bpy.data,kind))
assert hashlib.sha256((ROOT/'test_sdf.blend').read_bytes()).hexdigest()==baseline['fixture_sha256']
report={'status':'PASS','file':bpy.data.filepath,'counts':{k:len(getattr(bpy.data,k)) for k in KINDS},
        'owned_ids':owned,'fixture_sha256_unchanged':True}
out=ROOT/'build'/'validation'/'v014'/'saved_file.json'
out.write_text(json.dumps(report,indent=2));print(json.dumps(report))
