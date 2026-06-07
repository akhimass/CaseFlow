#if os(iOS)
import SwiftUI
import LiveKit
import PhotosUI
import UIKit

struct SessionView: View {
    @ObservedObject var manager: LiveKitManager
    let onEnd: () -> Void

    @State private var showIntelligencePanel = false
    @State private var isCameraOn = false
    @State private var docCaptureActive = false
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var selectedPhotoImage: UIImage?
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .bottom) {
                Color(.systemBackground).ignoresSafeArea()

                VStack(spacing: 0) {
                    // Top: Aria visualizer + camera
                    ZStack(alignment: .bottomTrailing) {
                        // Aria aura — full width on top half
                        auraPanel(width: geo.size.width)

                        // PiP: local camera preview
                        if isCameraOn || selectedPhotoImage != nil {
                            previewTile
                                .padding(16)
                        }
                    }
                    .frame(height: geo.size.height * 0.46)

                    // Intelligence panel (transcript + Moss)
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
                            .foregroundStyle(.white)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 10)
                            .background(Color.red.opacity(0.92), in: RoundedRectangle(cornerRadius: 14))
                            .padding(.bottom, 96)
                            .padding(.horizontal, 20)
                    }
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                }
            }
            .ignoresSafeArea(edges: .bottom)
        }
        .task { await manager.connect() }
        .onDisappear { Task { await manager.disconnect() } }
        .onChange(of: selectedPhotoItem) { _, newItem in
            guard let newItem else { return }
            Task { await handleSelectedPhotoItem(newItem) }
        }
    }

    // MARK: Subviews

    private func auraPanel(width: CGFloat) -> some View {
        ZStack {
            // Dark gradient bg for aura
            LinearGradient(
                colors: [
                    CaseFlowTheme.auraAccent(colorScheme).opacity(0.12),
                    Color(.systemBackground)
                ],
                startPoint: .top,
                endPoint: .bottom
            )

            VStack(spacing: 12) {
                AuraVisualizerView(
                    state: manager.ariaState,
                    audioLevel: manager.audioLevel,
                    size: 170
                )

                VStack(spacing: 4) {
                    Text("Aria")
                        .font(.cfHeadline)
                        .foregroundStyle(CaseFlowTheme.textPrimary)
                    Text(manager.ariaState.label)
                        .font(.cfCaption)
                        .foregroundStyle(CaseFlowTheme.textSecondary)
                        .animation(.easeInOut(duration: 0.3), value: manager.ariaState.label)
                }
            }
        }
    }

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
            .padding(.top, 10)

            Divider()

            if showIntelligencePanel {
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        MossResultsView(events: manager.mossEvents)

                        if !manager.documentEvents.isEmpty {
                            DocumentEventsView(events: manager.documentEvents)
                        }
                    }
                    .padding(16)
                }
            } else {
                TranscriptView(messages: manager.transcript)
            }
        }
        .background(Color(.systemBackground))
    }

    private var controlBar: some View {
        HStack(spacing: 20) {
            // Microphone
            ControlButton(
                icon: "mic.fill",
                label: "Mic",
                isActive: true,
                color: CaseFlowTheme.auraAccent(colorScheme)
            ) {}

            // Camera toggle
            ControlButton(
                icon: isCameraOn ? "video.fill" : "video.slash.fill",
                label: isCameraOn ? "Camera" : "Camera",
                isActive: isCameraOn,
                color: CaseFlowTheme.auraAccent(colorScheme)
            ) {
                isCameraOn.toggle()
                Task { try? await manager.setCamera(enabled: isCameraOn) }
            }

            // Doc capture
            ControlButton(
                icon: "doc.viewfinder",
                label: "Doc",
                isActive: docCaptureActive,
                color: .orange
            ) {
                docCaptureActive.toggle()
                if !isCameraOn && docCaptureActive {
                    isCameraOn = true
                    Task { try? await manager.setCamera(enabled: true) }
                }
            }

            PhotosPicker(selection: $selectedPhotoItem, matching: .images, photoLibrary: .shared()) {
                ControlButton(
                    icon: "photo.on.rectangle.angled",
                    label: "Photo",
                    isActive: selectedPhotoImage != nil,
                    color: .orange
                ) {}
            }

            // End call
            ControlButton(
                icon: "phone.down.fill",
                label: "End",
                isActive: false,
                color: .red
            ) {
                Task {
                    await manager.disconnect()
                    onEnd()
                }
            }
        }
        .padding(.horizontal, 32)
        .padding(.vertical, 14)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 24))
        .padding(.horizontal, 20)
    }

    private var previewTile: some View {
        ZStack(alignment: .bottom) {
            if let selectedPhotoImage {
                Image(uiImage: selectedPhotoImage)
                    .resizable()
                    .scaledToFill()
                    .frame(width: 100, height: 140)
                    .clipped()
            } else {
                LocalCameraView(room: manager.room)
                    .frame(width: 100, height: 140)
            }

            DocumentCaptureOverlay(isActive: docCaptureActive || selectedPhotoImage != nil)
        }
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(Color.white.opacity(0.3), lineWidth: 1)
        )
        .shadow(radius: 8, y: 4)
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
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Text(label)
                    .font(.cfLabel)
                    .foregroundStyle(isSelected ? CaseFlowTheme.auraAccent(colorScheme) : CaseFlowTheme.textSecondary)
                Rectangle()
                    .fill(isSelected ? CaseFlowTheme.auraAccent(colorScheme) : .clear)
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
            VStack(spacing: 5) {
                Image(systemName: icon)
                    .font(.system(size: 20, weight: .semibold))
                    .foregroundStyle(isActive ? color : Color(.tertiaryLabel))
                    .frame(width: 52, height: 52)
                    .background(
                        Circle()
                            .fill(isActive ? color.opacity(0.15) : Color(.secondarySystemBackground))
                    )
                Text(label)
                    .font(.cfCaption)
                    .foregroundStyle(Color(.secondaryLabel))
            }
        }
        .buttonStyle(.plain)
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
            }
            ForEach(events.prefix(3)) { event in
                VStack(alignment: .leading, spacing: 4) {
                    Text(event.docType.replacingOccurrences(of: "_", with: " ").capitalized)
                        .font(.cfLabel)
                        .foregroundStyle(.primary)
                    ForEach(Array(event.fields.prefix(4)), id: \.key) { key, value in
                        HStack {
                            Text(key.replacingOccurrences(of: "_", with: " "))
                                .font(.cfCaption)
                                .foregroundStyle(.secondary)
                            Spacer()
                            Text(value)
                                .font(.cfCaption)
                                .foregroundStyle(.primary)
                        }
                    }
                }
                .padding(10)
                .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 10))
            }
        }
    }
}

// MARK: - Local camera (uses LiveKit Room)

private struct LocalCameraView: UIViewRepresentable {
    let room: Room

    func makeUIView(context: Context) -> UIView {
        let view = UIView()
        view.backgroundColor = .black
        view.clipsToBounds = true
        view.layer.cornerRadius = 14

        if let track = room.localParticipant.localVideoTracks.first?.track as? LocalVideoTrack {
            let videoView = VideoView()
            videoView.track = track
            videoView.frame = view.bounds
            videoView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
            view.addSubview(videoView)
        }
        return view
    }

    func updateUIView(_ uiView: UIView, context: Context) {}
}
#endif
