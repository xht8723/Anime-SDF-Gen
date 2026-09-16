"""Button explanations shared by selected, normal, and disabled popup states."""

from .core.model import MAP_LABELS, SWEEP_LABELS
from .core.messages import mark, msg, contour_label
from .i18n import tip as translate_tip

TEXT = {
    "UNDO": (mark("Undo"), mark("Undo the last authoring edit. Ctrl+Z.")),
    "REDO": (mark("Redo"), mark("Restore the last undone edit. Ctrl+Shift+Z.")),
    "DESTINATION": (
        mark("Save location"),
        mark("Choose the destination folder and file name. Generate & Finish writes the files."),
    ),
    "FILENAME": (
        mark("File name"),
        mark("Set the base name shared by the textures and editable project."),
    ),
    "RESOLUTION": (mark("Texture resolution"), mark("Choose the size of all exported textures.")),
    "BIT_DEPTH": (
        mark("Output precision"),
        mark("Choose 8-bit PNG, 16-bit PNG (default), or 32-bit Float EXR for every output file."),
    ),
    "SMOOTHING": (
        mark("Smoothing value"),
        mark(
            "Enter a precise amount. 0 is Off. Smoothing can alter small details; hard shadow edges remain hard."
        ),
    ),
    "SMOOTHING_SLIDER": (
        mark("Smoothing"),
        mark(
            "Drag to smooth threshold values before UV baking. Can alter small details. 0 is Off; strength scales from a 2048-pixel face canvas. Escape cancels."
        ),
    ),
    "DRAFT": (
        mark("Save draft & close"),
        mark("Save the editable project without a texture, then restore the original workspace."),
    ),
    "CLOSE": (
        mark("Discard & close"),
        mark("Close this session and restore the workspace. Previously saved files are kept."),
    ),
    "GENERATE": (
        mark("Generate & finish"),
        mark("Export the configured SDF textures and editable project, then close the editor."),
    ),
    "CANCEL_GENERATION": (
        mark("Cancel generation"),
        mark("Stop generation and keep the current editing session."),
    ),
    "KEYFRAME_COUNT": (
        mark("Shadow keyframes"),
        mark("Set the number of keyframes per complete sweep. Odd and even counts are supported."),
    ),
    "KEYFRAMES_LESS": (
        mark("Fewer keyframes"),
        mark("Use one fewer keyframe per sweep when fitting."),
    ),
    "KEYFRAMES_MORE": (
        mark("More keyframes"),
        mark("Use one more keyframe per sweep when fitting."),
    ),
    "PRESET_CLEAN": (
        mark("Clean Face"),
        mark("Start with straight shadow boundaries and editable points at the marker heights."),
    ),
    "PRESET_NOSE": (
        mark("Nose Accent"),
        mark("Start with a more pronounced nose profile fitted to the markers."),
    ),
    "REF_NEUTRAL": (
        mark("Neutral reference"),
        mark("Show the facial features with neutral studio shading."),
    ),
    "REF_MATERIAL": (
        mark("Material reference"),
        mark("Preview copies of the source materials under studio lighting."),
    ),
    "FRAME": (mark("Frame face"), mark("Center and fit the face in the views.")),
    "SOURCE": (
        mark("Source and UV"),
        mark(
            "Review the captured facial surface and output UV map. Return to orientation to change the UV map."
        ),
    ),
    "NAV_FRONT": (mark("Front view"), mark("Use Blender’s exact front view. Numpad 1.")),
    "NAV_RIGHT": (mark("Right view"), mark("Use Blender’s exact right view. Numpad 3.")),
    "NAV_TOP": (mark("Top view"), mark("Use Blender’s exact top view. Numpad 7.")),
    "ADD_KEYFRAME": (
        mark("Add keyframe"),
        mark(
            "Insert a keyframe in this sweep by copying nearby artwork. Mirroring also updates the opposite row."
        ),
    ),
    "REMOVE_KEYFRAME": (
        mark("Remove keyframe"),
        mark("Remove this keyframe from its sweep. The first and last keyframes are retained."),
    ),
    "COPY_KEYFRAME": (
        mark("Copy previous keyframe"),
        mark("Replace this keyframe’s artwork with the preceding keyframe in this row."),
    ),
    "TRIANGLE": (
        mark("Add triangle"),
        mark(
            "Add and select a smooth three-point curve. Move/Rotate/Scale shortcuts adjust it; choose Lit area to carve light or Shadow area to darken."
        ),
    ),
    "LIT": (
        mark("Lit area"),
        mark(
            "Cut a lit area out of the shadow. This cutout also applies to earlier keyframes in the same sweep; edit its shape on this keyframe."
        ),
    ),
    "SHADOW": (
        mark("Shadow area"),
        mark(
            "Fill this curve with shadow on the current keyframe. Later Lit cutouts still protect earlier keyframes."
        ),
    ),
    "DUPLICATE": (
        mark("Duplicate curve"),
        mark("Copy the selected closed curve with a small offset."),
    ),
    "DELETE_SHAPE": (
        mark("Delete curve"),
        mark("Remove the selected closed curve from this keyframe."),
    ),
    "UP": (mark("Move layer up"), mark("Apply this curve earlier in the layer order.")),
    "DOWN": (mark("Move layer down"), mark("Apply this curve later in the layer order.")),
    "TRANSFORM": (
        mark("Transform curve"),
        mark("Move, rotate or scale the entire selected curve using numeric values."),
    ),
    "POINT": (
        mark("Point coordinates"),
        mark(
            "Edit the active point’s precise head-space coordinates and Bézier handle offsets. Use Move/Rotate/Scale shortcuts to transform selected points together."
        ),
    ),
    "SMOOTH": (
        mark("Smooth handles"),
        mark("Smooth selected points using automatically aligned Bézier handles."),
    ),
    "CORNER": (mark("Corner handles"), mark("Make sharp corners at selected points.")),
    "FREE": (
        mark("Free handles"),
        mark("Give selected points independently adjustable incoming and outgoing Bézier handles."),
    ),
    "INSERT_POINT": (
        mark("Insert point"),
        mark("Split the following segment while preserving the current curve."),
    ),
    "DELETE_POINT": (mark("Remove point"), mark("Delete this point from the curve.")),
    "DISMISS_ERROR": (
        mark("Dismiss warning"),
        mark("Hide this message. The artwork still needs to pass validation before export."),
    ),
}


