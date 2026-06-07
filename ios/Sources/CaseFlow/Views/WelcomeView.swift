#if os(iOS)
import SwiftUI

struct WelcomeView: View {
    let onStart: () -> Void
    @Environment(\.colorScheme) private var colorScheme
    @State private var pulseAura = false

    var body: some View {
        ZStack {
            // Background gradient
            LinearGradient(
                colors: [
                    CaseFlowTheme.auraAccent(colorScheme).opacity(0.05),
                    Color(.systemBackground)
                ],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                // Aura hero
                ZStack {
                    Circle()
                        .fill(CaseFlowTheme.auraAccent(colorScheme).opacity(0.08))
                        .frame(width: 200, height: 200)
                        .blur(radius: 30)
                        .scaleEffect(pulseAura ? 1.15 : 0.95)
                        .animation(.easeInOut(duration: 2.0).repeatForever(autoreverses: true), value: pulseAura)

                    Circle()
                        .stroke(CaseFlowTheme.auraAccent(colorScheme).opacity(0.25), lineWidth: 1.5)
                        .frame(width: 120, height: 120)
                        .scaleEffect(pulseAura ? 1.08 : 0.95)
                        .animation(.easeInOut(duration: 1.6).repeatForever(autoreverses: true), value: pulseAura)

                    // Logo/wordmark placeholder
                    VStack(spacing: 4) {
                        Image(systemName: "waveform.badge.mic")
                            .font(.system(size: 32, weight: .light))
                            .foregroundStyle(CaseFlowTheme.auraAccent(colorScheme))
                        Text("Aria")
                            .font(.system(size: 13, weight: .semibold, design: .rounded))
                            .foregroundStyle(CaseFlowTheme.auraAccent(colorScheme))
                    }
                }
                .padding(.bottom, 40)

                // Title block
                VStack(spacing: 10) {
                    Text("Start Your Case")
                        .font(.cfTitle)
                        .foregroundStyle(CaseFlowTheme.textPrimary)
                        .multilineTextAlignment(.center)

                    Text("Speak with Aria in English or Spanish.\nWe'll guide you through your intake.")
                        .font(.cfBody)
                        .foregroundStyle(CaseFlowTheme.textSecondary)
                        .multilineTextAlignment(.center)
                        .lineSpacing(4)
                }
                .padding(.horizontal, 32)

                Spacer().frame(height: 48)

                // Feature pills
                HStack(spacing: 10) {
                    FeaturePill(icon: "globe", label: "Bilingual")
                    FeaturePill(icon: "lock.fill", label: "Private")
                    FeaturePill(icon: "doc.text.viewfinder", label: "Doc scan")
                }
                .padding(.horizontal, 24)

                Spacer()

                // CTA
                VStack(spacing: 14) {
                    Button(action: onStart) {
                        HStack(spacing: 10) {
                            Image(systemName: "video.fill")
                            Text("Start My Case")
                                .font(.cfHeadline)
                        }
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 17)
                        .background(CaseFlowTheme.auraAccent(colorScheme), in: RoundedRectangle(cornerRadius: 16))
                    }
                    .buttonStyle(.plain)

                    Text("Tap to speak with Aria about your personal injury case")
                        .font(.cfCaption)
                        .foregroundStyle(CaseFlowTheme.textTertiary)
                        .multilineTextAlignment(.center)
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 40)
            }
        }
        .onAppear { pulseAura = true }
    }
}

private struct FeaturePill: View {
    let icon: String
    let label: String
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        HStack(spacing: 5) {
            Image(systemName: icon)
                .font(.system(size: 11, weight: .semibold))
            Text(label)
                .font(.cfLabel)
        }
        .foregroundStyle(CaseFlowTheme.auraAccent(colorScheme))
        .padding(.horizontal, 12)
        .padding(.vertical, 7)
        .background(CaseFlowTheme.auraAccent(colorScheme).opacity(0.1), in: Capsule())
    }
}

#Preview {
    WelcomeView(onStart: {})
}
#endif
