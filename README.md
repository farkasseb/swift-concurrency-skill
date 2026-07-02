# Swift Concurrency Skill

AI skill reference for Swift 6.2–6.4 Approachable Concurrency — SE-0461, `@concurrent`, default actor isolation, isolated conformances, `await` in `defer`, task cancellation shields, migration patterns, and data-race safety guidance.

**This skill is slightly opinionated — it favors @MainActor for UI modules, nonisolated for libraries, non-Sendable types over actors where possible, and @concurrent over Task.detached. These opinions align with Apple's WWDC 2025 guidance and community consensus, but your project may warrant different choices.**

## Why this exists

Swift 6.2, 6.3, and 6.4 shipped after (or near) the training cutoff of current AI models. When you ask Claude, Codex, or Gemini about `nonisolated(nonsending)`, `@concurrent`, `await` in `defer`, or `withTaskCancellationShield`, they confidently give **wrong answers** based on older behavior.

The single most dangerous mistake: AI models believe nonisolated async functions always switch to the generic executor. Since Swift 6.2 with `NonisolatedNonsendingByDefault`, they inherit the caller's isolation instead. This changes the behavior of virtually all async code.

A second class of mistake: conflating compiler and runtime availability. Some features need only the new compiler and run on any iOS version (`await` in `defer`, `weak let`); others compile fine but crash the availability checker below a minimum OS (`Task.immediate` → iOS 26+, cancellation shields → iOS 27+). Every claim in this skill is annotated with which kind it is, verified by compile probes against the shipping toolchains and SDK interface files.

This skill gives AI coding assistants accurate, verified reference material for Swift 6.2–6.4 concurrency — including behavior changes, migration pitfalls, and design patterns that no single source covers end-to-end.

### What AI models get wrong vs. what this skill corrects

| Topic | What AI says (wrong) | What's actually true |
|-------|---------------------|----------------------|
| nonisolated async | "Runs on generic executor" | Inherits caller's isolation (with NonisolatedNonsendingByDefault) — Swift 6.2 |
| @concurrent | Doesn't know it exists | Explicit opt-in to generic executor (SE-0461, Swift 6.2) |
| Default actor isolation | Doesn't know it exists | Modules can default to @MainActor (SE-0466, Swift 6.2) |
| Isolated conformances | Doesn't know they exist | `@MainActor Equatable` constrains conformance to isolation domain (SE-0470, Swift 6.2) |
| Approachable Concurrency | Doesn't know it exists | Xcode build setting enabling NonisolatedNonsendingByDefault + InferIsolatedConformances |
| Combine + @MainActor | Suggests mixing freely | Runtime crash (`_dispatch_assert_queue_fail`) from dynamic actor isolation |
| isolated deinit | "Not yet available" | Implemented in Swift 6.2 (SE-0371) |
| await in defer | "Not allowed — use `defer { Task { } }`" | Legal in Swift 6.4 (SE-0493), any deployment target; the Task workaround is an anti-pattern |
| Ignoring cancellation | "Impossible — cancellation is final" | `withTaskCancellationShield` blocks observation (SE-0504, Swift 6.4, iOS 27+) |
| weak references in Sendable types | "weak requires var, so you can't" | `weak let` since Swift 6.3 (SE-0481) |
| `Task { try await ... }` | No issue | Warns in Swift 6.4: unused throwing task silently drops errors (SE-0520) |

## Installation

### Claude Code (as a skill)

```bash
mkdir -p ~/.claude/skills/swift-concurrency
cp SKILL.md ~/.claude/skills/swift-concurrency/
cp -r references ~/.claude/skills/swift-concurrency/
```

The skill activates automatically when your conversation involves async/await, actors, Sendable, concurrency migration, or any Swift 6.2–6.4 concurrency feature.

### Codex CLI (as agents)

```bash
mkdir -p ~/.agents/skills/swift-concurrency
cp SKILL.md ~/.agents/skills/swift-concurrency/
cp -r references ~/.agents/skills/swift-concurrency/
```

### Other AI tools (as context)

The files are plain markdown — feed them as context to any AI coding assistant. Each reference file is self-contained:

- **Swift 6.2 behavior changes**: `references/swift-6_2-changes.md`
- **Swift 6.3/6.4 changes**: `references/swift-6_3-6_4-changes.md`
- **Migration guide**: `references/migration-guide.md`
- **Isolation patterns & design**: `references/isolation-patterns.md`
- **Quick keyword reference**: `references/concurrency-glossary.md`

## File structure

```
SKILL.md                              # Router + top 7 pitfalls + decision trees + settings detection
references/
├── swift-6_2-changes.md              # SE-0461, SE-0466, SE-0470, Task.immediate, Observations, compiler settings, SPM setup
├── swift-6_3-6_4-changes.md          # await in defer, cancellation shields, weak let, ~Sendable, SE-0520 warning
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
- [SE-0493: Support async calls in defer bodies](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0493-defer-async.md)
- [SE-0504: Task Cancellation Shields](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0504-task-cancellation-shields.md)
- [SE-0520: Discardable result use in Task initializers](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0520-discardableresult-task-initializers.md)
- [SE-0481: weak let](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0481-weak-let.md)
- [SE-0472: Starting tasks synchronously from caller context](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0472-task-start-synchronously-on-caller-context.md)
- [SE-0475: Transactional observation of values](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0475-observed.md)
- [SE-0469: Task naming](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0469-task-names.md)

**Empirical verification (Jul 2026):** availability gates in the glossary matrix and the 6.3/6.4 reference were verified by compile probes against Swift 6.3.3 (Xcode 26.6) and Swift 6.4 (Xcode 27 beta 2), and by reading `@available` annotations in the iOS 27 SDK `.swiftinterface` files — not taken from proposal text alone.

**Apple sessions:**
- [What's new in Swift concurrency (WWDC 2025, session 268)](https://developer.apple.com/videos/play/wwdc2025/268/) — Doug Gregor's progressive disclosure model, @concurrent, recommended settings

**Community sources (public blogs):**
- [Matt Massicotte](https://massicotte.org) — isolation intuition, non-sendable first design, Combine annotations, `@preconcurrency` guide, default isolation analysis, concurrency glossary
- [Use Your Loaf](https://useyourloaf.com/blog/approachable-concurrency-in-swift-packages/) — SPM Approachable Concurrency setup
- [Antoine van der Lee](https://www.avanderlee.com/concurrency/approachable-concurrency-in-swift-6-2-a-clear-guide/) — Approachable Concurrency clear guide
- [apple/swift-async-algorithms](https://github.com/apple/swift-async-algorithms) — AsyncSequence algorithms as Combine replacement

## Evals

`evals/evals.json` contains 6 benchmark prompts with graded assertions. Each targets a post-training-cutoff knowledge delta (not reasoning ability): a competent model without the skill gives a confidently wrong answer from stale knowledge — "you can't await in defer", "withTaskCancellationShield works on iOS 18", "weak let has been there since 5.9". Assertions grade two objective dimensions: correct version gate and correct deployment-target story. Run them by giving each prompt to a model with and without skill access (forbid web/documentation lookup so the delta measures the skill).

## Contributing

Found an inaccuracy, a missing SE proposal detail, or have experience migrating to Swift 6.2–6.4? PRs welcome. Please include the source (SE proposal URL, WWDC session timestamp, or your own migration experience) for any additions.
