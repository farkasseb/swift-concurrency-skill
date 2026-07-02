# Migration Guide

> **Read this file when**: migrating a project to Swift 6 language mode, fixing concurrency warnings, working with Combine in Swift 6, or using `@preconcurrency`.

## Table of Contents

1. [Migration Strategy](#strategy)
2. [Combine + @MainActor Crash](#combine-crash)
3. [@preconcurrency — Three Distinct Uses](#preconcurrency)
4. [Protocol Conformance Isolation Mismatch](#protocol-mismatch)
5. [Dynamic Isolation for Incremental Adoption](#dynamic-isolation)
6. [SwiftUI View Isolation](#swiftui)
7. [ModelActor Pitfalls](#modelactor)
8. [Migration CLI Tool](#migration-cli)
9. [Escape Hatches](#escape-hatches)

---

## Migration Strategy {#strategy}

### Outside-In Approach

Start at the UI layer and work inward:
1. UI modules have clear `@MainActor` boundaries — easiest to annotate
2. Synchronous accesses to model data define core constraints
3. Then migrate service/network layers

### The Six Habits

1. **Enable warnings first** — don't code blind. `StrictConcurrency = complete` or at minimum `targeted`.
2. **Express truth** — annotate what's already true (`@MainActor` on types that only run on main thread).
3. **Don't chase rabbit holes** — fix one warning at a time, don't let cascading errors pull you deep.
4. **Use `@preconcurrency` to contain blast radius** — prevent MainActor annotations from cascading across modules.
5. **Module-by-module** — language mode is per-module. Modularize first if needed.
6. **Don't refactor while migrating** — migration and refactoring are separate concerns.

### Recommended Settings Sequence

1. Enable Approachable Concurrency (NonisolatedNonsendingByDefault + InferIsolatedConformances)
2. Set default isolation: MainActor for UI modules, nonisolated for libraries
3. Enable Swift 6 language mode per module
4. Fix remaining warnings/errors

---

## Combine + @MainActor Crash {#combine-crash}

### The Problem

Combine APIs generally do not model sendability or isolation correctly. When `receive(on:)` moves execution to a background queue, closure inference plus queue hopping triggers runtime actor-isolation failures:

```swift
@MainActor class ViewModel {
    private var cancellables = Set<AnyCancellable>()

    func setup() {
        Just(1)
            .receive(on: DispatchQueue.global())  // moves to background
            .sink { value in
                // CRASH: _dispatch_assert_queue_fail
                // Runtime checks that we're on MainActor — we're not
                print(value)
            }
            .store(in: &cancellables)
    }
}
```

### How to Identify

- Crash function: `_dispatch_assert_queue_fail`
- A few frames deeper: the actual function missing `@Sendable`
- Look for `receive(on:)` or `subscribe(on:)` in Combine chains within `@MainActor` contexts

### Fixes

1. **Add `@Sendable` to closure** — but then you can't access MainActor state inside
2. **Remove `receive(on:)`** if unnecessary — many chains don't actually need it
3. **Use `MainActor.assumeIsolated`** inside the closure if you know it runs on main
4. **Bridge to async** — use `values` property to get an `AsyncSequence`

For Combine replacement patterns, see [isolation-patterns.md](isolation-patterns.md) section 13 (AsyncAlgorithms equivalence table).

---

## @preconcurrency — Three Distinct Uses {#preconcurrency}

### 1. Preconcurrency Conformance (SE-0423)

For protocol isolation mismatches with protocols you don't control:

```swift
@MainActor class MyVC: @preconcurrency ViewDelegateProtocol {
    func respondToUIEvent() {
        // No nonisolated/assumeIsolated needed
        // Runtime check ensures this runs on MainActor
    }
}
```

Adds runtime isolation check. More concise than nonisolated + assumeIsolated.

### 2. API Annotation for Swift 5 Compatibility

When you add `@Sendable` to a public API but don't want to break Swift 5 clients:

```swift
@preconcurrency public func doWork(block: @escaping @Sendable () -> Void) { ... }
```

Conditionalizes concurrency features: Swift 6 clients see `@Sendable`, Swift 5 clients don't get warnings.

### 3. Import-Level Suppression

```swift
@preconcurrency import SomeModule
```

Tells compiler: "types from this module that aren't Sendable — I'm asserting they're used safely."

**Caution**: Applies to entire file. Can mask real problems. Use with care.

---

## Protocol Conformance Isolation Mismatch {#protocol-mismatch}

The error: `Main actor-isolated function cannot satisfy nonisolated requirement`

### Solutions (ranked by preference)

1. **Make the type nonisolated** (Non-Sendable First Design) — eliminates the mismatch entirely
2. **Isolated conformance** (Swift 6.2): `extension MyType: @MainActor Equatable { ... }`
3. **Inferred isolated conformance** (with `InferIsolatedConformances` enabled) — happens automatically
4. **`@preconcurrency` conformance**: `extension MyType: @preconcurrency Equatable { ... }`
5. **`nonisolated` + `MainActor.assumeIsolated`** — verbose, last resort

### When Isolated Conformances Don't Work

- Protocol inherits `SendableMetatype` or `Sendable`
- Generic code needs to send the conformance across isolation domains
- Dynamic cast `as? any Sendable & P` — isolated conformances rejected

---

## Dynamic Isolation for Incremental Adoption {#dynamic-isolation}

Use `MainActor.assumeIsolated` and `MainActor.run` to contain the spread of `@MainActor` during migration:

```swift
// Stop @MainActor from spreading to this type
class NotYetMigrated {
    func needsMainActor() {
        MainActor.assumeIsolated {
            let obj = NewlyMainActored()
            // ...
        }
    }

    func asyncNeedsMainActor() async {
        await MainActor.run {
            let obj = NewlyMainActored()
            // ...
        }
    }
}
```

**Prefer static isolation** (`@MainActor` on the type) as the end state. Dynamic isolation is a migration tool.

**`MainActor.run` for atomicity**: Groups multiple synchronous calls without risk of interleaving:

```swift
await MainActor.run {
    obj.methodA()
    obj.methodB()
    // No suspension between these — atomic on MainActor
}
```

---

## SwiftUI View Isolation {#swiftui}

The isolation of `View` changed with the SDK, not just the compiler:

- **iOS 18-era SDKs (Xcode 16–18)**: per-member isolation — `body` is `@MainActor`, other members of a conforming type are NOT automatically MainActor.
- **iOS 26+ SDKs (Xcode 26/27)**: the entire `View` protocol is `@preconcurrency @MainActor` (verified in the SDK's SwiftUICore swiftinterface). A type whose primary declaration conforms to `View` is inferred `@MainActor` in full — all its members, not just `body`.

**Recommendation**: don't rely on the inference rules — make SwiftUI views `@MainActor` explicitly or via default MainActor isolation. Same end state on every SDK, and the intent is visible in source.

---

## ModelActor Pitfalls {#modelactor}

`@ModelActor` types are context-sensitive:
- Created on main thread → uses main thread for isolation (defeats purpose)
- Created on background → uses background (expected behavior)

```swift
// WRONG: creates on main thread, runs on main thread
@MainActor func makeActor() -> MyModelActor {
    MyModelActor(modelContainer: .shared)
}

// RIGHT: creates on background
func makeActor() async -> MyModelActor {
    MyModelActor(modelContainer: .shared)
}
```

Use the `withContext` pattern to push work into the ModelActor safely. See Massicotte's ModelActor article for the full `withContext` extension.

---

## Migration CLI Tool {#migration-cli}

Swift 6.2 introduces `swift package migrate` for automated migration:

```bash
swift package migrate --to-feature NonisolatedNonsendingByDefault,InferIsolatedConformances
# --to-feature accepts comma-separated list of features
```

Provides fix-its to preserve behavior when enabling `NonisolatedNonsendingByDefault` (adds `@concurrent` where needed).

---

## Escape Hatches {#escape-hatches}

| Escape Hatch | When to Use |
|-------------|-------------|
| `@unchecked Sendable` | Type has internal locking; you assert thread-safety |
| `nonisolated(unsafe)` | Targeted opt-out for a single declaration |
| `@preconcurrency import` | Module lacks correct annotations |
| `@preconcurrency` conformance | Protocol isolation mismatch you can't fix |
| `-disable-dynamic-actor-isolation` | Disable runtime MainActor checks (for Combine crashes) |
| Swift 5 companion module | Park code that can't be made Swift 6 compliant yet |

All escape hatches are technical debt. Use them to unblock, but track and revisit.
