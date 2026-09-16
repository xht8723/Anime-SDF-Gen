"""One timer/report/teardown path for disposable Blender UI validation."""

import json
import time
import traceback
import bpy
import anime_sdf_gen


def run(workflow, test, filename, timeout=300):
    steps = workflow()

    def tick():
        try:
            if time.perf_counter() - test.started > timeout:
                raise AssertionError("UI validation timed out")
            delay = next(steps)
            test.write(filename)
            return delay
        except StopIteration:
            test.report["status"] = "PASS"
        except Exception:
            test.report.update(status="FAIL", traceback=traceback.format_exc())
            traceback.print_exc()
            try:
                anime_sdf_gen.unregister()
            except Exception:
                traceback.print_exc()
        test.write(filename)
        print(json.dumps(test.report), flush=True)
        windows = list(bpy.context.window_manager.windows)
        origin = test.origin if test.origin in windows else next(iter(windows), None)
        if origin:
            with bpy.context.temp_override(window=origin):
                bpy.ops.wm.quit_blender()
        return None

    bpy.app.timers.register(tick, first_interval=1)
