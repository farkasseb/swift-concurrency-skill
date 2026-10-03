#!/usr/bin/env python3
"""Compile and runtime probes for the swift-concurrency skill.

Run through tests/run.sh, which selects the Xcode. Every check prints PASS or
FAIL; the exit status is non-zero if any check fails.

Sections:
  snippets   every ```swift block in SKILL.md and references/ compiles, or fails
             with the diagnostic the text documents (swiftc -emit-sil, iOS SDK)
  facts      compile-time claims: feature defaults, default-isolation rules,
             diagnostics and their severity, availability gates
  runtime    where code runs, Task inheritance, cancellation, the Combine crash
             and legacy callback entry (macOS executables)
  templates  Swift settings in Xcode's new-project templates
  swiftpm    the Package.swift examples build and enable the documented features
"""

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
DEV = os.environ.get("DEVELOPER_DIR", "")
NN = ["-enable-upcoming-feature", "NonisolatedNonsendingByDefault"]
RESULTS = []
WORK = Path(tempfile.mkdtemp(prefix="swift-concurrency-probes-"))


def report(section, name, ok, detail=""):
    RESULTS.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  [{section}] {name}")
    if not ok and detail:
        print(textwrap.indent(detail.strip()[:1500], "      "))


def run(cmd, cwd=None, timeout=300):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def ios_sdk():
    return run(["xcrun", "--sdk", "iphoneos", "--show-sdk-path"]).stdout.strip()


def compile_ios(src, flags=(), target="17.0", mode="6", sil=True):
    """Compile for iOS; returns (returncode, [(severity, message)], raw stderr)."""
    path = WORK / f"probe{len(RESULTS)}_{abs(hash(src)) % 10**8}.swift"
    path.write_text(src)
    cmd = ["xcrun", "swiftc", "-parse-as-library", "-emit-sil" if sil else "-typecheck"]
    if sil:
        cmd += ["-o", os.devnull]
    cmd += ["-swift-version", mode, "-sdk", SDK, "-target", f"arm64-apple-ios{target}", *flags, str(path)]
    r = run(cmd)
    diags = re.findall(r"^\S+\.swift:\d+:\d+: (error|warning): (.*)$", r.stderr, re.M)
    return r.returncode, diags, r.stderr


def expect_clean(section, name, src, **kw):
    rc, diags, err = compile_ios(src, **kw)
    report(section, name, rc == 0 and not diags, err)


def expect_diag(section, name, src, needles, severity="error", **kw):
    rc, diags, err = compile_ios(src, **kw)
    msgs = [m for s, m in diags if s == severity]
    ok = all(any(n in m for m in msgs) for n in needles)
    if severity == "error":
        ok = ok and rc != 0
    report(section, name, ok, err)


def warnings_of(src, **kw):
    _, diags, _ = compile_ios(src, sil=False, **kw)
    return {m for s, m in diags if s == "warning"}


# ---------------------------------------------------------------- toolchain

def check_toolchain():
    r = run(["xcrun", "swiftc", "--version"])
    out = r.stdout + r.stderr
    m = re.search(r"Swift version (\d+)\.(\d+)", out)
    print(f"DEVELOPER_DIR={DEV or '(xcode-select default)'}")
    print(out.strip().splitlines()[0] if out.strip() else "no swiftc found")
    if not m or (int(m.group(1)), int(m.group(2))) < (6, 4):
        print("These probes need Swift 6.4 or later (Xcode 27). Set XCODE or DEVELOPER_DIR.")
        sys.exit(2)


# ---------------------------------------------------------------- snippets

def swift_blocks():
    blocks = []
    for f in [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]:
        text = f.read_text()
        for m in re.finditer(r"```swift\n(.*?)```", text, re.S):
            blocks.append((f.relative_to(SKILL).as_posix(), textwrap.dedent(m.group(1))))
    return blocks


