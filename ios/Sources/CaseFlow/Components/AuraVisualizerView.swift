import SwiftUI

/// GPU-lite aura visualizer that responds to AriaState + audio level.
/// Matches the web app's aura shader aesthetics using SwiftUI Canvas.
struct AuraVisualizerView: View {
    let state: AriaState
    let audioLevel: Float
    var size: CGFloat = 200
    @Environment(\.colorScheme) private var colorScheme

    @State private var phase: Double = 0
    @State private var pulseScale: CGFloat = 1.0
    private let timer = Timer.publish(every: 1/60, on: .main, in: .common).autoconnect()

    private var accentColor: Color { CaseFlowTheme.auraAccent(colorScheme) }

    private var animationSpeed: Double {
        switch state {
        case .speaking:  return 2.5
        case .thinking:  return 1.2
        case .listening: return 0.7
        default:         return 0.3
        }
    }

    private var targetScale: CGFloat {
        let base: CGFloat = state.isActive ? 1.0 : 0.85
        return base + CGFloat(audioLevel) * 0.4
    }

    var body: some View {
        ZStack {
            // Outer ambient glow
            Circle()
                .fill(accentColor.opacity(0.08))
                .frame(width: size * 1.4, height: size * 1.4)
                .blur(radius: 20)

            // Animated rings
            ForEach(0..<3, id: \.self) { i in
                let delay = Double(i) * 0.3
                let scale = pulseScale - CGFloat(i) * 0.12
                let opacity = state.isActive ? (0.5 - Double(i) * 0.15) : (0.15 - Double(i) * 0.04)

                Circle()
                    .stroke(accentColor, lineWidth: i == 0 ? 1.5 : 1.0)
                    .frame(width: size * scale, height: size * scale)
                    .opacity(opacity)
                    .animation(
                        .easeInOut(duration: 1.2 + delay).repeatForever(autoreverses: true),
                        value: pulseScale
                    )
            }

            // Core canvas aura
            Canvas { ctx, size in
                let center = CGPoint(x: size.width / 2, y: size.height / 2)
                let r = min(size.width, size.height) / 2 * 0.9

                // Draw layered arcs with hue rotation
                for i in 0..<36 {
                    let t = Double(i) / 36.0
                    let angleStart = Angle(radians: t * .pi * 2 + phase)
                    let angleEnd = Angle(radians: t * .pi * 2 + phase + .pi / 18)

                    // Hue shift like the web shader's colorShift
                    let hue = (0.6 + t * 0.25 + phase * 0.02).truncatingRemainder(dividingBy: 1.0)
                    let saturation = state.isActive ? 0.9 : 0.5
                    let brightness = state.isActive ? (0.7 + Double(audioLevel) * 0.3) : 0.4
                    let alpha = state.isActive ? (0.6 + Double(audioLevel) * 0.4) : 0.3

                    let color = Color(hue: hue, saturation: saturation, brightness: brightness)
                        .opacity(alpha)

                    let radiusVariance = r * (0.85 + sin(phase * 2 + t * .pi * 4) * 0.15 * Double(1 + audioLevel))
                    let path = Path { p in
                        p.addArc(
                            center: center,
                            radius: radiusVariance,
                            startAngle: angleStart,
                            endAngle: angleEnd,
                            clockwise: false
                        )
                    }
                    ctx.stroke(path, with: .color(color), lineWidth: 3)
                }
            }
            .frame(width: size, height: size)
            .clipShape(Circle())

            // Center dot
            Circle()
                .fill(accentColor)
                .frame(width: 6, height: 6)
                .opacity(state.isActive ? 0.8 : 0.3)
        }
        .frame(width: size * 1.4, height: size * 1.4)
        .onReceive(timer) { _ in
            phase += animationSpeed / 60.0
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true)) {
                pulseScale = 1.08
            }
        }
    }
}

#Preview {
    ZStack {
        Color.black.ignoresSafeArea()
        VStack(spacing: 40) {
            AuraVisualizerView(state: .speaking, audioLevel: 0.6, size: 180)
            AuraVisualizerView(state: .listening, audioLevel: 0.1, size: 180)
            AuraVisualizerView(state: .thinking, audioLevel: 0.0, size: 180)
        }
    }
}
