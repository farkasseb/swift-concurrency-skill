---
name: swift-concurrency
description: "Swift concurrency for Swift 6.2-6.4 and Xcode 26-27: async/await, actors, @MainActor, Sendable, Task, and data races. Use when a build shows concurrency errors or warnings (\"sending 'x' risks causing data races\", \"main actor-isolated\", \"not concurrency-safe\", \"unstructured throwing task ... is not used\"), when async code blocks the UI or runs on the wrong thread, for cancellation, cleanup, or actor-reentrancy bugs, Combine queue crashes, Swift 6 migration, Approachable Concurrency or default isolation settings, and newer features such as @concurrent, Task.immediate, weak let, ~Sendable, await in defer, and task cancellation shields."
---

# Swift Concurrency (Swift 6.2-6.4)

Xcode 27 ships Swift 6.4. Xcode 26.x ships Swift 6.2 or 6.3 depending on the point release; `swift --version` settles it. Much of this area changed after most models' training data, so prefer this skill over recalled behavior when they disagree.

## Step 1: Read the project's settings

Where a nonisolated `async` function runs depends on build settings. Check them before answering, and state the assumption when you can't see them.

**Xcode projects:** find the effective settings for the relevant target and configuration. Values can come from `project.pbxproj` (project and target level), referenced `.xcconfig` files, and command-line overrides; `xcodebuild -showBuildSettings -target <name>` or the actual compiler invocation settles it. The settings that matter:

- `SWIFT_VERSION`: language mode, `5.0` or `6.0`.
- `SWIFT_APPROACHABLE_CONCURRENCY = YES`: turns on the Approachable Concurrency upcoming features (below).
- `SWIFT_UPCOMING_FEATURE_NONISOLATED_NONSENDING_BY_DEFAULT`: explicit override of the most important one.
- `SWIFT_DEFAULT_ACTOR_ISOLATION = MainActor`: module-wide default isolation.
- `SWIFT_STRICT_CONCURRENCY`: `minimal` / `targeted` / `complete` checking in Swift 5 mode. Swift 6 mode is always complete.

**Swift packages** (`Package.swift`; target `swiftSettings` first, then package-level defaults):

- `.swiftLanguageMode(.v5)` / `.v6`, or package `swiftLanguageModes:`. With `swift-tools-version: 6.0` or later and no explicit mode, targets build in Swift 6 mode. The tools version is not the language mode.
- `.enableUpcomingFeature("ApproachableConcurrency")`: enables all five Approachable Concurrency features at once (accepted by Swift 6.3 and 6.4). Also look for the features enabled individually, such as `.enableUpcomingFeature("NonisolatedNonsendingByDefault")` and `.enableUpcomingFeature("InferIsolatedConformances")`.
- `.defaultIsolation(MainActor.self)` (tools 6.2+). Packages default to nonisolated.
- Default isolation is separate from `ApproachableConcurrency`. Xcode and SwiftPM settings are independent of each other.

**New Xcode 26 and 27 app projects** (verified in the Xcode 27 RC and 26.6 templates) set `SWIFT_VERSION = 5.0`, `SWIFT_APPROACHABLE_CONCURRENCY = YES`, and `SWIFT_DEFAULT_ACTOR_ISOLATION = MainActor`. A fresh app is therefore Swift 5 mode, all five Approachable Concurrency features on, and eligible unannotated declarations default to MainActor (see the inference exceptions in [references/execution-and-settings.md](references/execution-and-settings.md)).

**Swift 6.4 defaults:** `NonisolatedNonsendingByDefault` and `InferIsolatedConformances` are still opt-in, even in Swift 6 mode. Setting default isolation to MainActor also turns on `InferIsolatedConformances`.

**Approachable Concurrency and default isolation are independent settings.** Approachable Concurrency enables five upcoming features: `DisableOutwardActorInference`, `GlobalActorIsolatedTypesUsability`, `InferSendableFromCaptures`, `InferIsolatedConformances`, `NonisolatedNonsendingByDefault`. Swift 6 mode already includes the first three, so there it adds the last two. Default actor isolation only changes what unannotated declarations are isolated to.

## Step 2: Where code runs

