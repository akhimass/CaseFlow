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

    func giveConsent() {
        consentGivenAt = .now
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
        screen = .welcome
    }
}
