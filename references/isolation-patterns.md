# Isolation Patterns

> **Read this file when**: choosing between actor / Mutex / @MainActor / nonisolated for thread safety, designing new types, encountering actor reentrancy issues, bridging callback APIs, replacing Combine, testing concurrent code, or fixing global/static variable warnings.

## Table of Contents

1. [Non-Sendable First Design](#non-sendable-first)
2. [Type Isolation Decision Guide](#decision-guide)
3. [Actor Justification Checklist](#actor-justification)
4. [Actor Reentrancy](#reentrancy)
5. [Mutex vs Actors](#mutex-vs-actors)
6. [Anti-Patterns](#anti-patterns)
7. [Task as Property Pattern](#task-property)
8. [Region-Based Isolation](#rbi)
9. [The `sending` Keyword](#sending)
10. [Synchronous Work](#sync-work)
11. [Structured Concurrency: async let vs TaskGroup](#structured-concurrency)
12. [Bridging Callbacks with Continuations](#continuations)
13. [Replacing Combine with AsyncAlgorithms](#async-algorithms)
14. [Testing Concurrent Code](#testing)
15. [Global and Static Variable Concurrency](#global-statics)

---

## Non-Sendable First Design {#non-sendable-first}

Start with nonisolated, non-Sendable types. Add isolation only when needed.

```swift
// Simple, flexible, works from any actor
class Counter {
    var state = 0
    func reset() { state = 0 }
    func toggle() async { state += 1 }  // with NonisolatedNonsendingByDefault: stays on caller's actor
}

// Conform to protocols without isolation mismatch
extension Counter: Equatable {
    static func == (lhs: Counter, rhs: Counter) -> Bool { lhs.state == rhs.state }
}
```

**Strengths**:
- Simplest possible type — no concurrency annotations
- Protocol conformances work naturally (no isolation mismatch)
- Synchronous access from ANY actor (not just MainActor)
- With NonisolatedNonsendingByDefault, async methods work naturally

**Weakness**: Starting `Task { }` from inside is hard (task can't capture `self` safely). Solution: use async methods and let callers create tasks.

**When to add isolation**: If you need MainActor state (UI), if compiler forces it, or if the type must be Sendable.

---

## Type Isolation Decision Guide {#decision-guide}

| Type's Purpose | Recommended Isolation | Why |
|---------------|----------------------|-----|
| SwiftUI View / ViewModel | `@MainActor` | Touches UI state |
| UIKit ViewController | `@MainActor` (implicit) | UIKit is MainActor |
| Data model presented in UI | `@MainActor` or nonisolated non-Sendable | Either works; nonisolated more flexible |
| Network service / API client (app internal) | `@MainActor` or nonisolated | @MainActor if mostly UI-driven; nonisolated if shared across modules. Use `@concurrent` for slow methods. |
| Network service / API client (library) | `nonisolated` | Let callers decide isolation — provide nonisolated APIs |
| Pure computation | `nonisolated` | No state to protect |
| Shared mutable state across isolation domains | `actor` (last resort) or `Mutex` | Only if MainActor causes contention |
| Cache / thread-safe counter | `Mutex` (iOS 18+) | Synchronous, lightweight |
| Library API | `nonisolated` | Callers choose where to run |

---

## Actor Justification Checklist {#actor-justification}

Before writing `actor`, verify ALL of these:

1. Has **non-Sendable mutable state** that requires protection
2. State is accessed from **multiple isolation domains** (not just MainActor)
3. Operations must be **atomic** (can't be interrupted)
4. **Cannot use MainActor** (would cause too much main-thread contention)
5. Can **tolerate asynchronous-only access** from outside

If ANY is false, use `@MainActor`, `Mutex`, or a non-Sendable class instead.

> "Every custom Swift actor needs justification in a doc comment: 'this is an actor because...' and the answer isn't allowed to be 'it helps deal with concurrency errors.'" — Matt Massicotte

---

## Actor Reentrancy {#reentrancy}

Actors are NOT FIFO queues. When an async method suspends at `await`, other work CAN execute on the actor before the original call resumes. This is called **interleaving**.

### The Auth Service Pattern

Problem: Multiple simultaneous API requests each try to refresh expired token.

```swift
// WRONG: Each caller triggers separate refresh
actor AuthService {
    func getBearerToken() async throws -> String {
        try await refreshToken()  // called N times simultaneously!
    }
}

// RIGHT: Deduplication via Task property
actor AuthService {
    private var tokenTask: Task<String, Error>?

    func getBearerToken() async throws -> String {
        if tokenTask == nil {
            tokenTask = Task { try await refreshToken() }
        }
        defer { tokenTask = nil }
        return try await tokenTask!.value
        // Force unwrap is safe: no suspension between write and read
    }
}
```

**Why the force unwrap is safe**: The code between `tokenTask = Task { ... }` and `return try await tokenTask!.value` has no suspension points. Actor reentrancy only happens at `await`. The unwrapped task is captured by the continuation, so even after `defer` nils it, resumed callers use their captured copy.

### Generalized Request Deduplicator

```swift
actor RequestDeduplicator<Value> {
    private var task: Task<Value, Error>?

    func deduplicate(_ operation: @escaping @Sendable () async throws -> Value) async throws -> Value {
        if let existingTask = task { return try await existingTask.value }
        let newTask = Task { try await operation() }
        task = newTask
        do {
            let value = try await newTask.value
            task = nil
            return value
        } catch {
            task = nil
            throw error
        }
    }
}
```

---

## Mutex vs Actors {#mutex-vs-actors}

### Mutex (Synchronization framework, iOS 18+ / macOS 15+)

```swift
import Synchronization

final class Cache: Sendable {
    private let store = Mutex<[String: Data]>([:])

    func get(_ key: String) -> Data? {
        store.withLock { $0[key] }
    }

    func set(_ key: String, value: Data) {
        store.withLock { $0[key] = value }
    }
}
```

**Rules**:
- Keep critical section (inside `withLock`) small
- NEVER recursively call `withLock` — behavior is platform-dependent (may panic, deadlock, or be undefined per SE-0433)
- Mutex is unconditionally `Sendable` — wraps non-Sendable values safely
- `withLockIfAvailable` returns nil if already locked (non-blocking)

### When to Use Which

| Criterion | Mutex | Actor |
|-----------|-------|-------|
| Synchronous access needed | Yes | No (async only from outside) |
| Simple state protection | Best fit | Overkill |
| Complex async workflows | Not suitable | Good fit |
| Performance (simple ops) | Generally faster for low-contention | Slightly more overhead |
| Deadlock risk | Possible (thread blocking) | Impossible (cooperative) |
| iOS version | 18+ | Any |
| Non-Sendable state wrapping | Yes (unconditionally Sendable) | Yes (actor isolation) |

**For iOS <18**: Use `OSAllocatedUnfairLock` (similar to Mutex but less compiler safety) or `@unchecked Sendable` with `NSLock`.

---

## Anti-Patterns {#anti-patterns}

### Stateless Actors
```swift
actor NetworkClient {
    // NO mutable state — actor is pointless
    func fetch() async -> Data { ... }
}
```
Fix: Use `@MainActor` class with `@concurrent` methods, or a plain struct.

### Split Isolation
```swift
class Mixed {
    var name: String                // nonisolated
    @MainActor var uiState: Int    // MainActor
}
```
Fix: Apply `@MainActor` to the whole type, or keep everything nonisolated.

### Redundant Sendable
```swift
@MainActor class Foo: Sendable { }  // Usually redundant: @MainActor types are implicitly Sendable
```
**Exception (SE-0434)**: A globally-isolated subclass of a nonisolated, non-Sendable superclass does NOT get implicit Sendable. Check the class hierarchy before assuming.

```swift
class NotSendable {}
@MainActor class Sub: NotSendable {}  // Sub is NOT implicitly Sendable
```

**Critical**: per SE-0434, `class Sub: NotSendable, Sendable {}` is **rejected by the compiler** — explicitly adding the conformance is an error here. The two ways forward:

1. **Drop the non-Sendable parent** if you don't need Objective-C interop / it's a vestigial `: NSObject`. Then `@MainActor` makes the subclass implicitly Sendable.
2. **`@unchecked Sendable`** — opt out of compiler verification and take responsibility:
   ```swift
   @MainActor final class Sub: NotSendable, @unchecked Sendable { }
   ```
   Safe only if all of the subclass's stored properties (and whatever the parent exposes) are immutable or are protected by a real lock.

### Non-Sendable + async = Red Flag
```swift
class Foo {
    func doWork() async { ... }  // Without NonisolatedNonsendingByDefault: generic executor!
}
```
Fix: Enable NonisolatedNonsendingByDefault, or use isolated params, or mark `@MainActor`.

---

## Task as Property Pattern {#task-property}

Cancel-and-replace for debouncing, cooldowns, or preventing duplicate work:

```swift
@State private var searchTask: Task<Void, Never>?

func search(_ query: String) {
    searchTask?.cancel()
    searchTask = Task {
        try? await Task.sleep(for: .milliseconds(300))
        guard !Task.isCancelled else { return }
        await performSearch(query)
    }
}
```

`Task.sleep` throws `CancellationError` if cancelled while sleeping. With `try await` in a throwing context that alone exits the task; with `try?` (as above) the error is swallowed and execution continues — that's why the `guard !Task.isCancelled` after the sleep is required, and after any other work.

---

## Region-Based Isolation (SE-0414) {#rbi}

The compiler tracks "regions" of values to allow non-Sendable types to cross isolation boundaries when provably safe.

### What RBI CAN prove safe

```swift
@MainActor func example() async {
    let ns = NonSendable()           // in its own region
    await nonisolatedFunc(ns: ns)    // ok: ns transferred, never used again here
}
```

### What RBI CANNOT prove safe

```swift
@MainActor func example() async {
    let ns = NonSendable()
    await nonisolatedFunc(ns: ns)
    print(ns)  // error: ns was already sent away
}
```

RBI works within single function bodies. For cross-function boundaries, use `sending` keyword.

---

## The `sending` Keyword (SE-0430) {#sending}

Relaxes Sendable requirements at call sites by constraining function bodies:

```swift
// Return value: function promises to return a disconnected value
func createModel() -> sending NonSendable { NonSendable() }

// Parameter: caller promises to not use value after passing it
func consume(ns: sending NonSendable) async { ... }
```

`sending` is a lighter constraint than `Sendable` — the type itself doesn't need to be thread-safe, just the specific usage pattern.

---

## Synchronous Work {#sync-work}

### Keep synchronous functions synchronous

A synchronous function is strictly more useful than an async one — it can be called from both sync and async contexts.

If you have slow synchronous work that blocks the main thread:

1. **Don't make the function async** — that limits callers
2. **Use `async let` to offload**: The `async let` child task runs on the generic executor by default (SE-0317)
3. **Or use `@concurrent`** wrapper: a `@concurrent` async function that calls the sync function
4. **For libraries**: provide `nonisolated` sync APIs, let callers decide how to offload

```swift
// Library: provide sync API
func decode(_ data: Data) -> Model { ... }

// Caller: offload via async let — child task runs on generic executor
@MainActor func process() async {
    async let model = decode(data)  // child task runs on generic executor (SE-0317)
    display(await model)
}
```

**The offload only works if the sync function is nonisolated.** Under default MainActor isolation (recommended for app modules), an unannotated local function is implicitly `@MainActor` — the `async let` child then hops back to the main actor and nothing is offloaded. Mark the sync function `nonisolated` (or keep it in a nonisolated-default library module). Verified empirically: with `-default-isolation MainActor` the child runs on the main thread; without it, on the generic executor — including under `NonisolatedNonsendingByDefault`, which does not change `async let` semantics.

---

## Structured Concurrency: async let vs TaskGroup {#structured-concurrency}

### When to use `async let`

Use when you know the **exact number of parallel tasks at compile time**:

```swift
func loadScreen() async throws -> ScreenData {
    async let user = fetchUser()
    async let friends = fetchFriends()
    async let settings = fetchSettings()
    return ScreenData(user: try await user, friends: try await friends, settings: try await settings)
}
```

- Tasks start immediately when `async let` is declared
- Suspension only happens when you `await` the result
- Cancellation propagates: if parent is cancelled, all child tasks are too
- If any throws, the others are automatically cancelled

### When to use `TaskGroup`

Use when you need to run an **arbitrary (runtime-determined) number** of tasks:

```swift
func fetchAllProfiles(ids: [String]) async throws -> [Profile] {
    try await withThrowingTaskGroup(of: Profile.self) { group in
        for id in ids {
            group.addTask { try await fetchProfile(id) }
        }
        var profiles: [Profile] = []
        for try await profile in group {
            profiles.append(profile)
        }
        return profiles
    }
}
```

- Results arrive in completion order, NOT submission order
- `DiscardingTaskGroup` (SE-0381) for fire-and-forget child tasks (no result collection)
- Use `group.cancelAll()` to cancel remaining tasks after getting what you need

### Limiting concurrency in TaskGroup

Prevent overwhelming a server with too many simultaneous requests:

```swift
func fetchWithLimit(ids: [String], maxConcurrent: Int) async throws -> [Profile] {
    try await withThrowingTaskGroup(of: Profile.self) { group in
        var iterator = ids.makeIterator()
        // Start initial batch
        for _ in 0..<min(maxConcurrent, ids.count) {
            if let id = iterator.next() {
                group.addTask { try await fetchProfile(id) }
            }
        }
        var results: [Profile] = []
        for try await profile in group {
            results.append(profile)
            // Add next task as each completes
            if let id = iterator.next() {
                group.addTask { try await fetchProfile(id) }
            }
        }
        return results
    }
}
```

### Timeout with TaskGroup

```swift
func fetchWithTimeout<T: Sendable>(timeout: Duration, work: @Sendable @escaping () async throws -> T) async throws -> T {
    try await withThrowingTaskGroup(of: T.self) { group in
        group.addTask { try await work() }
        group.addTask {
            try await Task.sleep(for: timeout)
            throw TimeoutError()
        }
        let result = try await group.next()!
        group.cancelAll()
        return result
    }
}
```

### When to use unstructured `Task { }`

- Bridging from sync to async context (e.g., `viewDidLoad`, button handlers)
- Fire-and-forget work where you don't need the result
- When you need to store the task for later cancellation

**Remember**: `Task { }` inherits actor context but NOT cancellation hierarchy. Only `async let` and `TaskGroup` create true parent-child cancellation.

---

## Bridging Callbacks with Continuations {#continuations}

For legacy callback-based APIs (SDK integrations, delegates, completion handlers):

### Basic pattern

```swift
func requestLocation() async throws -> CLLocation {
    try await withCheckedThrowingContinuation { continuation in
        locationManager.requestLocation()
        self.locationContinuation = continuation  // store for delegate callback
    }
}

// In delegate:
func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
    locationContinuation?.resume(returning: locations.first!)
    locationContinuation = nil
}

func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
    locationContinuation?.resume(throwing: error)
    locationContinuation = nil
}
```

### Critical rules

- **Resume exactly once** — resuming zero times = leak; resuming twice = crash
- Use `withCheckedContinuation` (misuse checks in all build configurations — traps on double resume, warns on leaked continuations, per SE-0300) or `withUnsafeContinuation` (no checks, slightly faster)
- Continuation does NOT suspend at call site when isolation matches (SE-0420) — synchronous code before the callback runs immediately
- Store continuation as optional, nil it after resume to prevent double-resume

### Wrapping delegate callbacks as AsyncStream

For repeated callbacks (not one-shot):

```swift
var headingStream: AsyncStream<CLHeading> {
    AsyncStream(bufferingPolicy: .bufferingNewest(1)) { continuation in
        self.headingContinuation = continuation
        manager.startUpdatingHeading()
        continuation.onTermination = { @Sendable _ in
            manager.stopUpdatingHeading()
        }
    }
}

// In delegate:
func locationManager(_ manager: CLLocationManager, didUpdateHeading heading: CLHeading) {
    headingContinuation?.yield(heading)
}
```

---

## Replacing Combine with AsyncAlgorithms {#async-algorithms}

Package: `apple/swift-async-algorithms` (v1.0+). Import: `import AsyncAlgorithms`

### Combine → AsyncAlgorithms equivalence

| Combine | AsyncAlgorithms | Notes |
|---------|----------------|-------|
| `combineLatest` | `combineLatest(_:...)` | Same semantics |
| `merge` | `merge(_:...)` | Same semantics |
| `zip` | `zip(_:...)` | Same semantics |
| `debounce` | `debounce(for:clock:)` | Uses Swift Clock |
| `throttle` | `throttle(for:clock:)` | Uses Swift Clock |
| `removeDuplicates` | `removeDuplicates()` | Same semantics |
| `flatMap` + `switchToLatest` | No direct equivalent | Use task cancellation pattern |
| `scan` | Use `for await` with accumulator | Manual but straightforward |
| `map` / `filter` | Built into `AsyncSequence` | Standard library |
| `sink` | `for await value in stream` | Natural loop |
| `PassthroughSubject` | `AsyncStream` / `AsyncChannel` | `AsyncChannel` has backpressure |
| `CurrentValueSubject` | `AsyncStream` + initial value | Manual |
| `@Published` | `@Observable` + `AsyncStream` | Prefer `@Observable` for SwiftUI |
| `@Published` observation outside SwiftUI | `Observations { model.value }` | SE-0475, iOS 26+ — transactional, coalesced per transaction. Below iOS 26: `AsyncStream` bridge. |
| `eraseToAnyPublisher()` | `some AsyncSequence<Element, Error>` | Opaque return type (SE-0421) |

### AsyncChannel (with backpressure)

```swift
let channel = AsyncChannel<String>()

// Producer (blocks until consumed):
await channel.send("hello")

// Consumer:
for await message in channel { print(message) }
```

### Key differences from Combine

- No `AnyCancellable` — cancellation is cooperative via Task
- No `store(in: &cancellables)` — lifetime tied to task/for-await loop
- Error handling: `AsyncThrowingStream` vs `Failure` type parameter
- Backpressure: `AsyncChannel` provides it; `AsyncStream` buffers (configurable)
- **Thread safety**: AsyncSequence iteration is NOT thread-safe — use from a single task

---

## Testing Concurrent Code {#testing}

### XCTest with async

```swift
// Async test methods work directly
func test_fetchUser_returnsUser() async throws {
    let user = try await sut.fetchUser()
    XCTAssertEqual(user.name, "Test")
}
```

### Testing unstructured Task code (XCTestExpectation)

When code creates `Task { }` internally, the test can't `await` it directly:

```swift
func test_refresh_callsRepository() {
    mockRepo.stubResponse = .success([])
    let exp = expectation(description: #function)
    mockRepo.didLoad = { exp.fulfill() }  // fulfill in mock's defer block
    sut.refresh()  // creates Task internally
    waitForExpectations(timeout: 1)
    XCTAssertEqual(mockRepo.loadCallCount, 1)
}
```

**Key pattern**: Add `didX: (() -> Void)?` closures to mocks, call them in `defer { }` blocks.

### Swift Testing framework

```swift
@Test func fetchUser() async throws {
    let user = try await sut.fetchUser()
    #expect(user.name == "Test")
}

// For callback-based code:
@Test func callbackTest() async {
    await confirmation("callback invoked") { done in
        sut.onComplete = { done() }
        sut.start()
    }
}
```

### Testing @MainActor code

```swift
// Mark test @MainActor to access MainActor-isolated state
@MainActor
func test_viewModel_updatesState() async {
    await sut.loadData()
    XCTAssertEqual(sut.state, .loaded)
}
```

### Deterministic testing with withMainSerialExecutor

From `swift-concurrency-extras` (Point-Free):

```swift
await withMainSerialExecutor {
    // Forces all tasks to execute serially on main thread
    // Eliminates flaky test ordering issues
    sut.refreshData()
    await Task.yield()  // allow scheduled tasks to execute
    XCTAssertEqual(sut.items.count, 3)
}
```

### Testing with event streams

For verifying ordered callbacks:

```swift
@Test func eventsAreOrdered() async {
    let (stream, continuation) = AsyncStream<String>.makeStream()
    sut.onEventA = { continuation.yield("a") }
    sut.onEventB = { continuation.yield("b") }
    await sut.go()
    continuation.finish()
    let events = await stream.reduce(into: []) { $0.append($1) }
    #expect(events == ["a", "b"])
}
```

---

## Global and Static Variable Concurrency {#global-statics}

The `GlobalConcurrency` setting (part of Swift 6 mode) enforces concurrency safety on global/static variables.

### Common warnings

```
// "Static property 'shared' is not concurrency-safe because..."
// "Reference to static property 'default' is not concurrency-safe..."
// "Var 'sharedConfig' is not concurrency-safe because it is non-isolated global shared mutable state"
```

### Solutions ranked best to worst

Apply in order — `nonisolated(unsafe)` is the LAST option, not the first.

**1. `let` constant of `Sendable` type** — eliminates the warning at the language level.
```swift
public let sharedConfig = Config.default          // best: immutable, Sendable, no warning
enum Constants {
    static let apiURL = URL(string: "...")!       // safe by definition
}
```

**2. `@MainActor`** — when access is UI-driven or main-thread-only. Compiler-verified.
```swift
@MainActor public var sharedConfig = Config.default
@MainActor class UserManager {
    static let shared = UserManager()
}
```

**3. `actor` wrapper** — when mutation comes from multiple isolation domains and async access is acceptable.
```swift
actor ConfigStore {
    static let shared = ConfigStore()
    var config = Config.default
}
```

**4. `Mutex` (iOS 18+) or `OSAllocatedUnfairLock` (iOS 16+)** — when you need synchronous thread-safe access.
```swift
// iOS 18+ — compiler-verified Sendable
static let configuration = Mutex(Config())

// iOS 16+ — pre-Mutex era, requires @unchecked Sendable on the containing type
final class Holder: @unchecked Sendable {
    private let lock = OSAllocatedUnfairLock(initialState: Config.default)
    var value: Config {
        get { lock.withLock { $0 } }
        set { lock.withLock { $0 = newValue } }
    }
}
```

**5. `nonisolated(unsafe)`** — LAST RESORT. Compiler does NO checking. Use only when an external invariant guarantees safety (e.g., set once at app launch before any concurrency, never mutated again).
```swift
nonisolated(unsafe) public var sharedConfig = Config.default
```

### Anti-patterns

- **Don't** start with `nonisolated(unsafe)`. It is the escape hatch, not the default. Audit each one — most globals can move to `let`, `@MainActor`, or an `actor`.
- **Don't** "fix" a global-mutable-state warning by adding `@unchecked Sendable` to the *type*. The warning is about the variable, not the type's Sendable status.
