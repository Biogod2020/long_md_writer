# Track Spec: Automated Headful Rescue for Image Sourcing

## Problem
Headless Google Search frequently triggers CAPTCHAs that automation cannot solve. 
While persistent profiles help, tokens expire or IPs get flagged, leading to silent failures.

## Goal
Implement a "Rescue UI" logic within `BrowserManager`:
1. **Detection**: Identify `google.com/sorry/index` during any search operation.
2. **Escalation**: Automatically relaunch the browser in `headless=False` mode if a CAPTCHA is detected.
3. **Synchronization**: Block the Python execution and wait for the user to solve the challenge.
4. **Resumption**: Detect URL change (successful challenge), persist the new cookies, and resume original search in headless mode.

## Success Criteria
- A search task hitting a CAPTCHA successfully pops up a window.
- Solving the CAPTCHA manually allows the script to finish without further intervention.
- Subsequent runs use the updated NID cookies.
