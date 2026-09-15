"""Fixture-specific selection stays in tests, outside the generic source API."""
import bpy


def fixture_face(source, front_only=True):
    obj=bpy.data.objects['body']
    slots={i for i,m in enumerate(obj.data.materials) if m and m.name=='head'}
    ids=[p.index for p in obj.data.polygons if p.material_index in slots]
    return source.extract(obj,'UVMap',region='SELECTED',selected=ids,front_only=front_only)
