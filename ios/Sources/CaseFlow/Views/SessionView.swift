#if os(iOS)
import SwiftUI
import LiveKit
import PhotosUI
import UIKit

struct SessionView: View {
    @ObservedObject var manager: LiveKitManager
    @EnvironmentObject var appState: AppState
    let onEnd: () -> Void

    @State private var showIntelligencePanel = false
    @State private var docCaptureActive = false
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var selectedPhotoImage: UIImage?

    private var cameraActive: Bool { manager.cameraEnabled || selectedPhotoImage != nil }

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .bottom) {
                // Pure black background — matches the web app
                Color.black.ignoresSafeArea()

                VStack(spacing: 0) {
                    // Top: camera (when active) fills the panel; otherwise the aura
                    topPanel(width: geo.size.width, height: geo.size.height * 0.55)
                        .frame(height: geo.size.height * 0.55)

                    // Intelligence panel (transcript + Moss + case)
                    intelligencePanel
                        .frame(maxHeight: .infinity)
                }

                // Floating control bar
                controlBar
                    .padding(.bottom, geo.safeAreaInsets.bottom + 16)

                if let errorMessage = manager.errorMessage {
                    VStack {
                        Spacer()
                        Text(errorMessage)
                            .font(.cfCaption)
                            .foregroundStyle(.black)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 10)
                            .background(Color.white.opacity(0.95), in: RoundedRectangle(cornerRadius: 14))
                            .padding(.bottom, 100)
                            .padding(.horizontal, 24)
                    }
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                }
            }
            .ignoresSafeArea(edges: .bottom)
            .animation(.spring(response: 0.4, dampingFraction: 0.85), value: cameraActive)
        }
        .task { await manager.connect(agentMetadata: appState.buildAgentMetadata()) }
        .onDisappear { Task { await manager.disconnect() } }
        .onChange(of: selectedPhotoItem) { _, newItem in
            guard let newItem else { return }
            Task { await handleSelectedPhotoItem(newItem) }
        }
    }

    // MARK: Top panel

    @ViewBuilder
    private func topPanel(width: CGFloat, height: CGFloat) -> some View {
        if cameraActive {
            // Camera fills the whole top panel — big, edge to edge
            ZStack(alignment: .top) {
                cameraFullView
                    .frame(width: width, height: height)
                    .clipped()

                // Compact aura + state badge floating at the top
                HStack(spacing: 10) {
                    AuraVisualizerView(
                        state: manager.ariaState,
                        audioLevel: manager.audioLevel,
                        size: 40
                    )
                    VStack(alignment: .leading, spacing: 1) {
                        Text("Aria")
                            .font(.cfLabel)
                            .foregroundStyle(.white)
                        Text(manager.ariaState.label)
                            .font(.cfCaption)
                            .foregroundStyle(.white.opacity(0.7))
                    }
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 9)
                .background(.ultraThinMaterial, in: Capsule())
                .environment(\.colorScheme, .dark)
                .padding(.top, 14)
            }
        } else {
            // No camera — aura is the centerpiece
            ZStack {
                RadialGradient(
                    colors: [Color.white.opacity(0.10), Color.clear],
                    center: .center,
                    startRadius: 20,
                    endRadius: height * 0.55
                )
                VStack(spacing: 14) {
                    AuraVisualizerView(
                        state: manager.ariaState,
                        audioLevel: manager.audioLevel,
                        size: 175
                    )
                    VStack(spacing: 4) {
                        Text("Aria")
                            .font(.cfHeadline)
                            .foregroundStyle(.white)
                        Text(manager.ariaState.label)
                            .font(.cfCaption)
                            .foregroundStyle(.white.opacity(0.55))
                            .animation(.easeInOut(duration: 0.3), value: manager.ariaState.label)
                    }
                }
            }
            .frame(width: width)
        }
    }

    private var cameraFullView: some View {
        ZStack {
            if let selectedPhotoImage {
                Image(uiImage: selectedPhotoImage)
                    .resizable()
                    .scaledToFill()
            } else {
                LocalCameraView(room: manager.room)
            }

            DocumentCaptureOverlay(
                isActive: docCaptureActive || manager.capturingDocument || selectedPhotoImage != nil
            )
        }
        .background(Color(white: 0.06))
    }

    // MARK: Intelligence panel

    private var intelligencePanel: some View {
        VStack(spacing: 0) {
            // Tab bar
            HStack {
                PanelTabButton(label: "Transcript", isSelected: !showIntelligencePanel) {
                    withAnimation(.easeInOut(duration: 0.2)) { showIntelligencePanel = false }
                }
                PanelTabButton(label: "Knowledge", isSelected: showIntelligencePanel) {
                    withAnimation(.easeInOut(duration: 0.2)) { showIntelligencePanel = true }
                }
                Spacer()
            }
            .padding(.horizontal, 16)
            .padding(.top, 12)

            Divider().overlay(Color.white.opacity(0.12))

            if showIntelligencePanel {
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        if let update = manager.latestCaseUpdate {
                            CaseStatusView(update: update)
                        }

                        MossResultsView(events: manager.mossEvents)

                        if !manager.documentEvents.isEmpty {
                            DocumentEventsView(events: manager.documentEvents)
                        }

                        if manager.mossEvents.isEmpty
                            && manager.documentEvents.isEmpty
                            && manager.latestCaseUpdate == nil {
                            Text("Knowledge and case details will appear here as Aria works.")
                                .font(.cfCaption)
                                .foregroundStyle(.white.opacity(0.5))
                        }
                    }
                    .padding(16)
                }
            } else {
                TranscriptView(messages: manager.transcript)
            }
        }
        .background(Color.black)
        .environment(\.colorScheme, .dark)
        // Keep scrollable content clear of the floating control bar.
        .safeAreaInset(edge: .bottom) {
            Color.clear.frame(height: 96)
        }
    }

    // MARK: Control bar

    private var controlBar: some View {
        HStack(spacing: 18) {
            // Microphone (mute toggle)
            ControlButton(
                icon: manager.isMicMuted ? "mic.slash.fill" : "mic.fill",
                label: manager.isMicMuted ? "Muted" : "Mic",
                isActive: !manager.isMicMuted,
                color: manager.isMicMuted ? .red : .white
            ) {
                Task { await manager.toggleMic() }
            }

            // Camera toggle
            ControlButton(
                icon: manager.cameraEnabled ? "video.fill" : "video.slash.fill",
                label: "Camera",
                isActive: manager.cameraEnabled,
                color: .white
            ) {
                let next = !manager.cameraEnabled
                Task { try? await manager.setCamera(enabled: next) }
            }

            // Doc capture
            ControlButton(
                icon: "doc.viewfinder",
                label: "Doc",
                isActive: docCaptureActive || manager.capturingDocument,
                color: Color(red: 1.0, green: 0.65, blue: 0.0)
            ) {
                docCaptureActive.toggle()
                if !manager.cameraEnabled && docCaptureActive {
                    Task { try? await manager.setCamera(enabled: true) }
                }
            }

            PhotosPicker(selection: $selectedPhotoItem, matching: .images, photoLibrary: .shared()) {
                ControlButtonLabel(
                    icon: "photo.on.rectangle.angled",
                    label: "Photo",
                    isActive: selectedPhotoImage != nil,
                    color: Color(red: 1.0, green: 0.65, blue: 0.0)
                )
            }

            // End call
            ControlButton(
                icon: "phone.down.fill",
                label: "End",
                isActive: true,
                color: .red
            ) {
                Task {
                    await manager.disconnect()
                    onEnd()
                }
            }
        }
        .padding(.horizontal, 24)
        .padding(.vertical, 14)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 28))
        .environment(\.colorScheme, .dark)
        .padding(.horizontal, 16)
    }

    @MainActor
    private func handleSelectedPhotoItem(_ item: PhotosPickerItem) async {
        defer { selectedPhotoItem = nil }

        do {
            guard let data = try await item.loadTransferable(type: Data.self) else { return }

            let normalizedData: Data
            if let image = UIImage(data: data), let jpeg = image.jpegData(compressionQuality: 0.92) {
                selectedPhotoImage = image
                normalizedData = jpeg
            } else {
                selectedPhotoImage = UIImage(data: data)
                normalizedData = data
            }

            try await manager.sendDocumentFrame(
                imageData: normalizedData,
                docType: "insurance",
                source: "photo_library"
            )
        } catch {
            manager.errorMessage = error.localizedDescription
        }
    }
}

