# Design Patterns

Type-level decisions behind SKILL.md step 3.

## When an actor is justified

Use an actor when the design needs its own serialized isolation domain. Check these before writing one:

1. The type has mutable state that needs protection.
2. That state is reached from more than one isolation domain, not only the main actor.
3. The operations on it must not interleave with each other between suspension points you control.
4. The main actor is the wrong home for it, for example because of main-thread cost or because the state has nothing to do with UI.
5. Callers can live with `await` on every access from outside.

If these don't hold, `@MainActor`, a `Mutex`, or a plain non-Sendable type is usually simpler. Say why in a doc comment on the actor; "it silenced a concurrency error" is not a reason.

Common mistakes:

- **Stateless actor.** For pure computation with no state, an actor only adds hops. Prefer a struct, free functions, or `@concurrent` functions.
- **Split isolation.** A class with some `@MainActor` properties and some nonisolated ones is hard to use from either side. Isolate the whole type or none of it.
- **Actor as a queue.** Actors are not FIFO. At every `await` inside an actor method, other calls can run and change state (reentrancy).

## Reentrancy: share one in-flight task

Several callers asking an actor for a token at once should share one refresh, not start one each:

```swift
actor TokenStore {
    private var refreshTask: Task<String, any Error>?

    func token() async throws -> String {
        if let refreshTask {
            return try await refreshTask.value
        }
        let task = Task { try await Self.fetchToken() }
        refreshTask = task
        defer { refreshTask = nil }
        return try await task.value
    }

    private static func fetchToken() async throws -> String { "token" }
}
```

State read before an `await` may be stale after it. Re-check it, or keep the check and the write on the same side of the suspension point, as above.

## Mutex or actor

| Need | Use |
|---|---|
| Synchronous access, short critical sections | `Mutex` (iOS 18+ / macOS 15+) |
| Deployment target below iOS 18 | `OSAllocatedUnfairLock` (iOS 16+); a wrapper with only immutable Sendable properties can use checked `Sendable` |
| Async workflows over the state | actor |

```swift
import Foundation
import Synchronization

final class ImageCache: Sendable {
    private let storage = Mutex<[String: Data]>([:])

    func image(for key: String) -> Data? {
        storage.withLock { $0[key] }
    }

    func insert(_ data: Data, for key: String) {
        storage.withLock { $0[key] = data }
    }
}
```

`Mutex` is `Sendable` whatever it wraps. Keep the closure short, never call `withLock` on the same mutex from inside it, and never `await` inside it (the closure is synchronous).

[`OSAllocatedUnfairLock`](https://developer.apple.com/documentation/os/osallocatedunfairlock) is itself Sendable. Its library-provided conformance lets a final wrapper keep checked conformance:

```swift
import os

final class LockedCounter: Sendable {
    private let storage = OSAllocatedUnfairLock(initialState: 0)

    func increment() -> Int {
        storage.withLock { value in
            value += 1
            return value
        }
    }
}
```

With a separate `NSLock` protecting an ordinary stored `var`, the compiler cannot verify the locking discipline. That design may need `@unchecked Sendable` after auditing every access. A lock's internal unchecked conformance does not require the wrapper to be unchecked too.

## Offloading synchronous work

Keep a slow synchronous function synchronous; that keeps it callable from anywhere. Offload at the call site:

```swift
nonisolated func parse(_ data: Data) -> [String] {
    String(decoding: data, as: UTF8.self).components(separatedBy: "\n")
}

@concurrent func parseInBackground(_ data: Data) async -> [String] {
    parse(data)
}

@MainActor
final class LogViewModel {
    var lines: [String] = []

    func load(_ data: Data) async {
        lines = await parseInBackground(data)
    }
}
```

`async let lines = parse(data)` also offloads, but only because `parse` is `nonisolated`. Under default MainActor isolation an unannotated `parse` is `@MainActor`, and the `async let` child runs it back on the main thread.

## Cancel and replace

For search-as-you-type and similar work, keep the task and cancel it before starting the next one:

```swift
import Foundation

@MainActor
final class SearchModel {
    private var searchTask: Task<Void, Never>?
    private var currentRequest: UUID?
    var results: [String] = []

    func queryChanged(_ query: String) {
        searchTask?.cancel()
        let requestID = UUID()
        currentRequest = requestID
        searchTask = Task {
            defer {
                if currentRequest == requestID { searchTask = nil }
            }
            try? await Task.sleep(for: .milliseconds(300))
            guard !Task.isCancelled else { return }
            let matches = await Self.search(query)
            guard !Task.isCancelled, currentRequest == requestID else { return }
            results = matches
        }
    }

    func stop() {
        currentRequest = nil
        searchTask?.cancel()
        searchTask = nil
    }

    private static func search(_ query: String) async -> [String] { [query] }
}
```

`try?` swallows the `CancellationError` from `Task.sleep`, so the first `guard` is what stops a cancelled search. The second `guard` matters when the search itself ignores cancellation: without it, an older search that finishes late overwrites newer results. In a SwiftUI view, `.task(id: query) { ... }` cancels and restarts without a stored task; it still needs the check after the `await` when the work ignores cancellation.

Cleanup also needs ownership. An unconditional `defer { searchTask = nil }` in the old task can erase its replacement's handle, leaving `stop()` unable to cancel the new task. The request ID guards both publication and cleanup. Test the ordering explicitly: start A, replace it with B, let A finish, then stop B.

## Cancellable callback bridges

`withTaskCancellationHandler` forwards task cancellation to a callback API. This example assumes `LegacyRequest` is `Sendable`, its `start` and `cancel` are safe to call concurrently and in either order, and it calls the completion exactly once, also after cancellation:

```swift
func fetch(_ request: LegacyRequest) async throws -> Int {
    try await withTaskCancellationHandler {
        try await withCheckedThrowingContinuation { continuation in
            request.start { result in continuation.resume(with: result) }
        }
    } onCancel: {
        request.cancel()
    }
}
```

If the task is already cancelled, `onCancel` runs first and the operation still runs. When the API doesn't meet those assumptions, keep lock-protected state that records cancellation even before the continuation is stored, and resume exactly once from whichever side gets there first. Don't make a reusable object single-use to get there.

## Passing non-Sendable values across isolation

Region-based isolation (SE-0414) lets a non-Sendable value cross a boundary when the compiler can prove nothing else still refers to it:

```swift
final class Draft { var text = "" }

actor Outbox {
    func submit(_ draft: sending Draft) { _ = draft.text }
}

@MainActor
func send(to outbox: Outbox) async {
    let draft = Draft()
    draft.text = "Hi"
    await outbox.submit(draft)  // fine: draft is not used again
    // draft.text = "again"     // would be an error: 'draft' was sent to the actor
}
```

Inside one function body the compiler tracks this itself. Across function boundaries, mark parameters and results `sending` (SE-0430): a `sending` parameter promises the caller gives up the value, a `sending` result promises a fresh, unshared value.
