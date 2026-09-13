package main

// Everything this service knows about the Minecraft server it administers.
//
// State lives in the game server, never here: the whitelist and the operator
// list are read back from it rather than mirrored, which is what keeps a single
// writer per piece of state (ARCHITECTURE.md section 7).

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/gorcon/rcon"
)

type mcClient struct {
	addr     string
	password string
	dataDir  string
}

func newMCClient(addr, password, dataDir string) *mcClient {
	return &mcClient{addr: addr, password: password, dataDir: dataDir}
}

func (c *mcClient) configured() bool { return c.addr != "" && c.password != "" }

// exec opens a short-lived connection per command. The alternative, a pooled
// long-lived one, would have to handle the server restarting underneath it -
// and restarting is something this very API offers.
func (c *mcClient) exec(cmd string) (string, error) {
	if !c.configured() {
		return "", fmt.Errorf("RCON is not configured")
	}
	conn, err := rcon.Dial(c.addr, c.password, rcon.SetDialTimeout(5*time.Second),
		rcon.SetDeadline(10*time.Second))
	if err != nil {
		return "", fmt.Errorf("rcon dial: %w", err)
	}
	defer conn.Close()

	out, err := conn.Execute(cmd)
	if err != nil {
		return "", fmt.Errorf("rcon %q: %w", cmd, err)
	}
	return stripFormatting(out), nil
}

// Minecraft answers with section-sign colour codes; strip them so the API
// returns text rather than terminal decoration.
var colourCodes = regexp.MustCompile("§.")

func stripFormatting(s string) string {
	return strings.TrimSpace(colourCodes.ReplaceAllString(s, ""))
}

type serverStatus struct {
	Online     bool     `json:"online"`
	Players    []string `json:"players"`
	PlayerCount int     `json:"playerCount"`
	MaxPlayers int      `json:"maxPlayers"`
	Version    string   `json:"version,omitempty"`
}

var listPattern = regexp.MustCompile(`There are (\d+) of a max of (\d+) players online:?\s*(.*)`)

func (c *mcClient) status() (*serverStatus, error) {
	out, err := c.exec("list")
	if err != nil {
		return &serverStatus{Online: false}, err
	}
	st := &serverStatus{Online: true, Players: []string{}}
	if m := listPattern.FindStringSubmatch(out); m != nil {
		st.PlayerCount, _ = strconv.Atoi(m[1])
		st.MaxPlayers, _ = strconv.Atoi(m[2])
		st.Players = splitNames(m[3])
	}
	return st, nil
}

func splitNames(s string) []string {
	s = strings.TrimSpace(s)
	if s == "" {
		return []string{}
	}
	parts := strings.Split(s, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if p = strings.TrimSpace(p); p != "" {
			out = append(out, p)
		}
	}
	sort.Strings(out)
	return out
}

var whitelistPattern = regexp.MustCompile(`There are \d+ whitelisted player\(s\):\s*(.*)`)

func (c *mcClient) whitelist() ([]string, error) {
	out, err := c.exec("whitelist list")
	if err != nil {
		return nil, err
	}
	if m := whitelistPattern.FindStringSubmatch(out); m != nil {
		return splitNames(m[1]), nil
	}
	return []string{}, nil
}

// playerName guards against a name being used to smuggle a second command or a
// stray argument into the RCON line.
var playerName = regexp.MustCompile(`^[A-Za-z0-9_]{3,16}$`)

func validName(name string) error {
	if !playerName.MatchString(name) {
		return fmt.Errorf("%q is not a valid Minecraft username", name)
	}
	return nil
}

func (c *mcClient) whitelistAdd(name string) (string, error) {
	if err := validName(name); err != nil {
		return "", err
	}
	return c.exec("whitelist add " + name)
}

func (c *mcClient) whitelistRemove(name string) (string, error) {
	if err := validName(name); err != nil {
		return "", err
	}
	return c.exec("whitelist remove " + name)
}

type operator struct {
	Name  string `json:"name"`
	UUID  string `json:"uuid"`
	Level int    `json:"level"`
}

// ops are read from the server's own ops.json rather than over RCON, because
// Minecraft offers no command that lists them.
func (c *mcClient) ops() ([]operator, error) {
	if c.dataDir == "" {
		return nil, fmt.Errorf("data directory is not mounted")
	}
	b, err := os.ReadFile(filepath.Join(c.dataDir, "ops.json"))
	if err != nil {
		if os.IsNotExist(err) {
			return []operator{}, nil
		}
		return nil, err
	}
	var ops []operator
	if err := json.Unmarshal(b, &ops); err != nil {
		return nil, fmt.Errorf("parse ops.json: %w", err)
	}
	sort.Slice(ops, func(i, j int) bool { return ops[i].Name < ops[j].Name })
	return ops, nil
}

func (c *mcClient) opAdd(name string) (string, error) {
	if err := validName(name); err != nil {
		return "", err
	}
	return c.exec("op " + name)
}

func (c *mcClient) opRemove(name string) (string, error) {
	if err := validName(name); err != nil {
		return "", err
	}
	return c.exec("deop " + name)
}

// restart stops the server and lets Docker's restart policy start it again.
// See ARCHITECTURE.md section 5.4 for why this is not done via the Docker
// socket.
func (c *mcClient) restart(message string) error {
	if message != "" {
		if _, err := c.exec("say " + sanitiseMessage(message)); err != nil {
			return err
		}
	}
	_, err := c.exec("stop")
	return err
}

// sanitiseMessage keeps an announcement on one line so it cannot carry a second
// RCON command.
func sanitiseMessage(s string) string {
	s = strings.NewReplacer("\n", " ", "\r", " ").Replace(s)
	if len(s) > 200 {
		s = s[:200]
	}
	return strings.TrimSpace(s)
}