R = "references/"
# (file, marker unique to the block, prelude, flags, target, expected error substrings or [], replace)
SNIPPETS = [
    (R + "execution-and-settings.md", "actor MyActor", "", [], "17.0", ["sending 'self.x' risks"], None),
    (R + "execution-and-settings.md", "actor MyActor", "", NN, "17.0", [], None),
    (R + "execution-and-settings.md", "struct ModelDecoder", "import Foundation\nstruct Model: Sendable { init(_ d: Data) {} }\n", NN, "17.0", [], None),
    (R + "execution-and-settings.md", "class Counter", "", NN, "17.0", ["passing closure as a 'sending' parameter"], None),
    (R + "execution-and-settings.md", "final class Profile", "", NN, "17.0", [], None),
    (R + "execution-and-settings.md", "final class Profile", "", NN, "17.0", ["Describable"],
     ("extension Profile: @MainActor Describable {",
      "func needsSendable<T: Describable & Sendable>(_ t: T) {}\n@MainActor func use(p: Profile) { needsSendable(p) }\n"
      "extension Profile: @MainActor Describable {")),
    (R + "migration.md", "final class FeedModel", "", [], "17.0", [], None),
    (R + "migration.md", "final class LegacyModel", "func legacyFetch(_ completion: @escaping (Int) -> Void) { completion(7) }\n", [], "17.0", [], None),
    (R + "migration.md", "LegacyDelegate", "", [], "17.0", [], None),
    (R + "migration.md", "public func schedule", "", [], "17.0", [], None),
    (R + "versions-and-availability.md", "func sync(over", "import Foundation\nfinal class Connection: Sendable {\n func close() async {}\n func send(_ d: Data) async throws {}\n}\n", [], "16.0", [], None),
    (R + "versions-and-availability.md", "withTaskCancellationShield", "final class Resource: Sendable {\n func shutdown() async {}\n func run() async {}\n}\n", [], "17.0", [], None),
    (R + "versions-and-availability.md", "struct Token: ~Sendable", "", [], "13.0", [], None),
    (R + "versions-and-availability.md", "struct Token: ~Sendable", "", [], "13.0", ["does not conform to the 'Sendable'"],
     ("struct Token: ~Sendable {", "func needsS<T: Sendable>(_ t: T) {}\nfunc use() { needsS(Token(id: 1)) }\nstruct Token: ~Sendable {")),
    (R + "versions-and-availability.md", "weak let owner", "", [], "13.0", [], None),
    (R + "versions-and-availability.md", "weak let owner", "", [], "13.0", ["contains non-Sendable type"],
     ("final class Coordinator: Sendable {}", "final class Coordinator {}")),
    (R + "versions-and-availability.md", "Task.immediate", "@MainActor final class DragModel { var isDragging = false; func loadPreview() async {} }\n", [], "17.0", [], None),
    (R + "versions-and-availability.md", "Observations(", "import Observation\n@MainActor @Observable final class Player { var score = 0 }\n", [], "17.0", [], None),
    (R + "versions-and-availability.md", "Observations(", "import Observation\n@Observable final class Player { var score = 0 }\n", [], "17.0", [], None),
    (R + "versions-and-availability.md", "Observations(", "import Observation\n@Observable final class Player { var score = 0 }\n", [], "17.0", ["non-Sendable"],
     ("@MainActor\nfunc watch", "nonisolated func watch")),
    (R + "design-patterns.md", "actor TokenStore", "", [], "17.0", [], None),
    (R + "design-patterns.md", "final class ImageCache", "", [], "18.0", [], None),
    (R + "design-patterns.md", "final class LockedCounter", "", [], "16.0", [], None),
    (R + "design-patterns.md", "func parseInBackground", "import Foundation\n", NN, "17.0", [], None),
    (R + "design-patterns.md", "final class SearchModel", "", NN, "17.0", [], None),
    (R + "design-patterns.md", "withTaskCancellationHandler",
     "final class LegacyRequest: Sendable {\n func start(_ c: @escaping @Sendable (Result<Int, any Error>) -> Void) {}\n func cancel() {}\n}\n",
     [], "17.0", [], None),
    (R + "design-patterns.md", "actor Outbox", "", NN, "17.0", [], None),
    (R + "design-patterns.md", "actor Outbox", "", NN, "17.0", ["risks causing data races"],
     ('    // draft.text = "again"', '    draft.text = "again"')),
]


def check_snippets():
    blocks = swift_blocks()
    used = set()
    for f, marker, prelude, flags, target, expect, repl in SNIPPETS:
        matches = [i for i, (bf, code) in enumerate(blocks) if bf == f and marker in code]
        name = f"{f} «{marker}»" + (" (variant)" if repl or expect else "") + (" +NNBD" if flags else "")
        if len(matches) != 1:
            report("snippets", name, False, f"expected exactly one block containing the marker, found {len(matches)}")
            continue
        used.add(matches[0])
        code = blocks[matches[0]][1]
        if repl:
            if repl[0] not in code:
                report("snippets", name, False, f"replacement anchor not found: {repl[0]!r}")
                continue
            code = code.replace(repl[0], repl[1])
        src = prelude + code
        if expect:
            expect_diag("snippets", name, src, expect, flags=flags, target=target)
        else:
            expect_clean("snippets", name, src, flags=flags, target=target)
    for i, (f, code) in enumerate(blocks):
        if i not in used and not code.lstrip().startswith("// swift-tools-version"):
            report("snippets", f"{f} block {code.splitlines()[0][:40]!r} has a probe", False,
                   "add a SNIPPETS entry for this block")


