import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import shutil
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agents.image_sourcing.downloader import ImageDownloader

class TestImageDownloaderDiagnosis(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.browser_manager = MagicMock()
        self.downloader = ImageDownloader(self.browser_manager, debug=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('requests.Session')
    def test_diagnostic_logging_on_failure(self, mock_session_class):
        """Verify that diagnostic info is captured when a request fails."""
        mock_session = mock_session_class.return_value
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = {'X-Bot-Protection': 'Cloudflare', 'Content-Type': 'text/html'}
        mock_response.text = "Forbidden"
        mock_session.get.return_value = mock_response

        url = "https://example.com/blocked.jpg"
        
        # We need to capture stdout to verify logging
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            result = self.downloader._download_single_requests(url, 0, self.test_dir, mock_session, "test")
        
        output = f.getvalue()
        
        self.assertIsNone(result)
        # These assertions are expected to FAIL initially
        self.assertIn("FAILED: 403", output)
        self.assertIn("X-Bot-Protection", output)
        self.assertIn("Cloudflare", output)

if __name__ == "__main__":
    unittest.main()
