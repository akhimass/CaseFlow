#if os(iOS)
import SwiftUI

struct SessionEndedView: View {
    let onStartNew: () -> Void
    @Environment(\.colorScheme) private var colorScheme
    @State private var showConfetti = false

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [
                    CaseFlowTheme.success.opacity(0.08),
                    Color(.systemBackground)
                ],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                // Success icon
                ZStack {
                    Circle()
                        .fill(CaseFlowTheme.success.opacity(0.12))
                        .frame(width: 120, height: 120)

                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 56))
                        .foregroundStyle(CaseFlowTheme.success)
                }
                .padding(.bottom, 28)

                Text("Intake Complete")
                    .font(.cfTitle)
                    .foregroundStyle(CaseFlowTheme.textPrimary)
                    .padding(.bottom, 10)

                Text("Aria has captured your case details.\nA matching firm will contact you shortly.")
                    .font(.cfBody)
                    .foregroundStyle(CaseFlowTheme.textSecondary)
                    .multilineTextAlignment(.center)
                    .lineSpacing(4)
                    .padding(.horizontal, 40)

                Spacer().frame(height: 48)

                // What happens next
                VStack(alignment: .leading, spacing: 14) {
                    NextStepRow(icon: "person.2.fill", text: "Your case is being matched to qualified PI attorneys in your area")
                    NextStepRow(icon: "phone.fill", text: "A firm will call you within 24 hours to schedule a consultation")
                    NextStepRow(icon: "doc.text.fill", text: "Your intake summary has been securely stored")
                }
                .padding(20)
                .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 16))
                .padding(.horizontal, 24)

                Spacer()

                Button(action: onStartNew) {
                    Text("Start a New Case")
                        .font(.cfHeadline)
                        .foregroundStyle(CaseFlowTheme.auraAccent(colorScheme))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 17)
                        .background(
                            CaseFlowTheme.auraAccent(colorScheme).opacity(0.12),
                            in: RoundedRectangle(cornerRadius: 16)
                        )
                }
                .buttonStyle(.plain)
                .padding(.horizontal, 24)
                .padding(.bottom, 40)
            }
        }
    }
}

private struct NextStepRow: View {
    let icon: String
    let text: String
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 15))
                .foregroundStyle(CaseFlowTheme.auraAccent(colorScheme))
                .frame(width: 24)
            Text(text)
                .font(.cfBody)
                .foregroundStyle(CaseFlowTheme.textPrimary)
                .lineSpacing(3)
        }
    }
}

#Preview {
    SessionEndedView(onStartNew: {})
}
#endif
