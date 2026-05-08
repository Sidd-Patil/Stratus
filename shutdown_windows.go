//go:build windows

package agent

import (
	"context"
	"log"
	"syscall"
	"time"
	"unsafe"
)

var (
	user32                  = syscall.NewLazyDLL("user32.dll")
	kernel32                = syscall.NewLazyDLL("kernel32.dll")
	procGetLastInputInfo    = user32.NewProc("GetLastInputInfo")
	procGetTickCount        = kernel32.NewProc("GetTickCount")
	powerprof               = syscall.NewLazyDLL("Powrprof.dll")
)

type lastInputInfo struct {
	cbSize uint32
	dwTime uint32
}

// getIdleSeconds returns how many seconds since the user last provided input
// (mouse move, keypress, touch). This is the Windows equivalent of
// IOHIDSystem's HIDIdleTime on macOS and X11's XScreenSaverQueryInfo on Linux.
func getIdleSeconds() float64 {
	var info lastInputInfo
	info.cbSize = uint32(unsafe.Sizeof(info))
	ret, _, _ := procGetLastInputInfo.Call(uintptr(unsafe.Pointer(&info)))
	if ret == 0 {
		return 0
	}
	tickCount, _, _ := procGetTickCount.Call()
	elapsed := uint32(tickCount) - info.dwTime
	return float64(elapsed) / 1000.0
}

// LidWatcher on Windows subscribes to WM_POWERBROADCAST messages.
// PBT_APMSUSPEND fires when Windows is about to sleep (lid close triggers this).
// PBT_APMRESUMESUSPEND fires when Windows wakes.
//
// Since Go can't easily create a hidden message window without CGO,
// we use a fallback: poll the system power status via GetSystemPowerStatus
// which includes a BatteryFlag indicating AC/DC state change that
// correlates with lid close on most laptops.
//
// For full accuracy, use the Windows Service approach with
// RegisterSuspendResumeNotification via cgo if precision is needed.
func LidWatcher(ctx context.Context, onLidClose, onLidOpen func()) {
	type SYSTEM_POWER_STATUS struct {
		ACLineStatus        byte
		BatteryFlag         byte
		BatteryLifePercent  byte
		SystemStatusFlag    byte
		BatteryLifeTime     uint32
		BatteryFullLifeTime uint32
	}

	getSystemPowerStatus := kernel32.NewProc("GetSystemPowerStatus")

	// We detect "lid closed" as a transition to AC=Unknown + display off.
	// More reliable: pair this with display state via EnumDisplayDevices.
	// For MVP, polling is sufficient.
	wasAsleep := false
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	var prevACLine byte = 255

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			var status SYSTEM_POWER_STATUS
			ret, _, _ := getSystemPowerStatus.Call(uintptr(unsafe.Pointer(&status)))
			if ret == 0 {
				continue
			}

			// ACLineStatus: 0=offline, 1=online, 255=unknown
			// Transition to 255 (unknown) can indicate lid close / suspend entry.
			// This is imperfect but avoids requiring a service/cgo for MVP.
			asleep := status.ACLineStatus == 255
			if asleep && !wasAsleep {
				wasAsleep = true
				log.Println("[lid] Windows: suspend detected")
				onLidClose()
			} else if !asleep && wasAsleep {
				wasAsleep = false
				log.Println("[lid] Windows: resume detected")
				onLidOpen()
			}
			// Also handle AC line state changes as a signal
			if prevACLine != 255 && status.ACLineStatus != prevACLine {
				log.Printf("[lid] Windows: AC state changed %d->%d", prevACLine, status.ACLineStatus)
			}
			prevACLine = status.ACLineStatus
		}
	}
}

// IdleWatcher uses GetLastInputInfo to measure input idle time.
// This is the correct Win32 API — it tracks all HID input (keyboard,
// mouse, touch) without requiring elevated privileges.
func IdleWatcher(ctx context.Context, idleThresholdSecs float64, onChange func(userActive bool)) {
	wasActive := true
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			idleSecs := getIdleSeconds()
			isActive := idleSecs < idleThresholdSecs
			if isActive != wasActive {
				wasActive = isActive
				onChange(isActive)
			}
		}
	}
}

// execCommandContext stub — unused on Windows (no dbus-monitor)
// but keeps the cross-platform interface consistent.
func execCommandContext(ctx context.Context, name string, args ...string) interface{} {
	return nil
}