# Phase Code Review

Systematically review the specified phase code file(s) for the PREDICT platform.

## Review Checklist (All Mandatory)

### 1. Security (CRITICAL)
- Unsafe deserialization — replace with `json.loads()` or safe alternatives
- Unsanitized user input in SQL, file paths, or shell commands
- Hardcoded secrets, API keys, or passwords
- Missing authentication/authorization on endpoints

### 2. Async/Await Correctness (CRITICAL)
- Sync `def` methods calling `async` functions without `await`
- Missing `await` on async calls (returns coroutine objects instead of results)
- Blocking sync calls inside async functions (blocks event loop)
- `session.query()` instead of `await session.execute()`

### 3. Timestamp and Datetime (HIGH)
- `datetime.now()` or `datetime.utcnow()` — must use `time.time()` (float)
- `sa.DateTime()` in DB columns — must use `sa.Float()`
- `from datetime import datetime` — only acceptable for parsing external input (e.g., ISO strings)

### 4. Import Violations (MEDIUM)
- `import X` inside function bodies — all imports must be at top of file
- Unused imports — remove dead imports
- `PyQt5` or `PyQt6` — must use `PySide6`

### 5. Architecture Violations (MEDIUM)
- `Column()` in ORM models — must use `Mapped[type]` + `mapped_column()`
- `print()` in production code (OK in `scripts/`) — must use `logging.getLogger()`
- Hardcoded paths like `C:\...` — must use `get_config()`
- Raw SQL in routers — must use `BaseRepository[ModelT]` pattern

### 6. Error Handling (LOW)
- Bare `except:` without specific exception types
- Missing error responses on API endpoints
- Non-existent method calls on objects

## Output Format

For each issue found:
```
[SEVERITY] file.py:LINE — Description
  Current:  <problematic code>
  Fixed:    <corrected code>
```

After review, provide summary table:
```
| Severity | Count | Issues |
|----------|-------|--------|
| CRITICAL | X     | ...    |
| HIGH     | X     | ...    |
| MEDIUM   | X     | ...    |
| LOW      | X     | ...    |
```

## Automated Grep Scan (Run First)

Before reading files, run these grep scans:
- `datetime.now|datetime.utcnow` — must be zero
- Unsafe deserialization patterns — must be zero
- `print\(` in `predict/core/` — must be zero
- `PyQt5|PyQt6` — must be zero
- `Column\(` in models — must be zero
- `import ` inside function bodies — must be zero

## Verdict

End with one of:
- **PASS** — No issues found
- **PASS (N fixes applied)** — Issues found and fixed
- **FAIL** — Critical issues remain unresolved
