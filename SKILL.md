---
name: swift-concurrency
description: "Swift 6.2–6.4 concurrency and API availability. Use for async/await, actors, Sendable, Task, @MainActor, nonisolated, AsyncSequence, Swift 6 migration, wrong-thread debugging, or actor vs Mutex decisions. Covers caller isolation when NonisolatedNonsendingByDefault is enabled (SE-0461), @concurrent, default actor isolation (SE-0466), isolated conformances (SE-0470), await in defer (SE-0493), cancellation shields (SE-0504), weak let (SE-0481), and Task.immediate. Diagnostics: \"Sending value of non-Sendable type\", \"cannot cross actor boundary\", \"unstructured throwing task ... is not used\" / #NoUseUnstructuredThrowingTask, conformance isolation mismatches, and Combine + @MainActor crashes."
---

# Swift 6.2–6.4 + Approachable Concurrency

## CRITICAL: Top 7 Things Claude Gets Wrong

### 1. nonisolated async functions NOW inherit caller's isolation

With `NonisolatedNonsendingByDefault` enabled (part of Approachable Concurrency):

```swift
// OLD behavior (pre-SE-0461): runs on generic executor
// NEW behavior (with NonisolatedNonsendingByDefault): stays on caller's actor
class MyClass {
    func doWork() async { /* WHERE does this run? Depends on the flag! */ }
}
```

- **Without flag**: nonisolated async = always switches off the actor to the generic executor (SE-0338 behavior)
- **With flag**: nonisolated async = stays on caller's actor (`nonisolated(nonsending)`)
- Use `@concurrent` to explicitly switch off the actor to the generic executor
- **ALWAYS check project settings before answering isolation questions**

### 2. @concurrent is NOT Task.detached

```swift
// @concurrent: implies nonisolated, runs on generic executor
// CANNOT combine with @MainActor, isolated params, or @isolated(any)
@concurrent func decode(_ data: Data) async -> Model { ... }

// Task.detached: also detaches from priority, task-local values, cancellation hierarchy
// Almost never the right tool — prefer @concurrent functions
```

### 3. Combine + @MainActor = runtime crash

Combine APIs generally do not model sendability or isolation correctly. When `receive(on:)` moves execution to a background queue, closure inference plus queue hopping triggers runtime actor-isolation failures:

```swift
@MainActor class Foo {
    func setup() {
        Just(1)
            .receive(on: DispatchQueue.global())  // moves to background
            .sink { value in
                // CRASH: _dispatch_assert_queue_fail
                // Compiler inserted MainActor check, but we're on background
            }
    }
}
```

Fix: Add `@Sendable` to closure, or avoid `receive(on:)` with MainActor contexts.
Escape hatch: `-disable-dynamic-actor-isolation` compiler flag (disables runtime checks).

### 4. Nested Tasks do NOT propagate cancellation

```swift
Task {
    Task { /* NOT cancelled when outer task is cancelled */ }
}
// Only async let and TaskGroup propagate cancellation to child tasks
```

Nested `Task { Task { } }` inherits actor context and priority, but NOT cancellation.

### 5. defer CAN await now (Swift 6.4)

```swift
func process() async throws {
    let handle = try await acquire()
    defer { await handle.release() }   // legal in Swift 6.4, ANY deployment target
    try await use(handle)
}
```

- Implicitly awaited at every scope exit; runs to completion before return. Inherits enclosing isolation.
- Language-only feature — works targeting old iOS versions; only the compiler must be 6.4 (Xcode 27).
- The pre-6.4 habit `defer { Task { await cleanup() } }` is an **anti-pattern**: cleanup races the function's return and errors vanish. Don't suggest it on Swift 6.4.
- Details + cancellation caveats: [references/swift-6_3-6_4-changes.md](references/swift-6_3-6_4-changes.md)

### 6. Swift 6.4 warns on unused throwing Tasks (SE-0520)

`Task { try await work() }` now emits `unstructured throwing task ... is not used [#NoUseUnstructuredThrowingTask]`. Fix by handling the error inside, or `let task = ...; try await task.value` — NOT by stripping `try` or silently swallowing. See [references/swift-6_3-6_4-changes.md](references/swift-6_3-6_4-changes.md).

### 7. "Approachable Concurrency" ≠ Default Actor Isolation

These are **independent** settings:
- **Approachable Concurrency** (Xcode build setting) = in Swift 6 mode, enables two additional flags: `NonisolatedNonsendingByDefault` + `InferIsolatedConformances`. In Swift 5 mode, enables all 5 flags (see [swift-6_2-changes.md](references/swift-6_2-changes.md)).
- **Default Actor Isolation** (separate setting) = sets module default to `@MainActor`
- Setting MainActor default **implicitly** enables `InferIsolatedConformances`
- You can have one without the other

## Routing: When to Read Each Reference

