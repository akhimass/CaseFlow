import SwiftUI

/// Monochrome aura visualizer that responds to AriaState + audio level.
struct AuraVisualizerView: View {
    let state: AriaState
    let audioLevel: Float
    var size: CGFloat = 200

    @State private var phase: Double = 0
    @State private var pulseScale: CGFloat = 1.0
    private let timer = Timer.publish(every: 1/60, on: .main, in: .common).autoconnect()

    // White when active, dim gray otherwise.
    private var intensity: Double {
        switch state {
        case .speaking:  return 1.0
        case .thinking:  return 0.85
        case .listening: return 0.8
        default:         return state.isActive ? 0.7 : 0.3
        }
    }

    private var animationSpeed: Double {
        switch state {
        case .speaking:  return 2.5
        case .thinking:  return 1.2
        case .listening: return 0.7
        default:         return 0.3
        }
    }

    var body: some View {
        ZStack {
            // Outer ambient glow
            Circle()
                .fill(Color.white.opacity(0.06 * intensity))
                .frame(width: size * 1.4, height: size * 1.4)
                .blur(radius: 20)

            // Animated rings
            ForEach(0..<3, id: \.self) { i in
                let delay = Double(i) * 0.3
                let scale = pulseScale - CGFloat(i) * 0.12
                let opacity = (state.isActive ? (0.5 - Double(i) * 0.15) : (0.15 - Double(i) * 0.04)) * intensity

                Circle()
                    .stroke(Color.white, lineWidth: i == 0 ? 1.5 : 1.0)
                    .frame(width: size * scale, height: size * scale)
                    .opacity(opacity)
                    .animation(
                        .easeInOut(duration: 1.2 + delay).repeatForever(autoreverses: true),
                        value: pulseScale
                    )
            }

            // Core canvas aura — grayscale layered arcs
            Canvas { ctx, size in
                let center = CGPoint(x: size.width / 2, y: size.height / 2)
                let r = min(size.width, size.height) / 2 * 0.9

                for i in 0..<36 {
                    let t = Double(i) / 36.0
                    let angleStart = Angle(radians: t * .pi * 2 + phase)
                    let angleEnd = Angle(radians: t * .pi * 2 + phase + .pi / 18)

                    // Grayscale brightness instead of hue rotation
                    let brightness = state.isActive ? (0.7 + Double(audioLevel) * 0.3) : 0.45
                    let alpha = (state.isActive ? (0.55 + Double(audioLevel) * 0.4) : 0.3) * intensity
                    let color = Color(white: brightness).opacity(alpha)

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
                .fill(Color.white)
                .frame(width: 6, height: 6)
                .opacity(state.isActive ? 0.85 : 0.3)
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
