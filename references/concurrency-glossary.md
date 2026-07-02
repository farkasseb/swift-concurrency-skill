# Swift Concurrency Glossary

> **Read this file when**: encountering an unfamiliar concurrency keyword, attribute, or type and needing a quick reference with the corresponding SE proposal.

## Isolation

| Term | Kind | Description | Proposal |
|------|------|-------------|----------|
| `actor` | keyword | Reference type with serial executor protecting mutable state | SE-0306 |
| `@MainActor` | attribute | Global actor isolating code to the main thread | SE-0316 |
| `@globalActor` | attribute | Marks an actor type as usable for global actor annotations | SE-0316 |
| `nonisolated` | keyword | Opts a declaration out of actor isolation | SE-0313 |
| `nonisolated(nonsending)` | attribute | Async function inherits caller's isolation (no boundary crossing) | SE-0461 |
| `nonisolated(unsafe)` | attribute | Targeted opt-out of isolation checking for a single declaration | SE-0412 |
| `@concurrent` | attribute | Async function always switches off the actor to the generic executor | SE-0461 |
| `isolated` | keyword | Function parameter that defines dynamic isolation | SE-0313 |
| `#isolation` | macro | Returns current static isolation as `(any Actor)?` | SE-0420 |
| `@isolated(any)` | attribute | Exposes a closure's captured isolation at runtime | SE-0431 |
| `isolated deinit` | keyword | Deinitializer runs on the type's actor (has performance cost). Implemented in Swift 6.2. | SE-0371 |
| Default Isolation | setting | Module-level default: `MainActor` or `nonisolated` | SE-0466 |

## Sendability

| Term | Kind | Description | Proposal |
|------|------|-------------|----------|
| `Sendable` | protocol | Marker: type safe to share across isolation domains | SE-0302 |
| `SendableMetatype` | protocol | Marker: metatype safe to cross isolation domains. `Sendable` inherits from this. | SE-0470 |
| `@Sendable` | attribute | Closure/function type safe to share across isolation domains | SE-0302 |
| `@unchecked Sendable` | attribute | Disables compiler checks; you assert thread-safety | SE-0302 |
| `sending` | keyword | Parameter/return value can safely cross isolation boundary (lighter than Sendable) | SE-0430 |
| `@preconcurrency` | attribute | Multiple uses: conformance, API annotation, import suppression | SE-0337, SE-0423 |
| `weak let` | syntax | Immutable weak reference — lets Sendable classes hold weak refs. Swift 6.3. | SE-0481 |
| `~Sendable` | syntax | Suppresses implicit Sendable inference on a type. Swift 6.4, still experimental flag `TildeSendable`. | SE-0518 |

## Task Management

| Term | Kind | Description | Proposal |
|------|------|-------------|----------|
| `async` / `await` | keywords | Mark function as suspendable / mark suspension point | SE-0296 |
| `async let` | keyword | Start child task immediately, await result later | SE-0317 |
| `Task` | type | Creates unstructured async context. Inherits actor context + priority. | SE-0304 |
| `Task.detached` | method | Creates task detached from actor context, priority, and task-locals | SE-0304 |
| `TaskGroup` | type | Manage arbitrary number of child tasks with cancellation propagation | SE-0304 |
| `withTaskGroup(of:returning:body:)` | function | Create a TaskGroup scope with typed child results | SE-0304 |
| `withThrowingTaskGroup(of:returning:body:)` | function | Throwing variant — propagates child errors | SE-0304 |
| `DiscardingTaskGroup` | type | Fire-and-forget child tasks, no result collection | SE-0381 |
| `Task.yield()` | method | Voluntarily gives up thread for other tasks | SE-0304 |
| `Task.sleep(for:)` | method | Suspends without blocking thread. Throws on cancellation. | SE-0304 |
| `Task.isCancelled` | property | Check cooperative cancellation state | SE-0304 |
| `@TaskLocal` | attribute | Task-scoped storage (like thread-local but for tasks) | SE-0311 |
| `Task.immediate` | method | Starts synchronously on caller's executor until first suspension. iOS 26+. | SE-0472 |
| `Task(name:)` / `Task.name` | API | Task naming for Instruments/debugging. Setting back-deploys; reading `Task.name` iOS 26+, `task.name` iOS 27+. | SE-0469 |
| `await` in `defer` | syntax | Async cleanup in defer bodies, implicitly awaited at scope exit. Swift 6.4, any deployment target. | SE-0493 |
| `withTaskCancellationShield` | function | Block observation of cancellation (static APIs + child-task propagation) inside the scope. iOS 27+. | SE-0504 |
| `Task.hasActiveCancellationShield` | property | Whether a cancellation shield is active in the current task. iOS 27+. | SE-0504 |