# ---------------------------------------------------------------- facts

def check_facts():
    s = "facts"
    features = """
#if hasFeature(NonisolatedNonsendingByDefault)
#warning("NonisolatedNonsendingByDefault")
#endif
#if hasFeature(InferIsolatedConformances)
#warning("InferIsolatedConformances")
#endif
#if hasFeature(DisableOutwardActorInference)
#warning("DisableOutwardActorInference")
#endif
#if hasFeature(InferSendableFromCaptures)
#warning("InferSendableFromCaptures")
#endif
#if hasFeature(GlobalActorIsolatedTypesUsability)
#warning("GlobalActorIsolatedTypesUsability")
#endif
#if hasFeature(ImmutableWeakCaptures)
#warning("ImmutableWeakCaptures")
#endif
"""
    five = {"NonisolatedNonsendingByDefault", "InferIsolatedConformances", "DisableOutwardActorInference",
            "InferSendableFromCaptures", "GlobalActorIsolatedTypesUsability"}
    w6 = warnings_of(features)
    report(s, "Swift 6 mode: NonisolatedNonsendingByDefault and InferIsolatedConformances are off",
           not ({"NonisolatedNonsendingByDefault", "InferIsolatedConformances"} & w6), str(w6))
    report(s, "Swift 6 mode includes the other three Approachable Concurrency features",
           {"DisableOutwardActorInference", "InferSendableFromCaptures", "GlobalActorIsolatedTypesUsability"} <= w6, str(w6))
    report(s, "ImmutableWeakCaptures is off in Swift 6 mode", "ImmutableWeakCaptures" not in w6, str(w6))
    wmain = warnings_of(features, flags=["-default-isolation", "MainActor"])
    report(s, "default MainActor isolation enables InferIsolatedConformances", "InferIsolatedConformances" in wmain, str(wmain))
    for mode in ("5", "6"):
        wac = warnings_of(features, mode=mode, flags=["-enable-upcoming-feature", "ApproachableConcurrency"])
        report(s, f"ApproachableConcurrency enables all five features (Swift {mode} mode)", five <= wac, str(wac))

    expect_diag(s, "default MainActor: plain `: Sendable` type is still MainActor",
                "struct S: Sendable { func f() -> Int { 1 } }\nnonisolated func use() -> Int { S().f() }\n",
                ["main actor-isolated"], flags=["-default-isolation", "MainActor"])
    expect_clean(s, "default MainActor: primary conformance to Error / CodingKey / nonisolated protocol exempts the type",
                 "struct E: Error { func f() -> Int { 1 } }\n"
                 "enum K: CodingKey { case a; func f() -> Int { 1 } }\n"
                 "nonisolated protocol Q: Sendable {}\nstruct V: Q { func f() -> Int { 1 } }\n"
                 "nonisolated func use() -> Int { E().f() + K.a.f() + V().f() }\n",
                 flags=["-default-isolation", "MainActor"])
    expect_diag(s, "default MainActor: conformance in an extension does not exempt",
                "struct E { func f() -> Int { 1 } }\nextension E: Error {}\nnonisolated func use() -> Int { E().f() }\n",
                ["main actor-isolated"], flags=["-default-isolation", "MainActor"])

    codable = ("import Foundation\nstruct Item: Codable { var id: Int }\n"
               "@concurrent func decode(_ d: Data) async throws -> Item { try JSONDecoder().decode(Item.self, from: d) }\n")
    expect_diag(s, "default MainActor: a Codable struct cannot be decoded off the main actor", codable,
                ["main actor-isolated conformance of 'Item' to 'Decodable'"], flags=["-default-isolation", "MainActor"])
    expect_clean(s, "default MainActor: a `nonisolated` type fixes the Codable conformance",
                 codable.replace("struct Item", "nonisolated struct Item"), flags=["-default-isolation", "MainActor"])
    expect_clean(s, "default MainActor: a `nonisolated` conformance fixes it too",
                 codable.replace("struct Item: Codable { var id: Int }",
                                 "struct Item { var id: Int }\nextension Item: nonisolated Codable {}"),
                 flags=["-default-isolation", "MainActor"])

    expect_diag(s, "SE-0434: explicit Sendable on @MainActor subclass of non-Sendable class is a warning",
                "class Base {}\n@MainActor final class Sub: Base, Sendable {}\n",
                ["cannot conform to the 'Sendable' protocol", "future Swift language mode"], severity="warning")
    rc, _, err = compile_ios("class Base {}\n@MainActor final class Sub: Base, Sendable {}\n")
    report(s, "SE-0434 case compiles (no error)", rc == 0, err)
    expect_clean(s, "@unchecked Sendable subclass of non-Sendable / ~Sendable base",
                 "class Base {}\n@MainActor final class Sub: Base, @unchecked Sendable {}\n"
                 "class B2: ~Sendable {}\nfinal class S2: B2, @unchecked Sendable {}\n")

    expect_diag(s, "public non-frozen struct is not implicitly Sendable",
                "public struct P { let v: [Int] }\nfunc n<T: Sendable>(_ t: T) {}\nfunc u() { n(P(v: [])) }\n",
                ["does not conform to the 'Sendable'"])
    expect_clean(s, "internal struct with Sendable fields is implicitly Sendable",
                 "struct P { let v: [Int] }\nfunc n<T: Sendable>(_ t: T) {}\nfunc u() { n(P(v: [])) }\n")

    expect_diag(s, "a separate NSLock does not make ordinary mutable storage checked Sendable",
                "import Foundation\nfinal class Counter: Sendable {\n"
                " let lock = NSLock()\n private var value = 0\n"
                " func increment() { lock.lock(); defer { lock.unlock() }; value += 1 }\n}\n",
                ["is mutable"], target="16.0")

    expect_diag(s, "SE-0520: unused throwing Task warns",
                "func f() { Task { try await Task.sleep(for: .seconds(1)) } }\n",
                ["unstructured throwing task", "is not used"], severity="warning")
    expect_clean(s, "SE-0520: `_ = Task { ... }` silences the warning",
                 "func f() { _ = Task { try await Task.sleep(for: .seconds(1)) } }\n")

    expect_diag(s, "@concurrent cannot combine with a global actor", "@MainActor @concurrent func a() async {}\n",
                ["@MainActor and @concurrent"])
    expect_diag(s, "@concurrent cannot take an isolated parameter", "actor A {}\n@concurrent func b(_ x: isolated A) async {}\n",
                ["isolated parameter"])
    expect_diag(s, "@concurrent requires async", "@concurrent func c() {}\n", ["non-async"])
    expect_diag(s, "@concurrent cannot combine with @isolated(any)",
                "func f(_ g: @concurrent @isolated(any) () async -> Void) {}\n", ["@isolated(any)"])
    expect_diag(s, "@concurrent method on non-Sendable instance stored in @MainActor type is a sending error",
                "import Foundation\nfinal class P { @concurrent func run(_ d: Data) async -> Int { 1 } }\n"
                "@MainActor final class VM { let p = P(); func go(_ d: Data) async { _ = await p.run(d) } }\n",
                ["sending 'self.p' risks"], flags=NN)
    expect_clean(s, "@concurrent method on a stateless struct stored in @MainActor type",
                 "import Foundation\nstruct P { @concurrent func run(_ d: Data) async -> Int { 1 } }\n"
                 "@MainActor final class VM { let p = P(); func go(_ d: Data) async { _ = await p.run(d) } }\n", flags=NN)
    expect_diag(s, "nonisolated witness cannot read a Sendable `var` or a non-Sendable `let`",
                "final class Ref { var x = 0 }\n@MainActor final class P { var name = \"\"; let ref = Ref() }\n"
                "extension P: Equatable { nonisolated static func == (l: P, r: P) -> Bool { l.name == r.name } }\n"
                "nonisolated func g(_ p: P) { _ = p.ref }\n",
                ["property 'name' can not be referenced", "property 'ref' can not be referenced"])
    expect_diag(s, "App Intents: a @MainActor intent type fails conformance isolation",
                "import AppIntents\n@MainActor struct I: AppIntent {\n static let title: LocalizedStringResource = \"I\"\n"
                " func perform() async throws -> some IntentResult { .result() }\n}\n",
                ["crosses into main actor-isolated code"])
    expect_clean(s, "App Intents: @MainActor perform() on a nonisolated intent",
                 "import AppIntents\nstruct I: AppIntent {\n static let title: LocalizedStringResource = \"I\"\n"
                 " @MainActor func perform() async throws -> some IntentResult { .result() }\n}\n")
    expect_diag(s, "global mutable var is an error in Swift 6 mode", "var counter = 0\n",
                ["nonisolated global shared mutable state"])

    # Availability: runtime APIs fail below their OS; compiler features compile at iOS 13.
    gated = [
        ("Task.immediate", "func f() { Task.immediate { } }", "26.0"),
        ("addImmediateTask", "func f() async { await withTaskGroup(of: Void.self) { g in g.addImmediateTask { } } }", "26.0"),
        ("static Task.name", "func f() -> String? { Task.name }", "26.0"),
        ("Observations", "import Observation\n@MainActor func f() { _ = Observations { 1 } }", "26.0"),
        ("instance task.name", "func f(t: Task<Void, Never>) -> String? { t.name }", "27.0"),
        ("withTaskCancellationShield", "func f() async { await withTaskCancellationShield { } }", "27.0"),
        ("Task.hasActiveCancellationShield", "func f() async -> Bool { Task.hasActiveCancellationShield }", "27.0"),
        ("withContinuation(of:)", "func f() async -> Int { await withContinuation(of: Int.self) { $0.resume(returning: 1) } }", "27.0"),
        ("UnownedTaskExecutor Hashable", "@available(iOS 18, *) func f(e: UnownedTaskExecutor) -> Int { e.hashValue }", "27.0"),
        ("Mutex", "import Synchronization\nfunc f() { _ = Mutex(0) }", "18.0"),
        ("typed-failure AsyncSequence", "func f() -> some AsyncSequence<Int, Never> { AsyncStream<Int> { $0.finish() } }", "18.0"),
        ("OSAllocatedUnfairLock", "import os\nfunc f() { _ = OSAllocatedUnfairLock(initialState: 0) }", "16.0"),
        ("Clock.systemEpoch", "func f() { _ = ContinuousClock().systemEpoch }", "16.0"),
    ]
    for name, src, version in gated:
        rc, diags, err = compile_ios(src + "\n", target="13.0", sil=False)
        ok = rc != 0 and any(f"only available in iOS {version} or newer" in m for _, m in diags)
        report(s, f"{name} requires iOS {version.split('.')[0]}", ok, err)
    anytarget = """
final class Owner: Sendable {}
final class Holder: Sendable { weak let owner: Owner?; init(o: Owner) { owner = o } }
final class Conn: Sendable { func close() async {} }
func d() async { let c = Conn(); defer { await c.close() }; await Task.yield() }
struct T: ~Sendable { let x: Int }
@MainActor final class D { var x = 0; isolated deinit { x = 1 } }
func n() { _ = Task(name: "n") { }; _ = Task.detached(name: "d") { } }
func r() async { _ = await Result { try await work() } }
func work() async throws {}
func s() { let (_, _) = AsyncStream<Int>.makeStream() }
@concurrent func c() async {}
nonisolated(nonsending) func ns() async {}
"""
    expect_clean(s, "compiler features and back-deployed APIs compile at iOS 13", anytarget, target="13.0")


