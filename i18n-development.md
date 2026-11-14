# Anime SDF Gen — translation maintenance

## Boundaries

The extension uses Blender's native translation registry under the context `Anime SDF Gen`. The only additional locale is `zh_HANS`. `i18n.py` adapts interface, tooltip and report presentation to Blender's separate translation flags. It does not change user preferences.

`core/messages.py` contains locale-independent message templates, named arguments and composed messages. Core exceptions retain their ValueError, OSError or RuntimeError category and readable English `str()`. Unexpected external exceptions are displayed under a translated explanation with verbatim details. Message objects never enter project JSON.

The existing session timer compares effective locale and translation flags. A change requests redraws only; it leaves computation, masks, texture upload revisions, export jobs and authoring state alone. Native dialogs use Blender's own translation/redraw behavior.

## Adding text

- Add English/Chinese pairs to the explicit `catalog.ENTRIES` sequence. Keep placeholder names, conversions and format specifications identical.
- Use `msg("Faces: {count}", count=count)` for dynamic text and retained notices. Nested translated labels should be messages; source names, paths and user text remain literal arguments.
- Mark canonical display constants with `mark()`. This marks extraction only and never changes their stored values.
- Resolve `iface()`, `tip()` or `report()` at presentation, before formatting/layout. Wrap user-owned strings with `raw()` when passing them through a generic text control.
- Do not translate fragments after interpolation or translate already-wrapped lines a second time. Warnings use report preferences even when interface translation is enabled.
- Native RNA properties need `translation_context=CONTEXT`. Registration assigns the same context to native operator and panel classes. Preserve operator IDs, enum identifiers, schema keys and file suffixes.
- Pass `report(...)` to `operator.report(...)`, including static notifications. Blender’s [native report implementation](https://github.com/blender/blender/blob/main/source/blender/blenkernel/intern/report.cc) looks up the default context; an operator’s RNA context does not automatically cover its reports.
- Reserved generated contour names have a display-only translation. Arbitrary custom names and all serialized names are retained.

The popup uses Blender's bundled font and CJK fallback. Mixed Chinese/Latin wrapping lives in the Blender-independent text module. It preserves word boundaries when possible, avoids detached Chinese punctuation and only splits oversized tokens when necessary. English wrapping retains the preceding release's behavior.

## Vocabulary

| English | 简体中文 |
|---|---|
| Shadow keyframes | 阴影关键帧 |
| Main boundary | 明暗分界线 |
| Mirror Full Sweep | 镜像同步关键帧 |
| Keyframes per sweep | 每组关键帧数 |
| Lit cutout / Shadow patch | 亮区 / 阴影区 |
| Fitting markers | 面部定位点 |
| Refit boundaries… | 重新生成分界线… |
| Clean Face / Nose Accent | 直线分界 / 突出鼻部 |
| Neutral / Materials | 素模 / 原有材质 |
| Flat mask | 黑白遮罩 |
| Focus / Frame face | 放大视图 / 显示整个面部 |
| Active point / Handles | 当前控制点 / 控制柄 |
| Bake UV map | 烘焙用 UV |
| Output packing | 输出通道 |
| Generate & Finish | 导出并关闭 |
| Source (region selection method) | 面部选取方式 |
| Face coverage | 面部覆盖范围 |
| Smoothing | 平滑强度 |

Keep Anime SDF Gen, SDF, UV, RGB channels, PNG, EXR and keyboard shortcuts recognizable. Direction labels describe the existing boundary sweep; translations must not redefine channel or light-direction semantics.

Write Chinese as native artist-facing copy, not as a word-for-word rendering of English. Labels describe the result; tooltips explain the action and its consequences. Use 形状 for list items, 曲线 for their contours, 控制点 for their points, 控制柄 for Bézier handles, 尖角 for the corner mode, and 工程 for saved projects. Explain each sweep as a group of keyframes; avoid 扫掠, 继承亮部, 头部空间 and 编辑会话 in everyday controls. Keep technical details when they help diagnose an error, after a plain-language explanation and any useful next step.

Mirror copy must state that Left → Right is the source and Right → Left is replaced and locked. Lit-area copy must explain its effect on earlier keyframes. Refit copy must explain replacement of edited boundaries and possible shape loss when reducing frame counts. UV copy must distinguish selecting existing UV coordinates from selecting a texture image. Keep references to renamed controls consistent in tooltips, reports and the Chinese guide.

## Checks

Run `python tools/check_i18n.py` for source coverage, duplicate/unused entries and placeholder agreement, and `python -m unittest tests.test_i18n` for deferred messages and typography. Blender's actual operator RNA property table is available through the operator's `get_rna_type()`; its class `bl_rna` does not contain operator parameter properties.

Run `tools/validate.py --blender ... --suite i18n` for registry cleanup, independent flags, Automatic/fallback, Unicode data and exact bilingual export comparison, followed by real 2K/4K popup checks. Run the complete suite before release. Screenshots and reports belong under `build/validation/<version>`. Never overwrite the model fixture or recapture frozen preview references merely to silence a failure.
