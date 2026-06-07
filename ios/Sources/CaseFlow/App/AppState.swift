import SwiftUI

enum AppScreen {
    case welcome
    case consent
    case location
    case session
    case ended
}

@MainActor
final class AppState: ObservableObject {
    @Published var screen: AppScreen = .welcome
    @Published var callerLocation: String?
    @Published var consentGivenAt: Date?
    /// Stable per-session case id, minted at consent. Stamped into agent dispatch
    /// metadata so the agent seeds the case identically to the web intake.
    @Published private(set) var caseId: String = UUID().uuidString

    func giveConsent() {
        consentGivenAt = .now
        caseId = UUID().uuidString
        screen = .location
    }

    func confirmLocation(_ location: String) {
        callerLocation = location
        screen = .session
    }

    func endSession() {
        screen = .ended
    }

    func restart() {
        callerLocation = nil
        consentGivenAt = nil
        caseId = UUID().uuidString
        screen = .welcome
    }

    /// Mirrors the web `buildAgentMetadata` (`frontend/lib/privacy-token.ts`).
    /// `user_id` is added server-side by the token route.
    func buildAgentMetadata() -> [String: String] {
        var metadata: [String: String] = ["case_id": caseId]
        if let consentGivenAt {
            metadata["consent_given_at"] = ISO8601DateFormatter().string(from: consentGivenAt)
        }
        if let location = callerLocation?.trimmingCharacters(in: .whitespacesAndNewlines),
           !location.isEmpty {
            metadata["caller_location"] = location
        }
        return metadata
    }
}
