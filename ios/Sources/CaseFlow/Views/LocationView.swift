#if os(iOS)
import SwiftUI

struct LocationView: View {
    let onConfirm: (String) -> Void
    @StateObject private var locationService = LocationService()
    @State private var city = ""
    @State private var selectedState = "CA"
    @State private var gpsAttempted = false
    @Environment(\.colorScheme) private var colorScheme

    private let usStates = [
        "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
        "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
        "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
        "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
        "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"
    ]

    private var canContinue: Bool { city.trimmingCharacters(in: .whitespaces).count >= 2 }

    private var isResolving: Bool {
        if case .requesting = locationService.status { return true }
        if case .resolving = locationService.status { return true }
        return false
    }

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

            Spacer().frame(height: 32)

            // GPS button
            Button {
                gpsAttempted = true
                locationService.requestLocation()
            } label: {
                HStack(spacing: 8) {
                    if isResolving {
                        ProgressView()
                            .progressViewStyle(.circular)
                            .tint(.white)
                            .scaleEffect(0.85)
                    } else {
                        Image(systemName: "location.fill")
                    }
                    Text(isResolving ? "Detecting location…" : "Use My Location")
                        .font(.cfHeadline)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(CaseFlowTheme.auraAccent(colorScheme), in: RoundedRectangle(cornerRadius: 14))
            }
            .buttonStyle(.plain)
            .disabled(isResolving)
            .padding(.horizontal, 24)

            // GPS status feedback
            if case .denied = locationService.status {
                Text("Location access denied — please enter manually or enable in Settings.")
                    .font(.cfCaption)
                    .foregroundStyle(.orange)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 24)
                    .padding(.top, 8)
            } else if case .failed(let msg) = locationService.status {
                Text("Could not detect location: \(msg)")
                    .font(.cfCaption)
                    .foregroundStyle(.orange)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 24)
                    .padding(.top, 8)
            } else if case .resolved = locationService.status {
                Label("Location detected", systemImage: "checkmark.circle.fill")
                    .font(.cfCaption)
                    .foregroundStyle(.green)
                    .padding(.top, 8)
            }

            // Divider
            HStack {
                Rectangle().frame(height: 1).foregroundStyle(Color(.separator))
                Text("or enter manually")
                    .font(.cfCaption)
                    .foregroundStyle(CaseFlowTheme.textTertiary)
                    .fixedSize()
                Rectangle().frame(height: 1).foregroundStyle(Color(.separator))
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 20)

            // Manual form
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
        .onChange(of: locationService.city) { _, newCity in
            if !newCity.isEmpty { city = newCity }
        }
        .onChange(of: locationService.state) { _, newState in
            if !newState.isEmpty, usStates.contains(newState) {
                selectedState = newState
            }
        }
    }
}

#Preview {
    LocationView(onConfirm: { _ in })
}
#endif
