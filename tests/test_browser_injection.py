import unittest
from unittest.mock import MagicMock
import requests
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestBrowserInjection(unittest.TestCase):
    def test_session_injection_logic(self):
        """Verify that cookies and UA are correctly mapped from browser to session."""
        mock_tab = MagicMock()
        mock_tab.cookies.return_value = [
            {'name': 'session_id', 'value': '12345', 'domain': 'example.com'},
            {'name': 'cf_clearance', 'value': 'abcde', 'domain': 'example.com'}
        ]
        mock_tab.user_agent = "Mozilla/5.0 Mock"
        
        # Sourcing logic we want to implement
        try:
            raw_c_list = mock_tab.cookies()
            raw_cookies = {c['name']: c['value'] for c in raw_c_list}
        except:
            raw_cookies = {}
            
        ua = mock_tab.user_agent
        
        session = requests.Session()
        session.headers.update({"User-Agent": ua})
        session.cookies.update(raw_cookies)
        
        self.assertEqual(session.headers["User-Agent"], "Mozilla/5.0 Mock")
        self.assertEqual(session.cookies.get("session_id"), "12345")
        self.assertEqual(session.cookies.get("cf_clearance"), "abcde")

if __name__ == "__main__":
    unittest.main()
