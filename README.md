# Swift Concurrency Skill

AI skill reference for Swift 6.2 Approachable Concurrency — SE-0461, `@concurrent`, default actor isolation, isolated conformances, migration patterns, and data-race safety guidance.

**This skill is slightly opinionated — it favors @MainActor for UI modules, nonisolated for libraries, non-Sendable types over actors where possible, and @concurrent over Task.detached. These opinions align with Apple's WWDC 2025 guidance and community consensus, but your project may warrant different choices.**

## Why this exists

Swift 6.2 shipped after the training cutoff of current AI models. When you ask Claude, Codex, or Gemini about `nonisolated(nonsending)`, `@concurrent`, or `InferIsolatedConformances`, they confidently give **wrong answers** based on pre-SE-0461 behavior.

The single most dangerous mistake: AI models believe nonisolated async functions always switch to the generic executor. Since Swift 6.2 with `NonisolatedNonsendingByDefault`, they inherit the caller's isolation instead. This changes the behavior of virtually all async code.

This skill gives AI coding assistants accurate, verified reference material for Swift 6.2 concurrency — including behavior changes, migration pitfalls, and design patterns that no single source covers end-to-end.

### What AI models get wrong vs. what this skill corrects

| Topic | What AI says (wrong) | What's actually true (Swift 6.2) |
|-------|---------------------|----------------------------------|
| nonisolated async | "Runs on generic executor" | Inherits caller's isolation (with NonisolatedNonsendingByDefault) |
| @concurrent | Doesn't know it exists | Explicit opt-in to generic executor (SE-0461) |
| Default actor isolation | Doesn't know it exists | Modules can default to @MainActor (SE-0466) |
| Isolated conformances | Doesn't know they exist | `@MainActor Equatable` constrains conformance to isolation domain (SE-0470) |
| Approachable Concurrency | Doesn't know it exists | Xcode build setting enabling NonisolatedNonsendingByDefault + InferIsolatedConformances |
| Combine + @MainActor | Suggests mixing freely | Runtime crash (`_dispatch_assert_queue_fail`) from dynamic actor isolation |
| isolated deinit | "Not yet available" | Implemented in Swift 6.2 (SE-0371) |

## Installation

### Claude Code (as a skill)

```bash
mkdir -p ~/.claude/skills/swift-concurrency
cp SKILL.md ~/.claude/skills/swift-concurrency/
cp -r references ~/.claude/skills/swift-concurrency/
```

The skill activates automatically when your conversation involves async/await, actors, Sendable, concurrency migration, or any Swift 6.2 concurrency feature.

### Codex CLI (as agents)

```bash
mkdir -p ~/.agents/skills/swift-concurrency
cp SKILL.md ~/.agents/skills/swift-concurrency/
cp -r references ~/.agents/skills/swift-concurrency/
```

### Other AI tools (as context)

The files are plain markdown — feed them as context to any AI coding assistant. Each reference file is self-contained:

- **Swift 6.2 behavior changes**: `references/swift-6_2-changes.md`
- **Migration guide**: `references/migration-guide.md`
- **Isolation patterns & design**: `references/isolation-patterns.md`
- **Quick keyword reference**: `references/concurrency-glossary.md`

## File structure

```
SKILL.md                              # Router + top 5 pitfalls + decision trees + settings detection
references/
├── swift-6_2-changes.md              # SE-0461, SE-0466, SE-0470, compiler settings, SPM setup
├── migration-guide.md                # Step-by-step migration, Combine crash, @preconcurrency, escape hatches
├── isolation-patterns.md             # Non-Sendable First Design, actors vs Mutex, reentrancy, testing, AsyncAlgorithms
└── concurrency-glossary.md           # Every keyword/attribute with SE proposal numbers + version matrix
```

## Sources

Synthesized from primary sources and verified against SE proposals:

**Swift Evolution proposals (full text verified):**
- [SE-0461: Run nonisolated async functions on the caller's actor by default](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0461-async-function-isolation.md)
- [SE-0466: Control default actor isolation inference](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0466-control-default-actor-isolation.md)
- [SE-0470: Global-actor isolated conformances](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0470-isolated-conformances.md)
- [SE-0414: Region based Isolation](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0414-region-based-isolation.md)
- [SE-0430: sending parameter and result values](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0430-transferring-parameters-and-results.md)
- [SE-0433: Synchronous Mutual Exclusion Lock (Mutex)](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0433-mutex.md)
- [SE-0434: Usability of global-actor-isolated types](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0434-global-actor-isolated-types-usability.md)
- [SE-0371: Isolated synchronous deinit](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0371-isolated-synchronous-deinit.md)

**Apple sessions:**
- [What's new in Swift concurrency (WWDC 2025, session 268)](https://developer.apple.com/videos/play/wwdc2025/268/) — Doug Gregor's progressive disclosure model, @concurrent, recommended settings

**Community sources (public blogs):**
- [Matt Massicotte](https://massicotte.org) — isolation intuition, non-sendable first design, Combine annotations, `@preconcurrency` guide, default isolation analysis, concurrency glossary
- [Use Your Loaf](https://useyourloaf.com/blog/approachable-concurrency-in-swift-packages/) — SPM Approachable Concurrency setup
- [Antoine van der Lee](https://www.avanderlee.com/concurrency/approachable-concurrency-in-swift-6-2-a-clear-guide/) — Approachable Concurrency clear guide
- [apple/swift-async-algorithms](https://github.com/apple/swift-async-algorithms) — AsyncSequence algorithms as Combine replacement

## Contributing

Found an inaccuracy, a missing SE proposal detail, or have experience migrating to Swift 6.2? PRs welcome. Please include the source (SE proposal URL, WWDC session timestamp, or your own migration experience) for any additions.
