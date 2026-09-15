"""Button explanations shared by selected, normal, and disabled popup states."""
from .core.model import MAP_LABELS, SWEEP_LABELS
TEXT={
    'UNDO':('Undo','Undo the last authoring edit. Ctrl+Z.'),
    'REDO':('Redo','Restore the last undone edit. Ctrl+Shift+Z.'),
    'DESTINATION':('Save location','Choose the destination folder and file name. Generate & Finish writes the files.'),
    'FILENAME':('File name','Set the base name shared by the textures and editable project.'),
    'RESOLUTION':('Texture resolution','Choose the size of all exported 16-bit PNG textures.'),
    'DRAFT':('Save draft & close','Save the editable project without a texture, then restore the original workspace.'),
    'CLOSE':('Discard & close','Close this session and restore the workspace. Previously saved files are kept.'),
    'GENERATE':('Generate & finish','Export the configured SDF textures and editable project, then close the editor.'),
    'CANCEL_GENERATION':('Cancel generation','Stop generation and keep the current editing session.'),
    'KEYFRAME_COUNT':('Shadow keyframes','Set the number of keyframes per complete sweep. Odd and even counts are supported.'),
    'KEYFRAMES_LESS':('Fewer keyframes','Use one fewer keyframe per sweep when fitting.'),
    'KEYFRAMES_MORE':('More keyframes','Use one more keyframe per sweep when fitting.'),
    'PRESET_CLEAN':('Clean Face','Start with straight shadow boundaries and editable points at the marker heights.'),
    'PRESET_NOSE':('Nose Accent','Start with a more pronounced nose profile fitted to the markers.'),
    'REF_NEUTRAL':('Neutral reference','Show the facial features with neutral studio shading.'),
    'REF_MATERIAL':('Material reference','Preview copies of the source materials under studio lighting.'),
    'FRAME':('Frame face','Center and fit the face in the views.'),
    'SOURCE':('Source and UV','Review the captured facial surface and output UV map. Return to orientation to change the UV map.'),
    'NAV_FRONT':('Front view','Use Blender’s exact front view. Numpad 1.'),
    'NAV_RIGHT':('Right view','Use Blender’s exact right view. Numpad 3.'),
    'NAV_TOP':('Top view','Use Blender’s exact top view. Numpad 7.'),
    'ADD_KEYFRAME':('Add keyframe','Insert a keyframe in this sweep by copying nearby artwork. Mirroring also updates the opposite row.'),
    'REMOVE_KEYFRAME':('Remove keyframe','Remove this keyframe from its sweep. The first and last keyframes are retained.'),
    'COPY_KEYFRAME':('Copy previous keyframe','Replace this keyframe’s artwork with the preceding keyframe in this row.'),
    'TRIANGLE':('Add triangle','Add and select a smooth three-point curve. Move/Rotate/Scale shortcuts adjust it; choose Lit area to carve light or Shadow area to darken.'),
    'LIT':('Lit area','Cut a lit area out of the shadow. This cutout also applies to earlier keyframes in the same sweep; edit its shape on this keyframe.'),
    'SHADOW':('Shadow area','Fill this curve with shadow on the current keyframe. Later Lit cutouts still protect earlier keyframes.'),
    'DUPLICATE':('Duplicate curve','Copy the selected closed curve with a small offset.'),
    'DELETE_SHAPE':('Delete curve','Remove the selected closed curve from this keyframe.'),
    'UP':('Move layer up','Apply this curve earlier in the layer order.'),
    'DOWN':('Move layer down','Apply this curve later in the layer order.'),
    'TRANSFORM':('Transform curve','Move, rotate or scale the entire selected curve using numeric values.'),
    'POINT':('Point coordinates','Edit the active point’s precise head-space coordinates and Bézier handle offsets. Use Move/Rotate/Scale shortcuts to transform selected points together.'),
    'SMOOTH':('Smooth handles','Smooth selected points using automatically aligned Bézier handles.'),
    'CORNER':('Corner handles','Make sharp corners at selected points.'),
    'FREE':('Free handles','Give selected points independently adjustable incoming and outgoing Bézier handles.'),
    'INSERT_POINT':('Insert point','Split the following segment while preserving the current curve.'),
    'DELETE_POINT':('Remove point','Delete this point from the curve.'),
    'DISMISS_ERROR':('Dismiss warning','Hide this message. The artwork still needs to pass validation before export.'),
}


