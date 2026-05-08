//go:build linux

package agent

import (
	"bufio"
	"context"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// LidWatcher watches for lid close events on Linux via logind D-Bus or
// the kernel's /proc/acpi/button/lid/<dev>/state fallback.
// When the lid closes, it calls onLidClose. When it reopens, onLidOpen.
func LidWatcher(ctx context.Context, onLidClose, onLidOpen func()) {
	// Prefer the /proc/acpi path — works on most laptops without D-Bus
	lidPaths, _ := filepath.Glob("/proc/acpi/button/lid/*/state")
	if len(lidPaths) == 0 {
		// No ACPI lid device found — fall back to D-Bus inhibitor
		log.Println("[lid] no ACPI lid device found, using D-Bus logind watcher")
		lidWatchDBus(ctx, onLidClose, onLidOpen)
		return
	}

	lidPath := lidPaths[0]
	lidClosed := false

	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			data, err := os.ReadFile(lidPath)
			if err != nil {
				continue
			}
			// File contains e.g. "state:      closed\n"
			closed := strings.Contains(string(data), "closed")
			if closed && !lidClosed {
				lidClosed = true
				onLidClose()
			} else if !closed && lidClosed {
				lidClosed = false
				onLidOpen()
			}
		}
	}
}

// lidWatchDBus uses org.freedesktop.login1 PrepareForSleep signal via dbus-monitor.
// This is the correct way to catch suspend/resume on systemd systems.
func lidWatchDBus(ctx context.Context, onLidClose, onLidOpen func()) {
	// Spawn dbus-monitor to listen for PrepareForSleep signals
	// True  = about to sleep (lid closed / suspend)
	// False = waking up (lid opened / resume)
	cmd := execCommandContext(ctx,
		"dbus-monitor",
		"--system",
		"type='signal',interface='org.freedesktop.login1.Manager',member='PrepareForSleep'",
	)
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		log.Println("[lid] dbus-monitor stdout pipe failed:", err)
		return
	}
	if err := cmd.Start(); err != nil {
		log.Println("[lid] dbus-monitor start failed:", err)
		return
	}

	scanner := bufio.NewScanner(stdout)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.Contains(line, "boolean true") {
			onLidClose()
		} else if strings.Contains(line, "boolean false") {
			onLidOpen()
		}
	}
}

// IdleWatcher polls /proc/stat to detect user CPU activity.
// Returns true when the user is actively using the machine (CPU > threshold).
func IdleWatcher(ctx context.Context, thresholdPct float64, onChange func(userActive bool)) {
	var prevIdle, prevTotal uint64
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()
	wasActive := false

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			idle, total, err := readCPUStat()
			if err != nil || prevTotal == 0 {
				prevIdle, prevTotal = idle, total
				continue
			}
			deltaIdle := float64(idle - prevIdle)
			deltaTotal := float64(total - prevTotal)
			prevIdle, prevTotal = idle, total

			if deltaTotal == 0 {
				continue
			}
			cpuUsage := (1 - deltaIdle/deltaTotal) * 100
			isActive := cpuUsage > thresholdPct

			if isActive != wasActive {
				wasActive = isActive
				onChange(isActive)
			}
		}
	}
}

func readCPUStat() (idle, total uint64, err error) {
	f, err := os.Open("/proc/stat")
	if err != nil {
		return 0, 0, err
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		if !strings.HasPrefix(line, "cpu ") {
			continue
		}
		// cpu  user nice system idle iowait irq softirq steal guest guest_nice
		var fields [11]uint64
		var label string
		if _, err = fmt.Sscanf(line, "%s %d %d %d %d %d %d %d %d %d %d",
			&label,
			&fields[0], &fields[1], &fields[2], &fields[3],
			&fields[4], &fields[5], &fields[6], &fields[7],
			&fields[8], &fields[9]); err != nil {
			return 0, 0, err
		}
		idle = fields[3] + fields[4] // idle + iowait
		for _, v := range fields {
			total += v
		}
		return idle, total, nil
	}
	return 0, 0, fmt.Errorf("cpu line not found in /proc/stat")
}