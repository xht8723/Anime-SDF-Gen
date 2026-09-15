import copy
import unittest
import numpy as np
from anime_sdf_gen.core import model,curves,compile,distance,files
from tests.test_core import project, ellipse


def triangle(dx=0):
    c=model.triangle();c['operation']='REMOVE'
    model.transform_contour(c,dx=dx)
    return c


def footprint(c,size):
    return curves.fill_polygon(curves.polygon(c,tolerance=model.SPAN/(size*4)),size)


def all_shadow(p):
    for c in [ph['contours'][0] for ph in p['sweeps'][model.LTR]]:
        for pt in c['points']:pt['co'][0]=1.23
    for ph in p['sweeps'][model.RTL]:
        for pt in ph['contours'][0]['points']:pt['co'][0]=-.23


class LitCutoutTests(unittest.TestCase):
    def test_reported_cutout_carries_back_and_encodes_without_conflict(self):
        p=project(9);size=256
        base=[curves.raster_keyframe(p,ph,model.LTR,size) for ph in model.sweep(p,model.LTR)]
        c=triangle(-.14);p['sweeps'][model.LTR][-1]['contours'].append(c);model.synchronize_mirror(p)
        saved=copy.deepcopy(p);hole=footprint(c,size)
        self.assertGreater(np.count_nonzero(base[-2]&hole),0)
        thresholds=compile.compile_project(p,size)
        domain=compile.face_domain(size)
        for i,ph in enumerate(model.sweep(p,model.LTR)):
            expected=base[i]&~hole
            np.testing.assert_array_equal(curves.raster_keyframe(p,ph,model.LTR,size),expected)
            np.testing.assert_array_equal(compile.decode(thresholds[...,0],ph['progress'])[domain],expected[domain])
        self.assertTrue(np.all(thresholds[...,0][hole]==1))
        np.testing.assert_array_equal(thresholds[...,0],thresholds[:,::-1,1])
        self.assertEqual(p,saved,'Carrying cutouts must not write duplicate authoring curves')
        # Quantized RGB export decodes the hole as lit even at the sweep endpoint.
        rgb=np.dstack([thresholds,domain.astype(float)])
        codes=files.quantize(rgb)
        self.assertTrue(np.all(codes[...,0][hole]==65535))
        self.assertFalse(compile.decode(codes[...,0].astype(float)/65535,1)[hole].any())

    def test_moved_hidden_and_deleted_cutout_invalidates_earlier_distance_fields(self):
        p=project(9);size=128;fields={};masks={}
        baseline=compile.compile_project(p,size)
        c=triangle(-.14);p['sweeps'][model.LTR][-1]['contours'].append(c)
        def cached():return distance.run(compile.compile_steps(p,size,field_cache=fields,mask_cache=masks))
        initial=cached();old_hole=footprint(c,size)
        model.transform_contour(c,dx=-.15)
        moved=cached();new_hole=footprint(c,size)
        np.testing.assert_array_equal(moved,compile.compile_project(p,size))
        self.assertGreater(np.max(np.abs(moved-initial)),.1)
        vacated=old_hole&~new_hole
        self.assertTrue(np.any(compile.decode(moved[...,0],1)[vacated]))
        c['enabled']=False
        np.testing.assert_array_equal(cached(),baseline)
        c['enabled']=True;cached();p['sweeps'][model.LTR][-1]['contours'].pop()
        np.testing.assert_array_equal(cached(),baseline)

    def test_first_frames_are_independent_and_carry_is_sweep_local(self):
        p=project(5,mirror=False);size=128;all_shadow(p)
        a,b=triangle(-.22),triangle(.22)
        p['sweeps'][model.LTR][-1]['contours'].append(a)
        p['sweeps'][model.RTL][-1]['contours'].append(b)
        ha,hb=footprint(a,size),footprint(b,size)
        thresholds=compile.compile_project(p,size)
        domain=compile.face_domain(size)
        for channel,direction,hole,other in ((0,model.LTR,ha,hb),(1,model.RTL,hb,ha)):
            for frame in model.sweep(p,direction):
                mask=curves.raster_keyframe(p,frame,direction,size)
                self.assertFalse(mask[hole].any());self.assertTrue(mask[other].all())
                np.testing.assert_array_equal(compile.decode(thresholds[...,channel],frame['progress'])[domain],mask[domain])
        seams=compile.endpoint_seams(thresholds,domain)
        self.assertGreater(seams['Front'],0);self.assertGreater(seams['Back'],0)

    def test_layer_order_only_carries_surviving_light(self):
        p=project(5,mirror=False);size=128;all_shadow(p)
        c=triangle(-.1);refill=ellipse('Refill',.4,.3,.025,.018,'ADD')
        p['sweeps'][model.LTR][-1]['contours'] += [c,refill]
        hole=footprint(c,size);filled=footprint(refill,size)
        earlier=curves.raster_keyframe(p,p['sweeps'][model.LTR][0],model.LTR,size)
        self.assertFalse(earlier[hole&~filled].any())
        self.assertTrue(earlier[filled].all())
        compile.compile_project(p,size)

    def test_moving_and_disappearing_cutouts_remain_monotonic(self):
        p=project(9,mirror=False);size=128;all_shadow(p)
        a,b=triangle(-.20),triangle(.15)
        p['sweeps'][model.LTR][1]['contours'].append(a);p['sweeps'][model.LTR][2]['contours'].append(b)
        ha,hb=footprint(a,size),footprint(b,size)
        phase2=curves.raster_keyframe(p,p['sweeps'][model.LTR][1],model.LTR,size)
        phase3=curves.raster_keyframe(p,p['sweeps'][model.LTR][2],model.LTR,size)
        phase4=curves.raster_keyframe(p,p['sweeps'][model.LTR][3],model.LTR,size)
        self.assertFalse(phase2[ha|hb].any())
        self.assertTrue(phase3[ha].all());self.assertFalse(phase3[hb].any())
        self.assertTrue(phase4[ha|hb].all())
        thresholds=compile.compile_project(p,size)
        last=np.zeros((size,size),bool)
        for t in np.linspace(0,1,61):
            mask=compile.decode(thresholds[...,0],t)
            self.assertFalse((last&~mask).any());last=mask

    def test_invalid_future_curve_cannot_reuse_unvalidated_mask(self):
        p=project(9);c=triangle(-.14);c['points'][1]['co']=c['points'][0]['co'][:]
        p['sweeps'][model.LTR][-1]['contours'].append(c);cache={}
        curves.raster_keyframe(p,p['sweeps'][model.LTR][0],model.LTR,64,False,cache)
        with self.assertRaisesRegex(ValueError,'crosses itself|coincident'):
            distance.run(compile.compile_steps(p,64,mask_cache=cache))

    def test_unrelated_shadow_reversal_still_rejected(self):
        p=project(9);c=triangle(-.14);p['sweeps'][model.LTR][-1]['contours'].append(c)
        p['sweeps'][model.LTR][0]['contours'].append(ellipse('Shadow patch',.8,.7,.04,.04,'ADD'))
        with self.assertRaises(compile.KeyframeConflict):compile.compile_project(p,128)
