#if os(iOS)
import SwiftUI

struct LocationView: View {
    let onConfirm: (String) -> Void
    @State private var city = ""
    @State private var selectedState = "CA"
    @Environment(\.colorScheme) private var colorScheme

    private let usStates = [
        "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
        "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
        "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
        "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
        "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"
    ]

    private var canContinue: Bool { city.trimmingCharacters(in: .whitespaces).count >= 2 }

    var body: some View {
        VStack(spacing: 0) {
            // Header
            VStack(spacing: 10) {
                Image(systemName: "location.circle.fill")
                    .font(.system(size: 44))
                    .foregroundStyle(CaseFlowTheme.auraAccent(colorScheme))
                    .padding(.top, 48)

                Text("Where did this happen?")
                    .font(.cfTitle)
                    .foregroundStyle(CaseFlowTheme.textPrimary)
                    .multilineTextAlignment(.center)

                Text("We use your location to find the right attorney\nand look up applicable state laws.")
                    .font(.cfBody)
                    .foregroundStyle(CaseFlowTheme.textSecondary)
                    .multilineTextAlignment(.center)
                    .lineSpacing(4)
            }
            .padding(.horizontal, 32)

            Spacer().frame(height: 48)

            // Form
            VStack(spacing: 14) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("City")
                        .font(.cfLabel)
                        .foregroundStyle(CaseFlowTheme.textSecondary)
                    TextField("e.g. Orange County", text: $city)
                        .font(.cfBody)
                        .padding(14)
                        .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 12))
                        .autocorrectionDisabled()
                }

                VStack(alignment: .leading, spacing: 6) {
                    Text("State")
                        .font(.cfLabel)
                        .foregroundStyle(CaseFlowTheme.textSecondary)
                    Picker("State", selection: $selectedState) {
                        ForEach(usStates, id: \.self) { state in
                            Text(state).tag(state)
                        }
                    }
                    .pickerStyle(.menu)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(14)
                    .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 12))
                }
            }
            .padding(.horizontal, 24)

            Spacer()

            // CTA
            Button {
                let location = "\(city.trimmingCharacters(in: .whitespaces)), \(selectedState)"
                onConfirm(location)
            } label: {
                Text("Continue")
                    .font(.cfHeadline)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 17)
                    .background(
                        canContinue
                            ? CaseFlowTheme.auraAccent(colorScheme)
                            : CaseFlowTheme.auraAccent(colorScheme).opacity(0.4),
                        in: RoundedRectangle(cornerRadius: 16)
                    )
            }
            .buttonStyle(.plain)
            .disabled(!canContinue)
            .padding(.horizontal, 24)
            .padding(.bottom, 40)
        }
    }
}

#Preview {
    LocationView(onConfirm: { _ in })
}
#endif