# ---------------------------------------------------------------- runtime

def run_macos(name, src, flags=(), expect_crash=False):
    d = WORK / f"rt_{name}"
    d.mkdir()
    (d / "main.swift").write_text(src)
    r = run(["xcrun", "swiftc", "-swift-version", "6", *flags, "-o", str(d / "x"), str(d / "main.swift")])
    if r.returncode != 0:
        return None, r.stderr
    try:
        p = run([str(d / "x")], timeout=30)
    except subprocess.TimeoutExpired:
        return None, "timed out"
    if expect_crash:
        return p.returncode, p.stdout + p.stderr
    return (p.stdout if p.returncode == 0 else None), p.stdout + p.stderr


def check_runtime():
    s = "runtime"
    where = """
import Foundation
nonisolated func onMain() -> Bool { Thread.isMainThread }
final class Worker {
    func plain() async -> Bool { onMain() }
    @concurrent func conc() async -> Bool { onMain() }
}
nonisolated func syncWork() -> Bool { onMain() }
func defaultIsoSync() -> Bool { onMain() }
@MainActor func probe() async {
    let w = Worker()
    let plain = await w.plain()
    let conc = await Worker().conc()
    async let a = syncWork()
    async let b = defaultIsoSync()
    let t = Task { onMain() }
    print("plain=\\(plain) concurrent=\\(conc) asyncLetNonisolated=\\(await a) asyncLetDefault=\\(await b) task=\\(await t.value)")
}
await probe()
"""
    configs = [
        ("NNBD off", [], "plain=false concurrent=false asyncLetNonisolated=false asyncLetDefault=false task=true"),
        ("NNBD on", NN, "plain=true concurrent=false asyncLetNonisolated=false asyncLetDefault=false task=true"),
        ("NNBD on + default MainActor", NN + ["-default-isolation", "MainActor"],
         "plain=true concurrent=false asyncLetNonisolated=false asyncLetDefault=true task=true"),
    ]
    for i, (label, flags, expected) in enumerate(configs):
        out, log = run_macos(f"where{i}", where, flags)
        report(s, f"where code runs, called from @MainActor ({label})", out is not None and out.strip() == expected,
               f"expected: {expected}\ngot: {log}")

    inherit = """
func isolationName(_ actor: isolated (any Actor)? = #isolation) -> String { String(describing: actor) }
actor A {
    func noCapture() async -> Bool { await Task { isolationName() == "nil" }.value }
    func capture() async -> Bool { await Task { _ = self; return isolationName() != "nil" }.value }
}
func param(_ a: isolated A) async -> Bool { await Task { isolationName() == "nil" }.value }
func paramCaptured(_ a: isolated A) async -> Bool { await Task { _ = a; return isolationName() != "nil" }.value }
let a = A()
print(await a.noCapture(), await a.capture(), await param(a), await paramCaptured(a))
"""
    out, log = run_macos("inherit", inherit)
    report(s, "Task in an actor / isolated-parameter context is isolated only when it captures the actor",
           out is not None and out.strip() == "true true true true", log)

    cancel = """
let outer = Task {
    let inner = Task { try? await Task.sleep(for: .milliseconds(200)); return Task.isCancelled }
    async let child: Bool = { try? await Task.sleep(for: .milliseconds(200)); return Task.isCancelled }()
    let c = await child
    let i = await inner.value
    print(c, i)
}
outer.cancel()
_ = await outer.value
"""
    out, log = run_macos("cancel", cancel)
    report(s, "cancelling a task cancels its async let child but not a nested Task", out is not None and out.strip() == "true false", log)

    preferred_executor = """
import Dispatch
final class QueueExecutor: TaskExecutor {
    let queue = DispatchQueue(label: "skill.executor.preference")
    func enqueue(_ job: consuming ExecutorJob) {
        let job = UnownedJob(job)
        let executor = asUnownedTaskExecutor()
        queue.async { job.runSynchronously(on: executor) }
    }
}
@concurrent func nonisolatedWork(on executor: QueueExecutor) async -> Bool {
    dispatchPrecondition(condition: .onQueue(executor.queue))
    return #isolation == nil
}
actor Counter {
    private var value = 0
    func increment(on executor: QueueExecutor) -> Int {
        preconditionIsolated()
        dispatchPrecondition(condition: .onQueue(executor.queue))
        value += 1
        return value
    }
}
let executor = QueueExecutor()
let counter = Counter()
let result = await Task(executorPreference: executor) { @Sendable in
    let nonisolated = await nonisolatedWork(on: executor)
    let value = await counter.increment(on: executor)
    return "\\(nonisolated) \\(value)"
}.value
print(result)
"""
    out, log = run_macos("executor_preference", preferred_executor, NN)
    report(s, "@concurrent and a default actor honor task executor preference while retaining their isolation",
           out is not None and out.strip() == "true 1", log)

    search = next(code for f, code in swift_blocks()
                  if f == R + "design-patterns.md" and "final class SearchModel" in code)
    # Replace only the example's API stub; keep its task, cleanup, stop and commit code.
    search = search.replace("async -> [String] { [query] }",
                            "async -> [String] { await SearchGate.shared.search(query) }")
    search_driver = """
actor SearchGate {
    static let shared = SearchGate()
    private var requests: [String: CheckedContinuation<[String], Never>] = [:]
    private var arrivals: [String: CheckedContinuation<Void, Never>] = [:]
    func search(_ query: String) async -> [String] {
        await withCheckedContinuation { continuation in
            requests[query] = continuation
            arrivals.removeValue(forKey: query)?.resume()
        }
    }
    func waitForRequest(_ query: String) async {
        if requests[query] != nil { return }
        await withCheckedContinuation { arrivals[query] = $0 }
    }
    func finish(_ query: String) {
        requests.removeValue(forKey: query)!.resume(returning: [query])
    }
}
extension SearchModel {
    func taskForProbe() -> Task<Void, Never>? { searchTask }
}
let model = SearchModel()
model.queryChanged("old")
let old = model.taskForProbe()!
await SearchGate.shared.waitForRequest("old")
model.queryChanged("new")
let new = model.taskForProbe()!
await SearchGate.shared.waitForRequest("new")
await SearchGate.shared.finish("old")
await old.value
precondition(model.taskForProbe() != nil, "lost replacement handle")
precondition(model.results.isEmpty, "old result was published")
model.stop()
precondition(new.isCancelled, "replacement was not cancelled")
await SearchGate.shared.finish("new")
await new.value
precondition(model.results.isEmpty, "result published after stop")
model.queryChanged("again")
let again = model.taskForProbe()!
await SearchGate.shared.waitForRequest("again")
await SearchGate.shared.finish("again")
await again.value
precondition(model.results == ["again"], "reuse failed")
precondition(model.taskForProbe() == nil, "completed task was retained")
print("replacement cancelled; reuse succeeded")
"""
    out, log = run_macos("search_restart", search + search_driver, NN)
    report(s, "cancel-and-replace preserves the new handle, stops publication and supports reuse",
           out is not None and out.strip() == "replacement cancelled; reuse succeeded", log)
    unguarded = search.replace("if currentRequest == requestID { searchTask = nil }", "searchTask = nil")
    rc, log = run_macos("search_unguarded_cleanup", unguarded + search_driver, NN, expect_crash=True)
    report(s, "the same schedule detects an old task clearing its replacement's handle",
           rc is not None and rc != 0 and "lost replacement handle" in log, log)

    bridge = next(code for f, code in swift_blocks()
                  if f == R + "design-patterns.md" and "withTaskCancellationHandler" in code)
    bridge_driver = """
final class LegacyRequest: Sendable {
    let events = Mutex<[String]>([])
    func start(_ completion: @escaping @Sendable (Result<Int, any Error>) -> Void) {
        events.withLock { $0.append("start") }
        completion(.success(1))
    }
    func cancel() { events.withLock { $0.append("cancel") } }
}
let request = LegacyRequest()
let value = try await Task {
    withUnsafeCurrentTask { $0?.cancel() }
    return try await fetch(request)
}.value
print(value, request.events.withLock { $0 })
"""
    out, log = run_macos("bridge_precancelled", "import Synchronization\n" + bridge + bridge_driver)
    report(s, "an already-cancelled task runs onCancel first, then the bridged operation",
           out is not None and out.strip() == '1 ["cancel", "start"]', log)

    # A real Swift 5 module reproduces actor-isolation erasure at a legacy boundary.
    legacy = WORK / "LegacyCallbacks.swift"
    legacy.write_text("import Dispatch\npublic func legacyFetch(_ completion: @escaping (Int) -> Void) {\n"
                      " DispatchQueue.global().async { completion(7) }\n}\n")
    legacy_object = WORK / "LegacyCallbacks.o"
    built = run(["xcrun", "swiftc", "-swift-version", "5", "-parse-as-library",
                 "-emit-module", "-emit-module-path", str(WORK / "LegacyCallbacks.swiftmodule"),
                 "-emit-object", "-module-name", "LegacyCallbacks", str(legacy), "-o", str(legacy_object)])
    report(s, "legacy callback fixture builds in Swift 5 mode", built.returncode == 0, built.stderr)
    if built.returncode == 0:
        client = next(code for f, code in swift_blocks()
                      if f == R + "migration.md" and "final class LegacyModel" in code)
        client = "@preconcurrency import LegacyCallbacks\n" + client
        driver = "\nlet model = LegacyModel()\nawait model.load()\nprint(model.value)\n"
        flags = ["-I", str(WORK), str(legacy_object)]
        out, log = run_macos("legacy_callback_fixed", client + driver, flags)
        report(s, "a nonisolated Sendable callback returns to MainActor before load completes",
               out is not None and out.strip() == "7", log)
        broken = client.replace("legacyFetch { @Sendable value in", "legacyFetch { value in")
        broken = broken.replace("continuation.resume(returning: value)",
                                "Task { @MainActor in continuation.resume(returning: value) }")
        rc, log = run_macos("legacy_callback_inner_hop", broken + driver, flags, expect_crash=True)
        report(s, "an inner MainActor task does not repair the outer callback's entry isolation",
               rc == -signal.SIGTRAP, f"returncode={rc}\n{log}")

    block = next(code for f, code in swift_blocks() if f == R + "migration.md" and "final class FeedModel" in code)
    driver = "\nlet m = await FeedModel()\nawait m.start()\ntry await Task.sleep(for: .milliseconds(300))\nprint(\"no crash\")\n"
    rc, log = run_macos("combine", block + driver, expect_crash=True)
    report(s, "migration.md Combine example traps in Swift 6 mode", rc is not None and rc != 0 and "no crash" not in log, log)
    fixed = block.replace(".sink { value in", ".sink { @Sendable value in")
    rc, log = run_macos("combinefixed", fixed + driver, expect_crash=True)
    report(s, "the @Sendable fix stops the trap", rc == 0 and "no crash" in log, log)


