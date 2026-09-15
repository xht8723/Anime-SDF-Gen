import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from anime_sdf_gen.core import model, curves, distance, compile, geometry, files


def project(keyframes=5, mirror=True):
    return model.new_project({'object': 'test', 'fingerprint': 'fixture'},
                             {'center': [0,0,0], 'right': [1,0,0], 'up': [0,1,0],
                              'forward': [0,0,1], 'width': 1, 'height': 1}, keyframes, mirror)


def ellipse(name, cx, cy, rx, ry, operation="ADD"):
    k = 0.5522847498307936
    pts = [model.point(cx + rx, cy, "FREE", [0, -k*ry], [0, k*ry]),
           model.point(cx, cy + ry, "FREE", [k*rx, 0], [-k*rx, 0]),
           model.point(cx - rx, cy, "FREE", [0, k*ry], [0, -k*ry]),
           model.point(cx, cy - ry, "FREE", [-k*rx, 0], [k*rx, 0])]
    return {"id": model.uid(), "name": name, "closed": True,
            "operation": operation, "enabled": True, "points": pts}


class DistanceTests(unittest.TestCase):
    def test_exact_against_brute_force(self):
        rng = np.random.default_rng(3001)
        for shape in ((3,7), (13,9), (24,24)):
            mask = rng.random(shape) > .7
            yy, xx = np.indices(shape)
            seeds = np.argwhere(mask)
            expected = np.min((yy[...,None]-seeds[:,0])**2+(xx[...,None]-seeds[:,1])**2, axis=-1)
            np.testing.assert_array_equal(distance.run(distance.squared_steps(mask)), expected)

    def test_empty_full_and_sign(self):
        for fill in (False, True):
            d = distance.signed(np.full((17,19), fill))
            self.assertTrue(np.isfinite(d).all())
            self.assertTrue(np.all(d > 0) if fill else np.all(d < 0))
        mask = np.zeros((16,16), bool); mask[4:12,4:12] = True; mask[7:9,7:9] = False
        d = distance.signed(mask)
        np.testing.assert_array_equal(d > 0, mask)


class CurveTests(unittest.TestCase):
    def test_smooth_triangle(self):
        c=model.triangle()
        self.assertEqual(len(c['points']),3)
        self.assertTrue(c['closed'] and c['enabled'])
        self.assertEqual(c['operation'],'ADD')
        self.assertTrue(all(pt['mode']=='AUTO' for pt in c['points']))
        self.assertFalse(curves.self_intersects(curves.polygon(c)))
        smooth=curves.fill_polygon(curves.polygon(c),256)
        self.assertGreater(smooth.sum(),0)
        for i,p in enumerate(c['points']):
            left,right=curves.handles(c,i);a=np.asarray(p['co'])-left;b=right-p['co']
            self.assertGreater(np.linalg.norm(a),0)
            self.assertAlmostEqual(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)),1.)
        sharp=copy.deepcopy(c)
        for point in sharp['points']:point['mode']='CORNER'
        self.assertGreater(np.count_nonzero(smooth!=curves.fill_polygon(curves.polygon(sharp),256)),10)

    def test_ellipse_fill_hole_and_order(self):
        p = project()
        p['sweeps'][model.LTR][0]['contours'][0]['enabled'] = False
        p['sweeps'][model.LTR][0]['contours'] += [ellipse('outer', .5,.5,.3,.3), ellipse('hole', .5,.5,.1,.1,'REMOVE')]
        mask = curves.raster_keyframe(p,p['sweeps'][model.LTR][0],model.LTR,128)
        self.assertFalse(mask[64,64]); self.assertTrue(mask[64,80]); self.assertFalse(mask[10,10])
        p['sweeps'][model.LTR][0]['contours'].append(ellipse('refill', .5,.5,.04,.04))
        self.assertTrue(curves.raster_keyframe(p,p['sweeps'][model.LTR][0],model.LTR,128)[64,64])

    def test_lit_triangle_inside_shadow_and_across_boundary(self):
        p=project(9,mirror=False);phase=p['sweeps'][model.LTR][-1];size=256
        uncut=curves.raster_keyframe(p,phase,model.LTR,size)
        for dx in (-.20,-.03):
            shape=model.triangle();shape['operation']='REMOVE'
            model.transform_contour(shape,dx=dx)
            phase['contours']=phase['contours'][:1]+[shape]
            cutout=curves.fill_polygon(curves.polygon(shape,tolerance=model.SPAN/(size*4)),size)
            mask=curves.raster_keyframe(p,phase,model.LTR,size)
            self.assertGreater(np.count_nonzero(uncut&cutout),0)
            self.assertFalse(mask[cutout].any())
            np.testing.assert_array_equal(mask[~cutout],uncut[~cutout])
            mirrored=model.mirror_keyframe(phase)
            right=curves.raster_keyframe(p,mirrored,model.RTL,size)
            np.testing.assert_array_equal(mask[:,::-1],right)
            # Adding a shadow layer after the cutout may intentionally refill it.
            refill=copy.deepcopy(shape);refill['operation']='ADD'
            phase['contours'].append(refill)
            self.assertTrue(curves.raster_keyframe(p,phase,model.LTR,size)[cutout].all())

    def test_self_intersection(self):
        self.assertTrue(curves.self_intersects(np.array([[0,0],[1,1],[0,1],[1,0]],float)))
        self.assertFalse(curves.self_intersects(np.array([[0,0],[1,0],[1,1],[0,1]],float)))

    def test_split_preserves_fill(self):
        c = ellipse('test', .5,.5,.3,.2)
        before = curves.fill_polygon(curves.polygon(c),128)
        curves.insert_point(c,1)
        after = curves.fill_polygon(curves.polygon(c),128)
        np.testing.assert_array_equal(before,after)


