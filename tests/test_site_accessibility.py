import unittest
from pathlib import Path


class SiteAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = Path("site/index.html").read_text(encoding="utf-8")
        cls.css = Path("site/styles.css").read_text(encoding="utf-8")
        cls.javascript = Path("site/app.js").read_text(encoding="utf-8")

    def test_page_has_navigation_landmarks_skip_link_and_labelled_controls(self) -> None:
        self.assertIn('href="#overview">Skip to dashboard', self.html)
        self.assertIn('<main id="overview">', self.html)
        self.assertIn('aria-label="Primary navigation"', self.html)
        self.assertIn('label for="city-select"', self.html)
        self.assertIn('aria-label="Switch to night shift"', self.html)
        self.assertIn("<caption", self.html)
        self.assertIn('id="weather-grid"', self.html)
        self.assertIn('id="data-refresh"', self.html)

    def test_dashboard_refreshes_and_renders_weather_readings(self) -> None:
        self.assertIn('cache: "no-store"', self.javascript)
        self.assertIn("window.setInterval", self.javascript)
        self.assertIn("renderWeather(data.cities)", self.javascript)
        self.assertIn("WAITING FOR TIME OVERLAP", Path("site/data/summary.json").read_text())

    def test_reduced_motion_is_honoured_in_css_and_javascript(self) -> None:
        self.assertIn("prefers-reduced-motion: reduce", self.css)
        self.assertIn('reduceMotion ? "auto" : "smooth"', self.javascript)

    def test_mobile_layout_and_visible_keyboard_focus_exist(self) -> None:
        self.assertIn("@media (max-width: 760px)", self.css)
        self.assertIn(":focus-visible", self.css)


if __name__ == "__main__":
    unittest.main()
