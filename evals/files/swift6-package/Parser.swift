import Foundation

public final class ResponseParser: Sendable {
    public init() {}

    public func parse(_ data: Data) async throws -> [String: String] {
        // CPU-heavy JSON work.
        try JSONDecoder().decode([String: String].self, from: data)
    }
}
