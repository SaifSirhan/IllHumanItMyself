"""Offline tests. All network calls are mocked."""

import logging
import unittest
from unittest.mock import patch

from humanizer import chunking
from humanizer.pipeline import humanize_text
from humanizer.prompts import PARAPHRASE_SYSTEM, STRIP_SYSTEM, VERIFY_SYSTEM
from humanizer.translate import _coherent, round_trip

API_KEY = "sk-test-key-do-not-log"


def _long_text(words: int = 60) -> str:
    return " ".join(f"claim{i}" for i in range(words))


def _two_chunk_text() -> str:
    paragraph = _long_text(700)
    return paragraph + "\n\n" + paragraph


def _fake_llm(api_key, system, user, temperature):
    if system == VERIFY_SYSTEM:
        return "NO LOSS"
    if system == PARAPHRASE_SYSTEM:
        return "PARAPHRASED " + user
    if system == STRIP_SYSTEM:
        return user
    raise AssertionError("unexpected system prompt")


class SplitTextTests(unittest.TestCase):
    def test_never_splits_mid_sentence_and_preserves_word_order(self):
        sentences = [
            "Sentence number one is here.",
            "The second sentence follows it!",
            "A third one asks a question?",
        ]
        paragraph = " ".join(sentences * 10)
        chunks = chunking.split_text(paragraph, max_words=25)

        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertIn(chunk.rstrip()[-1], ".!?")
        self.assertEqual(" ".join(chunks).split(), paragraph.split())

    def test_keeps_paragraphs_together_when_under_limit(self):
        text = "First paragraph has words.\n\nSecond paragraph here."
        chunks = chunking.split_text(text, max_words=100)

        self.assertEqual(len(chunks), 1)
        self.assertIn("\n\n", chunks[0])
        self.assertEqual(chunks[0].split(), text.split())

    def test_splits_oversized_paragraph_on_sentences(self):
        paragraph = " ".join(["This is a short sentence."] * 60)
        chunks = chunking.split_text(paragraph, max_words=30)

        self.assertGreater(len(chunks), 1)
        self.assertEqual(" ".join(chunks).split(), paragraph.split())


class CoherenceTests(unittest.TestCase):
    def test_rejects_empty(self):
        self.assertFalse(_coherent("hello world", ""))
        self.assertFalse(_coherent("hello world", "   "))

    def test_rejects_identical(self):
        self.assertFalse(_coherent("hello world", "hello world"))

    def test_rejects_ten_times_longer(self):
        source = "one two three"
        self.assertFalse(_coherent(source, "x" * (len(source) * 10)))

    def test_accepts_normal_translation(self):
        self.assertTrue(_coherent("Hello world", "Hola mundo"))


class RoundTripTests(unittest.TestCase):
    def test_skips_failing_hop_and_warns(self):
        progress = []

        def fake_translate(text, source, target):
            if target == "ja":
                raise RuntimeError("hop down")
            return f"{text} [{target}]"

        with patch("humanizer.translate.translate", side_effect=fake_translate), patch(
            "humanizer.translate.time.sleep"
        ):
            output, warnings = round_trip(
                "Start text",
                ["zh-CN", "ja"],
                progress_cb=lambda *args: progress.append(args),
            )

        self.assertEqual(output, "Start text [zh-CN] [en]")
        self.assertEqual(len(warnings), 1)
        self.assertIn("ja", warnings[0])
        self.assertEqual(
            progress,
            [(0, 3, "zh-CN"), (1, 3, "ja"), (2, 3, "en")],
        )

    def test_raises_when_every_hop_fails(self):
        with patch(
            "humanizer.translate.translate", side_effect=RuntimeError("network down")
        ), patch("humanizer.translate.time.sleep"):
            with self.assertRaises(RuntimeError):
                round_trip("Start text", ["zh-CN", "ja"])


class PipelineTests(unittest.TestCase):
    def test_returns_stages_per_step_per_chunk(self):
        progress = []

        with patch("humanizer.llm.call_llm", side_effect=_fake_llm), patch(
            "humanizer.translate.translate", side_effect=lambda t, s, target: "T " + t
        ), patch("humanizer.translate.time.sleep"):
            result = humanize_text(
                _two_chunk_text(),
                API_KEY,
                chain=["zh-CN", "ja"],
                progress_cb=lambda *args: progress.append(args),
            )

        names = [stage.name for stage in result.stages]
        self.assertEqual(len(names), 7)
        for chunk_number in (1, 2):
            chunk_stages = [n for n in names if f"chunk {chunk_number}/2" in n]
            self.assertEqual(len(chunk_stages), 3)
            self.assertTrue(any("paraphrase" in n for n in chunk_stages))
            self.assertTrue(any("translate" in n for n in chunk_stages))
            self.assertTrue(any("strip" in n for n in chunk_stages))
        self.assertEqual(names[-1], "verify")

        self.assertEqual(result.final_text.count("PARAPHRASED"), 2)
        self.assertIn("\n\n", result.final_text)
        self.assertEqual(result.claim_loss, [])
        self.assertTrue(progress)

    def test_falls_back_to_paraphrase_when_translation_fails(self):
        with patch("humanizer.llm.call_llm", side_effect=_fake_llm), patch(
            "humanizer.translate.translate", side_effect=RuntimeError("translator down")
        ), patch("humanizer.translate.time.sleep"):
            result = humanize_text(
                _long_text(100),
                API_KEY,
                chain=["zh-CN"],
                run_verification=False,
            )

        self.assertIn("PARAPHRASED", result.final_text)
        self.assertIn("claim99", result.final_text)
        self.assertTrue(any("translator down" in w for w in result.warnings))
        translate_stage = next(s for s in result.stages if "translate" in s.name)
        self.assertEqual(translate_stage.output, translate_stage.output.strip())
        self.assertTrue(translate_stage.warnings)

    def test_rejects_short_input(self):
        with self.assertRaises(ValueError):
            humanize_text("too short to process", API_KEY)

    def test_api_key_never_leaks(self):
        leaky = RuntimeError(f"auth failed for {API_KEY}")

        with patch("humanizer.llm.call_llm", side_effect=leaky), patch(
            "humanizer.translate.translate", side_effect=RuntimeError("translator down")
        ), patch("humanizer.translate.time.sleep"), self.assertLogs(
            level=logging.DEBUG
        ) as captured:
            result = humanize_text(_long_text(60), API_KEY, chain=["zh-CN"])

        self.assertNotIn(API_KEY, repr(result))
        for line in captured.output:
            self.assertNotIn(API_KEY, line)
        self.assertTrue(result.warnings)


if __name__ == "__main__":
    unittest.main()
