// Package logx writes one "MARKER key=value ..." line per event so the daily
// log file can be grepped by marker and documentid. main() redirects os.Stdout
// to that file, so Output is resolved at call time, never cached.
package logx

import (
	"fmt"
	"io"
	"os"
	"strings"
	"time"
)

// Output overrides the destination (tests); nil means os.Stdout.
var Output io.Writer

func Event(marker string, kv ...any) {
	var b strings.Builder
	b.WriteString(marker)
	for i := 0; i < len(kv); i += 2 {
		b.WriteByte(' ')
		b.WriteString(fmt.Sprint(kv[i]))
		b.WriteByte('=')
		if i+1 < len(kv) {
			b.WriteString(format(kv[i+1]))
		} else {
			b.WriteString("<missing>")
		}
	}
	b.WriteByte('\n')
	w := Output
	if w == nil {
		w = os.Stdout
	}
	io.WriteString(w, b.String())
}

func Ms(start time.Time) int64 { return time.Since(start).Milliseconds() }

func format(v any) string {
	switch x := v.(type) {
	case error:
		return quoteIfNeeded(x.Error())
	case string:
		return quoteIfNeeded(x)
	case time.Duration:
		return x.String()
	default:
		return fmt.Sprint(x)
	}
}

func quoteIfNeeded(s string) string {
	if s == "" || strings.ContainsAny(s, " \t\n\"=") {
		return fmt.Sprintf("%q", s)
	}
	return s
}
