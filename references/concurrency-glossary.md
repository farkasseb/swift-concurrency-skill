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

## Async Sequences

| Term | Kind | Description | Proposal |
|------|------|-------------|----------|
| `AsyncSequence` | protocol | Sequence whose values arrive over time | SE-0298 |
| `AsyncStream` | type | Easy way to create AsyncSequence from callbacks/delegates | SE-0314 |
| `AsyncThrowingStream` | type | AsyncStream that can propagate errors | SE-0314 |
| `AsyncStream.makeStream()` | method | Preferred factory: returns `(stream, continuation)` tuple | SE-0388 |
| `for await ... in` | syntax | Iterate over AsyncSequence | SE-0298 |

## Execution Control

| Term | Kind | Description | Proposal |
|------|------|-------------|----------|
| `Mutex` | type | Mutual exclusion lock. Unconditionally Sendable. iOS 18+. | SE-0433 |
| `Atomic` | type | Atomic operations on primitive types. iOS 18+. | SE-0433 |
| `withCheckedContinuation` | function | Bridge callback-based API to async/await | SE-0300 |
| `withCheckedThrowingContinuation` | function | Bridge throwing callback-based API to async/await | SE-0300 |
| `MainActor.assumeIsolated` | method | Promise compiler you're on MainActor (crashes if wrong) | SE-0392 |
| `MainActor.run` | method | Execute synchronous block on MainActor (requires await) | SE-0316 |
| `TaskExecutor` | protocol | Custom executor for controlling where tasks run | SE-0417 |

## Compiler Settings (Swift 6.2)

| Setting | Effect | Part of "Approachable Concurrency"? |
|---------|--------|--------------------------------------|
| `NonisolatedNonsendingByDefault` | nonisolated async inherits caller isolation | YES |
| `InferIsolatedConformances` | MainActor types get MainActor conformances | YES |
| `StrictConcurrency` | complete/targeted/minimal checking | No (6 mode setting) |
| `DynamicActorIsolation` | Runtime crashes for isolation violations | No (6 mode setting) |
| `GlobalConcurrency` | Checks on global/static vars | No (6 mode setting) |
| `RegionBasedIsolation` | SE-0414 flow analysis | No (but auto-enabled by StrictConcurrency=complete) |
| Default Actor Isolation | Module default: MainActor or nonisolated | NO (independent setting) |

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
| SE-0430 | `sending` parameter and result values | 6.0 |
| SE-0431 | @isolated(any) function types | 6.0 |
| SE-0433 | Synchronization framework (Mutex, Atomic) | 6.0 |
| SE-0434 | Usability of global-actor-isolated types | 6.0 |
| SE-0449 | Allow nonisolated to prevent global actor inference | 6.1 |
| SE-0461 | nonisolated(nonsending) / @concurrent | 6.2 |
| SE-0466 | Control default actor isolation | 6.2 |
| SE-0470 | Global-actor isolated conformances | 6.2 |
