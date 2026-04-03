# Implementation Plan

- [ ] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - AWS Credentials Not Loading from Wrong .env Path
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: For deterministic bugs, scope the property to the concrete failing case(s) to ensure reproducibility
  - Test that config.py loads AWS credentials from backend/.env (from Bug Condition in design)
  - The test should verify: STORAGE_TYPE, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_BUCKET are loaded from backend/.env
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists because config loads from project root .env which lacks AWS credentials)
  - Document counterexamples found (e.g., "STORAGE_TYPE defaults to 'local' instead of loading 's3' from backend/.env")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Local Storage and Non-AWS Config Loading
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-AWS configs (DATABASE_URL, REDIS_URL, CLERK_SECRET_KEY)
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements
  - Property-based testing generates many test cases for stronger guarantees
  - Verify that database, redis, and clerk configs still load correctly (they're in backend/.env too)
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 3. Fix for wrong .env path in config.py

  - [x] 3.1 Implement the fix
    - Change line 10 in backend/app/core/config.py from:
      ```python
      env_file = Path(__file__).parent.parent.parent / ".env"
      ```
      to:
      ```python
      env_file = Path(__file__).parent.parent / ".env"
      ```
    - This changes path resolution from 3 levels up (project root) to 2 levels up (backend directory)
    - _Bug_Condition: isBugCondition() - config.py loads from wrong .env path causing AWS credentials to be None_
    - _Expected_Behavior: expectedBehavior() - AWS credentials load from backend/.env when path is corrected_
    - _Preservation: Local storage behavior remains unchanged when STORAGE_TYPE=local_
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - AWS Credentials Loading from Correct .env Path
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Local Storage and Non-AWS Config Preservation
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.