| Code | Runs on |
|---|---|
| `@MainActor` function, or member of a `@MainActor` type | main actor |
| actor method | that actor |
| nonisolated `async` function, `NonisolatedNonsendingByDefault` off | nonisolated; the task's preferred executor, or the default global concurrent executor |
| nonisolated `async` function, `NonisolatedNonsendingByDefault` on | the caller's actor: it is `nonisolated(nonsending)` |
| `@concurrent` async function | nonisolated; the task's preferred executor, or the default global concurrent executor |
| synchronous nonisolated function | the caller's thread |
| `Task { }` | the enclosing global actor (for example `@MainActor`). Inside an actor or with an `isolated` parameter, only if the closure captures that actor (`self` or the parameter); otherwise nonisolated. Inherits priority and task-locals. |
| `Task { }` inside any nonisolated function (sync, `nonisolated(nonsending)`, or `@concurrent`) | nonisolated, even when the function itself runs on the caller's actor |
| `Task.detached { }` | nonisolated; drops priority and task-locals |
| `async let` / task-group child | concurrent executor, unless the called function is isolated. Under default MainActor isolation an unannotated sync function is `@MainActor`, so `async let x = work()` runs back on main. |

Consequences:

- To move heavy work off the caller's actor, mark the function `@concurrent` (Swift 6.2, any deployment target). Prefer it over `Task.detached`, which is unstructured and also drops priority and task-locals.
- `@concurrent` applies only to async functions and implies `nonisolated`. It cannot be combined with a global actor, an `isolated` parameter, or `@isolated(any)`.
- A `@concurrent` method on a non-Sendable class still has to send `self`. Calling it on an instance stored in a `@MainActor` type fails with "sending 'self.x' risks causing data races". Make the type Sendable (a struct of Sendable values, or a final class with only `let` Sendable state), or make the work a `static`/free function that takes Sendable inputs.
- An unstructured `Task { }` is not cancelled when the enclosing task is cancelled. Only `async let` and task groups propagate cancellation.

Details, `#isolation`, and the default-isolation inference rules: [references/execution-and-settings.md](references/execution-and-settings.md).

## Step 3: Choose isolation for a type

1. **Framework protocols decide first.** SwiftUI views and UIKit/AppKit types are `@MainActor`. App Intents types are `Sendable` and `perform()` is nonisolated: mark `perform()` `@MainActor` or hop inside it, but don't make the intent type `@MainActor`. When a framework-specific skill is available (for example Apple's `swiftui-specialist` or `app-intents-specialist`), follow it for that framework's types.
2. **`@Observable` models read by SwiftUI views:** `@MainActor`, unless the module already defaults to MainActor.
3. **Plain logic and data types:** nonisolated and non-Sendable (or a Sendable struct). Under default MainActor isolation, write `nonisolated` on the type. They are usable from any isolation, and their conformances have no isolation mismatch.
4. **Synchronous access to shared mutable state from several isolation domains:** `Mutex` (iOS 18+ / macOS 15+) or `OSAllocatedUnfairLock` (iOS 16+ / macOS 13+).
5. **`actor`:** when the design needs its own serialized isolation domain; see the checklist in [references/design-patterns.md](references/design-patterns.md). For stateless computation, prefer functions or structs.

Libraries should expose nonisolated APIs and let callers choose where to run them.

## Step 4: Fix the diagnostic

- **"sending 'x' risks causing data races"**: the value is used after crossing an isolation boundary, or it belongs to an actor's region. Stop using it after the send, create it on the destination side, mark the parameter or result `sending`, or make the type Sendable.
- **"capture of 'x' with non-Sendable type in a `@Sendable` closure"**: capture Sendable values instead, or run the closure in the same isolation as the value.
- **"main actor-isolated ... cannot satisfy nonisolated requirement"**, in order of preference:
  1. A `nonisolated` witness, when everything it touches is accessible without isolation, such as immutable (`let`) stored properties of Sendable type. A `var`, even of a Sendable type, or a `let` of a non-Sendable type is still isolated.
  2. An isolated conformance, `extension T: @MainActor P`, when it needs main-actor state. It cannot satisfy a `Sendable` or `SendableMetatype` requirement.
  3. `InferIsolatedConformances` to get (2) module-wide.
  4. A `@preconcurrency` conformance, for a protocol you don't own that predates concurrency.