# ---------------------------------------------------------------- templates

def check_templates():
    s = "templates"
    base = Path(DEV or run(["xcode-select", "-p"]).stdout.strip()) / "Library/Xcode/Templates/Project Templates/Base"

    def setting(plist, key):
        m = re.search(rf"<key>{key}</key>\s*<string>([^<]*)</string>", plist.read_text())
        return m.group(1) if m else None

    proj = base / "Base_ProjectSettings.xctemplate/TemplateInfo.plist"
    app = base / "App Base.xctemplate/TemplateInfo.plist"
    if not proj.exists() or not app.exists():
        report(s, "template files found", False, f"missing {proj} or {app}")
        return
    report(s, "SWIFT_VERSION = 5.0", setting(proj, "SWIFT_VERSION") == "5.0", str(setting(proj, "SWIFT_VERSION")))
    report(s, "SWIFT_APPROACHABLE_CONCURRENCY = YES", setting(proj, "SWIFT_APPROACHABLE_CONCURRENCY") == "YES")
    report(s, "app targets: SWIFT_DEFAULT_ACTOR_ISOLATION = MainActor", setting(app, "SWIFT_DEFAULT_ACTOR_ISOLATION") == "MainActor")


# ---------------------------------------------------------------- swiftpm

def build_package(name, manifest, source):
    d = WORK / f"pkg_{name}"
    (d / "Sources" / "Feature").mkdir(parents=True)
    (d / "Package.swift").write_text(manifest)
    (d / "Sources" / "Feature" / "F.swift").write_text(source)
    r = run(["xcrun", "swift", "build"], cwd=d, timeout=600)
    clean = re.sub(r"\x1b\[[0-9;]*m", "", r.stdout + r.stderr)
    return r.returncode, clean


