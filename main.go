// main.go — Agent entrypoint
package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/your-org/p2p-compute/agent"
)

func main() {
	cfgPath := "agent.json"
	if len(os.Args) > 1 {
		cfgPath = os.Args[1]
	}

	a, err := agent.NewAgent(cfgPath)
	if err != nil {
		log.Fatalf("failed to init agent: %v", err)
	}

	ctx, cancel := signal.NotifyContext(context.Background(),
		os.Interrupt, syscall.SIGTERM,
	)
	defer cancel()

	a.Run(ctx)
}