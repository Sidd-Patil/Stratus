// agent.go — Core P2P Compute Agent
// Compiles to a single binary on Windows, macOS, Linux.
// Run: go build -o agent ./...
//
// The agent:
//   1. Heartbeats resource availability to the Controller API
//   2. Watches for lid close / user activity events (platform-specific)
//   3. Throttles or pauses Docker containers gracefully on state changes
//   4. Resumes containers when the owner is gone / lid is open

package agent

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/exec"
	"runtime"
	"strings"
	"time"

	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/mem"
)

// Config is loaded from agent.json at startup.
type Config struct {
	ControllerURL   string  `json:"controller_url"`   // e.g. "http://controller.tailnet:8080"
	NodeName        string  `json:"node_name"`        // e.g. "alice"
	IdleThresholdS  float64 `json:"idle_threshold_s"` // seconds of inactivity = "idle"
	CPUCapActive    float64 `json:"cpu_cap_active"`   // CPU limit when owner is active (e.g. 0.5 cores)
	CPUCapIdle      float64 `json:"cpu_cap_idle"`     // CPU limit when owner is idle (e.g. 2.0 cores)
	HeartbeatSecs   int     `json:"heartbeat_secs"`   // how often to report to controller
}

// ContainerState represents what we want containers to be doing.
type ContainerState int

const (
	StateRunningFull    ContainerState = iota // owner idle — full resource cap
	StateRunningThrottle                       // owner active — reduced cap
	StatePaused                                // lid closed — fully paused
)

type Agent struct {
	cfg            Config
	containerState ContainerState
	activeContainers []string // container IDs we manage
}

func NewAgent(cfgPath string) (*Agent, error) {
	data, err := os.ReadFile(cfgPath)
	if err != nil {
		return nil, fmt.Errorf("reading config: %w", err)
	}
	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("parsing config: %w", err)
	}
	if cfg.IdleThresholdS == 0 {
		cfg.IdleThresholdS = 120 // 2 minutes default
	}
	if cfg.HeartbeatSecs == 0 {
		cfg.HeartbeatSecs = 15
	}
	return &Agent{cfg: cfg, containerState: StateRunningFull}, nil
}

// Run starts all agent loops. Blocks until ctx is cancelled.
func (a *Agent) Run(ctx context.Context) {
	log.Printf("[agent] starting on %s (%s)", a.cfg.NodeName, runtime.GOOS)

	// Start heartbeat loop
	go a.heartbeatLoop(ctx)

	// Wire up lid watcher (platform-specific)
	go LidWatcher(ctx,
		func() {
			// Lid closed — pause all containers immediately
			log.Println("[agent] lid closed → pausing containers")
			a.setContainerState(StatePaused)
			a.reportEvent("lid_closed")
		},
		func() {
			// Lid opened — resume to throttled state until we confirm owner is idle
			log.Println("[agent] lid opened → resuming throttled")
			a.setContainerState(StateRunningThrottle)
			a.reportEvent("lid_opened")
		},
	)

	// Wire up idle watcher (platform-specific)
	go IdleWatcher(ctx, a.cfg.IdleThresholdS,
		func(userActive bool) {
			// Don't override a lid-close pause
			if a.containerState == StatePaused {
				return
			}
			if userActive {
				log.Println("[agent] user active → throttling containers")
				a.setContainerState(StateRunningThrottle)
				a.reportEvent("user_active")
			} else {
				log.Println("[agent] user idle → full resources")
				a.setContainerState(StateRunningFull)
				a.reportEvent("user_idle")
			}
		},
	)

	// Block until context cancelled
	<-ctx.Done()
	log.Println("[agent] shutting down — pausing all containers")
	a.pauseAll()
}

// setContainerState transitions all managed containers to the new state.
// It first discovers running containers with our label, then applies changes.
func (a *Agent) setContainerState(next ContainerState) {
	if next == a.containerState {
		return
	}
	a.containerState = next

	containers, err := a.listManagedContainers()
	if err != nil {
		log.Println("[agent] error listing containers:", err)
		return
	}

	switch next {
	case StatePaused:
		for _, id := range containers {
			if err := dockerExec("pause", id); err != nil {
				log.Printf("[agent] pause %s: %v", id, err)
			}
		}

	case StateRunningThrottle:
		for _, id := range containers {
			// First unpause if it was paused
			dockerExec("unpause", id) // ignore error — may not be paused
			// Then apply reduced CPU cap
			if err := dockerExec("update",
				"--cpus", fmt.Sprintf("%.1f", a.cfg.CPUCapActive),
				id,
			); err != nil {
				log.Printf("[agent] throttle %s: %v", id, err)
			}
		}

	case StateRunningFull:
		for _, id := range containers {
			dockerExec("unpause", id)
			if err := dockerExec("update",
				"--cpus", fmt.Sprintf("%.1f", a.cfg.CPUCapIdle),
				id,
			); err != nil {
				log.Printf("[agent] full-cap %s: %v", id, err)
			}
		}
	}
}

