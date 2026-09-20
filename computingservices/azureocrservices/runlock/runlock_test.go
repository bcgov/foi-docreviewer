package runlock

import (
	"errors"
	"os"
	"path/filepath"
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
