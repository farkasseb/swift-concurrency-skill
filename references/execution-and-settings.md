# Execution Model and Settings

Details behind SKILL.md steps 1 and 2. Proposal numbers refer to `https://github.com/swiftlang/swift-evolution/tree/main/proposals`.

## SE-0461: nonisolated async functions run on the caller's actor

Upcoming feature `NonisolatedNonsendingByDefault`. Implemented in Swift 6.2, still opt-in in Swift 6.4 (in both language modes).

- **Off:** a nonisolated `async` function leaves the caller's actor. It uses the task's preferred executor if set, otherwise the default global concurrent executor (SE-0338, SE-0417).
- **On:** it runs on the caller's actor. The explicit spelling is `nonisolated(nonsending)`, which works with or without the feature.
- `@concurrent` is the explicit spelling of the old behavior. It is only valid on async functions and implies `nonisolated`.

The change removes many "sending" errors, because a non-Sendable value no longer has to leave the actor when a method on it is awaited:

```swift
class NotSendable {
    func performAsync() async {}
}

actor MyActor {
    let x = NotSendable()
    func call() async {
        // Feature off: error, "sending 'self.x' risks causing data races".
        // Feature on: fine, performAsync stays on MyActor.
        await x.performAsync()
    }
}
```

Choosing a spelling:

```swift
struct ModelDecoder {
    @concurrent func decode(_ data: Data) async -> Model { Model(data) }  // always off-actor
    nonisolated(nonsending) func validate(_ model: Model) async -> Bool { true }  // caller's actor
}
```

### Unstructured tasks inside nonisolated functions

`Task { }` inherits only *static* isolation. From a global actor such as `@MainActor` that is automatic; inside an actor method, the task is isolated to the actor only if the closure captures `self` (any use of `self` or its members counts), and otherwise runs nonisolated. Inside any nonisolated function (synchronous, `nonisolated(nonsending)`, or `@concurrent`) the task is nonisolated, even when the function itself is running on the caller's actor at that moment. Capturing a non-Sendable parameter is then an error:

```swift
class Counter { var value = 0 }

nonisolated(nonsending) func bump(_ counter: Counter) async {
    Task {
        counter.value += 1  // error: passing closure as a 'sending' parameter risks causing data races
    }
}
```

To run the task on the caller's actor, take an explicit `isolated` parameter (for example `isolation: isolated (any Actor)? = #isolation`) and capture it in the task.

### `#isolation`

- In a `nonisolated(nonsending)` async function: the caller's actor (may be `nil`).
- In a `@concurrent` function or a synchronous nonisolated function: `nil`.
- In an actor-isolated function: that actor.

### Task executor preference

`@concurrent` determines isolation, not a fixed thread pool. A caller can select a `TaskExecutor` through `Task(executorPreference:)` or `withTaskExecutorPreference` (iOS 18+ / macOS 15+). A nonisolated `@concurrent` callee uses that preference instead of the default global concurrent executor.

Actor isolation remains separate. An ordinary actor without a custom executor can execute on the preferred task executor while retaining its own serial isolation. MainActor and actors with custom executors keep their executor requirements. A queue or thread observation alone does not prove actor isolation. See [SE-0417](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0417-task-executor-preference.md).

### Objective-C async imports

Independently of the feature flag, Swift 6.2 imports Objective-C completion-handler methods that become `async` as `nonisolated(nonsending)`. Their runtime behavior did not change; the compiler stopped reporting boundary crossings that never happened.

## SE-0466: default actor isolation

Xcode setting `SWIFT_DEFAULT_ACTOR_ISOLATION` (`MainActor` or `nonisolated`); SwiftPM `.defaultIsolation(MainActor.self)` or `.defaultIsolation(nil)`. Per module. Swift 6.2, any deployment target.

With `MainActor` as the default, these become `@MainActor` unless marked otherwise: top-level functions and variables, types and their members, static properties, nested types, and closures that inherit their context.

These do not:

