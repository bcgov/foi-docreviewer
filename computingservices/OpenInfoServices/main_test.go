package main

import (
	"testing"
)

func TestPrint(t *testing.T) {
	result, err := JoinStr("ab", "c")
	if result != "abc" || (err != nil) {
		t.Errorf("Error")
	}
}