// listManagedContainers returns IDs of containers started by this agent
// (identified by the label "managed-by=p2p-agent").
func (a *Agent) listManagedContainers() ([]string, error) {
	out, err := exec.Command("docker", "ps", "-q",
		"--filter", "label=managed-by=p2p-agent",
	).Output()
	if err != nil {
		return nil, err
	}
	ids := []string{}
	for _, line := range strings.Split(strings.TrimSpace(string(out)), "\n") {
		if line != "" {
			ids = append(ids, line)
		}
	}
	return ids, nil
}

func (a *Agent) pauseAll() {
	containers, err := a.listManagedContainers()
	if err != nil {
		return
	}
	for _, id := range containers {
		dockerExec("pause", id)
	}
}

// Heartbeat payload sent to the Controller every HeartbeatSecs seconds.
type HeartbeatPayload struct {
	Node           string         `json:"node"`
	OS             string         `json:"os"`
	CPUFreePercent float64        `json:"cpu_free_pct"`
	RAMFreeMB      int64          `json:"ram_free_mb"`
	ContainerState string         `json:"container_state"`
	Timestamp      time.Time      `json:"ts"`
}

func (a *Agent) heartbeatLoop(ctx context.Context) {
	ticker := time.NewTicker(time.Duration(a.cfg.HeartbeatSecs) * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := a.sendHeartbeat(); err != nil {
				log.Println("[agent] heartbeat error:", err)
			}
		}
	}
}

func (a *Agent) sendHeartbeat() error {
	payload := HeartbeatPayload{
		Node:           a.cfg.NodeName,
		OS:             runtime.GOOS,
		CPUFreePercent: getCPUFree(),
		RAMFreeMB:      getRAMFreeMB(),
		ContainerState: stateLabel(a.containerState),
		Timestamp:      time.Now().UTC(),
	}
	body, _ := json.Marshal(payload)
	resp, err := http.Post(
		a.cfg.ControllerURL+"/api/v1/heartbeat",
		"application/json",
		bytes.NewReader(body),
	)
	if err != nil {
		return err
	}
	resp.Body.Close()
	return nil
}

func (a *Agent) reportEvent(event string) {
	type EventPayload struct {
		Node  string `json:"node"`
		Event string `json:"event"`
		TS    time.Time `json:"ts"`
	}
	payload := EventPayload{Node: a.cfg.NodeName, Event: event, TS: time.Now().UTC()}
	body, _ := json.Marshal(payload)
	resp, err := http.Post(
		a.cfg.ControllerURL+"/api/v1/events",
		"application/json",
		bytes.NewReader(body),
	)
	if err != nil {
		log.Println("[agent] event report error:", err)
		return
	}
	resp.Body.Close()
}

// dockerExec runs `docker <args>` and returns any error.
func dockerExec(args ...string) error {
	cmd := exec.Command("docker", args...)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("%w: %s", err, string(out))
	}
	return nil
}

func stateLabel(s ContainerState) string {
	switch s {
	case StateRunningFull:
		return "running_full"
	case StateRunningThrottle:
		return "running_throttle"
	case StatePaused:
		return "paused"
	default:
		return "unknown"
	}
}

// getCPUFree returns the percentage of CPU not currently in use.
// Samples over 500ms for a stable reading — gopsutil handles
// Windows/macOS/Linux differences internally.
func getCPUFree() float64 {
	percents, err := cpu.Percent(500*time.Millisecond, false)
	if err != nil || len(percents) == 0 {
		log.Println("[agent] cpu.Percent error:", err)
		return 0
	}
	return 100 - percents[0]
}

// getRAMFreeMB returns available (not just free) RAM in megabytes.
// "Available" includes memory the OS can reclaim from caches — more
// useful than raw "free" for deciding how much to offer the pool.
func getRAMFreeMB() int64 {
	v, err := mem.VirtualMemory()
	if err != nil {
		log.Println("[agent] mem.VirtualMemory error:", err)
		return 0
	}
	return int64(v.Available / 1024 / 1024)
}