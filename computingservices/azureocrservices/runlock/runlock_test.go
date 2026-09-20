package runlock

import (
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"testing"
	"time"
)

func TestAcquireFreeThenRelease(t *testing.T) {
	path := filepath.Join(t.TempDir(), "run.lock")
	release, err := Acquire(path, time.Hour)
	if err != nil {
		t.Fatal(err)
	}
	data, _ := os.ReadFile(path)
	if string(data) != strconv.Itoa(os.Getpid()) {
		t.Fatalf("lock body = %q", data)
	}
	release()
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatal("lock file should be removed on release")
	}
}

func TestAcquireHeldByLivePid(t *testing.T) {
	path := filepath.Join(t.TempDir(), "run.lock")
	os.WriteFile(path, []byte(strconv.Itoa(os.Getpid())), 0o644)
	_, err := Acquire(path, time.Hour)
	if !errors.Is(err, ErrHeld) {
		t.Fatalf("want ErrHeld, got %v", err)
	}
}

func TestAcquireTakesOverDeadPid(t *testing.T) {
	path := filepath.Join(t.TempDir(), "run.lock")
	os.WriteFile(path, []byte("2147483000"), 0o644) // no such process
	release, err := Acquire(path, time.Hour)
	if err != nil {
		t.Fatalf("want takeover, got %v", err)
	}
	defer release()
	data, _ := os.ReadFile(path)
	if string(data) != strconv.Itoa(os.Getpid()) {
		t.Fatalf("lock not rewritten: %q", data)
	}
}

func TestAcquireTakesOverStaleLivePid(t *testing.T) {
	path := filepath.Join(t.TempDir(), "run.lock")
	os.WriteFile(path, []byte(strconv.Itoa(os.Getpid())), 0o644)
	old := time.Now().Add(-2 * time.Hour)
	os.Chtimes(path, old, old)
	release, err := Acquire(path, time.Hour)
	if err != nil {
		t.Fatalf("want takeover of stale lock, got %v", err)
	}
	release()
}

func TestAcquireUnreadableLockBodyIsStale(t *testing.T) {
	path := filepath.Join(t.TempDir(), "run.lock")
	os.WriteFile(path, []byte("garbage"), 0o644)
	release, err := Acquire(path, time.Hour)
	if err != nil {
		t.Fatalf("want takeover, got %v", err)
	}
	release()
}

// TestReleaseDoesNotRemoveTakenOverLock guards against a use-after-free of
// the lock file: if another process took the lock over (e.g. this process
// was judged stale while still alive), release() must not delete a lock it
// no longer owns.
func TestReleaseDoesNotRemoveTakenOverLock(t *testing.T) {
	path := filepath.Join(t.TempDir(), "run.lock")
	release, err := Acquire(path, time.Hour)
	if err != nil {
		t.Fatal(err)
	}
	// Simulate another process taking over the lock after judging this one
	// stale: the file now holds a different owner's PID.
	if err := os.WriteFile(path, []byte("999999"), 0o644); err != nil {
		t.Fatal(err)
	}
	release()
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("lock file owned by another pid should not be removed: %v", err)
	}
}

// TestAcquireReturnsErrHeldAfterRetryExhausted forces the second create
// attempt to fail with os.ErrExist (simulating a competing process winning
// the race right after this one removed a stale lock) and asserts that
// Acquire reports ErrHeld rather than a raw "file exists" error, so callers
// can rely on errors.Is(err, ErrHeld) to detect "someone else holds it".
func TestAcquireReturnsErrHeldAfterRetryExhausted(t *testing.T) {
	path := filepath.Join(t.TempDir(), "run.lock")
	os.WriteFile(path, []byte("2147483000"), 0o644) // dead pid: first attempt is judged stale

	orig := createLock
	calls := 0
	createLock = func(p string) (func(), error) {
		calls++
		if calls == 2 {
			return nil, os.ErrExist
		}
		return orig(p)
	}
	defer func() { createLock = orig }()

	_, err := Acquire(path, time.Hour)
	if !errors.Is(err, ErrHeld) {
		t.Fatalf("want ErrHeld, got %v", err)
	}
}

// TestHeartbeatKeepsLiveLockHeld is the C1 regression: a run that legitimately
// outlives `stale` must not be taken over while its holder is alive. The
// holder refreshes the lock's mtime, so even after the file is aged past
// `stale` a competing Acquire sees a fresh heartbeat and reports ErrHeld.
func TestHeartbeatKeepsLiveLockHeld(t *testing.T) {
	orig := heartbeatInterval
	heartbeatInterval = 10 * time.Millisecond
	defer func() { heartbeatInterval = orig }()

	path := filepath.Join(t.TempDir(), "run.lock")
	release, err := Acquire(path, 50*time.Millisecond)
	if err != nil {
		t.Fatal(err)
	}
	defer release()
	old := time.Now().Add(-2 * time.Hour)
	if err := os.Chtimes(path, old, old); err != nil {
		t.Fatal(err)
	}
	time.Sleep(5 * heartbeatInterval)
	if _, err := Acquire(path, 50*time.Millisecond); !errors.Is(err, ErrHeld) {
		t.Fatalf("want ErrHeld from heartbeated lock, got %v", err)
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if time.Since(info.ModTime()) > time.Minute {
		t.Fatalf("mtime not refreshed: %s", info.ModTime())
	}
}

// TestReleaseStopsHeartbeat asserts the heartbeat goroutine exits with the
// lock: after release() the file must stay gone (no Chtimes recreating or
// touching it) and no goroutine keeps running.
func TestReleaseStopsHeartbeat(t *testing.T) {
	orig := heartbeatInterval
	heartbeatInterval = 5 * time.Millisecond
	defer func() { heartbeatInterval = orig }()

	path := filepath.Join(t.TempDir(), "run.lock")
	release, err := Acquire(path, time.Hour)
	if err != nil {
		t.Fatal(err)
	}
	before := runtime.NumGoroutine()
	release()
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatal("lock file should be removed on release")
	}
	time.Sleep(10 * heartbeatInterval)
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatal("heartbeat must not touch the lock after release")
	}
	if after := runtime.NumGoroutine(); after >= before {
		t.Fatalf("heartbeat goroutine still running: before=%d after=%d", before, after)
	}
}