class SchemaTests(unittest.TestCase):
    def test_current_schema_only(self):
        p=project(9,False)
        self.assertEqual(model.loads(model.dumps(p)),p)
        for change in ({'format':'different_tool'},{'format_version':1},{'format_version':2},{'format_version':model.FORMAT_VERSION+1}):
            invalid=copy.deepcopy(p);invalid.update(change)
            with self.assertRaisesRegex(ValueError,'Unsupported project format'):
                model.loads(json.dumps(invalid))
        invalid=copy.deepcopy(p);invalid.pop('format')
        with self.assertRaises(ValueError):model.loads(json.dumps(invalid))
        invalid=copy.deepcopy(p);invalid['authoring'].pop('front_only')
        with self.assertRaisesRegex(ValueError,'authoring source settings'):model.loads(json.dumps(invalid))

    def test_surface_anchor_roundtrip_and_refit_retains_patches(self):
        p=project()
        p['authoring'].update(stage='FIT',anchors={'nose':{'world':[1,2,3],'vertices':[5,8,11],'barycentric':[.2,.3,.5]}})
        self.assertEqual(p,model.loads(model.dumps(p)))
        patch_=model.triangle();p['sweeps'][model.LTR][0]['contours'].append(patch_)
        p['landmarks']['nose'][1]=.4
        model.refit(p)
        self.assertEqual(p['sweeps'][model.LTR][0]['contours'][1],patch_)
        self.assertEqual(p['authoring']['stage'],'EDIT')
        bad=copy.deepcopy(p);bad['authoring']['anchors']['nose']['barycentric']=[1,1,1]
        with self.assertRaises(ValueError):model.validate_project(bad)

class UVTests(unittest.TestCase):
    def test_uv_shared_edges_valid_overlap_invalid(self):
        valid = np.array([[[0,0],[1,0],[1,1]],[[0,0],[1,1],[0,1]]],float)
        geometry.validate_uv(valid)
        with self.assertRaisesRegex(ValueError,'Overlapping'):
            geometry.validate_uv(np.concatenate([valid,valid[:1]]))
        with self.assertRaisesRegex(ValueError,'zero-area'):
            geometry.validate_uv(np.zeros((1,3,2)))
        with self.assertRaisesRegex(ValueError,'0–1'):
            geometry.validate_uv(valid+2)

    def test_uv_transfer_padding_and_orientation(self):
        uv = np.array([[[.1,.1],[.9,.1],[.9,.9]],[[.1,.1],[.9,.9],[.1,.9]]])
        projected = np.concatenate([(uv-.1)/.8,np.zeros((2,3,1))],axis=-1)
        depth,facing=distance.run(geometry.projection_steps(projected,64))
        t = np.zeros((64,64,2),np.float32); t[...,0]=.25;t[...,1]=.75
        image=distance.run(geometry.bake_steps(t,uv,projected,depth,facing,64))
        cov=image[...,2].copy()
        np.testing.assert_allclose(image[32,32],[.25,.75,1])
        distance.run(geometry.pad_steps(image,3))
        np.testing.assert_array_equal(cov,image[...,2])
        np.testing.assert_allclose(image[32,4,:2],[.25,.75])

    def test_occluded_surface_coverage_and_scale(self):
        uv=np.array([[[.05,.05],[.45,.05],[.05,.45]],[[.55,.55],[.95,.55],[.55,.95]]])
        front=np.array([[0,0,.2],[1,0,.2],[0,1,.2]])
        projected=np.stack([front,front-[0,0,.3]])
        for scale in (1e-5,1,1e5):geometry.validate_uv(uv,projected*scale)
        depth,facing=distance.run(geometry.projection_steps(projected,64))
        t=np.full((64,64,2),.4,dtype=np.float32)
        image=distance.run(geometry.bake_steps(t,uv,projected,depth,facing,64))
        self.assertEqual(image[10,10,2],1)
        self.assertEqual(image[40,40,2],0)


class FileTests(unittest.TestCase):
    def test_png16_roundtrip_and_atomic_export(self):
        p=project(); p['settings']['resolution']=512
        rng=np.random.default_rng(44)
        image=rng.random((32,32,3)).astype(np.float32)
        image[0,0]=[0,1,1]
        with tempfile.TemporaryDirectory() as tmp:
            texture,sidecar=files.export_bundle(p,image,Path(tmp)/'face')
            codes=files.read_png16(texture)
            np.testing.assert_array_equal(codes,files.quantize(image))
            self.assertGreater(np.unique(codes[...,0]).size,256)
            self.assertEqual(json.loads(Path(sidecar).read_text())['textures'][0]['bits'],16)
            oldtex=Path(texture).read_bytes();oldjson=Path(sidecar).read_bytes()
            real_replace=files.os.replace
            def fail_commit(src,dst):
                if str(src).endswith('.tmp') and str(dst).endswith('.sdfproject.json'):
                    raise OSError('injected commit failure')
                return real_replace(src,dst)
            with patch.object(files.os,'replace',side_effect=fail_commit):
                with self.assertRaises(OSError): files.export_bundle(p,1-image,Path(tmp)/'face')
            self.assertEqual(Path(texture).read_bytes(),oldtex)
            self.assertEqual(Path(sidecar).read_bytes(),oldjson)
            self.assertEqual(len(list(Path(tmp).iterdir())),2)


if __name__ == '__main__':
    unittest.main()
