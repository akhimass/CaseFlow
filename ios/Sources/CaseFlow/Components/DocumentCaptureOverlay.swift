import SwiftUI

/// Corner-bracket overlay drawn over the camera preview to guide doc framing.
struct DocumentCaptureOverlay: View {
    var isActive: Bool = false
    @Environment(\.colorScheme) private var colorScheme

    private let cornerLen: CGFloat = 28
    private let cornerWidth: CGFloat = 3

    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width
            let h = geo.size.height
            let inset: CGFloat = 16
            let color = CaseFlowTheme.auraAccent(colorScheme)

            ZStack {
                // Semi-tinted border
                RoundedRectangle(cornerRadius: 12)
                    .stroke(color.opacity(isActive ? 0.6 : 0.25), lineWidth: 1)
                    .padding(inset)

                // Corner brackets
                ForEach(Corner.allCases, id: \.self) { corner in
                    CornerBracket(corner: corner, inset: inset, len: cornerLen)
                        .stroke(color, style: StrokeStyle(lineWidth: cornerWidth, lineCap: .round))
                }

                if isActive {
                    VStack {
                        Spacer()
                        HStack {
                            Image(systemName: "doc.viewfinder")
                            Text("Hold document in frame")
                                .font(.cfCaption)
                        }
                        .foregroundStyle(color)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 5)
                        .background(.ultraThinMaterial, in: Capsule())
                        .padding(.bottom, inset + 8)
                    }
                }
            }
            .frame(width: w, height: h)
        }
        .animation(.easeInOut(duration: 0.3), value: isActive)
    }
}

private enum Corner: CaseIterable {
    case topLeft, topRight, bottomLeft, bottomRight
}

private struct CornerBracket: Shape {
    let corner: Corner
    let inset: CGFloat
    let len: CGFloat

    func path(in rect: CGRect) -> Path {
        let x0 = inset, x1 = rect.width - inset
        let y0 = inset, y1 = rect.height - inset

        var path = Path()
        switch corner {
        case .topLeft:
            path.move(to: CGPoint(x: x0, y: y0 + len))
            path.addLine(to: CGPoint(x: x0, y: y0))
            path.addLine(to: CGPoint(x: x0 + len, y: y0))
        case .topRight:
            path.move(to: CGPoint(x: x1 - len, y: y0))
            path.addLine(to: CGPoint(x: x1, y: y0))
            path.addLine(to: CGPoint(x: x1, y: y0 + len))
        case .bottomLeft:
            path.move(to: CGPoint(x: x0, y: y1 - len))
            path.addLine(to: CGPoint(x: x0, y: y1))
            path.addLine(to: CGPoint(x: x0 + len, y: y1))
        case .bottomRight:
            path.move(to: CGPoint(x: x1 - len, y: y1 - len))
            path.addLine(to: CGPoint(x: x1, y: y1))
            path.addLine(to: CGPoint(x: x1 - len, y: y1))
        }
        return path
    }
}
