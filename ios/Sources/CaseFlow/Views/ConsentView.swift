#if os(iOS)
import SwiftUI

struct ConsentView: View {
    let onConsent: () -> Void
    let onDecline: () -> Void
    @State private var hasScrolledToBottom = true
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        VStack(spacing: 0) {
            // Header
            VStack(spacing: 8) {
                Image(systemName: "lock.shield.fill")
                    .font(.system(size: 36))
                    .foregroundStyle(CaseFlowTheme.auraAccent(colorScheme))
                    .padding(.top, 32)

                Text("Privacy & Consent")
                    .font(.cfTitle)
                    .foregroundStyle(CaseFlowTheme.textPrimary)

                Text("Please read and agree before your intake")
                    .font(.cfBody)
                    .foregroundStyle(CaseFlowTheme.textSecondary)
            }
            .padding(.bottom, 24)

            // Scrollable consent text
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    ConsentSection(
                        title: "Recording & Transcription",
                        icon: "waveform",
                        content: "This video consultation will be recorded and transcribed to assist with your personal injury case intake. Audio and video data are transmitted securely."
                    )
                    ConsentSection(
                        title: "Data Use",
                        icon: "doc.text",
                        content: "Your information, including documents you share, will be used solely to match you with a qualified personal injury attorney. We do not sell your data."
                    )
                    ConsentSection(
                        title: "Document Parsing",
                        icon: "doc.viewfinder",
                        content: "If you hold documents up to the camera, our system will parse them automatically to assist your intake. You may decline to share any document at any time."
                    )
                    ConsentSection(
                        title: "Your Rights",
                        icon: "person.badge.shield.checkmark",
                        content: "You may request deletion of your case data at any time by contacting support. You can end this session at any moment without penalty."
                    )

                    // Invisible anchor to detect scroll-to-bottom
                    GeometryReader { geo in
                        Color.clear
                            .onAppear { hasScrolledToBottom = true }
                    }
                    .frame(height: 1)
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 16)
            }
            .background(Color(.secondarySystemBackground))
            .cornerRadius(16)
            .padding(.horizontal, 16)

            // Actions
            VStack(spacing: 12) {
                Button(action: onConsent) {
                    Text("I Agree — Start My Intake")
                        .font(.cfHeadline)
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 17)
                        .background(
                            CaseFlowTheme.auraAccent(colorScheme)
                                .opacity(hasScrolledToBottom ? 1 : 0.5),
                            in: RoundedRectangle(cornerRadius: 16)
                        )
                }
                .buttonStyle(.plain)
                .disabled(!hasScrolledToBottom)

                Button(action: onDecline) {
                    Text("Decline")
                        .font(.cfBody)
                        .foregroundStyle(CaseFlowTheme.textSecondary)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 20)
        }
    }
}

private struct ConsentSection: View {
    let title: String
    let icon: String
    let content: String
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(CaseFlowTheme.auraAccent(colorScheme))
                Text(title)
                    .font(.cfHeadline)
                    .foregroundStyle(CaseFlowTheme.textPrimary)
            }
            Text(content)
                .font(.cfBody)
                .foregroundStyle(CaseFlowTheme.textSecondary)
                .lineSpacing(4)
        }
        .padding(14)
        .background(Color(.systemBackground), in: RoundedRectangle(cornerRadius: 12))
    }
}

#Preview {
    ConsentView(onConsent: {}, onDecline: {})
}
#endif
