#if os(iOS)
import SwiftUI

struct AuraVisualizerView: View {
    let state: AriaState
    let audioLevel: Float
    var size: CGFloat = 200

    @State private var phase: Double = 0
    @State private var breathScale: CGFloat = 1.0
    private let timer = Timer.publish(every: 1/60, on: .main, in: .common).autoconnect()

    // Monochrome — white when active, dim gray otherwise
    private var orbOpacity: Double {
        switch state {
        case .speaking:  return 1.0
        case .thinking:  return 0.85
        case .listening: return 0.80
        case .waiting:   return 0.40
        default:         return 0.20
        }
    }

    private var rotationSpeed: Double {
        switch state {
        case .speaking:  return 3.2
        case .thinking:  return 2.0
        case .listening: return 0.7
        default:         return 0.25
        }
    }

    private var breathDuration: Double {
        switch state {
        case .speaking:  return 0.45
        case .thinking:  return 1.0
        case .listening: return 2.0
        default:         return 4.0
        }
    }

    private var boost: CGFloat { CGFloat(audioLevel) }

    var body: some View {
        ZStack {
            // Ambient outer cloud
            Circle()
                .fill(Color.white.opacity(0.06 * orbOpacity))
                .frame(width: size * 1.55, height: size * 1.55)
                .blur(radius: 28)
                .scaleEffect(breathScale + boost * 0.18)

            // Outer ring
            Circle()
                .stroke(Color.white.opacity(0.08 * orbOpacity), lineWidth: 0.6)
                .frame(width: size * 1.02, height: size * 1.02)
                .scaleEffect(breathScale)

            // Mid ring
            Circle()
                .stroke(Color.white.opacity(0.15 * orbOpacity), lineWidth: 0.9)
                .frame(width: size * 0.88, height: size * 0.88)
                .scaleEffect(breathScale + boost * 0.06)

            // Inner ring
            Circle()
                .stroke(Color.white.opacity(0.30 * orbOpacity), lineWidth: 1.3)
                .frame(width: size * 0.76, height: size * 0.76)
                .scaleEffect(breathScale + boost * 0.12)

            // Thinking: sweeping arc
            if state == .thinking {
                Circle()
                    .trim(from: 0, to: 0.38)
                    .stroke(
                        AngularGradient(
                            colors: [Color.white.opacity(0.7), Color.clear],
                            center: .center
                        ),
                        style: StrokeStyle(lineWidth: 2.2, lineCap: .round)
                    )
                    .frame(width: size * 0.83, height: size * 0.83)
                    .rotationEffect(.radians(phase * 1.9))

                Circle()
                    .trim(from: 0, to: 0.18)
                    .stroke(Color.white.opacity(0.30), style: StrokeStyle(lineWidth: 1.4, lineCap: .round))
                    .frame(width: size * 0.83, height: size * 0.83)
                    .rotationEffect(.radians(phase * 1.9 + .pi * 1.25))
            }

            // Speaking: extra reactive pulse ring
            if state == .speaking && boost > 0.08 {
                Circle()
                    .stroke(Color.white.opacity(Double(boost) * 0.45), lineWidth: 1.5)
                    .frame(width: size * (0.76 + 0.20 * boost), height: size * (0.76 + 0.20 * boost))
                    .blur(radius: 2)
            }

            // Core orb
            Circle()
                .fill(
                    RadialGradient(
                        colors: [
                            Color.white.opacity(0.22 * orbOpacity),
                            Color.white.opacity(0.85 * orbOpacity),
                            Color.white.opacity(0.20 * orbOpacity),
                            Color.clear
                        ],
                        center: UnitPoint(x: 0.37, y: 0.30),
                        startRadius: 0,
                        endRadius: size * 0.44
                    )
                )
                .frame(width: size * 0.66, height: size * 0.66)
                .scaleEffect(breathScale + boost * 0.20)
                .shadow(color: Color.white.opacity(0.30 * orbOpacity), radius: 18, x: 0, y: 0)
        }
        .frame(width: size * 1.55, height: size * 1.55)
        .animation(.easeInOut(duration: 0.55), value: state)
        .onReceive(timer) { _ in
            phase += rotationSpeed / 60.0
        }
        .onAppear { animateBreath() }
        .onChange(of: state) { _, _ in
            breathScale = 1.0
            animateBreath()
        }
    }

    private func animateBreath() {
        withAnimation(.easeInOut(duration: breathDuration).repeatForever(autoreverses: true)) {
            breathScale = state.isActive ? 1.06 : 1.02
        }
    }
}

#Preview {
    ZStack {
        Color.black.ignoresSafeArea()
        VStack(spacing: 32) {
            HStack(spacing: 24) {
                VStack(spacing: 8) {
                    AuraVisualizerView(state: .speaking, audioLevel: 0.65, size: 110)
                    Text("Speaking").font(.caption).foregroundStyle(.white.opacity(0.5))
                }
                VStack(spacing: 8) {
                    AuraVisualizerView(state: .thinking, audioLevel: 0.0, size: 110)
                    Text("Thinking").font(.caption).foregroundStyle(.white.opacity(0.5))
                }
            }
            HStack(spacing: 24) {
                VStack(spacing: 8) {
                    AuraVisualizerView(state: .listening, audioLevel: 0.2, size: 110)
                    Text("Listening").font(.caption).foregroundStyle(.white.opacity(0.5))
                }
                VStack(spacing: 8) {
                    AuraVisualizerView(state: .waiting, audioLevel: 0.0, size: 110)
                    Text("Waiting").font(.caption).foregroundStyle(.white.opacity(0.5))
                }
            }
        }
    }
}
#endif
