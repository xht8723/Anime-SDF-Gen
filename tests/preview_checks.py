"""GPU assertions shared by real popup tests."""
import numpy as np
from tests.ui_helpers import redraw, session




def pixels():
    redraw();b=session.ACTIVE.editor.buffers['PREVIEW']
    a=np.asarray(b.texture_color.read(),dtype=float).reshape(b.height,b.width,4)[...,:3]
    return a/255 if a.max()>1 else a


def appearance(flat=False):
    """Classify independent brightness ranges; never infer coverage from normals."""
    a=pixels()
    background=np.max(np.abs(a-[.055,.065,.083]),axis=2)<.006
    uncovered=np.max(np.abs(a-[.12]*3),axis=2)<.006
    valid=~(background|uncovered)
    luminance=a@np.array([.2126,.7152,.0722])
    lit=valid&(luminance>.25);shadow=valid&~lit
    if flat:
        assert np.all(np.abs(a[lit]-1)<.006)
        assert np.all(np.abs(a[shadow])<.006)
    else:
        assert np.all((luminance[lit]>.30)&(luminance[lit]<.71))
        assert np.all((luminance[shadow]>.085)&(luminance[shadow]<.22))
    return a,lit,shadow
