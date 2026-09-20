// Package runlock stops two scheduled runs from consuming the same ActiveMQ
// queue at once. The lock is a file created with O_EXCL holding the owner's
// PID; a lock whose PID is dead, or whose mtime is older than `stale`, is
// taken over so a crash never wedges the scheduler.
package runlock

import (
	"errors"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"azureocrservice/logx"
)

var ErrHeld = errors.New("run lock held by a live process")

func Acquire(path string, stale time.Duration) (release func(), err error) {
	for attempt := 0; attempt < 2; attempt++ {
		release, err = createLock(path)
		if err == nil {
			return release, nil
		}
		if !errors.Is(err, os.ErrExist) {
			return nil, fmt.Errorf("create lock %s: %w", path, err)
		}
		pid, age, readErr := inspect(path)
		if readErr == nil && pidAlive(pid) && age <= stale {
			return nil, fmt.Errorf("%w: pid=%d age=%s", ErrHeld, pid, age.Truncate(time.Second))
		}
		logx.Event("RUNLOCK_STALE", "path", path, "pid", pid, "age", age.Truncate(time.Second))
		if rmErr := os.Remove(path); rmErr != nil && !os.IsNotExist(rmErr) {
			return nil, fmt.Errorf("remove stale lock %s: %w", path, rmErr)
		}
	}
	// Retry budget exhausted while a competitor kept winning the create
	// race: report this the same way as a live, unexpired holder.
	return nil, fmt.Errorf("%w: %s", ErrHeld, path)
}

// createLock is a package var so tests can force the race where a competing
// process wins the create right after this one judged the existing lock
// stale, without changing the public API.
var createLock = func(path string) (func(), error) {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o644)
	if err != nil {
		return nil, err
	}
	pid := os.Getpid()
	_, werr := f.WriteString(strconv.Itoa(pid))
	f.Close()
	if werr != nil {
		os.Remove(path)
		return nil, werr
	}
	return func() { releaseIfOwned(path, pid) }, nil
}

// releaseIfOwned removes the lock file only if it still holds the PID that
// created it. If another process has since taken the lock over, the file
// belongs to that process and must be left alone.
func releaseIfOwned(path string, pid int) {
	body, err := os.ReadFile(path)
	if err != nil {
		return
	}
	owner, err := strconv.Atoi(strings.TrimSpace(string(body)))
	if err != nil || owner != pid {
		return
	}
	os.Remove(path)
}

// inspect returns the PID stored in the lock and the lock's age. A body that
// is not a PID yields an error so the caller treats the lock as stale.
func inspect(path string) (pid int, age time.Duration, err error) {
	info, err := os.Stat(path)
	if err != nil {
		return 0, 0, err
	}
	age = time.Since(info.ModTime())
	body, err := os.ReadFile(path)
	if err != nil {
		return 0, age, err
	}
	pid, err = strconv.Atoi(strings.TrimSpace(string(body)))
	return pid, age, err
}