def check_swiftpm():
    s = "swiftpm"
    probe = ('#if hasFeature(NonisolatedNonsendingByDefault)\n#warning("feature-NNBD")\n#endif\n'
             '#if hasFeature(DisableOutwardActorInference)\n#warning("feature-DOAI")\n#endif\n'
             "func f() {}\n")
    text = (SKILL / "references/execution-and-settings.md").read_text()
    manifest = next(m.group(1) for m in re.finditer(r"```swift\n(.*?)```", text, re.S) if "swift-tools-version" in m.group(1))
    rc, log = build_package("skill", manifest, probe)
    report(s, "execution-and-settings.md Package.swift builds with NonisolatedNonsendingByDefault on",
           rc == 0 and "feature-NNBD" in log, log[-1500:])

    combined = ('// swift-tools-version: 6.2\nimport PackageDescription\nlet package = Package(name: "Feature", targets: ['
                '.target(name: "Feature", swiftSettings: [.swiftLanguageMode(.v5), .enableUpcomingFeature("ApproachableConcurrency")])])\n')
    rc, log = build_package("approachable", combined, probe)
    report(s, ".enableUpcomingFeature(\"ApproachableConcurrency\") enables the features in a package",
           rc == 0 and "feature-NNBD" in log and "feature-DOAI" in log, log[-1500:])

    plain = '// swift-tools-version: 6.2\nimport PackageDescription\nlet package = Package(name: "Feature", targets: [.target(name: "Feature")])\n'
    rc, log = build_package("mode", plain, "var counter = 0\n")
    report(s, "tools-version 6.2 without a language mode builds in Swift 6 mode",
           rc != 0 and "nonisolated global shared mutable state" in log, log[-1500:])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip", action="append", default=[],
                        choices=["snippets", "facts", "runtime", "templates", "swiftpm"])
    args = parser.parse_args()
    check_toolchain()
    global SDK
    SDK = ios_sdk()
    for section, fn in [("snippets", check_snippets), ("facts", check_facts), ("runtime", check_runtime),
                        ("templates", check_templates), ("swiftpm", check_swiftpm)]:
        if section not in args.skip:
            fn()
    if "swiftpm" in args.skip:
        print("note: the Package.swift block in references/ is checked only by the swiftpm section")
    failed = RESULTS.count(False)
    print(f"\n{len(RESULTS) - failed} passed, {failed} failed")
    if failed:
        print(f"probe files kept in {WORK}")
    else:
        shutil.rmtree(WORK, ignore_errors=True)
    sys.exit(1 if failed else 0)


SDK = ""

if __name__ == "__main__":
    main()