- **Migrating to Swift 6 or fixing concurrency warnings** → Read [references/migration-guide.md](references/migration-guide.md)
- **If codebase uses Combine with Swift 6** → You MUST read [references/migration-guide.md](references/migration-guide.md)
- **Choosing between actor / Mutex / @MainActor / nonisolated** → Read [references/isolation-patterns.md](references/isolation-patterns.md)
- **Using @concurrent, nonisolated(nonsending), default isolation, isolated conformances, Task.immediate, Observations, task naming** → Read [references/swift-6_2-changes.md](references/swift-6_2-changes.md)
- **await in defer, cancellation shields, weak let, ~Sendable, SE-0520 warning, anything Swift 6.3/6.4 or Xcode 26.6/27** → Read [references/swift-6_3-6_4-changes.md](references/swift-6_3-6_4-changes.md)
- **"What iOS version does this concurrency API need?"** → Feature Availability Matrix in [references/concurrency-glossary.md](references/concurrency-glossary.md)
- **Enabling Approachable Concurrency in SPM packages** → Read [references/swift-6_2-changes.md](references/swift-6_2-changes.md) (SPM section)
- **Structured concurrency (async let vs TaskGroup)** → Read [references/isolation-patterns.md](references/isolation-patterns.md) (section 11)
- **Bridging callback/delegate APIs** → Read [references/isolation-patterns.md](references/isolation-patterns.md) (section 12: Continuations)
- **Replacing Combine with AsyncSequence/AsyncAlgorithms** → Read [references/isolation-patterns.md](references/isolation-patterns.md) (section 13)
- **Testing concurrent code** → Read [references/isolation-patterns.md](references/isolation-patterns.md) (section 14)
- **Global/static variable warnings** → Read [references/isolation-patterns.md](references/isolation-patterns.md) (section 15)
- **Encountering an unfamiliar concurrency keyword or attribute** → Read [references/concurrency-glossary.md](references/concurrency-glossary.md)
- **For full SE proposal text** → Use `mcp__cupertino__read_document` with `swift-evolution://SE-XXXX`

## Decision Trees

### How should I isolate this type?

1. Is it a UI-facing type or model presented in the UI? → `@MainActor`
2. Is it a plain data/logic type with no concurrency needs? → Leave nonisolated (non-Sendable). See Non-Sendable First Design in [isolation-patterns.md](references/isolation-patterns.md)
3. Does it need to protect mutable state accessed from multiple isolation domains AND you can't use MainActor? → Consider actor (but read justification checklist in [isolation-patterns.md](references/isolation-patterns.md) first)
4. Need synchronous thread-safe access to a single value? → `Mutex` (iOS 18+)

### I have a Sendable error

1. Is the type a value type with all Sendable properties? → Conform to `Sendable`
2. Is it a `@MainActor` class? → Usually implicitly `Sendable`, BUT NOT if it subclasses a nonisolated non-`Sendable` type (SE-0434). The fix in that case is `@unchecked Sendable` (with discipline) or drop the non-Sendable parent — **explicitly adding `: Sendable` to the subclass is a compile error**.
3. Is the error "Sending main-actor-isolated value..." across an isolation boundary? → **Mark the parameter `sending`** as the surgical fix (SE-0430). Alternatives: make the value type a `struct`, restructure so the value is built nonisolated, or `@unchecked Sendable` with locking.
4. Can region-based isolation prove the usage is safe? → See [isolation-patterns.md](references/isolation-patterns.md) (Region-Based Isolation)
5. Is it a class with internal locking? → `@unchecked Sendable`
6. Is the error from an API you don't control? → Prefer `@preconcurrency` on the conformance over `@preconcurrency import` (import applies per-file and silently swallows real errors)
7. Is it a `@MainActor` class conforming to a protocol like `Equatable` and you get an isolation mismatch on the witness? → That's **SE-0470 (Global-Actor Isolated Conformances)**. See "How do I fix a `@MainActor` + protocol conformance error?" decision tree below.

### "Var X is not concurrency-safe because it is non-isolated global shared mutable state"

Rank fixes from best (highest safety + clearest intent) to worst (escape hatch). **Stick to this order — `nonisolated(unsafe)` is LAST RESORT.**

1. **`let` constant** — best if the value is actually immutable. Eliminates the warning at the language level.
2. **`@MainActor`** — if access is UI-driven / main-thread-only. Compiler-verified; preferred for app-level singletons.
3. **`actor` wrapper** — if mutation happens from multiple isolation domains and async access is acceptable.
4. **`Mutex` (iOS 18+) or `OSAllocatedUnfairLock` (iOS 16+)** — if you need synchronous thread-safe access.
5. **`nonisolated(unsafe)`** — LAST RESORT. Only when external invariants guarantee safety (e.g. set once at startup before any concurrency, never mutated again). The compiler does no checking.

**Anti-pattern to reject**: adding `@unchecked Sendable` to the *type* doesn't address this warning. The warning is on the variable, not the type's Sendable status.

### Code runs on the wrong thread

1. Is `NonisolatedNonsendingByDefault` enabled? → nonisolated async now stays on caller's actor. Add `@concurrent` to switch to generic executor. See [swift-6_2-changes.md](references/swift-6_2-changes.md)
2. Is default isolation set to MainActor? → Everything not explicitly `nonisolated` runs on main thread
3. Did you use `Task { }` from `@MainActor`? → Task inherits MainActor context. Move work into an `@concurrent` function, or use `Task.detached` as fallback
4. Did you use `Task { }` inside a nonisolated function (sync, `nonisolated(nonsending)` async, OR `@concurrent` async)? → **The unstructured `Task { }` does NOT inherit caller's actor isolation** — this rule is consistent across all three nonisolated function shapes (SE-0461). Capturing non-`Sendable` values from the enclosing context is a compile error.

