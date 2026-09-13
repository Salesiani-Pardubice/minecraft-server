package main

// The JSON API behind Cloudflare Access. Every handler here is reached only
// through accessVerifier.requireAccess, and every mutation is logged with the
// identity that made it.

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
)

type api struct {
	mc *mcClient
}

func (a *api) routes(mux *http.ServeMux, guard func(http.Handler) http.Handler) {
	h := func(fn http.HandlerFunc) http.Handler { return guard(fn) }

	mux.Handle("GET /api/identity", h(handleIdentity))
	mux.Handle("GET /api/status", h(a.status))
	mux.Handle("GET /api/whitelist", h(a.whitelistList))
	mux.Handle("POST /api/whitelist", h(a.whitelistAdd))
	mux.Handle("DELETE /api/whitelist/{name}", h(a.whitelistRemove))
	mux.Handle("GET /api/ops", h(a.opsList))
	mux.Handle("POST /api/ops", h(a.opsAdd))
	mux.Handle("DELETE /api/ops/{name}", h(a.opsRemove))
	mux.Handle("POST /api/restart", h(a.restart))
}

func (a *api) status(w http.ResponseWriter, r *http.Request) {
	st, err := a.mc.status()
	if err != nil {
		// A server that is down is a fact to report, not a failure of this API.
		writeJSON(w, http.StatusOK, map[string]any{
			"online": false,
			"error":  err.Error(),
		})
		return
	}
	writeJSON(w, http.StatusOK, st)
}

func (a *api) whitelistList(w http.ResponseWriter, r *http.Request) {
	names, err := a.mc.whitelist()
	if err != nil {
		writeError(w, http.StatusBadGateway, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"players": names})
}

type nameRequest struct {
	Name string `json:"name"`
}

func decodeName(r *http.Request) (string, error) {
	var req nameRequest
	if err := json.NewDecoder(http.MaxBytesReader(nil, r.Body, 4096)).Decode(&req); err != nil {
		return "", err
	}
	return strings.TrimSpace(req.Name), nil
}

func (a *api) whitelistAdd(w http.ResponseWriter, r *http.Request) {
	name, err := decodeName(r)
	if err != nil {
		writeError(w, http.StatusBadRequest, "expected a JSON body with a name field")
		return
	}
	out, err := a.mc.whitelistAdd(name)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	audit(r, "whitelist add %s", name)
	writeJSON(w, http.StatusOK, map[string]string{"result": out})
}

func (a *api) whitelistRemove(w http.ResponseWriter, r *http.Request) {
	name := r.PathValue("name")
	out, err := a.mc.whitelistRemove(name)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	audit(r, "whitelist remove %s", name)
	writeJSON(w, http.StatusOK, map[string]string{"result": out})
}

func (a *api) opsList(w http.ResponseWriter, r *http.Request) {
	ops, err := a.mc.ops()
	if err != nil {
		writeError(w, http.StatusBadGateway, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"operators": ops})
}

func (a *api) opsAdd(w http.ResponseWriter, r *http.Request) {
	name, err := decodeName(r)
	if err != nil {
		writeError(w, http.StatusBadRequest, "expected a JSON body with a name field")
		return
	}
	out, err := a.mc.opAdd(name)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	audit(r, "op add %s", name)
	writeJSON(w, http.StatusOK, map[string]string{"result": out})
}

func (a *api) opsRemove(w http.ResponseWriter, r *http.Request) {
	name := r.PathValue("name")
	out, err := a.mc.opRemove(name)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	// Worth stating in the log: if this name is still in the compose OPS list
	// it will come back on the next restart. See ARCHITECTURE.md section 7.
	audit(r, "op remove %s (check OPS: in docker-compose.yml)", name)
	writeJSON(w, http.StatusOK, map[string]string{"result": out})
}

func (a *api) restart(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Message string `json:"message"`
	}
	_ = json.NewDecoder(http.MaxBytesReader(nil, r.Body, 4096)).Decode(&req)

	audit(r, "restart (%q)", req.Message)
	if err := a.mc.restart(req.Message); err != nil {
		writeError(w, http.StatusBadGateway, err.Error())
		return
	}
	writeJSON(w, http.StatusAccepted, map[string]string{
		"result": "Server se zastavuje; Docker ho nastartuje zpátky.",
	})
}

// audit records who did what. There is no separate audit store: these land in
// the container log alongside everything else, which is where an operator
// already looks.
func audit(r *http.Request, format string, args ...any) {
	id := identityFrom(r.Context())
	who := "unknown"
	if id != nil {
		if who = id.Email; who == "" {
			who = id.Subject
		}
	}
	log.Printf("AUDIT %s: %s", who, fmt.Sprintf(format, args...))
}
