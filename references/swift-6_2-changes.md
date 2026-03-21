# Swift 6.2 Changes Reference

> **Read this file when**: working with `@concurrent`, `nonisolated(nonsending)`, default actor isolation, isolated conformances, `InferIsolatedConformances`, `NonisolatedNonsendingByDefault`, or needing to understand compiler settings.

## Table of Contents

1. [SE-0461: nonisolated(nonsending) by Default](#se-0461)
2. [SE-0466: Default Actor Isolation](#se-0466)
3. [SE-0470: Isolated Conformances](#se-0470)
4. [ObjC Import-as-Async Change](#objc-change)
5. [Compiler Settings Guide](#compiler-settings)
6. [Function Conversion Table](#function-conversions)

---

## SE-0461: Run nonisolated async functions on the caller's actor by default {#se-0461}

**Upcoming feature flag**: `NonisolatedNonsendingByDefault`
**Status**: Implemented in Swift 6.2

### The Behavior Change

**Before (SE-0338)**: nonisolated async functions ALWAYS switch off the caller's actor to run on the generic executor.

**After (with flag)**: nonisolated async functions stay on the caller's actor by default.

```swift
class NotSendable {
    func performAsync() async { ... }
}

actor MyActor {
    let x: NotSendable
    func call() async {
        // OLD: error — x leaves actor to generic executor
        // NEW: ok — performAsync stays on MyActor
        await x.performAsync()
    }
}
```

### Explicit Spellings

- `nonisolated(nonsending)` — explicit opt-in to new behavior (works in any language mode)
- `@concurrent` — explicit opt-in to old behavior (always switches off the actor to the generic executor)

### @concurrent Rules

- Implies `nonisolated` — cannot combine with `@MainActor`, `isolated` params, `@isolated(any)`
- Cannot apply to synchronous functions
- Can combine with `@Sendable` or `sending`
- Use when you want to guarantee switching off the actor

```swift
@concurrent func heavyWork() async -> Result { ... }  // always on generic executor
nonisolated(nonsending) func lightWork() async { ... } // stays on caller's actor
```

### Task Isolation Inheritance

**Unstructured tasks in nonisolated functions NEVER inherit actor isolation** — this is consistent across sync, nonsending async, and @concurrent async:

```swift
nonisolated(nonsending) func createTask(ns: NotSendable) async {
    Task {
        // Does NOT run on caller's actor
        ns.value += 1 // error: concurrent access
    }
}
```

### #isolation Behavior

- In `nonisolated(nonsending)` async function: expands to the implicit actor parameter (may be non-nil)
- In `@concurrent` async function: expands to `nil`
- In synchronous nonisolated function: expands to `nil`

### Dynamic Isolation APIs

`assumeIsolated`, `assertIsolated`, `preconditionIsolated` — the `noasync` restriction is removed. These are now usable in async contexts.

---

## SE-0466: Control Default Actor Isolation {#se-0466}

**Status**: Implemented in Swift 6.2. New Xcode 26 app projects default to MainActor.

### How to Set

**Xcode**: Build setting `SWIFT_DEFAULT_ACTOR_ISOLATION` = `MainActor`

**SPM**:
```swift
.target(
    name: "MyTarget",
    swiftSettings: [
        .defaultIsolation(MainActor.self)  // or nil for nonisolated
    ]
)
```

Only `MainActor.self` and `nil` are valid. Per-module setting.

### What Gets MainActor Inference

When `-default-isolation MainActor` is set:
- Free functions, classes, structs, enums → `@MainActor`
- Init, deinit, static vars, nested types → `@MainActor`
- Non-@Sendable closures and `Task.init` closures → inherit enclosing `@MainActor`

### What Does NOT Get MainActor Inference

- Declarations with explicit isolation (`@MyActor`, `nonisolated`)
- Declarations with inferred isolation from superclass, overrides, conformances
- **All declarations inside an `actor` type** (including static vars, init, deinit)
- Types conforming to protocols that inherit `SendableMetatype` (including `Sendable`)
- Types nested within a nonisolated type
- Typealiases, imports, enum cases, individual accessors
- `Task.detached` closures → always nonisolated

### Implicit Side Effect

Setting MainActor default **implicitly enables `InferIsolatedConformances`**.

---

## SE-0470: Global-Actor Isolated Conformances {#se-0470}

**Status**: Implemented in Swift 6.2
**Upcoming feature flag**: `InferIsolatedConformances`

### Syntax

```swift
@MainActor class MyModel: @MainActor Equatable {
    static func == (lhs: MyModel, rhs: MyModel) -> Bool {
        lhs.name == rhs.name  // ok: MainActor-isolated
    }
}
```

### Three Safety Rules

1. **Isolated conformance can only be used within its isolation domain**
2. **Cannot combine with `T: Sendable` or `T: SendableMetatype` constraints** — prevents sending isolated conformance across boundaries
3. **Values using isolated conformances merge into global actor's region** — cannot be `sending`

### SendableMetatype Protocol

- New marker protocol: `protocol SendableMetatype { }`
- `Sendable` inherits from `SendableMetatype`
- All concrete types implicitly conform to `SendableMetatype`
- Generic `T.Type` is only Sendable if `T: SendableMetatype`

### Dynamic Casts

`as?` / `is` checks executor at runtime for isolated conformances. Cast **fails** if not running on the conformance's actor. Cast involving `Sendable` or `SendableMetatype` never accepts isolated conformance.

### InferIsolatedConformances Behavior

When enabled, conformances of `@MainActor` types are inferred `@MainActor` UNLESS:
- Protocol inherits `SendableMetatype` (or `Sendable`) → inferred `nonisolated`
- All requirement-satisfying declarations are `nonisolated` → inferred `nonisolated`

### Protocol Conformance Solutions (ranked)

1. **nonisolated type** (Non-Sendable First Design) — no mismatch at all
2. **Isolated conformance** (`@MainActor Equatable`) — explicit, type-safe
3. **`@preconcurrency` conformance** — works everywhere, less type-safe
4. **`nonisolated` + `assumeIsolated`** — verbose, crashes if wrong

---

## ObjC Import-as-Async Change {#objc-change}

**NOT gated behind upcoming feature** — applies immediately in Swift 6.2.

Nonisolated ObjC functions matching the import-as-async heuristic (SE-0297) are now implicitly imported as `nonisolated(nonsending)`. This eliminates many data-race safety errors when calling ObjC async APIs from the main actor, because the function no longer switches to the generic executor.

The runtime behavior is unchanged (ObjC async already ran on caller's actor); only the compiler's understanding is corrected.

---

## Compiler Settings Guide {#compiler-settings}

### Just Turn These On (safe, unlikely to break anything)

BareSlashRegexLiterals, ConciseMagicFile, DeprecateApplicationMain, ForwardTrailingClosures, ImplicitOpenExistentials, ImportObjcForwardDeclarations, NonfrozenEnumExhaustivity, DisableOutwardActorInference, GlobalActorIsolatedTypesUsability, InferSendableFromCaptures, RegionBasedIsolation, IsolatedDefaultValues

### Need Understanding Before Enabling

| Setting | Effect |
|---------|--------|
| `NonisolatedNonsendingByDefault` | Changes nonisolated async to inherit caller isolation. **The big one.** |
| `InferIsolatedConformances` | MainActor types get MainActor conformances by default |
| `GlobalConcurrency` | Concurrency checks on global/static vars |
| `DynamicActorIsolation` | Turns potential data races into runtime crashes |
| `StrictConcurrency` | The main dial: minimal → targeted → complete |
| Default Actor Isolation | Permanent mode, not upcoming feature. MainActor or nonisolated. |

### Far Off (ignore for now)

ExistentialAny, InternalImportsByDefault, MemberImportVisibility

### "Approachable Concurrency" Xcode Setting

**In Swift 6 language mode**, enables exactly two additional flags:
- `NonisolatedNonsendingByDefault`
- `InferIsolatedConformances`

(The other 3 flags — DisableOutwardActorInference, GlobalActorIsolatedTypesUsability, InferSendableFromCaptures — are already part of Swift 6 mode.)

**In Swift 5 language mode**, enables all 5 flags listed in the SPM section above.

### Migration CLI

See [migration-guide.md](migration-guide.md) for `swift package migrate` CLI usage.

### Enabling in SPM Packages

Requires `swift-tools-version: 6.2` or later.

**Per-target:**
```swift
.target(
    name: "MyFeature",
    swiftSettings: [
        .defaultIsolation(MainActor.self),
        .enableUpcomingFeature("NonisolatedNonsendingByDefault"),
        .enableUpcomingFeature("InferIsolatedConformances")
    ]
)
```

**All targets (append to end of Package.swift):**
```swift
for target in package.targets {
    var settings = target.swiftSettings ?? []
    settings.append(contentsOf: [
        .defaultIsolation(MainActor.self),
        .enableUpcomingFeature("NonisolatedNonsendingByDefault"),
        .enableUpcomingFeature("InferIsolatedConformances")
    ])
    target.swiftSettings = settings
}
```

**Full Approachable Concurrency in SPM** (all 5 flags — needed for Swift 5 mode; in Swift 6 mode only the last 2 are additional):
```swift
.enableUpcomingFeature("DisableOutwardActorInference"),     // SE-401
.enableUpcomingFeature("GlobalActorIsolatedTypesUsability"), // SE-434
.enableUpcomingFeature("InferIsolatedConformances"),         // SE-470
.enableUpcomingFeature("InferSendableFromCaptures"),         // SE-418
.enableUpcomingFeature("NonisolatedNonsendingByDefault")     // SE-461
```

**Critical**: SPM and Xcode build settings are INDEPENDENT. Changes to one don't affect the other.

---

## Function Conversion Table {#function-conversions}

From SE-0461 — whether a function conversion crosses an isolation boundary (requiring Sendable args/results):

| From | To | Crosses Boundary? |
|------|-----|-------------------|
| Nonisolated / nonsending | Actor isolated | **No** |
| Nonisolated / nonsending | `@isolated(any)` | **No** |
| Nonisolated / nonsending | `@concurrent` | **No** |
| Actor isolated | Actor isolated | Yes |
| Actor isolated | `@isolated(any)` | **No** |
| Actor isolated | Nonisolated | Yes |
| Actor isolated | `@concurrent` | Yes |
| `@isolated(any)` | Actor isolated | Yes |
| `@isolated(any)` | Nonisolated | Yes |
| `@isolated(any)` | `@concurrent` | Yes |
| `@concurrent` | Actor isolated | Yes |
| `@concurrent` | `@isolated(any)` | **No** |
| `@concurrent` | Nonisolated | Yes |

Key insight: `nonisolated(nonsending)` → anything = no boundary crossing. This is why the new default eliminates so many Sendable errors.