// MARK: - Supporting Views

private struct PanelTabButton: View {
    let label: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Text(label)
                    .font(.cfLabel)
                    .foregroundStyle(isSelected ? Color.white : Color.white.opacity(0.4))
                Rectangle()
                    .fill(isSelected ? Color.white : .clear)
                    .frame(height: 2)
                    .cornerRadius(1)
            }
        }
        .buttonStyle(.plain)
        .padding(.trailing, 16)
    }
}

private struct ControlButton: View {
    let icon: String
    let label: String
    let isActive: Bool
    let color: Color
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            ControlButtonLabel(icon: icon, label: label, isActive: isActive, color: color)
        }
        .buttonStyle(.plain)
    }
}

private struct ControlButtonLabel: View {
    let icon: String
    let label: String
    let isActive: Bool
    let color: Color

    var body: some View {
        VStack(spacing: 5) {
            Image(systemName: icon)
                .font(.system(size: 19, weight: .semibold))
                .foregroundStyle(isActive ? (color == .white ? .black : .white) : Color.white.opacity(0.85))
                .frame(width: 50, height: 50)
                .background(
                    Circle().fill(isActive ? color : Color.white.opacity(0.12))
                )
            Text(label)
                .font(.cfCaption)
                .foregroundStyle(.white.opacity(0.6))
        }
    }
}

