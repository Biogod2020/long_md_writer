# Implementation Plan: Automated CAPTCHA Rescue - COMPLETED

- [x] **Phase 1: BrowserManager Enhancement**
    - [x] Add `check_and_rescue()` method to `BrowserManager`.
    - [x] Implement a monitor loop that detects URL transitions out of CAPTCHA.
- [x] **Phase 2: Searcher Integration**
    - [x] Update `GoogleImageSearcher` to detect blocks and call `check_and_rescue()`.
- [x] **Phase 3: Persistence Guard**
    - [x] Ensure `user_data_dir` is never nuked during rescue to keep session integrity (`./.gemini/browser_profile_stable`).
- [x] **Phase 4: Validation**
    - [x] Run `scripts/interactive_rescue_search.py` as a regression test.
