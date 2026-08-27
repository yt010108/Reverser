import unittest

from reverser_harness.security import SecurityError, contains_flag, safe_filename, validate_http_url


class SecurityTests(unittest.TestCase):
    def test_urls_reject_credentials_and_non_http(self):
        self.assertEqual(validate_http_url("https://ctf.example/challenges"), "https://ctf.example/challenges")
        with self.assertRaises(SecurityError):
            validate_http_url("https://user:pass@ctf.example/")
        with self.assertRaises(SecurityError):
            validate_http_url("file:///tmp/challenge")

    def test_filename_and_flag_detection(self):
        self.assertEqual(safe_filename("../../rev?.bin"), "rev_.bin")
        candidate = "EXAMPLE" + "{not-for-git}"
        self.assertTrue(contains_flag(candidate))


if __name__ == "__main__":
    unittest.main()
