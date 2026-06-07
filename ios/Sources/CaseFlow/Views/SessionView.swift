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
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var selectedPhotoImage: UIImage?

    private var cameraActive: Bool { isCameraOn || selectedPhotoImage != nil }

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .bottom) {
                // Pure black background — matches the web app
                Color.black.ignoresSafeArea()

                VStack(spacing: 0) {
                    // Top: camera (when active) takes the whole panel; otherwise the aura
                    topPanel(width: geo.size.width, height: geo.size.height * 0.55)
                        .frame(height: geo.size.height * 0.55)

                    // Intelligence panel (transcript + Moss)
                    intelligencePanel
                        .frame(maxHeight: .infinity)
                }

                // Floating control bar
                controlBar
                    .padding(.bottom, geo.safeAreaInsets.bottom + 16)

                // Error toast
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
        .task { await manager.connect() }
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
                VStack(spacing: 16) {
                    AuraVisualizerView(
                        state: manager.ariaState,
                        audioLevel: manager.audioLevel,
                        size: 180
                    )
                    VStack(spacing: 4) {
                        Text("Aria")
                            .font(.cfHeadline)
                            .foregroundStyle(.white)
                        HStack(spacing: 5) {
                            if manager.ariaState == .thinking {
                                ProgressView()
                                    .progressViewStyle(.circular)
                                    .scaleEffect(0.55)
                                    .tint(.white.opacity(0.6))
                            }
                            Text(manager.ariaState.label)
                                .font(.cfCaption)
                                .foregroundStyle(.white.opacity(0.55))
                                .animation(.easeInOut(duration: 0.3), value: manager.ariaState.label)
                        }
                    }
                }
            }
            .frame(width: width)
        }
    }

    private var cameraFullView: some View {
        ZStack(alignment: .bottomLeading) {
            if let image = selectedPhotoImage {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFill()
            } else {
                LocalCameraView(track: manager.localVideoTrack)
            }

            if selectedPhotoImage != nil {
                Text("Document")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(.black.opacity(0.6), in: Capsule())
                    .padding(16)
            }
        }
        .background(Color(white: 0.06))
    }

    // MARK: Intelligence panel

    private var intelligencePanel: some View {
        VStack(spacing: 0) {
            // Tab bar
            HStack(spacing: 0) {
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
                        if manager.isAnalyzingDocument {
                            analyzingBanner
                        }
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
        .background(Color.black)
        .environment(\.colorScheme, .dark)
        // Keep scrollable content clear of the floating control bar.
        .safeAreaInset(edge: .bottom) {
            Color.clear.frame(height: 96)
        }
    }

    private var analyzingBanner: some View {
        HStack(spacing: 8) {
            ProgressView()
                .progressViewStyle(.circular)
                .scaleEffect(0.7)
                .tint(.white)
            Text("Analyzing document…")
                .font(.cfLabel)
                .foregroundStyle(.white.opacity(0.85))
            Spacer()
        }
        .padding(12)
        .background(Color.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
    }

    // MARK: Control bar

    private var controlBar: some View {
        HStack(spacing: 18) {
            // Camera toggle
            ControlButton(
                icon: isCameraOn ? "video.fill" : "video.slash.fill",
                label: "Camera",
                isActive: isCameraOn
            ) {
                isCameraOn.toggle()
                Task { try? await manager.setCamera(enabled: isCameraOn) }
            }

            // Doc scan from photo library
            PhotosPicker(
                selection: $selectedPhotoItem,
                matching: .images,
                photoLibrary: .shared()
            ) {
                ControlButtonLabel(
                    icon: "doc.viewfinder.fill",
                    label: "Scan Doc",
                    isActive: selectedPhotoImage != nil
                )
            }

            // End call
            Button {
                Task {
                    await manager.disconnect()
                    onEnd()
                }
            } label: {
                VStack(spacing: 5) {
                    Image(systemName: "phone.down.fill")
                        .font(.system(size: 22, weight: .semibold))
                        .foregroundStyle(.black)
                        .frame(width: 58, height: 58)
                        .background(Color.white, in: Circle())
                    Text("End")
                        .font(.cfCaption)
                        .foregroundStyle(.white.opacity(0.6))
                }
            }
            .buttonStyle(.plain)

            // Knowledge toggle
            ControlButton(
                icon: showIntelligencePanel ? "text.bubble.fill" : "brain",
                label: showIntelligencePanel ? "Transcript" : "Knowledge",
                isActive: showIntelligencePanel
            ) {
                withAnimation(.easeInOut(duration: 0.2)) {
                    showIntelligencePanel.toggle()
                }
            }

            // Mic mute toggle
            ControlButton(
                icon: manager.isMicMuted ? "mic.slash.fill" : "mic.fill",
                label: manager.isMicMuted ? "Muted" : "Mic",
                isActive: !manager.isMicMuted
            ) {
                Task { await manager.toggleMic() }
            }
        }
        .padding(.horizontal, 22)
        .padding(.vertical, 14)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 28))
        .environment(\.colorScheme, .dark)
        .padding(.horizontal, 16)
    }

    // MARK: Photo handler

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
            // Jump to the Knowledge tab so the parsed analysis is visible.
            withAnimation(.easeInOut(duration: 0.2)) { showIntelligencePanel = true }
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
            VStack(spacing: 5) {
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
        .padding(.trailing, 20)
    }
}

