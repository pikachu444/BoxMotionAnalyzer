import os
import tempfile
import unittest

from src.analysis.pipeline.artifact_io import (
    PROC_FILE_EXTENSION,
    SLICE_FILE_EXTENSION,
    build_batch_proc_path,
    is_result_file,
    is_slice_file,
    list_result_files,
    list_slice_files,
    proc_file_filter,
    raw_csv_file_filter,
    result_file_filter,
    slice_file_filter,
)


class TestArtifactIoFilters(unittest.TestCase):
    def test_shared_filters_match_current_extensions(self):
        self.assertEqual(raw_csv_file_filter(), "CSV Files (*.csv)")
        self.assertEqual(slice_file_filter(), "Slice Files (*.slice)")
        self.assertEqual(proc_file_filter(), "Processed Files (*.proc)")
        self.assertEqual(result_file_filter(), "Result Files (*.proc)")

    def test_batch_proc_path_and_file_listing_use_shared_rules(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            filenames = [
                "scene_a.slice",
                "scene_b.slice",
                "scene_b.proc",
                "legacy_result.csv",
                "notes.txt",
            ]
            for filename in filenames:
                with open(os.path.join(temp_dir, filename), "w", encoding="utf-8") as handle:
                    handle.write("test")

            self.assertEqual(
                build_batch_proc_path(os.path.join(temp_dir, "scene_a.slice")),
                os.path.join(temp_dir, "scene_a.proc"),
            )
            self.assertTrue(is_slice_file("scene_a.slice"))
            self.assertFalse(is_slice_file("scene_a.csv"))
            self.assertTrue(is_result_file("scene_b.proc"))
            self.assertFalse(is_result_file("legacy_result.csv"))
            self.assertFalse(is_result_file("notes.txt"))
            self.assertEqual(list_slice_files(temp_dir), ["scene_a.slice", "scene_b.slice"])
            self.assertEqual(list_result_files(temp_dir), ["scene_b.proc"])

            self.assertEqual(PROC_FILE_EXTENSION, ".proc")
            self.assertEqual(SLICE_FILE_EXTENSION, ".slice")


if __name__ == "__main__":
    unittest.main()
