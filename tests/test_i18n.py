"""Catalog, deferred diagnostics and mixed Chinese/Latin layout behavior."""

import copy
import sys
import unittest
from anime_sdf_gen.catalog import ENTRIES
from anime_sdf_gen.core.messages import (
    Message,
    Joined,
    Literal,
    msg,
    raw,
    diagnostic,
    contour_label,
    UserError,
    FileError,
)
from anime_sdf_gen.core.text import wrap_text, NO_START, NO_END
from tools.check_i18n import audit


class TranslationTests(unittest.TestCase):
    def test_catalog_covers_marked_sources_and_preserves_placeholders(self):
        self.assertEqual(audit(), [])

    def test_messages_resolve_at_display_time_and_leave_arguments_literal(self):
        translations = dict(ENTRIES)
        item = msg("Source: {name}", name="Smoothing {user}")
        self.assertEqual(str(item), "Source: Smoothing {user}")
        self.assertEqual(
            item.render(lambda text: translations.get(text, text)), "源模型：Smoothing {user}"
        )
        self.assertEqual(str(item), "Source: Smoothing {user}")
        self.assertIsInstance(raw("Smoothing"), Literal)

    def test_nested_progress_and_joined_warnings_remain_deferred(self):
        translations = dict(ENTRIES)
        tr = lambda value: translations.get(value, value)
        item = msg(
            "{label} · {progress:.0%}",
            label=msg(
                "{direction} keyframe {index}/{count}",
                direction=msg("Left → Right"),
                index=2,
                count=9,
            ),
            progress=0.25,
        )
        self.assertEqual(str(item), "Left → Right keyframe 2/9 · 25%")
        self.assertEqual(item.render(tr), "左 → 右关键帧 2/9 · 25%")
        joined = Joined((msg("Front"), msg("Back")))
        self.assertEqual(joined.render(tr), "正面, 背面")
        self.assertEqual(copy.deepcopy(item), item)

    def test_error_categories_and_external_details_are_preserved(self):
        error = UserError("The source has no UV map named {uv_name}.", uv_name="面部{UV}")
        self.assertIsInstance(error, ValueError)
        self.assertIs(diagnostic(error), error.message)
        self.assertIn("面部{UV}", str(error))
        file_error = FileError("Project round-trip verification failed.")
        self.assertIsInstance(file_error, OSError)
        external = OSError("原始错误: {details}")
        translated = diagnostic(external).render(lambda s: dict(ENTRIES).get(s, s))
        self.assertEqual(translated, "发生意外错误：原始错误: {details}")

    def test_generated_names_and_user_names_are_not_rewritten(self):
        tr = lambda s: dict(ENTRIES).get(s, s)
        self.assertEqual(contour_label("Triangle 12 copy copy").render(tr), "三角形 12 副本 副本")
        self.assertEqual(str(contour_label("Triangle 2 copy")), "Triangle 2 copy")
        self.assertIsInstance(contour_label("Smoothing"), Literal)
        self.assertIsInstance(contour_label("下巴亮部"), Literal)
        self.assertIsInstance(contour_label("Main boundary 2"), Literal)


class TextWrappingTests(unittest.TestCase):
    @staticmethod
    def width(value):
        from unicodedata import east_asian_width, combining

        return sum(
            0 if combining(c) else 2 if east_asian_width(c) in ("W", "F") else 1 for c in value
        )

    def test_english_behavior_and_oversized_tokens(self):
        self.assertEqual(wrap_text("one two three four", 9, len), ["one two", "three", "four"])
        self.assertEqual(wrap_text("abcdefghijklmn", 5, len), ["abcde", "fghij", "klmn"])
        self.assertEqual(wrap_text("", 5, len), [])

    def test_chinese_punctuation_stays_attached(self):
        for text in (
            "请调整曲线（保留亮部），然后生成。",
            "在编辑模式下选择面部几何，然后点击“创建”。",
            "选择‘创建’后，调整面部朝向。",
        ):
            for width in range(6, 32):
                lines = wrap_text(text, width, self.width)
                self.assertEqual("".join(lines), text)
                for line in lines:
                    self.assertLessEqual(self.width(line), width)
                    self.assertNotIn(line[0], NO_START)
                    self.assertNotIn(line[-1], NO_END)

    def test_mixed_unicode_paths_shortcuts_and_combining_marks(self):
        text = "保存 D:/角色/face_sdf.exr；使用 Ctrl+Shift+Z 撤销，Cafe\u0301。"
        lines = wrap_text(text, 24, self.width)
        self.assertEqual("".join(lines).replace(" ", ""), text.replace(" ", ""))
        self.assertTrue(any("Ctrl+Shift+Z" in line for line in lines), lines)
        self.assertTrue(any("Cafe\u0301" in line for line in lines), lines)
        for line in lines:
            self.assertLessEqual(self.width(line), 24)

    def test_tiny_width_always_makes_progress(self):
        self.assertEqual("".join(wrap_text("中文。", 1, self.width)), "中文。")
