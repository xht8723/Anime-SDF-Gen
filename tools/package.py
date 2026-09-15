"""Build the extension archive without bundling the model or test outputs."""
from pathlib import Path
import hashlib
import json
import sys
import tomllib
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'anime_sdf_gen'
manifest=tomllib.loads((PACKAGE/'blender_manifest.toml').read_text(encoding='utf-8'))
OUT=ROOT/'dist';OUT.mkdir(exist_ok=True)
target=OUT/f"anime_sdf_gen-{manifest['version']}.zip"
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for path in sorted(PACKAGE.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc':continue
        rel=path.relative_to(PACKAGE).as_posix()
        info=zipfile.ZipInfo(rel,date_time=(2026,9,14,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        info.external_attr=0o644<<16
        archive.writestr(info,path.read_bytes())
    for name in ('usage.md','output-format.md'):
        path=ROOT/'docs'/name
        info=zipfile.ZipInfo('docs/'+name,date_time=(2026,9,14,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        archive.writestr(info,path.read_bytes())
digest=hashlib.sha256(target.read_bytes()).hexdigest()
(OUT/(target.name+'.sha256')).write_text(digest+'  '+target.name+'\n',encoding='ascii')
print(json.dumps({'archive':str(target),'bytes':target.stat().st_size,'sha256':digest}))

# Companion development bundle: no fixture, generated images, or installed cache.
source_target=OUT/f"anime_sdf_gen-{manifest['version']}-source.zip"
files=[ROOT/'README.md',ROOT/'AGENTS.md']
for folder in ('anime_sdf_gen','tests','tools','docs'):
    files.extend(path for path in (ROOT/folder).rglob('*')
                 if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc'
                 and path.name not in ('blender_character_toon.py','setup_character_toon.py')
                 and (not path.name.startswith('plan_') or path.name in ('plan_anime-sdf-gen-full-sweeps.md','plan_anime-sdf-gen-curve-controls.md','plan_anime-sdf-gen-restore-preview.md')))
with zipfile.ZipFile(source_target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for path in sorted(files):
        info=zipfile.ZipInfo(path.relative_to(ROOT).as_posix(),date_time=(2026,9,14,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        info.external_attr=0o644<<16
        archive.writestr(info,path.read_bytes())
source_digest=hashlib.sha256(source_target.read_bytes()).hexdigest()
(OUT/(source_target.name+'.sha256')).write_text(source_digest+'  '+source_target.name+'\n',encoding='ascii')
print(json.dumps({'source_archive':str(source_target),'bytes':source_target.stat().st_size,'sha256':source_digest}))
