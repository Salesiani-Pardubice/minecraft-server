package main

import (
	"os"
	"reflect"
	"testing"
)

func TestStripFormatting(t *testing.T) {
	got := stripFormatting("§aThere are §f2§a of a max of §f20§a players online:§f alice, bob")
	want := "There are 2 of a max of 20 players online: alice, bob"
	if got != want {
		t.Errorf("got %q, want %q", got, want)
	}
}

func TestListPattern(t *testing.T) {
	cases := []struct {
		in      string
		count   string
		max     string
		players []string
	}{
		{"There are 0 of a max of 20 players online: ", "0", "20", []string{}},
		{"There are 2 of a max of 20 players online: bob, alice", "2", "20", []string{"alice", "bob"}},
		{"There are 1 of a max of 20 players online: petrkucerak", "1", "20", []string{"petrkucerak"}},
	}
	for _, c := range cases {
		m := listPattern.FindStringSubmatch(c.in)
		if m == nil {
			t.Fatalf("no match for %q", c.in)
		}
		if m[1] != c.count || m[2] != c.max {
			t.Errorf("%q: counts %s/%s, want %s/%s", c.in, m[1], m[2], c.count, c.max)
		}
		if got := splitNames(m[3]); !reflect.DeepEqual(got, c.players) {
			t.Errorf("%q: players %#v, want %#v", c.in, got, c.players)
		}
	}
}

func TestWhitelistPattern(t *testing.T) {
	if m := whitelistPattern.FindStringSubmatch("There are no whitelisted players"); m != nil {
		t.Error("the empty form should not match the populated pattern")
	}
	m := whitelistPattern.FindStringSubmatch("There are 2 whitelisted player(s): alice, bob")
	if m == nil {
		t.Fatal("populated form did not match")
	}
	if got := splitNames(m[1]); !reflect.DeepEqual(got, []string{"alice", "bob"}) {
		t.Errorf("got %#v", got)
	}
}

func TestValidName(t *testing.T) {
	valid := []string{"alice", "petrkucerak", "Bob_99", "abc"}
	invalid := []string{
		"ab",                  // too short
		"seventeencharacter",  // too long
		"alice bob",           // space could smuggle an argument
		"alice; stop",         // or a second command
		"",                    // empty
		"alice\nstop",         // or a newline
	}
	for _, n := range valid {
		if err := validName(n); err != nil {
			t.Errorf("%q should be valid: %v", n, err)
		}
	}
	for _, n := range invalid {
		if err := validName(n); err == nil {
			t.Errorf("%q should be rejected", n)
		}
	}
}

func TestSanitiseMessage(t *testing.T) {
	if got := sanitiseMessage("restart\nstop"); got != "restart stop" {
		t.Errorf("newline survived: %q", got)
	}
	long := make([]byte, 300)
	for i := range long {
		long[i] = 'x'
	}
	if got := sanitiseMessage(string(long)); len(got) != 200 {
		t.Errorf("length %d, want 200", len(got))
	}
}

// Integration: runs only when pointed at a live server.
func TestAgainstLiveServer(t *testing.T) {
	addr, pw := os.Getenv("RCON_ADDR"), os.Getenv("RCON_PASSWORD")
	if addr == "" || pw == "" {
		t.Skip("RCON_ADDR/RCON_PASSWORD not set")
	}
	c := newMCClient(addr, pw, os.Getenv("MC_DATA_DIR"))

	st, err := c.status()
	if err != nil {
		t.Fatalf("status: %v", err)
	}
	t.Logf("status: online=%v players=%d/%d %v", st.Online, st.PlayerCount, st.MaxPlayers, st.Players)
	if st.MaxPlayers == 0 {
		t.Error("max players parsed as 0; the list output shape may have changed")
	}

	wl, err := c.whitelist()
	if err != nil {
		t.Fatalf("whitelist: %v", err)
	}
	t.Logf("whitelist: %v", wl)

	if os.Getenv("MC_DATA_DIR") != "" {
		ops, err := c.ops()
		if err != nil {
			t.Fatalf("ops: %v", err)
		}
		t.Logf("operators: %v", ops)
	}
}
