import unittest
from pathlib import Path

from scripts.release_check import check_repository


class ReleaseCheckTests(unittest.TestCase):
    def test_repository_passes_static_release_checks(self) -> None:
        self.assertEqual(check_repository(Path.cwd()), [])


if __name__ == "__main__":
    unittest.main()
