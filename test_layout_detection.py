"""Integration tests for automatic form-layout identification."""

import unittest
from pathlib import Path

from config import build_config
from preprocessing import identify_layout, read_image


class LayoutDetectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parent
        cls.config = build_config("simple", cls.root)

    def test_td320_template(self):
        image = read_image(self.root / "figs" / "td320_blank.png")
        layout, audit = identify_layout(image, self.config)
        self.assertEqual(layout.form_id, "td320")
        self.assertEqual(audit["method"], "orb_homography")

    def test_td555_template(self):
        image = read_image(self.root / "figs" / "td555_blank.png")
        layout, _audit = identify_layout(image, self.config)
        self.assertEqual(layout.form_id, "td555")


if __name__ == "__main__":
    unittest.main()
