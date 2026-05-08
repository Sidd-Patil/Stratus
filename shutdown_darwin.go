//go:build darwin

package agent

/*
#cgo LDFLAGS: -framework IOKit -framework CoreFoundation
#include <IOKit/IOKitLib.h>
#include <IOKit/pwr_mgt/IOPM.h>
#include <IOKit/pwr_mgt/IOPMLib.h>
#include <CoreFoundation/CoreFoundation.h>

// Returns 1 if the lid is currently closed, 0 if open.
// Uses the IORegistry AppleClamshellState key.
int isLidClosed() {
    io_service_t service = IOServiceGetMatchingService(
        kIOMainPortDefault,
        IOServiceMatching("AppleSmartBattery")
    );
    if (service == IO_OBJECT_NULL) return 0;

    CFBooleanRef clamshell = (CFBooleanRef)IORegistryEntryCreateCFProperty(
        service,
        CFSTR("AppleClamshellState"),
        kCFAllocatorDefault,
        0
    );
    IOObjectRelease(service);
    if (!clamshell) return 0;
    int closed = (clamshell == kCFBooleanTrue) ? 1 : 0;
    CFRelease(clamshell);
    return closed;
}

// Returns system idle time in seconds using HIDIdleTime.
double systemIdleSeconds() {
    io_iterator_t iter = 0;
    IOServiceGetMatchingServices(kIOMainPortDefault,
        IOServiceMatching("IOHIDSystem"), &iter);
    io_registry_entry_t entry = IOIteratorNext(iter);
    IOObjectRelease(iter);
    if (entry == IO_OBJECT_NULL) return 0;

    CFMutableDictionaryRef props = NULL;
    IORegistryEntryCreateCFProperties(entry, &props, kCFAllocatorDefault, 0);
    IOObjectRelease(entry);
    if (!props) return 0;

    CFNumberRef idle = (CFNumberRef)CFDictionaryGetValue(props, CFSTR("HIDIdleTime"));
    int64_t ns = 0;
    if (idle) CFNumberGetValue(idle, kCFNumberSInt64Type, &ns);
    CFRelease(props);
    return (double)ns / 1e9;
}
*/
import "C"
import (
	"context"
	"log"
	"os/exec"
	"strings"
	"time"
)

// LidWatcher polls IORegistry for the clamshell (lid) state every 2 seconds.
// macOS does not expose a simple file for lid state the way Linux does,
// so IOKit via cgo is the correct approach here.
func LidWatcher(ctx context.Context, onLidClose, onLidOpen func()) {
	wasClosed := false
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			closed := C.isLidClosed() == 1
			if closed && !wasClosed {
				wasClosed = true
				log.Println("[lid] macOS: lid closed")
				onLidClose()
			} else if !closed && wasClosed {
				wasClosed = false
				log.Println("[lid] macOS: lid opened")
				onLidOpen()
			}
		}
	}
}

// IdleWatcher uses HIDIdleTime from IOHIDSystem to measure how long
// since the user last moved the mouse or typed. This is more reliable
// than CPU polling on macOS because the OS aggressively schedules
// background processes, making CPU usage a noisy signal.
func IdleWatcher(ctx context.Context, idleThresholdSecs float64, onChange func(userActive bool)) {
	wasActive := true
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			idleSecs := float64(C.systemIdleSeconds())
			// User is "active" if they did something in the last threshold window
			isActive := idleSecs < idleThresholdSecs
			if isActive != wasActive {
				wasActive = isActive
				onChange(isActive)
			}
		}
	}
}

// execCommandContext is a helper so Linux and Darwin share the same
// dbus-monitor call interface (on macOS it's unused but keeps the
// build happy).
func execCommandContext(ctx context.Context, name string, args ...string) *exec.Cmd {
	return exec.CommandContext(ctx, name, args...)
}

// isSleepPending checks if the system just woke from sleep using pmset.
// Called once at agent startup to handle the case where the agent
// was running when the lid closed.
func isSleepPending() bool {
	out, err := exec.Command("pmset", "-g", "assertions").Output()
	if err != nil {
		return false
	}
	return strings.Contains(string(out), "PreventUserIdleSystemSleep")
}