## Async Sequences

| Term | Kind | Description | Proposal |
|------|------|-------------|----------|
| `AsyncSequence` | protocol | Sequence whose values arrive over time | SE-0298 |
| `AsyncStream` | type | Easy way to create AsyncSequence from callbacks/delegates | SE-0314 |
| `AsyncThrowingStream` | type | AsyncStream that can propagate errors | SE-0314 |
| `AsyncStream.makeStream()` | method | Preferred factory: returns `(stream, continuation)` tuple | SE-0388 |
| `for await ... in` | syntax | Iterate over AsyncSequence | SE-0298 |
| `Observations` | type | Transactional AsyncSequence over `@Observable` state changes. iOS 26+. | SE-0475 |

## Execution Control

| Term | Kind | Description | Proposal |
|------|------|-------------|----------|
| `Mutex` | type | Mutual exclusion lock. Unconditionally Sendable. iOS 18+. | SE-0433 |
| `Atomic` | type | Atomic operations on primitive types. iOS 18+. | SE-0410 |
| `withCheckedContinuation` | function | Bridge callback-based API to async/await | SE-0300 |
| `withCheckedThrowingContinuation` | function | Bridge throwing callback-based API to async/await | SE-0300 |
| `MainActor.assumeIsolated` | method | Promise compiler you're on MainActor (crashes if wrong) | SE-0392 |
| `MainActor.run` | method | Execute synchronous block on MainActor (requires await) | SE-0316 |
| `TaskExecutor` | protocol | Custom executor for controlling where tasks run | SE-0417 |
| `Continuation` / `withContinuation(of:)` | type/function | Move-only continuation: compile-time double-resume prevention. iOS 27+. | SE-0528 |
| `Result { try await ... }` | init | Async catching initializer. Swift 6.4, back-deployed. | SE-0530 |
| `Clock.systemEpoch` | property | Zero point of Continuous/SuspendingClock (uptime math). Swift 6.3, iOS 16+. | SE-0473 |

## Compiler Settings (Swift 6.2+; flag states verified against Swift 6.4)

| Setting | Effect | Part of "Approachable Concurrency"? |
|---------|--------|--------------------------------------|
| `NonisolatedNonsendingByDefault` | nonisolated async inherits caller isolation | YES |
| `InferIsolatedConformances` | MainActor types get MainActor conformances | YES |
| `StrictConcurrency` | complete/targeted/minimal checking | No (6 mode setting) |
| `DynamicActorIsolation` | Runtime crashes for isolation violations | No (6 mode setting) |
| `GlobalConcurrency` | Checks on global/static vars | No (6 mode setting) |
| `RegionBasedIsolation` | SE-0414 flow analysis | No (but auto-enabled by StrictConcurrency=complete) |
| Default Actor Isolation | Module default: MainActor or nonisolated | NO (independent setting) |
| `ImmutableWeakCaptures` | `[weak x]` captures become immutable (Swift 6.3 upcoming) | No |
| `TildeSendable` | Enables `~Sendable` (Swift 6.4, still *experimental*) | No |

## Feature Availability Matrix

