package main

// Verification of Cloudflare Access JWTs.
//
// ARCHITECTURE.md section 14: the API verifies the assertion rather than
// assuming that traffic arriving on the tunnel came through Access. The
// difference matters because cloudflared routes the whole hostname here, so a
// misconfigured or absent Access policy would otherwise leave these paths open.
//
// Everything here fails closed. A missing audience, an unreachable key set, an
// absent header or a signature that does not check out all produce a refusal,
// never a pass.

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"math/big"
	"crypto/rsa"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

type identity struct {
	Email    string   `json:"email"`
	Subject  string   `json:"sub"`
	Name     string   `json:"name,omitempty"`
	Groups   []string `json:"groups,omitempty"`
	Issuer   string   `json:"iss"`
	Audience []string `json:"aud"`
	IssuedAt int64    `json:"iat"`
	Expires  int64    `json:"exp"`
	// Custom carries every remaining claim, so an operator can see exactly what
	// the identity provider returned - which is the fastest way to debug a
	// policy that authenticates but refuses to authorise.
	Custom map[string]any `json:"custom,omitempty"`
}

type accessVerifier struct {
	teamDomain string
	audience   string
	issuer     string

	mu        sync.RWMutex
	keys      map[string]*rsa.PublicKey
	fetchedAt time.Time
}

var errNotConfigured = errors.New("access verification is not configured")

func newAccessVerifier(teamDomain, audience string) *accessVerifier {
	return &accessVerifier{
		teamDomain: teamDomain,
		audience:   audience,
		issuer:     "https://" + teamDomain,
		keys:       map[string]*rsa.PublicKey{},
	}
}

func (v *accessVerifier) configured() bool {
	return v.teamDomain != "" && v.audience != ""
}

