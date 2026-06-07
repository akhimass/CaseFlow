import SwiftUI

struct MossResultsView: View {
    let events: [MossContextEvent]
    @State private var isExpanded = true
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        if events.isEmpty { EmptyView() } else {
            VStack(alignment: .leading, spacing: 8) {
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) { isExpanded.toggle() }
                } label: {
                    HStack(spacing: 6) {
                        Circle()
                            .fill(CaseFlowTheme.auraAccent(colorScheme))
                            .frame(width: 8, height: 8)
                        Text("Knowledge Matches")
                            .font(.cfLabel)
                            .foregroundStyle(CaseFlowTheme.textPrimary)
                        Spacer()
                        Text("\(events.count)")
                            .font(.cfCaption)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(CaseFlowTheme.auraAccent(colorScheme).opacity(0.15), in: Capsule())
                            .foregroundStyle(CaseFlowTheme.auraAccent(colorScheme))
                        Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundStyle(CaseFlowTheme.textSecondary)
                    }
                }
                .buttonStyle(.plain)

                if isExpanded {
                    ForEach(events.prefix(3)) { event in
                        MossEventCard(event: event)
                    }
                }
            }
        }
    }
}

private struct MossEventCard: View {
    let event: MossContextEvent
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            if !event.query.isEmpty {
                HStack {
                    Image(systemName: "magnifyingglass")
                        .font(.system(size: 10))
                        .foregroundStyle(CaseFlowTheme.textTertiary)
                    Text(event.query)
                        .font(.cfCaption)
                        .foregroundStyle(CaseFlowTheme.textSecondary)
                        .lineLimit(1)
                }
            }
            ForEach(event.results.prefix(2)) { result in
                Text(result.text)
                    .font(.cfCaption)
                    .foregroundStyle(CaseFlowTheme.textPrimary)
                    .lineLimit(3)
                    .padding(8)
                    .background(
                        RoundedRectangle(cornerRadius: 8)
                            .fill(CaseFlowTheme.auraAccent(colorScheme).opacity(0.07))
                            .overlay(
                                RoundedRectangle(cornerRadius: 8)
                                    .stroke(CaseFlowTheme.auraAccent(colorScheme).opacity(0.2), lineWidth: 0.5)
                            )
                    )
            }
        }
    }
}
