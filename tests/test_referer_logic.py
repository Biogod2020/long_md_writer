import unittest
from urllib.parse import urlparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestRefererLogic(unittest.TestCase):
    def get_referer(self, url):
        """Mock implementation of the referer logic we intend to add."""
        parsed_url = urlparse(url)
        return f"{parsed_url.scheme}://{parsed_url.netloc}/"

    def test_basic_referer(self):
        url = "https://www.researchgate.net/publication/123/figure/fig1/img.png"
        self.assertEqual(self.get_referer(url), "https://www.researchgate.net/")

    def test_http_referer(self):
        url = "http://example.com/path/to/image.jpg"
        self.assertEqual(self.get_referer(url), "http://example.com/")

    def test_complex_subdomain(self):
        url = "https://images.sub.provider.co.uk/file.webp"
        self.assertEqual(self.get_referer(url), "https://images.sub.provider.co.uk/")

if __name__ == "__main__":
    unittest.main()