// refreshKeys pulls the team's signing keys. Cloudflare rotates them, so the
// set is refetched when a token presents an unknown key id, rate-limited to
// avoid turning a bad token into a request amplifier.
func (v *accessVerifier) refreshKeys(ctx context.Context) error {
	v.mu.RLock()
	recent := time.Since(v.fetchedAt) < time.Minute
	v.mu.RUnlock()
	if recent {
		return nil
	}

	url := fmt.Sprintf("https://%s/cdn-cgi/access/certs", v.teamDomain)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return err
	}
	resp, err := (&http.Client{Timeout: 10 * time.Second}).Do(req)
	if err != nil {
		return fmt.Errorf("fetch access certs: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("fetch access certs: status %d", resp.StatusCode)
	}

	var doc struct {
		Keys []struct {
			Kid string `json:"kid"`
			Kty string `json:"kty"`
			N   string `json:"n"`
			E   string `json:"e"`
		} `json:"keys"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&doc); err != nil {
		return fmt.Errorf("decode access certs: %w", err)
	}

	keys := map[string]*rsa.PublicKey{}
	for _, k := range doc.Keys {
		if k.Kty != "RSA" || k.Kid == "" {
			continue
		}
		n, err := base64.RawURLEncoding.DecodeString(k.N)
		if err != nil {
			continue
		}
		e, err := base64.RawURLEncoding.DecodeString(k.E)
		if err != nil {
			continue
		}
		keys[k.Kid] = &rsa.PublicKey{
			N: new(big.Int).SetBytes(n),
			E: int(new(big.Int).SetBytes(e).Int64()),
		}
	}
	if len(keys) == 0 {
		return errors.New("access certs contained no usable RSA keys")
	}

	v.mu.Lock()
	v.keys, v.fetchedAt = keys, time.Now()
	v.mu.Unlock()
	return nil
}

func (v *accessVerifier) keyFor(kid string) (*rsa.PublicKey, bool) {
	v.mu.RLock()
	defer v.mu.RUnlock()
	k, ok := v.keys[kid]
	return k, ok
}

// verify checks the assertion and returns the identity it carries.
func (v *accessVerifier) verify(ctx context.Context, raw string) (*identity, error) {
	if !v.configured() {
		return nil, errNotConfigured
	}
	if raw == "" {
		return nil, errors.New("no access assertion present")
	}

	keyfunc := func(t *jwt.Token) (any, error) {
		kid, _ := t.Header["kid"].(string)
		if kid == "" {
			return nil, errors.New("token has no key id")
		}
		if k, ok := v.keyFor(kid); ok {
			return k, nil
		}
		if err := v.refreshKeys(ctx); err != nil {
			return nil, err
		}
		if k, ok := v.keyFor(kid); ok {
			return k, nil
		}
		return nil, fmt.Errorf("unknown key id %q", kid)
	}

	claims := jwt.MapClaims{}
	// RS256 is pinned rather than read from the token header, which is what
	// makes algorithm-confusion and alg=none irrelevant here.
	_, err := jwt.ParseWithClaims(raw, claims, keyfunc,
		jwt.WithValidMethods([]string{"RS256"}),
		jwt.WithIssuer(v.issuer),
		jwt.WithAudience(v.audience),
		jwt.WithExpirationRequired(),
	)
	if err != nil {
		return nil, err
	}
	return identityFromClaims(claims), nil
}

func identityFromClaims(c jwt.MapClaims) *identity {
	id := &identity{Custom: map[string]any{}}
	for k, val := range c {
		switch k {
		case "email":
			id.Email, _ = val.(string)
		case "sub":
			id.Subject, _ = val.(string)
		case "name":
			id.Name, _ = val.(string)
		case "iss":
			id.Issuer, _ = val.(string)
		case "iat":
			id.IssuedAt = toUnix(val)
		case "exp":
			id.Expires = toUnix(val)
		case "aud":
			id.Audience = toStrings(val)
		case "groups":
			id.Groups = toStrings(val)
		default:
			id.Custom[k] = val
		}
	}
	return id
}

func toUnix(v any) int64 {
	if f, ok := v.(float64); ok {
		return int64(f)
	}
	return 0
}

func toStrings(v any) []string {
	switch t := v.(type) {
	case string:
		return []string{t}
	case []any:
		out := make([]string, 0, len(t))
		for _, e := range t {
			if s, ok := e.(string); ok {
				out = append(out, s)
			}
		}
		return out
	}
	return nil
}

// assertionFrom reads the token from the header cloudflared sets, falling back
// to the cookie a browser carries.
func assertionFrom(r *http.Request) string {
	if h := r.Header.Get("Cf-Access-Jwt-Assertion"); h != "" {
		return h
	}
	if c, err := r.Cookie("CF_Authorization"); err == nil {
		return c.Value
	}
	if a := r.Header.Get("Authorization"); strings.HasPrefix(a, "Bearer ") {
		return strings.TrimPrefix(a, "Bearer ")
	}
	return ""
}

type identityKey struct{}

func identityFrom(ctx context.Context) *identity {
	id, _ := ctx.Value(identityKey{}).(*identity)
	return id
}

// requireAccess gates a handler behind a verified Access assertion.
func (v *accessVerifier) requireAccess(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !v.configured() {
			log.Printf("refusing %s: ACCESS_TEAM_DOMAIN/ACCESS_AUD not set", r.URL.Path)
			writeError(w, http.StatusServiceUnavailable,
				"Access verification is not configured on the server, so protected routes are closed.")
			return
		}
		id, err := v.verify(r.Context(), assertionFrom(r))
		if err != nil {
			log.Printf("refusing %s: %v", r.URL.Path, err)
			writeError(w, http.StatusForbidden, "Cloudflare Access assertion missing or invalid.")
			return
		}
		next.ServeHTTP(w, r.WithContext(context.WithValue(r.Context(), identityKey{}, id)))
	})
}

func writeError(w http.ResponseWriter, code int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(map[string]string{"error": msg})
}
