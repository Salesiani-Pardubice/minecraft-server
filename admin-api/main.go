// Command admin-api serves the public surfaces of
// minecraft.petrkucerak.cz from the Raspberry Pi.
//
// It owns the whole hostname so that Cloudflare Tunnel has a single origin and
// path routing stays on this side: /mapa is public, /admin and /api will sit
// behind Cloudflare Access. See ARCHITECTURE.md sections 4 and 5.4.
package main

import (
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"context"
	"strings"
	"syscall"
	"time"
)

func main() {
	addr := envOr("ADDR", ":8080")
	mapDir := envOr("MAP_DIR", "/srv/map")

	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", handleHealth)
	mux.Handle("GET /mapa/", http.StripPrefix("/mapa/", noIndex(http.FileServer(http.Dir(mapDir)))))
	mux.HandleFunc("GET /mapa", redirectTo("/mapa/"))
	mux.HandleFunc("GET /{$}", redirectTo("/mapa/"))

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
	w.Header().Set("Content-Type", "application/json")
	_, _ = w.Write([]byte(`{"status":"ok"}`))
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

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
