# NoteVault (intentionally vulnerable)

> ⚠️ **Do not deploy.** This tiny Flask API is deliberately insecure. It exists only as a target for the Exhibit A demo.

It contains five planted bugs:

1. Missing authentication on an admin endpoint
2. IDOR (any logged-in user can read anyone's note)
3. Hardcoded signing secret
4. SQL injection in login
5. Permissive CORS (reflects any origin with credentials)

The tests in `tests/test_smoke.py` cover the happy path only and pass on the vulnerable code. Exhibit A's job is to add tests that **fail** because of each bug, then fix the code until they pass without breaking the smoke tests.

```bash
pip install -r requirements.txt
pytest -q
```
