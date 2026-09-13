// Command admin-api serves the public surfaces of
// minecraft.salesianipardubice.cz from the Raspberry Pi.
//
// It owns the whole hostname so that Cloudflare Tunnel has a single origin and
// path routing stays on this side: /mapa is public, /admin and /api/* sit
// behind Cloudflare Access. See ARCHITECTURE.md sections 4 and 5.4.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"
)

func main() {
	addr := envOr("ADDR", ":8080")
	mapDir := envOr("MAP_DIR", "/srv/map")
	verifier := newAccessVerifier(os.Getenv("ACCESS_TEAM_DOMAIN"), os.Getenv("ACCESS_AUD"))

	if !verifier.configured() {
		log.Print("WARNING: ACCESS_TEAM_DOMAIN or ACCESS_AUD is unset - /admin and /api/* will refuse every request")
	} else {
		// Warm the key set so the first real request is not also the one
		// paying for a round trip to Cloudflare.
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		if err := verifier.refreshKeys(ctx); err != nil {
			log.Printf("could not preload Access signing keys (will retry on demand): %v", err)
		}
		cancel()
	}

	mux := http.NewServeMux()

	// Public.
	mux.HandleFunc("GET /healthz", handleHealth)
	mux.Handle("GET /mapa/", http.StripPrefix("/mapa/", noIndex(http.FileServer(http.Dir(mapDir)))))
	mux.HandleFunc("GET /mapa", redirectTo("/mapa/"))
	mux.HandleFunc("GET /{$}", redirectTo("/mapa/"))

	// Behind Cloudflare Access.
	mc := newMCClient(os.Getenv("RCON_ADDR"), os.Getenv("RCON_PASSWORD"), envOr("MC_DATA_DIR", "/srv/mcdata"))
	if !mc.configured() {
		log.Print("WARNING: RCON_ADDR or RCON_PASSWORD is unset - the API cannot reach the server")
	}
	(&api{mc: mc}).routes(mux, verifier.requireAccess)
	mux.Handle("GET /admin", verifier.requireAccess(http.HandlerFunc(handleAdmin)))

	srv := &http.Server{
		Addr:              addr,
		Handler:           logRequests(mux),
		ReadHeaderTimeout: 10 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	go func() {
		log.Printf("listening on %s, serving map from %s", addr, mapDir)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("server: %v", err)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Printf("shutdown: %v", err)
	}
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

// handleIdentity echoes the verified Access identity. It exists to answer, from
// the origin's point of view, exactly which claims Cloudflare forwarded - the
// quickest way to tell an authentication problem from an authorisation one.
func handleIdentity(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, identityFrom(r.Context()))
}

func handleAdmin(w http.ResponseWriter, r *http.Request) {
	id := identityFrom(r.Context())
	who := id.Email
	if who == "" {
		who = id.Subject
	}
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	_, _ = w.Write([]byte("Access ověřen jako " + who + ".\nAdministrace se teprve staví.\n"))
}

func redirectTo(target string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, target, http.StatusFound)
	}
}

// noIndex stops http.FileServer from rendering directory listings, which would
// otherwise expose the tile tree at /mapa/tiles/.
func noIndex(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, "/") && r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func logRequests(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		log.Printf("%s %s %s", r.Method, r.URL.Path, time.Since(start).Round(time.Millisecond))
	})
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
