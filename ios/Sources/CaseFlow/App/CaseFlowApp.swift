#if os(iOS)
import SwiftUI

@main
struct CaseFlowApp: App {
    @StateObject private var appState = AppState()
    @StateObject private var liveKit = LiveKitManager()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(appState)
                .environmentObject(liveKit)
        }
    }
}

struct RootView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var liveKit: LiveKitManager

    var body: some View {
        ZStack {
            switch appState.screen {
            case .welcome:
                WelcomeView(onStart: {
                    withAnimation(.easeInOut(duration: 0.4)) {
                        appState.screen = .consent
                    }
                })
                .transition(.opacity.combined(with: .move(edge: .trailing)))

            case .consent:
                ConsentView(
                    onConsent: {
                        withAnimation(.easeInOut(duration: 0.4)) { appState.giveConsent() }
                    },
                    onDecline: {
                        withAnimation(.easeInOut(duration: 0.4)) { appState.screen = .welcome }
                    }
                )
                .transition(.opacity.combined(with: .move(edge: .trailing)))

            case .location:
                LocationView(onConfirm: { location in
                    withAnimation(.easeInOut(duration: 0.4)) { appState.confirmLocation(location) }
                })
                .transition(.opacity.combined(with: .move(edge: .trailing)))

            case .session:
                SessionView(
                    manager: liveKit,
                    onEnd: {
                        withAnimation(.easeInOut(duration: 0.4)) { appState.endSession() }
                    }
                )
                .transition(.opacity)

            case .ended:
                SessionEndedView(onStartNew: {
                    withAnimation(.easeInOut(duration: 0.4)) { appState.restart() }
                })
                .transition(.opacity.combined(with: .scale(scale: 0.95)))
            }
        }
        .animation(.easeInOut(duration: 0.35), value: appState.screen)
    }
}
#endif
