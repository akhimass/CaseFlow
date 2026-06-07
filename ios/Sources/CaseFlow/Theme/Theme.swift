import SwiftUI

enum CaseFlowTheme {
    // Brand
    static let blue = Color(red: 0.145, green: 0.388, blue: 0.922)       // #2563EB
    static let blueDark = Color(red: 0.220, green: 0.741, blue: 0.973)    // #38BDF8
    static let ink = Color(red: 0.039, green: 0.039, blue: 0.039)         // #0A0A0A

    // Surfaces
    static let surface = Color(.systemBackground)
    static let surfaceSecondary = Color(.secondarySystemBackground)

    // Text
    static let textPrimary = Color(.label)
    static let textSecondary = Color(.secondaryLabel)
    static let textTertiary = Color(.tertiaryLabel)

    // Semantic
    static let success = Color(red: 0.118, green: 0.565, blue: 0.376)
    static let warning = Color(red: 0.957, green: 0.620, blue: 0.153)
    static let destructive = Color(.systemRed)

    // Aura accent — adapts to color scheme
    static func auraAccent(_ scheme: ColorScheme) -> Color {
        scheme == .dark ? blueDark : blue
    }
}

extension Font {
    static let cfTitle = Font.system(size: 28, weight: .bold, design: .rounded)
    static let cfHeadline = Font.system(size: 17, weight: .semibold, design: .rounded)
    static let cfBody = Font.system(size: 15, weight: .regular, design: .default)
    static let cfCaption = Font.system(size: 12, weight: .regular, design: .default)
    static let cfLabel = Font.system(size: 13, weight: .medium, design: .rounded)
}