def describe(s, key, enabled=True):
    if key.startswith("PACK:"):
        _, name, route = key.split(":")
        label = msg(MAP_LABELS[name])
        tip = (
            msg(
                "{name} · {channel}",
                name=label,
                channel=msg("Separate") if route == "SEPARATE" else route,
            ),
            (
                mark(
                    "Save this map as its own single-channel image using the selected output precision."
                )
                if route == "SEPARATE"
                else msg(
                    "Pack this map into the {channel} channel. If occupied, the two map assignments swap.",
                    channel=route,
                )
            ),
        )
    elif key == "NEXT":
        tip = (
            mark("Next step"),
            {
                "ORIENT": mark("Use this view as the face’s front and place default markers."),
                "FIT": mark(
                    "Fit the preset to the markers and open the first Left → Right keyframe."
                ),
                "EDIT": mark("Review the complete 360° light rotation and choose where to save."),
            }[s.stage],
        )
    elif key == "BACK":
        tip = (
            mark("Previous step"),
            {
                "EDIT": mark("Return to markers without losing their positions."),
                "CONFIRM": mark("Return to the first Left → Right keyframe. Your curves are kept."),
            }.get(s.stage, mark("Return to face orientation.")),
        )
    elif key == "DESTINATION":
        tip = (
            mark("Save location"),
            msg(
                "{path}\nChoose the folder and file name. Files are written by Generate & Finish.",
                path=s.project["settings"]["output"],
            ),
        )
    elif key == "FLAT":
        tip = (
            mark("Preview appearance"),
            (
                mark("Switch to shaded preview.")
                if s.flat
                else mark("Switch to the flat black-and-white mask.")
            ),
        )
    elif key == "MIRROR":
        tip = (
            mark("Mirror Full Sweep"),
            (
                mark("Unlink the two complete sweeps for independent artwork and keyframe counts.")
                if s.project["mirror_sweeps"]
                else mark(
                    "Reflect this entire sweep into the opposite row, keeping keyframe order. This replaces the opposite row’s artwork."
                )
            ),
        )
    elif key == "PLAY":
        tip = (
            mark("Pause rotation") if s.playing else mark("Play 360°"),
            (
                mark("Pause the light orbit.")
                if s.playing
                else mark(
                    "Rotate through Front, character left, Back, character right and Front. The opposite map is sampled backward on the return half."
                )
            ),
        )
    elif key == "TOGGLE":
        tip = (
            mark("Curve visibility"),
            (
                mark("Hide this curve’s effect, including carried light.")
                if s.curve.get("enabled", True)
                else mark("Show this curve’s effect, including carried light.")
            ),
        )
    elif key.startswith("FOCUS_"):
        role = key[6:]
        tip = (
            (mark("Split views"), mark("Restore the curve and preview views side by side."))
            if s.editor.focus == role
            else (mark("Focus view"), mark("Expand this view. Ctrl+Space also toggles focus."))
        )
    elif key.startswith("KEYFRAME:"):
        _, direction, index = key.split(":")
        index = int(index)
        tip = (
            msg(
                "{direction} · Keyframe {index}",
                direction=msg(SWEEP_LABELS[direction]),
                index=index + 1,
            ),
            mark(
                "Edit this frame of the complete boundary sweep. Selecting it pauses the light orbit."
            ),
        )
    elif key.startswith("LANDMARK:"):
        name = {"nose": mark("Nose"), "mouth": mark("Mouth center"), "chin": mark("Chin")}[
            key.split(":")[1]
        ]
        tip = (
            msg("{name} marker", name=msg(name)),
            mark("Select this marker, then drag it onto the matching feature on the face."),
        )
    elif key.startswith("LAYER:"):
        curve = s.keyframe["contours"][int(key.split(":")[1])]
        tip = (
            contour_label(curve["name"]),
            mark(
                "Select all points of this curve. Move/Rotate/Scale shortcuts adjust them together."
            ),
        )
    else:
        tip = TEXT.get(key, (mark("Control"), mark("Use this authoring control.")))
    reason = ""
    if not enabled:
        reason = (
            mark("Wait for generation to finish or cancel it.")
            if s.busy
            else {
                "UNDO": mark("There are no edits to undo."),
                "REDO": mark("There are no edits to redo."),
                "BACK": mark("This is the first step."),
                "KEYFRAMES_LESS": mark("At least two keyframes per sweep are required."),
                "KEYFRAMES_MORE": mark("The maximum is 33 keyframes per sweep."),
                "ADD_KEYFRAME": mark("The maximum is 33 keyframes per sweep."),
                "REMOVE_KEYFRAME": mark("The first and last keyframes of this sweep must be kept."),
                "COPY_KEYFRAME": mark("The first keyframe has no preceding keyframe."),
                "UP": mark("This curve is already the first editable layer."),
                "DOWN": mark("This curve is already the last layer."),
                "DELETE_POINT": mark(
                    "Keep the main boundary endpoints and at least three points in a closed curve."
                ),
            }.get(key, mark("This action is unavailable in the current state."))
        )
    return {
        "title": translate_tip(tip[0]),
        "body": translate_tip(tip[1]),
        "reason": translate_tip(reason),
    }