### How do I fix a `@MainActor` type's protocol conformance isolation mismatch?

This is **SE-0470 (Global-Actor Isolated Conformances)**, implemented in Swift 6.2. The error fires when the protocol's requirement is `nonisolated` (e.g. `Equatable.==`) but the conforming type is `@MainActor`-isolated.

Ranked fixes for `@MainActor class Foo: Equatable { static func ==(...) {...} }`:

1. **`nonisolated static func ==`** — best when the body only reads `let` properties or other Sendable state. The protocol witness explicitly opts out of MainActor isolation. Most common, simplest, no flag required.
2. **`@MainActor Equatable`** (isolated conformance) — use when the body MUST access MainActor-isolated state. Trade-off: an isolated conformance cannot satisfy a `Sendable` or `SendableMetatype` requirement, so the type can't cross those boundaries via this conformance.
3. **`InferIsolatedConformances` upcoming feature** — module-wide; conformances of `@MainActor` types automatically get `@MainActor` isolation. Right tool when you want #2 broadly across the module.
4. Don't refactor to a `struct` "to dodge the issue" if the type genuinely needs reference semantics — that's off-topic.

## Recommended Build Settings (WWDC 2025, Doug Gregor)

| Setting | UI/App Modules | Libraries/Services |
|---------|---------------|-------------------|
| Approachable Concurrency | ON | ON |
| Default Actor Isolation | `MainActor` | `nonisolated` (default) |
| Swift Language Mode | 6 | 6 |

- Libraries should provide `nonisolated` APIs — let callers decide whether to offload
- Model classes should be `@MainActor` or non-Sendable — avoid making them actors unless you have a clear justification (see actor checklist in isolation-patterns.md)
- Progressive disclosure: single-threaded → async → concurrent → actors
- **Note on @MainActor + Sendable**: Usually implicitly Sendable, but NOT always — see SE-0434 subclass exception in [isolation-patterns.md](references/isolation-patterns.md). Check class hierarchy before assuming.

## Determining Project Concurrency Settings

Before answering concurrency questions, CHECK the project's settings:

**For SPM packages** — grep `Package.swift` for:
- `.swiftLanguageMode(.v6)` or `.swiftLanguageMode(.v5)` (per-target, this is what matters)
- `.enableUpcomingFeature("NonisolatedNonsendingByDefault")`
- `.enableUpcomingFeature("InferIsolatedConformances")`
- `.defaultIsolation(MainActor.self)`
- `swift-tools-version:` (only tells you manifest API version, NOT target language mode)

**For Xcode projects** — grep `project.pbxproj` for:
- `SWIFT_VERSION` (language mode: 5, 6)
- `SWIFT_STRICT_CONCURRENCY` (minimal, targeted, complete)
- `SWIFT_APPROACHABLE_CONCURRENCY = YES`
- `SWIFT_DEFAULT_ACTOR_ISOLATION = MainActor`
- `SWIFT_UPCOMING_FEATURE_NONISOLATED_NONSENDING_BY_DEFAULT`

**Important**: `swift-tools-version` is NOT language mode. A package can be `swift-tools-version: 6.2` while targets use `.swiftLanguageMode(.v5)`. Always check **target-level** `swiftSettings` first, then fall back to package-level defaults.

## Behavioral Rules

- **NEVER write new Combine code.** When encountering existing Combine: understand pitfalls, bridge with concurrency, or migrate to AsyncSequence/AsyncAlgorithms.
- **For Combine replacement**: use `swift-async-algorithms` package — provides `merge`, `combineLatest`, `zip`, `debounce`, `throttle`, `chain`, `removeDuplicates`, `chunks`.
- **Favor `@concurrent` over `Task.detached`.** Task.detached also detaches priority and task-locals.
- **Use actors sparingly.** Prefer @MainActor or non-Sendable types. Actors are for: non-Sendable state + atomic mutations + can't be on MainActor.
- **Always distinguish language features from runtime features when noting availability.** Language features need only the compiler and work on any deployment target: `@concurrent`, default isolation (Swift 6.2), `weak let` (6.3), `await` in `defer` (6.4). Runtime features need a minimum OS regardless of compiler: `Mutex` (iOS 18+), `Task.immediate`/`Observations`/static `Task.name` (iOS 26+), `withTaskCancellationShield`/move-only `Continuation` (iOS 27+). For iOS 16 deployment: use `OSAllocatedUnfairLock` or `@unchecked Sendable` with `NSLock` instead of Mutex. Full table: glossary Feature Availability Matrix.
- **Check NonisolatedNonsendingByDefault before answering** any question about where async code runs.
- **Prefer `@preconcurrency` conformance over `@preconcurrency import`** — import applies per-file and silently suppresses real errors.
