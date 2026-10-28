import io
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reverser_harness.importer import ChallengeImporter
from reverser_harness.site_import import _open_public, _public_address, download_attachment, preview_site
from reverser_harness.storage import ChallengeStore


class Response:
    def __init__(self, body: bytes, content_type: str = "text/html; charset=utf-8") -> None:
        self.body = io.BytesIO(body)
        self.headers = {"content-type": content_type, "content-length": str(len(body))}

    def getheader(self, name: str) -> str | None:
        return self.headers.get(name.lower())

    def read(self, size: int) -> bytes:
        return self.body.read(size)


class SiteImportTests(unittest.TestCase):
    def test_preview_extracts_statement_and_selectable_files(self):
        html = b"""<html><head><title>Site name</title></head><body>
        <nav>Other challenges</nav><main><h1>Reverse One</h1>
        <p>Find the correct input.</p><a href='/files/rev.zip'>Download</a>
        <a download href='/files/attachment'>Get file</a></main></body></html>"""
        connection = unittest.mock.Mock()
        with patch("reverser_harness.site_import._open_public", return_value=(Response(html), connection, "https://ctf.example/challenge/1")):
            value = preview_site("https://ctf.example/challenge/1")
        self.assertEqual(value["title"], "Reverse One")
        self.assertIn("Find the correct input.", value["description"])
        self.assertNotIn("Other challenges", value["description"])
        self.assertEqual(len(value["files"]), 2)
        self.assertEqual(value["files"][0]["url"], "https://ctf.example/files/rev.zip")
        connection.close.assert_called_once()

    def test_private_network_address_is_rejected(self):
        private = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]
        with patch("reverser_harness.site_import.socket.getaddrinfo", return_value=private):
            with self.assertRaisesRegex(ValueError, "공개 인터넷"):
                _public_address("localhost", 80)

    def test_redirect_to_private_address_is_rejected(self):
        connection = unittest.mock.Mock()
        connection.getresponse.return_value.status = 302
        connection.getresponse.return_value.getheader.return_value = "http://127.0.0.1/admin"
        def addresses(host, port, **_kwargs):
            address = "127.0.0.1" if host == "127.0.0.1" else "93.184.215.14"
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]
        with patch("reverser_harness.site_import.socket.getaddrinfo", side_effect=addresses), \
             patch("reverser_harness.site_import.http.client.HTTPConnection", return_value=connection):
            with self.assertRaisesRegex(ValueError, "공개 인터넷"):
                _open_public("http://ctf.example/challenge")
        connection.close.assert_called_once()

    def test_download_rejects_html_instead_of_attachment(self):
        connection = unittest.mock.Mock()
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "challenge.zip"
            with patch("reverser_harness.site_import._open_public", return_value=(Response(b"<html>login</html>"), connection, "https://ctf.example/login")):
                with self.assertRaisesRegex(ValueError, "웹 페이지"):
                    download_attachment("https://ctf.example/files/challenge.zip", target)
            self.assertFalse(target.exists())
        connection.close.assert_called_once()

    def test_url_only_import_keeps_description(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = ChallengeStore(Path(temporary))
            importer = ChallengeImporter(store)
            with self.assertRaisesRegex(ValueError, "At least one"):
                importer.import_local(title="Rev", files=[])
            state = importer.import_local(title="Rev", files=[], platform_url="https://ctf.example/rev",
                                          description="Find the key.", allow_empty=True)
            self.assertEqual(state["status"], "imported")
            self.assertEqual(state["description"], "Find the key.")
            self.assertTrue((store.challenge_dir(state["challenge_id"]) / "original" / "description.md").is_file())


if __name__ == "__main__":
    unittest.main()