private struct CaseStatusView: View {
    let update: CaseUpdate

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: "doc.badge.gearshape")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(.white)
                Text("Case Update")
                    .font(.cfLabel)
                    .foregroundStyle(.white)
                Spacer()
                Text(update.event.replacingOccurrences(of: "_", with: " ").capitalized)
                    .font(.cfCaption)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.white.opacity(0.15), in: Capsule())
                    .foregroundStyle(.white)
            }
            ForEach(Array(update.fields.sorted(by: { $0.key < $1.key }).prefix(5)), id: \.key) { key, value in
                HStack(alignment: .top) {
                    Text(key.replacingOccurrences(of: "_", with: " "))
                        .font(.cfCaption)
                        .foregroundStyle(.white.opacity(0.5))
                    Spacer()
                    Text(value)
                        .font(.cfCaption)
                        .foregroundStyle(.white.opacity(0.9))
                        .multilineTextAlignment(.trailing)
                        .lineLimit(2)
                }
            }
        }
        .padding(10)
        .background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 10))
    }
}

private struct DocumentEventsView: View {
    let events: [DocumentParseEvent]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: "doc.text.magnifyingglass")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(.orange)
                Text("Parsed Documents")
                    .font(.cfLabel)
                    .foregroundStyle(.white)
            }
            ForEach(events.prefix(3)) { event in
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 6) {
                        Text(event.docType.replacingOccurrences(of: "_", with: " ").capitalized)
                            .font(.cfLabel)
                            .foregroundStyle(.white)
                        Spacer()
                        statusBadge(for: event.status)
                    }
                    ForEach(Array(event.fields.prefix(4)), id: \.key) { key, value in
                        HStack {
                            Text(key.replacingOccurrences(of: "_", with: " "))
                                .font(.cfCaption)
                                .foregroundStyle(.white.opacity(0.5))
                            Spacer()
                            Text(value)
                                .font(.cfCaption)
                                .foregroundStyle(.white.opacity(0.9))
                                .multilineTextAlignment(.trailing)
                        }
                    }
                }
                .padding(10)
                .background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 10))
            }
        }
    }

    @ViewBuilder
    private func statusBadge(for status: DocumentParseStatus) -> some View {
        switch status {
        case .parsing:
            HStack(spacing: 4) {
                ProgressView().scaleEffect(0.6).tint(.white)
                Text("Parsing…")
                    .font(.cfCaption)
                    .foregroundStyle(.white.opacity(0.6))
            }
        case .parsed:
            HStack(spacing: 4) {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 11))
                    .foregroundStyle(.green)
                Text("Parsed")
                    .font(.cfCaption)
                    .foregroundStyle(.green)
            }
        case .error:
            HStack(spacing: 4) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 11))
                    .foregroundStyle(.red)
                Text("Error")
                    .font(.cfCaption)
                    .foregroundStyle(.red)
            }
        }
    }
}

// MARK: - Local camera (uses LiveKit Room)

private struct LocalCameraView: UIViewRepresentable {
    let room: Room

    func makeUIView(context: Context) -> UIView {
        let container = UIView()
        container.backgroundColor = UIColor(white: 0.06, alpha: 1)
        container.clipsToBounds = true
        let videoView = VideoView()
        videoView.tag = 1
        videoView.frame = container.bounds
        videoView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        container.addSubview(videoView)
        return container
    }

    func updateUIView(_ uiView: UIView, context: Context) {
        // Re-bind the track on every update — the local camera track may not exist
        // yet when the view is first created (publishing is async).
        let track = room.localParticipant.localVideoTracks.first?.track as? LocalVideoTrack
        (uiView.viewWithTag(1) as? VideoView)?.track = track
    }
}
#endif
