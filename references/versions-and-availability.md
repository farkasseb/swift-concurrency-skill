# Versions and Availability

Swift 6.2-6.4 concurrency additions, and what each one needs. Gates were checked against Swift 6.4 and the iOS 27 SDK; the README records the last run.

- **Compiler feature:** needs only the new compiler; works at any deployment target.
- **Runtime API:** needs a minimum OS version, whatever the compiler. Use `if #available` or raise the deployment target.

## Matrix

| Feature | Proposal | Compiler | Deployment target |
|---|---|---|---|
| `nonisolated(nonsending)`, `@concurrent` | SE-0461 | 6.2 | any |
| Default actor isolation | SE-0466 | 6.2 | any |
| Isolated conformances | SE-0470 | 6.2 | any (dynamic-cast check only on new runtimes) |
| `isolated deinit` | SE-0371 | 6.2 | any |
| `Task.immediate`, `Task.immediateDetached`, `addImmediateTask` | SE-0472 | 6.2 | iOS 26 / macOS 26 |
| `Observations` | SE-0475 | 6.2 | iOS 26 / macOS 26 |
| `Task(name:)` (setting a name) | SE-0469 | 6.2 | any |
| static `Task.name` (current task) | SE-0469 | 6.2 | iOS 26 / macOS 26 |
| instance `task.name` | SE-0469 amendment | 6.4 | iOS 27 / macOS 27 |
| `weak let` | SE-0481 | 6.3 | any |
| `ContinuousClock.systemEpoch`, `SuspendingClock.systemEpoch` | SE-0473 | 6.3 | iOS 16 / macOS 13 (same as the clocks) |
| `await` in `defer` | SE-0493 | 6.4 | any |
| Unused throwing `Task` warning | SE-0520 | 6.4 | any (diagnostic) |
| `~Sendable` | SE-0518 | 6.4 | any |
| `withTaskCancellationShield`, `Task.hasActiveCancellationShield` | SE-0504 | 6.4 | iOS 27 / macOS 27 |
| `Continuation`, `withContinuation(of:)` | SE-0528 | 6.4 | iOS 27 / macOS 27 |
| `UnownedTaskExecutor: Hashable` | SE-0523 | 6.4 | iOS 27 / macOS 27 |
| `Result { try await ... }` | SE-0530 | 6.4 | any (emitted into client) |
| `Mutex`, `Atomic` | SE-0433, SE-0410 | 6.0 | iOS 18 / macOS 15 |
| `some AsyncSequence<Element, Failure>` with a typed failure | SE-0421 | 6.0 | iOS 18 / macOS 15 |
| `OSAllocatedUnfairLock` | (os framework) | any | iOS 16 / macOS 13 |
| `AsyncStream.makeStream()` | SE-0388 | 5.9 | any (emitted into client) |

Other platforms gate on the same yearly release with their own numbers: iOS 16 = macOS 13, watchOS 9; iOS 18 = macOS 15, watchOS 11, visionOS 2. tvOS matches iOS, and from 26 on every platform does.

## Swift 6.4

### `await` in `defer` (SE-0493)

```swift
func sync(over connection: Connection) async throws {
    defer { await connection.close() }
    try await connection.send(Data())
}
```

- The `defer` body runs to completion at every exit, including thrown errors, before the function returns. It inherits the enclosing isolation.
- The enclosing function must be `async`.
- The older workaround `defer { Task { await cleanup() } }` is wrong on 6.4: the cleanup races the function's return and its errors are lost.
- If the task was cancelled, cleanup code that checks cancellation may skip work. On iOS 27+ wrap it in a cancellation shield; before that, see the fallback below.
- Use `#if compiler(>=6.4)` when the code must also build with older compilers.

### Task cancellation shields (SE-0504, iOS 27+)

```swift
@available(iOS 27, macOS 27, *)
func finish(_ resource: Resource) async {
    defer {
        await withTaskCancellationShield {
            await resource.shutdown()  // sees Task.isCancelled == false
        }
    }
    await resource.run()
}
```

- A shield hides cancellation from code inside it: static `Task.isCancelled` is `false`, `Task.checkCancellation()` does not throw, and cancellation handlers registered inside don't fire. The task itself stays cancelled.
- Child tasks (`async let`, task-group children) created inside the shield are not cancelled by the outer task's cancellation. Cancelling a child or group explicitly still works.
- The instance property `task.isCancelled` still reports the real state.
- There is a synchronous overload too.
- **Before iOS 27:** `await Task { await resource.shutdown() }.value` runs cleanup in an unstructured task that the outer cancellation doesn't reach. It is unstructured, so use it only for cleanup.

### Unused throwing `Task` warning (SE-0520)

`Task.init`, `Task.detached`, `Task.immediate`, and `Task.immediateDetached` with a throwing closure lost `@discardableResult`:

