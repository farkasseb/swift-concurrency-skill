# Swift Concurrency Skill

An agent skill for Swift 6.2-6.4 concurrency: where async code runs under the new defaults, how to fix data-race diagnostics, and which new APIs need the compiler versus a minimum OS. It follows the [Agent Skills](https://agentskills.io) format and works with any agent that loads `SKILL.md` skills, including Claude Code and OpenAI Codex CLI.

The skill is opinionated in a few places: `@MainActor` for app and UI modules, nonisolated APIs for libraries, plain non-Sendable types before actors, and `@concurrent` over `Task.detached`. These follow Apple's WWDC 2025 guidance, but your project may warrant different choices.

## Why it exists

Swift 6.2, 6.3, and 6.4 changed behavior that models learned from older material:

- With `NonisolatedNonsendingByDefault`, a nonisolated `async` function runs on the caller's actor instead of leaving it. Whether that applies depends on build settings, so the skill starts by reading them.
- New Xcode 26 and 27 app templates use Swift 5 language mode with Approachable Concurrency and default MainActor isolation, which changes the answer to "where does this run".
- Some additions need only the new compiler (`await` in `defer`, `weak let`, `~Sendable`); others need a new OS (`Task.immediate` on iOS 26, cancellation shields on iOS 27).

## Installation

Copy or clone the directory into your agent's skills folder:

```bash
# Claude Code
git clone https://github.com/farkasseb/swift-concurrency-skill ~/.claude/skills/swift-concurrency

# Codex CLI
git clone https://github.com/farkasseb/swift-concurrency-skill ~/.agents/skills/swift-concurrency
```

Agents load only `SKILL.md` and read `references/` on demand. `evals/` is optional.

## Layout

```
SKILL.md                                  settings detection, execution model, isolation choices, diagnostic fixes
references/execution-and-settings.md     SE-0461, SE-0466, SE-0470, feature flags, SwiftPM setup, swift package migrate
references/versions-and-availability.md  Swift 6.2-6.4 additions with compiler vs OS gates
references/design-patterns.md            actor checklist, reentrancy, Mutex vs actor, offloading, cancel-and-replace
references/migration.md                  migration order, Combine crash, @preconcurrency, escape hatches
evals/                                    benchmark prompts, fixtures, and graded expectations
tests/                                    compile and runtime probes (run.sh, probes.py)
```

The skill defers to framework-specific skills where they exist, for example Apple's SwiftUI and App Intents skills that ship with Xcode 27, and `swift-testing`, falling back to Apple's `modernize-tests`, for XCTest to Swift Testing migration.

## Verification

`tests/run.sh` checks the skill against an installed Xcode with Swift 6.4 or later. It uses `$XCODE` (an `.app` path), then `$DEVELOPER_DIR`, then the `xcode-select` default, and stops if the compiler is older than 6.4.

```bash
XCODE=/Applications/Xcode.app tests/run.sh
tests/run.sh --skip swiftpm   # skip the slower package builds
```

It checks:

- **snippets:** every Swift block in `SKILL.md` and `references/` compiles with `swiftc -emit-sil` against the iOS SDK, or fails with the diagnostic the text describes. `-emit-sil` is needed because region-isolation errors are reported after type checking. A new block without a probe fails the run.
- **facts:** feature defaults (`hasFeature`), `ApproachableConcurrency`, default-isolation exceptions, diagnostics and their severity (SE-0434, SE-0520, `@concurrent` restrictions, App Intents conformance isolation), and the availability gates in the matrix.
- **runtime** (macOS): where code runs with and without `NonisolatedNonsendingByDefault` and default MainActor isolation, `Task` isolation inheritance, cancellation propagation, task executor preference, replacement-task cleanup and reuse, and Combine/legacy callback `_dispatch_assert_queue_fail` traps.
- **templates:** the Swift settings in Xcode's new-project templates.
- **swiftpm:** the `Package.swift` example and `ApproachableConcurrency` build, and a 6.x tools version defaults to Swift 6 mode.

Last full run: 92 checks passed with Swift 6.4 (swiftlang-6.4.0.34.1, Xcode 27.1 beta), 2026-10-03. Proposal statuses were checked against the Swift Evolution index on swift.org; the probes don't cover them.

## Evals

`evals/evals.json` has 16 prompts with graded expectations. They cover facts that changed after most models' training, answers that must be derived from attached project files (`evals/files/`), Swift 6.4 details older material gets wrong, and one case where Apple's App Intents guidance should win. Run each prompt with and without the skill, with web search and documentation tools disabled, and compile any code in the answers with Swift 6.4.

## Sources

- Swift Evolution: [SE-0461](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0461-async-function-isolation.md), [SE-0466](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0466-control-default-actor-isolation.md), [SE-0470](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0470-isolated-conformances.md), [SE-0414](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0414-region-based-isolation.md), [SE-0430](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0430-transferring-parameters-and-results.md), [SE-0433](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0433-mutex.md), [SE-0434](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0434-global-actor-isolated-types-usability.md), [SE-0469](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0469-task-names.md), [SE-0472](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0472-task-start-synchronously-on-caller-context.md), [SE-0475](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0475-observed.md), [SE-0481](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0481-weak-let.md), [SE-0493](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0493-defer-async.md), [SE-0504](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0504-task-cancellation-shields.md), [SE-0518](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0518-tilde-sendable.md), [SE-0520](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0520-discardableresult-task-initializers.md), [SE-0528](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0528-noncopyable-continuation.md)
- [What's new in Swift concurrency, WWDC 2025 session 268](https://developer.apple.com/videos/play/wwdc2025/268/)
- [Matt Massicotte](https://massicotte.org): isolation, non-Sendable-first design, Combine and `@preconcurrency` guidance
- [Use Your Loaf](https://useyourloaf.com/blog/approachable-concurrency-in-swift-packages/): Approachable Concurrency in Swift packages
- [Antoine van der Lee](https://www.avanderlee.com/concurrency/approachable-concurrency-in-swift-6-2-a-clear-guide/): Approachable Concurrency guide

## Contributing

Corrections and additions are welcome. Please include the source (proposal, WWDC session, or a compile probe with the toolchain version) for any change in behavior or availability.