def describe(s,key,enabled=True):
    if key.startswith('PACK:'):
        _,name,route=key.split(':');label=MAP_LABELS[name]
        tip=(label+' · '+('Separate' if route=='SEPARATE' else route),
             'Save this map as its own 16-bit grayscale PNG.' if route=='SEPARATE' else
             f'Pack this map into the {route} channel. If occupied, the two map assignments swap.')
    elif key=='NEXT':
        tip=('Next step',{'ORIENT':'Use this view as the face’s front and place default markers.',
             'FIT':'Fit the preset to the markers and open the first Left → Right keyframe.',
             'EDIT':'Review the complete 360° light rotation and choose where to save.'}[s.stage])
    elif key=='BACK':tip=('Previous step',{'EDIT':'Return to markers without losing their positions.',
         'CONFIRM':'Return to the first Left → Right keyframe. Your curves are kept.'}.get(s.stage,'Return to face orientation.'))
    elif key=='DESTINATION':tip=('Save location',s.project['settings']['output']+'\nChoose the folder and file name. Files are written by Generate & Finish.')
    elif key=='FLAT':tip=('Preview appearance','Switch to shaded preview.' if s.flat else 'Switch to the flat black-and-white mask.')
    elif key=='MIRROR':tip=('Mirror Full Sweep','Unlink the two complete sweeps for independent artwork and keyframe counts.' if s.project['mirror_sweeps'] else 'Reflect this entire sweep into the opposite row, keeping keyframe order. This replaces the opposite row’s artwork.')
    elif key=='PLAY':tip=('Pause rotation' if s.playing else 'Play 360°','Pause the light orbit.' if s.playing else 'Rotate through Front, character left, Back, character right and Front. The opposite map is sampled backward on the return half.')
    elif key=='TOGGLE':tip=('Curve visibility','Hide this curve’s effect, including carried light.' if s.curve.get('enabled',True) else 'Show this curve’s effect, including carried light.')
    elif key.startswith('FOCUS_'):
        role=key[6:];tip=('Split views','Restore the curve and preview views side by side.') if s.editor.focus==role else ('Focus view','Expand this view. Ctrl+Space also toggles focus.')
    elif key.startswith('KEYFRAME:'):
        _,direction,index=key.split(':');index=int(index)
        tip=(f'{SWEEP_LABELS[direction]} · Keyframe {index+1}','Edit this frame of the complete boundary sweep. Selecting it pauses the light orbit.')
    elif key.startswith('LANDMARK:'):
        name={'nose':'Nose','mouth':'Mouth center','chin':'Chin'}[key.split(':')[1]]
        tip=(name+' marker','Select this marker, then drag it onto the matching feature on the face.')
    elif key.startswith('LAYER:'):
        curve=s.keyframe['contours'][int(key.split(':')[1])]
        tip=(curve['name'],'Select all points of this curve. Move/Rotate/Scale shortcuts adjust them together.')
    else:tip=TEXT.get(key,('Control','Use this authoring control.'))
    reason=''
    if not enabled:
        reason=('Wait for generation to finish or cancel it.' if s.busy else {
            'UNDO':'There are no edits to undo.','REDO':'There are no edits to redo.',
            'BACK':'This is the first step.','KEYFRAMES_LESS':'At least two keyframes per sweep are required.',
            'KEYFRAMES_MORE':'The maximum is 33 keyframes per sweep.','ADD_KEYFRAME':'The maximum is 33 keyframes per sweep.',
            'REMOVE_KEYFRAME':'The first and last keyframes of this sweep must be kept.',
            'COPY_KEYFRAME':'The first keyframe has no preceding keyframe.',
            'UP':'This curve is already the first editable layer.',
            'DOWN':'This curve is already the last layer.',
            'DELETE_POINT':'Keep the main boundary endpoints and at least three points in a closed curve.'
        }.get(key,'This action is unavailable in the current state.'))
    return {'title':tip[0],'body':tip[1],'reason':reason}
