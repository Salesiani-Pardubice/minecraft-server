package main

import (
	_ "embed"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// The landmarks scattered over the map, written by build/landmarks.py from
// the same table the builds are put up from - so what the map marks and what
// is standing cannot drift apart. It is embedded rather than read from disk
// because ./data is not in the repository and these coordinates are.
//
//go:embed landmarks.json
var landmarksJSON []byte

type landmark struct {
	Name  string `json:"name"`
	X     int    `json:"x"`
	Z     int    `json:"z"`
	Label string `json:"label"`
	Note  string `json:"note"`
}

// The icon is served by handleLandmarkIcon at the path squaremap's front end
// builds for this key.
const landmarkIcon = "squaremap-landmark"

func landmarkLayer() (json.RawMessage, error) {
	var marks []landmark
	if err := json.Unmarshal(landmarksJSON, &marks); err != nil {
		return nil, err
	}
	icons := make([]any, 0, len(marks))
	for _, m := range marks {
		tooltip := m.Label
		if m.Note != "" {
			tooltip = m.Label + " – " + m.Note
		}
		icons = append(icons, map[string]any{
			"type":           "icon",
			"point":          map[string]int{"x": m.X, "z": m.Z},
			"icon":           landmarkIcon,
			"size":           map[string]int{"x": 16, "z": 16},
			"anchor":         map[string]int{"x": 8, "z": 8},
			"tooltip_anchor": map[string]int{"x": 0, "z": -8},
			"tooltip":        tooltip,
		})
	}
	return json.Marshal(map[string]any{
		"id":        "landmarks",
		"name":      "Stavby",
		"control":   true,
		"hide":      false,
		"z_index":   2,
		"order":     2,
		"markers":   icons,
		"timestamp": time.Now().UnixMilli(),
	})
}

// handleMarkers serves squaremap's marker file for one world with our layer
// added to it. The plugin rewrites that file every time it updates the map,
// so the layer is merged on the way out rather than written into it.
func handleMarkers(mapDir string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		world := r.PathValue("world")
		if world == "" || strings.ContainsAny(world, `/\.`) {
			http.NotFound(w, r)
			return
		}
		raw, err := os.ReadFile(filepath.Join(mapDir, "tiles", world, "markers.json"))
		if err != nil {
			http.NotFound(w, r)
			return
		}
		var layers []json.RawMessage
		if err := json.Unmarshal(raw, &layers); err != nil {
			// Whatever squaremap wrote, serve it: a marker layer of ours is
			// not worth breaking the map over.
			log.Printf("markers.json for %s did not parse: %v", world, err)
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write(raw)
			return
		}
		if world == "minecraft_overworld" {
			layer, err := landmarkLayer()
			if err != nil {
				log.Printf("could not build the landmark layer: %v", err)
			} else {
				layers = append(layers, layer)
			}
		}
		writeJSON(w, http.StatusOK, layers)
	}
}

func handleLandmarkIcon(w http.ResponseWriter, r *http.Request) {
	png, err := adminUI.ReadFile("web/landmark.png")
	if err != nil {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "image/png")
	w.Header().Set("Cache-Control", "public, max-age=86400")
	_, _ = w.Write(png)
}
