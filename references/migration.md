# Migration

Moving an existing codebase to Swift 6 mode and the 6.2 features.

## Order of work

1. Turn on the checking first: `SWIFT_STRICT_CONCURRENCY = complete` in Swift 5 mode, so problems show as warnings.
2. Decide the defaults per module: MainActor default isolation for app and UI modules, nonisolated for libraries. Turn on `NonisolatedNonsendingByDefault` and `InferIsolatedConformances` (Approachable Concurrency in Xcode). Use `swift package migrate` or the `MIGRATE` build-setting value to add `@concurrent` where code relied on the old behavior; see [execution-and-settings.md](execution-and-settings.md).
3. Switch modules to Swift 6 mode one at a time. Language mode is per module.
4. Work from the UI layer inward: annotate what is already true (`@MainActor` on main-thread types) before touching services.
5. Keep refactoring separate from migration, and contain spread with `@preconcurrency` rather than annotating across module boundaries in one pass.

## Combine and `@MainActor`: `_dispatch_assert_queue_fail`

Combine doesn't describe isolation or sendability to the compiler. In a `@MainActor` context a `sink` closure is inferred `@MainActor`, and Swift 6 mode inserts a runtime check at its start. If `receive(on:)` delivers on a background queue, that check traps:

```swift
import Combine
import Foundation

@MainActor
final class FeedModel {
    private var cancellables = Set<AnyCancellable>()

    func start() {
        Just(1)
            .receive(on: DispatchQueue.global())
            .sink { value in print(value) }  // crashes: _dispatch_assert_queue_fail
            .store(in: &cancellables)
    }
}
```

The crashing thread is a background queue with `_dispatch_assert_queue_fail` at the top; a few frames down is the closure that needs `@Sendable`.

Fixes:

1. Mark the closure `@Sendable` (`.sink { @Sendable value in ... }`). It is then nonisolated, so it can't touch main-actor state directly.
2. Remove `receive(on:)` if the pipeline doesn't need it, or deliver on `DispatchQueue.main` / `RunLoop.main`.
3. Consume the publisher as an `AsyncSequence` with `publisher.values` inside a task on the right actor.

`-disable-dynamic-actor-isolation` removes the runtime checks for the whole module. It hides the crash along with any real isolation bug.

## Legacy callbacks: repair the entry boundary

A closure created in a MainActor context can inherit MainActor isolation even when a Swift 5 or Objective-C API accepts an unannotated callback. An off-actor invocation can trap at the outer closure's entry, before an inner `Task { @MainActor in ... }` starts. `@preconcurrency import` does not dispatch the callback. See [SE-0423](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0423-dynamic-actor-isolation.md).

Make the outer callback nonisolated, for example by explicitly marking it `@Sendable`, then transfer Sendable values to actor-isolated code. For a callback that delivers one `Int` exactly once, a continuation lets the enclosing MainActor method update state before returning:

```swift
@MainActor
final class LegacyModel {
    private(set) var value = 0

    func load() async {
        let received: Int = await withCheckedContinuation { continuation in
            legacyFetch { @Sendable value in
                continuation.resume(returning: value)
            }
        }
        value = received
    }
}
```

Here `legacyFetch` is the dependency's callback API. Verify its delivery, ordering and completion contract. Repeated callbacks need a stream or serialized delivery design; one unstructured MainActor task per callback does not guarantee event order. Non-Sendable payloads need a safe transfer strategy. `MainActor.assumeIsolated` checks an existing guarantee and cannot perform a hop.

## Three uses of `@preconcurrency`

1. **On a conformance**, for a protocol you don't control that predates concurrency. The compiler inserts a runtime isolation check instead of rejecting the witness:

   ```swift
   protocol LegacyDelegate: AnyObject {
       func didUpdate()
   }

   @MainActor
   final class Screen: @preconcurrency LegacyDelegate {
       func didUpdate() {}
   }
   ```

2. **On your own public API**, when you add `@Sendable` or `@MainActor` and don't want to break clients still in Swift 5 mode:

   ```swift
   @preconcurrency
   public func schedule(_ work: @escaping @Sendable () -> Void) { work() }
   ```

3. **On an import**, `@preconcurrency import LegacyKit`: suppresses Sendable diagnostics for that module's types in this file. It applies to the whole file and can hide real problems, so prefer (1) where it fits.

## Dynamic isolation while migrating

In code that is not yet isolated but knows it runs on the main thread:

- `MainActor.assumeIsolated { ... }`: synchronous; traps if not actually on the main actor.
- `await MainActor.run { ... }`: hops to the main actor and runs the closure without interleaving. Apple's framework guidance also uses this for a single hop from nonisolated code (for example from an App Intent's `perform()`).

End state: static isolation (`@MainActor` on the type or function).

## Escape hatches

| Escape hatch | Use when |
|---|---|
| `@unchecked Sendable` | Synchronization protects every access, but the compiler cannot verify it. A final wrapper with only immutable Sendable properties should keep checked conformance. |
| `nonisolated(unsafe)` | One declaration is safe for a reason the compiler can't see. |
| `@preconcurrency import` | A dependency lacks annotations. |
| `@preconcurrency` conformance | A protocol you don't own causes an isolation mismatch. |
| `-disable-dynamic-actor-isolation` | Temporary relief from Combine or legacy runtime-check crashes. |
| A Swift 5 mode module | Code that can't reach Swift 6 yet. |

Each one is debt. Leave a comment saying why and when it can go.
