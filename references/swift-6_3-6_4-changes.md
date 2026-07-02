# Swift 6.3 / 6.4 Changes

Swift 6.3 ships in Xcode 26.6; Swift 6.4 ships in Xcode 27. Flag statuses below were verified against Xcode 27 beta 2 — experimental flags may be promoted by GM.

**Language feature vs runtime feature**: every entry notes whether it works on any deployment target (compiler-only) or requires a minimum OS (new Concurrency runtime entry points). This distinction is the most common thing to get wrong when recommending these APIs.

## SE-0493: `await` in `defer` Bodies (Swift 6.4)

**Gate**: Language-only. Works on **any deployment target** (verified: compiles targeting iOS 16 with the 6.4 compiler). No ABI impact.

```swift
func process() async throws {
    let handle = try await acquireResource()
    defer { await handle.release() }   // OK in Swift 6.4
    try await use(handle)
}
```

- The `defer` body is implicitly awaited at every scope exit point, and runs to completion before the function returns.
- Requires the enclosing context to be `async`. `defer { await ... }` in a synchronous function is still an error.
- The `defer` body inherits the enclosing scope's isolation — no extra suspension points beyond what the called functions introduce.
- In closures, an `await` inside `defer` is enough to infer the closure as `async`.

**Not a fix (pre-6.4 habit to unlearn)**: `defer { Task { await cleanup() } }`. That spawns unstructured cleanup that races with the function's return — the caller can resume before cleanup runs, and errors vanish. On Swift 6.4 write the `await` directly; on older compilers, prefer restructuring exit paths over the fire-and-forget `Task`.

**Cancellation caveat**: code in a `defer` observes the task's cancellation state normally. If the enclosing task was cancelled, cleanup calls that check `Task.isCancelled` internally may short-circuit. On iOS 27+ wrap the body in a cancellation shield (SE-0504 below); on older targets use the `await Task { ... }.value` workaround or cancellation-insensitive cleanup APIs.

## SE-0504: Task Cancellation Shields (Swift 6.4, iOS/macOS/tvOS/watchOS/visionOS 27+)

**Gate**: Runtime feature. `@available(...27.0)` — the proposal is explicit: "requires a number of runtime changes, it will not be available in back-deployment."

```swift
defer {
    await withTaskCancellationShield {   // sync overload exists too
        await resource.shutdown()        // runs as if not cancelled
    }
}
```

- Shields **observation**, not the cancellation itself: inside the block, static `Task.isCancelled` is `false`, `Task.checkCancellation()` doesn't throw, and cancellation handlers registered inside don't fire. Outside the block the task is still cancelled.
- Child tasks (`async let`, task groups) created *inside* the shield don't get auto-cancelled by the outer task's cancellation.
- `task.isCancelled` (instance) still reports the real state — only the static "current context" APIs respect shields.
- Shield the child task's body (`group.addTask { withTaskCancellationShield { ... } }`), not the `addTask` call — shielding `addTask` itself does nothing.
- Debug/introspect via `Task.hasActiveCancellationShield` (also iOS 27+).

**Pre-27 fallback** (the proposal's own former workaround): `await Task { resource.cleanup() }.value` — breaks out of the task tree so cleanup can't observe cancellation, at the cost of unstructured scheduling. Not usable in synchronous code.

## SE-0520: Throwing `Task` Initializers Lose `@discardableResult` (Swift 6.4)

**Gate**: Compiler diagnostic only. Fires on any deployment target once compiled with Swift 6.4 (verified: absent in 6.3.3, present in 6.4).

```text
warning: unstructured throwing task created by 'init(name:priority:operation:)' is not used,
which may accidentally ignore errors thrown inside the task [#NoUseUnstructuredThrowingTask]
```

Affects `Task.init`, `Task.detached`, `Task.immediate`, `Task.immediateDetached` when the closure throws. Ranked fixes:

1. **Handle the error inside the task** (`do/catch` in the closure) — best when the error is actionable.
2. **Store and await**: `let task = Task { ... }; try await task.value` — when the caller cares about the result.
3. **`_ = Task { ... }`** — explicit, intentional discard. Last resort; you're documenting that errors are dropped.

**Not a fix**: removing `try`/`throws` from the closure to silence the warning, or wrapping in a non-throwing closure that swallows errors silently.

## SE-0481: `weak let` (Swift 6.3)

**Gate**: Language-only, any deployment target, no flag needed for declarations (verified on 6.3.3 and 6.4).

```swift
final class Delegate: Sendable {
    weak let owner: Owner?          // legal since Swift 6.3; weak no longer requires var
    init(owner: Owner) { self.owner = owner }
}
```

The point: `Sendable` classes and `@Sendable` closures can now hold weak references — previously impossible because `weak` forced `var`, and mutable state breaks `Sendable`.

**`ImmutableWeakCaptures` upcoming flag** (separate, source-breaking part): makes explicit `[weak x]` captures immutable like every other capture. With the flag, assigning to a weak capture inside the closure errors with `cannot assign to value: 'x' is an immutable capture` (verified). Off by default in Swift 6 mode as of 6.4; will flip in a future language mode.

## SE-0518: `~Sendable` (Swift 6.4, still experimental)

Suppresses `Sendable` inference on a type that would otherwise be implicitly `Sendable` — declares "this type is *deliberately* not Sendable" (e.g. you plan to add non-Sendable state later, and don't want clients depending on accidental sendability).

**Gate**: still requires `-enable-experimental-feature TildeSendable` in Xcode 27 beta 2 (verified — errors without the flag). Don't recommend for production until it ships without the flag; check with `#if hasFeature(TildeSendable)`.

## Smaller Additions

| Feature | Swift | Availability | Note |
|---|---|---|---|
| `Continuation<Success, Failure>` + `withContinuation(of:)` (SE-0528) | 6.4 | **iOS 27+** | Move-only continuation: compile-time double-resume prevention, runtime trap on missing resume. Supersedes the unsafe-vs-checked continuation tradeoff — but only on 27+; keep `withCheckedContinuation` for older targets. |
| `UnownedTaskExecutor: Hashable` (SE-0523) | 6.4 | **iOS 27+** | Executor-keyed dictionaries; server-side niche. |
| `Result { try await ... }` async catching init (SE-0530) | 6.4 | **Any target** (back-deployed, `@_alwaysEmitIntoClient`) | Wraps async throwing work in a `Result` directly. |
| `ContinuousClock/SuspendingClock.systemEpoch` (SE-0473) | 6.3 | **iOS 16+** (back-deployed to the Clock APIs' floor) | Uptime = `clock.now - clock.systemEpoch`. |
| `Test.cancel()` (ST-0016, Swift Testing) | 6.3 | Library feature | Cancels the current test case; other parameterized cases continue. The swift-testing shipped with 6.2 mishandles task cancellation in some conditions — don't rely on cancellation semantics in tests before 6.3. |

## Diagnosing "which Swift do I have"

- Xcode 26.0–26.6 → Swift 6.2 / 6.3.x. Xcode 27 → Swift 6.4.
- `#if compiler(>=6.4)` for conditional adoption of `await`-in-`defer`.
- `NonisolatedNonsendingByDefault` and `InferIsolatedConformances` are **still opt-in** in Swift 6.4's v6 mode (verified via `hasFeature` probe) — everything in [swift-6_2-changes.md](swift-6_2-changes.md) about checking project settings still applies unchanged.
- Xcode 27's new-project templates still set `SWIFT_APPROACHABLE_CONCURRENCY = YES` and `SWIFT_DEFAULT_ACTOR_ISOLATION = MainActor` (verified in beta 2 templates), same as Xcode 26.