```text
warning: unstructured throwing task created by 'init(name:priority:operation:)' is not used,
which may accidentally ignore errors thrown inside the task [#NoUseUnstructuredThrowingTask]
```

Fixes, best first:

1. Handle the error inside the task with `do`/`catch`.
2. Keep the task and await it: `let task = Task { ... }` then `try await task.value`.
3. For fire-and-forget work where failures really don't matter, discard explicitly: `_ = Task { ... }`.

Removing `try` or wrapping the call to swallow errors hides the problem the warning reports.

### `~Sendable` (SE-0518)

Marks a type as deliberately non-Sendable and stops implicit `Sendable` inference. Shipped in Swift 6.4 with no flag:

```swift
// Internal types with only Sendable stored properties are implicitly Sendable;
// ~Sendable stops that.
struct Token: ~Sendable {
    let id: Int
}

// Public non-frozen types are never implicitly Sendable. On them, ~Sendable
// documents that the missing conformance is deliberate, not an oversight.
public struct Snapshot: ~Sendable {
    let values: [Int]
}

public class Base: ~Sendable {}

// Unlike an unavailable Sendable conformance, ~Sendable lets subclasses opt in.
public final class LockedCache: Base, @unchecked Sendable {}
```

- In public APIs it tells clients and reviewers that the type was audited and is intentionally not Sendable.
- An `@unchecked Sendable` subclass of a `~Sendable` class must still protect the inherited mutable state.
- It must be on the type declaration, not an extension, and it is not valid on protocols or generic parameters.
- Swift 6.3 rejects it ("'~Sendable' requires -enable-experimental-feature TildeSendable"). Code that must still build there needs nothing on a public non-frozen type, which isn't implicitly Sendable. An internal type can use `@available(*, unavailable) extension T: Sendable {}`, which, unlike `~Sendable`, also stops subclasses from opting in.

### Smaller 6.4 additions

- `Continuation` / `withContinuation(of:)` (SE-0528, iOS 27+): a noncopyable continuation. Double resume is a compile error; forgetting to resume traps at runtime. Below iOS 27 keep `withCheckedContinuation`.
- `Result { try await ... }` (SE-0530): async catching initializer, any deployment target.
- `UnownedTaskExecutor: Hashable` (SE-0523, iOS 27+).

## Swift 6.3

### `weak let` (SE-0481)

`weak` no longer requires `var`, so a `Sendable` class or a `@Sendable` closure can hold a weak reference. The referenced type must itself be `Sendable`:

```swift
final class Coordinator: Sendable {}

final class ConnectionPool: Sendable {
    weak let owner: Coordinator?
    init(owner: Coordinator) { self.owner = owner }
}
```

With a non-Sendable `Coordinator`, the compiler reports "stored property 'owner' of 'Sendable'-conforming class 'ConnectionPool' contains non-Sendable type". No flag or OS requirement applies to the declaration.

The separate upcoming feature `ImmutableWeakCaptures` makes `[weak x]` closure captures immutable. It is off by default in Swift 6.4.

## Swift 6.2 runtime APIs

### `Task.immediate` (SE-0472, iOS 26+)

Starts the task synchronously on the current executor and runs it until its first suspension, instead of waiting for a scheduler hop. Useful in gesture and event handlers where the first part must happen right away.

```swift
@available(iOS 26, macOS 26, *)
@MainActor
func beginDrag(_ model: DragModel) {
    Task.immediate {
        model.isDragging = true  // runs before beginDrag returns
        await model.loadPreview()
    }
}
```

### `Observations` (SE-0475, iOS 26+)

An `AsyncSequence` of values from `@Observable` state. Changes made in one transaction are coalesced. The closure is `@Sendable` but inherits the caller's actor, so create the sequence from the isolation that owns the model, usually the main actor:

```swift
@available(iOS 26, macOS 26, *)
@MainActor
func watch(_ player: Player) async {
    for await score in Observations({ player.score }) {
        print(score)
    }
}
```

From nonisolated code, capturing a non-Sendable model is an error. Below iOS 26, bridge with an `AsyncStream`.

### Task names (SE-0469)

`Task(name:)`, `Task.detached(name:)`, and `group.addTask(name:)` work at any deployment target. Reading the name needs iOS 26 for static `Task.name` and iOS 27 for the instance property. Names appear in Instruments and debugger task dumps.

## Accepted, not in Swift 6.4

Don't recommend these as available:

- `withDeadline` (SE-0526): composable absolute time limit for async work. Until it ships, use a task group that races the work against `Task.sleep`.
- File-level default isolation and diagnostics (SE-0478).
- `Disconnected` (SE-0538): a type that keeps a non-Sendable value in a disconnected region while it sits in storage, so containers can pass it across isolation boundaries.
