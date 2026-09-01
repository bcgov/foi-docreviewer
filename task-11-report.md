
## Re-review Fix: TestOpenDatabaseContextCancellationPropagatesClean

**Finding:** Test called `t.Parallel()` while mutating package-global `pingFn`, creating a data race.

**Fix:** Removed `t.Parallel()` from `TestOpenDatabaseContextCancellationPropagatesClean` in `computingservices/OCRServices/internal/app/app_test.go`. Added explanatory comment. No behavior change.

**Test result:** `go test -race ./internal/app/` → `ok  ocrservices/internal/app  1.007s`