- declarations with explicit isolation (`nonisolated`, `@concurrent`, another global actor);
- declarations whose isolation is inferred from a superclass, an overridden member, or a protocol conformance;
- anything inside an `actor`;
- types nested in a nonisolated type;
- types whose primary declaration conforms to a nonisolated protocol that refines `SendableMetatype` or `Sendable`, such as `Error` or `CodingKey`. In Swift 6.4, a conformance written in an extension, or plain `: Sendable` on the type, does not exempt it. A protocol declared in the same MainActor-default module counts only if it is marked `nonisolated protocol`;
- `Task.detached` closures.

A synchronous `nonisolated` function still runs on its caller's executor; to take work off the main actor, call it from an `@concurrent` async function. Default MainActor isolation also enables `InferIsolatedConformances`.

## SE-0470: global-actor isolated conformances

Swift 6.2. Needed when a `@MainActor` type conforms to a protocol whose requirements are nonisolated.

```swift
@MainActor
final class Profile {
    let id: Int
    var name = ""
    init(id: Int) { self.id = id }
}

// Witness only reads `let` state: make it nonisolated.
extension Profile: Hashable {
    nonisolated static func == (lhs: Profile, rhs: Profile) -> Bool { lhs.id == rhs.id }
    nonisolated func hash(into hasher: inout Hasher) { hasher.combine(id) }
}

protocol Describable { func describe() -> String }

// Witness needs main-actor state: isolate the conformance.
extension Profile: @MainActor Describable {
    func describe() -> String { name }
}
```

Rules for isolated conformances:

- They can be used only inside their actor.
- They cannot satisfy a `Sendable` or `SendableMetatype` requirement, so generic code such as `func f<T: Describable & Sendable>` rejects them.
- `as?` and `is` casts to the protocol succeed only when running on that actor. Older runtimes that predate isolated conformances skip that check and let the cast succeed, so don't rely on a failing cast for safety on older OS versions.
- `SendableMetatype` is the marker protocol `Sendable` refines. A generic `T.Type` is Sendable only if `T: SendableMetatype`.

With `InferIsolatedConformances`, conformances of `@MainActor` types are inferred as `@MainActor`, except when the protocol refines `SendableMetatype` or all witnesses are `nonisolated`.

## Upcoming features and build settings

| Feature | Effect | In Swift 6 mode | In Approachable Concurrency |
|---|---|---|---|
| `NonisolatedNonsendingByDefault` | nonisolated async runs on the caller's actor | no | yes |
| `InferIsolatedConformances` | `@MainActor` types get `@MainActor` conformances | no | yes |
| `DisableOutwardActorInference` | property wrappers stop inferring isolation onto the type (SE-0401) | yes | yes |
| `GlobalActorIsolatedTypesUsability` | SE-0434 rules for global-actor types | yes | yes |
| `InferSendableFromCaptures` | infer `@Sendable` for method references (SE-0418) | yes | yes |
| `GlobalConcurrency` | checks on global and static variables | yes | no |
| `ImmutableWeakCaptures` | `[weak x]` captures become immutable (SE-0481) | no | no |

In Xcode, `SWIFT_APPROACHABLE_CONCURRENCY = YES` sets the default of each feature's own build setting, so an explicit per-feature setting (for example `SWIFT_UPCOMING_FEATURE_NONISOLATED_NONSENDING_BY_DEFAULT = NO`) wins.

### SwiftPM

```swift
// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "Feature",
    targets: [
        .target(
            name: "Feature",
            swiftSettings: [
                .defaultIsolation(MainActor.self),  // app-facing modules only
                .enableUpcomingFeature("NonisolatedNonsendingByDefault"),
                .enableUpcomingFeature("InferIsolatedConformances"),
            ]
        )
    ]
)
```

`.enableUpcomingFeature("ApproachableConcurrency")` enables all five Approachable Concurrency features in one setting, matching Xcode's switch; it works in Swift 5 and Swift 6 mode. Default isolation still needs its own `.defaultIsolation(...)`.

### `swift package migrate`

Swift 6.2's SwiftPM can apply the fix-its that preserve behavior when a feature is turned on, for example adding `@concurrent` where a function relied on leaving the actor:

```bash
swift package migrate --to-feature NonisolatedNonsendingByDefault,InferIsolatedConformances
```

In Xcode, setting a feature's build setting to `MIGRATE` produces the same fix-its as warnings.