- **"main actor-isolated conformance of 'T' to 'Decodable' cannot be used in ... context"**: default MainActor isolation made the type and its conformances `@MainActor`. Mark the type `nonisolated struct T: Codable`, or only the conformance: `extension T: nonisolated Codable {}`.
- **Global or static mutable state**, in order of preference: `let` of a Sendable type, then `@MainActor`, then an actor or `Mutex`, then `nonisolated(unsafe)` as a last resort. Adding `@unchecked Sendable` to the type does not fix a warning about the variable.
- **`@MainActor` subclass of a non-Sendable class:** not implicitly Sendable (SE-0434). Adding `: Sendable` is a warning in Swift 6.4 ("will be an error in a future Swift language mode"). Drop the non-Sendable superclass, or use `@unchecked Sendable` only if the subclass protects both its own and the inherited mutable state.
- **Missing annotations in a module you don't control:** prefer a `@preconcurrency` conformance over `@preconcurrency import`, which applies to the whole file and hides real errors.
- **`_dispatch_assert_queue_fail` in Combine or a legacy callback:** check the outer callback's isolation before adding an inner task hop; see [references/migration.md](references/migration.md).

## Step 5: Check the version and deployment target

Separate compiler features from runtime features:

- **Compiler features** need only the new compiler and work at any deployment target: `@concurrent`, `nonisolated(nonsending)`, default isolation (6.2), `weak let` (6.3), `await` in `defer`, `~Sendable`, the unused-throwing-Task warning (6.4). Rules for the newest ones:
  - `await` in `defer` (SE-0493, 6.4): write `defer { await x.close() }` directly. `defer { Task { ... } }` races the return and loses errors.
  - Unused throwing `Task` warning (SE-0520, 6.4): throwing `Task` initializers lost `@discardableResult`. Handle errors inside the task, keep and await the task, or discard deliberately with `_ = Task { ... }`.
  - `weak let` (SE-0481, 6.3) lets a `Sendable` class hold a weak reference; the referenced type must itself be `Sendable`.
  - Public non-frozen types are never implicitly `Sendable`. To mark a type deliberately non-Sendable, declare `: ~Sendable` on it (SE-0518, 6.4), not a dummy stored property or an unavailable conformance. Swift 6.3 rejects `~Sendable`; for code that must still build there, see the reference.
- **Runtime APIs** need a minimum OS whatever the compiler: `Mutex` (iOS 18), `Task.immediate`, `Observations`, reading `Task.name` (iOS 26), `withTaskCancellationShield`, `Continuation` (iOS 27).

Full matrix and per-feature notes: [references/versions-and-availability.md](references/versions-and-availability.md).

## Working rules

- Name the settings you assumed whenever an answer depends on them.
- Prefer structured concurrency (`async let`, task groups) over `Task { }`, and `@concurrent` over `Task.detached`.
- For new code, prefer `AsyncSequence`, `Observation`, and `swift-async-algorithms` over new Combine pipelines.
- Treat `@unchecked Sendable`, `nonisolated(unsafe)`, `@preconcurrency import`, and `-disable-dynamic-actor-isolation` as tracked debt, not fixes.
- For moving tests from XCTest to Swift Testing, use the `swift-testing` skill if it is available, otherwise Apple's `modernize-tests` skill exported from Xcode. If neither is available, follow Apple's Swift Testing migration documentation. Swift Testing runs tests in parallel on arbitrary tasks, so add `@MainActor` only where a test needs it.

## References

- [references/execution-and-settings.md](references/execution-and-settings.md): SE-0461 details, task executor preference, `#isolation`, SE-0466 inference rules, SE-0470 isolated conformances, SwiftPM snippets, `swift package migrate`.
- [references/versions-and-availability.md](references/versions-and-availability.md): Swift 6.2-6.4 additions, compiler vs runtime gates, proposals accepted but not yet shipped.
- [references/design-patterns.md](references/design-patterns.md): actor checklist, reentrancy, Mutex vs actor, offloading synchronous work, cancel-and-replace, cancellable callback bridges, `sending`.
- [references/migration.md](references/migration.md): migration order, Combine and legacy callback crashes, the three uses of `@preconcurrency`, escape hatches.
- Proposal text: `https://github.com/swiftlang/swift-evolution/tree/main/proposals` (file names start with the four-digit SE number).