| Feature | Compiler Req | Runtime/Deploy Req | Notes |
|---------|-------------|-------------------|-------|
| `@concurrent` | Swift 6.2 (Xcode 26) | Any deployment target | Compiler feature only |
| `nonisolated(nonsending)` | Swift 6.2 (Xcode 26) | Any deployment target | Compiler feature only |
| Default actor isolation | Swift 6.2 (Xcode 26) | Any deployment target | Compiler feature only |
| Isolated conformances | Swift 6.2 (Xcode 26) | Any deployment target | Compiler feature + runtime for `as?` checks |
| `SendableMetatype` | Swift 6.2 (Xcode 26) | Any deployment target | Compiler feature only |
| `Mutex` | Swift 6.0 (Xcode 16) | iOS 18+ / macOS 15+ | Runtime: Synchronization framework |
| `Atomic` | Swift 6.0 (Xcode 16) | iOS 18+ / macOS 15+ | Runtime: Synchronization framework |
| Region-based isolation | Swift 6.0 (Xcode 16) | Any deployment target | Compiler feature only |
| `sending` keyword | Swift 6.0 (Xcode 16) | Any deployment target | Compiler feature only |
| `some AsyncSequence<Element, Error>` | Swift 6.0 (Xcode 16) | iOS 18+ / macOS 15+ | Primary associated types |
| `isolated deinit` | Swift 6.2 (Xcode 26) | Any deployment target | Compiler feature; opt-in with `isolated` keyword |
| `swift package migrate` | Swift 6.2 toolchain | N/A | CLI tool, not runtime |
| `OSAllocatedUnfairLock` | Any | iOS 16+ / macOS 13+ | Use as Mutex alternative for older OS |
| `AsyncStream.makeStream()` | Swift 5.9+ | iOS 17+ / macOS 14+ | Preferred over closure-based init |
| `Task.immediate` / `Observations` / static `Task.name` | Swift 6.2 (Xcode 26) | iOS 26+ / macOS 26+ | Runtime-gated despite 6.2 compiler |
| `await` in `defer` | Swift 6.4 (Xcode 27) | Any deployment target | Compiler feature only (verified vs iOS 16 target) |
| Throwing-`Task` unused-result warning | Swift 6.4 (Xcode 27) | Any deployment target | Compiler diagnostic (SE-0520) |
| `weak let` | Swift 6.3 (Xcode 26.6) | Any deployment target | Compiler feature only |
| `withTaskCancellationShield` | Swift 6.4 (Xcode 27) | iOS 27+ / macOS 27+ | Runtime; no back-deployment (per proposal) |
| `Continuation` (move-only) | Swift 6.4 (Xcode 27) | iOS 27+ / macOS 27+ | Runtime |
| `UnownedTaskExecutor: Hashable` | Swift 6.4 (Xcode 27) | iOS 27+ / macOS 27+ | Runtime |
| `Result` async catching init | Swift 6.4 (Xcode 27) | Any deployment target | Back-deployed (`@_alwaysEmitIntoClient`) |
| `Clock.systemEpoch` | Swift 6.3 (Xcode 26.6) | iOS 16+ / macOS 13+ | Back-deployed to Clock API floor |

**Rule of thumb**: Syntax/annotations = compiler only (any deploy target). Types/APIs = may need runtime support (check deploy target).

## Key SE Proposals by Number

For full text of any proposal, use: `mcp__cupertino__read_document` with URI `swift-evolution://SE-XXXX`

| Proposal | Title | Swift Version |
|----------|-------|---------------|
| SE-0302 | Sendable and @Sendable closures | 5.5 |
| SE-0306 | Actors | 5.5 |
| SE-0338 | Clarify execution of non-actor-isolated async functions | 5.7 |
| SE-0401 | Remove actor isolation inference from property wrappers | 6.0 |
| SE-0414 | Region-based isolation | 6.0 |
| SE-0420 | Inheritance of actor isolation (#isolation) | 6.0 |
| SE-0421 | Generalize effect polymorphism for AsyncSequence | 6.0 |
| SE-0423 | Dynamic actor isolation enforcement (@preconcurrency conformance) | 6.0 |
| SE-0410 | Low-Level Atomic Operations (Atomic) | 6.0 |
| SE-0430 | `sending` parameter and result values | 6.0 |
| SE-0431 | @isolated(any) function types | 6.0 |
| SE-0433 | Synchronous Mutual Exclusion Lock (Mutex) | 6.0 |
| SE-0434 | Usability of global-actor-isolated types | 6.0 |
| SE-0449 | Allow nonisolated to prevent global actor inference | 6.1 |
| SE-0461 | nonisolated(nonsending) / @concurrent | 6.2 |
| SE-0466 | Control default actor isolation | 6.2 |
| SE-0470 | Global-actor isolated conformances | 6.2 |
| SE-0469 | Task naming | 6.2 (instance `name` amendment: 6.4) |
| SE-0472 | Task.immediate (start on caller context) | 6.2 |
| SE-0475 | Observations (transactional observation) | 6.2 |
| SE-0473 | Clock epochs (systemEpoch) | 6.3 |
| SE-0481 | weak let | 6.3 |
| SE-0493 | await in defer bodies | 6.4 |
| SE-0504 | Task cancellation shields | 6.4 |
| SE-0518 | ~Sendable (suppress inference) | 6.4 (experimental) |
| SE-0520 | Throwing Task inits lose @discardableResult | 6.4 |
| SE-0523 | UnownedTaskExecutor: Hashable | 6.4 |
| SE-0528 | Move-only Continuation | 6.4 |
| SE-0530 | Async Result support | 6.4 |