private struct ControlButton: View {
    let icon: String
    let label: String
    let isActive: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            ControlButtonLabel(icon: icon, label: label, isActive: isActive)
        }
        .buttonStyle(.plain)
    }
}

private struct ControlButtonLabel: View {
    let icon: String
    let label: String
    let isActive: Bool

    var body: some View {
        VStack(spacing: 5) {
            Image(systemName: icon)
                .font(.system(size: 19, weight: .semibold))
                .foregroundStyle(isActive ? Color.black : Color.white.opacity(0.85))
                .frame(width: 50, height: 50)
                .background(
                    Circle().fill(isActive ? Color.white : Color.white.opacity(0.12))
                )
            Text(label)
                .font(.cfCaption)
                .foregroundStyle(.white.opacity(0.6))
        }
    }
}

private struct DocumentEventsView: View {
    let events: [DocumentParseEvent]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: "doc.text.magnifyingglass")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(.white.opacity(0.7))
                Text("Parsed Documents")
                    .font(.cfLabel)
                    .foregroundStyle(.white)
            }
            ForEach(events.prefix(3)) { event in
                VStack(alignment: .leading, spacing: 4) {
                    Text(event.docType.replacingOccurrences(of: "_", with: " ").capitalized)
                        .font(.cfLabel)
                        .foregroundStyle(.white)
                    ForEach(Array(event.fields.prefix(4)), id: \.key) { key, value in
                        HStack {
                            Text(key.replacingOccurrences(of: "_", with: " "))
                                .font(.cfCaption)
                                .foregroundStyle(.white.opacity(0.5))
                            Spacer()
                            Text(value)
                                .font(.cfCaption)
                                .foregroundStyle(.white.opacity(0.85))
                        }
                    }
                }
                .padding(10)
                .background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 10))
            }
        }
    }
}

// MARK: - Local camera preview

private struct LocalCameraView: UIViewRepresentable {
    let track: LocalVideoTrack?

    func makeUIView(context: Context) -> UIView {
        let container = UIView()
        container.backgroundColor = UIColor(white: 0.06, alpha: 1)
        container.clipsToBounds = true
        let videoView = VideoView()
        videoView.tag = 1
        videoView.frame = container.bounds
        videoView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        videoView.track = track
        container.addSubview(videoView)
        return container
    }

    func updateUIView(_ uiView: UIView, context: Context) {
        (uiView.viewWithTag(1) as? VideoView)?.track = track
    }
}
#endif
