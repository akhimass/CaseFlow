#if os(iOS)
import AVFoundation
import Foundation
import LiveKit
import Combine
import UIKit

@MainActor
final class LiveKitManager: ObservableObject {
    // MARK: State
    @Published var ariaState: AriaState = .disconnected
    @Published var audioLevel: Float = 0
    @Published var transcript: [TranscriptMessage] = []
    @Published var mossEvents: [MossContextEvent] = []
    @Published var documentEvents: [DocumentParseEvent] = []
    @Published var isConnected = false
    @Published var errorMessage: String?
    @Published var localVideoTrack: LocalVideoTrack?
    @Published var isMicMuted = false
    @Published var isAnalyzingDocument = false

    private let fallbackRoom = Room()
    private let tokenService = TokenService()
    private var session: Session?
    private var sessionObservation: AnyCancellable?
    private var audioLevelTask: Task<Void, Never>?
    private var audioRouteObserver: NSObjectProtocol?

    var room: Room {
        session?.room ?? fallbackRoom
    }

    // MARK: Connect

    func connect(agentMetadata: [String: String] = [:]) async {
        _ = agentMetadata
        ariaState = .connecting
        errorMessage = nil
        transcript = []
        mossEvents = []
        documentEvents = []

        if session != nil {
            await disconnect()
        }

        do {
            try await configureAudioSession()
            let session = Session(tokenSource: tokenService)
            self.session = session
            session.room.add(delegate: self)
            observeSession(session)

            try await session.start()

            // WebRTC reconfigures the audio session when remote audio tracks
            // arrive (asynchronously, after session.start returns). Register a
            // persistent observer so we lock to speaker on every route change.
            audioRouteObserver = NotificationCenter.default.addObserver(
                forName: AVAudioSession.routeChangeNotification,
                object: nil,
                queue: .main
            ) { [weak self] _ in
                guard self?.isConnected == true else { return }
                try? AVAudioSession.sharedInstance().overrideOutputAudioPort(.speaker)
            }

            syncFromSession()
            if session.agent.agentState == nil {
                ariaState = .waiting
            }
        } catch {
            ariaState = .disconnected
            errorMessage = error.localizedDescription
            sessionObservation?.cancel()
            sessionObservation = nil
            session = nil
        }
    }

    private func configureAudioSession() async throws {
        let session = AVAudioSession.sharedInstance()
        let permission = await withCheckedContinuation { continuation in
            session.requestRecordPermission { granted in
                continuation.resume(returning: granted)
            }
        }

        guard permission else {
            throw NSError(
                domain: "CaseFlow.Audio",
                code: 1,
                userInfo: [NSLocalizedDescriptionKey: "Microphone access is required for Aria to hear you."]
            )
        }

        try session.setCategory(.playAndRecord, mode: .videoChat, options: [.defaultToSpeaker, .allowBluetooth, .allowBluetoothA2DP])
        try session.setActive(true)
        // Override immediately so the built-in speaker is the output before
        // WebRTC starts configuring routes.
        try? session.overrideOutputAudioPort(.speaker)
    }

    func disconnect() async {
        audioLevelTask?.cancel()
        audioLevelTask = nil
        sessionObservation?.cancel()
        sessionObservation = nil
        if let obs = audioRouteObserver {
            NotificationCenter.default.removeObserver(obs)
            audioRouteObserver = nil
        }

        let activeSession = session
        session = nil

        await activeSession?.end()
        isConnected = false
        ariaState = .disconnected
        audioLevel = 0
        transcript = []
        mossEvents = []
        documentEvents = []
    }

    func setCamera(enabled: Bool) async throws {
        let publication = try await room.localParticipant.setCamera(enabled: enabled)

        guard enabled else {
            localVideoTrack = nil
            return
        }

        // Prefer the track from the returned publication. Publishing can lag the
        // call returning, so poll briefly until the local video track appears.
        if let track = publication?.track as? LocalVideoTrack {
            localVideoTrack = track
            return
        }

        for _ in 0..<20 {
            if let track = room.localParticipant.localVideoTracks.first?.track as? LocalVideoTrack {
                localVideoTrack = track
                return
            }
            try? await Task.sleep(nanoseconds: 100_000_000) // 100ms
        }
    }

    /// Toggle the local microphone. When muted, Aria stops receiving audio.
    func toggleMic() async {
        let newMuted = !isMicMuted
        do {
            try await room.localParticipant.setMicrophone(enabled: !newMuted)
            isMicMuted = newMuted
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func sendDocumentFrame(imageData: Data, docType: String, source: String) async throws {
        guard let session else {
            throw NSError(
                domain: "CaseFlow.LiveKit",
                code: 2,
                userInfo: [NSLocalizedDescriptionKey: "Session is not connected."]
            )
        }

        // Show an "analyzing" indicator until parsed fields come back from the agent.
        isAnalyzingDocument = true

        let imageBase64 = imageData.base64EncodedString()
        let payload: [String: Any] = [
            "type": "document_frame",
            "data": [
                "doc_type": docType,
                "image_base64": "data:image/jpeg;base64,\(imageBase64)",
                "turn": 0,
                "source": source
            ]
        ]
        let data = try JSONSerialization.data(withJSONObject: payload)
        try await session.room.localParticipant.publish(
            data: data,
            options: DataPublishOptions(reliable: true)
        )
    }

    // MARK: Audio level polling

    private func startAudioLevelPolling(track: RemoteAudioTrack) {
        _ = track
        audioLevelTask?.cancel()
        audioLevelTask = Task { [weak self] in
            while !Task.isCancelled {
                await MainActor.run {
                    // LiveKit exposes audioLevel on RemoteParticipant
                    if let participant = self?.room.remoteParticipants.values.first {
                        self?.audioLevel = Float(participant.audioLevel)
                    }
                }
                try? await Task.sleep(nanoseconds: 50_000_000) // 50ms
            }
        }
    }

    private func observeSession(_ session: Session) {
        sessionObservation = session.objectWillChange.sink { [weak self] _ in
            Task { @MainActor in
                self?.syncFromSession()
            }
        }
    }

    private func syncFromSession() {
        guard let session else { return }

        isConnected = session.isConnected

        if let sessionError = session.error {
            errorMessage = sessionError.localizedDescription
        } else if let agentError = session.agent.error {
            errorMessage = agentError.localizedDescription
        }

        ariaState = resolveAriaState(session: session)

        transcript = session.messages.compactMap { message in
            let text: String
            let isAgent: Bool

            switch message.content {
            case .agentTranscript(let value):
                text = value
                isAgent = true
            case .userTranscript(let value):
                text = value
                isAgent = false
            case .userInput(let value):
                text = value
                isAgent = false
            }

            return TranscriptMessage(text: text, isAgent: isAgent, timestamp: message.timestamp)
        }
    }

    private func resolveAriaState(session: Session) -> AriaState {
        if session.error != nil || session.agent.error != nil || session.agent.isFinished {
            return .disconnected
        }

        if let agentState = session.agent.agentState {
            switch agentState {
            case .listening:
                return .listening
            case .thinking:
                return .thinking
            case .speaking:
                return .speaking
            case .idle, .initializing:
                return session.isConnected ? .waiting : .connecting
            }
        }

        if session.agent.isPending {
            return session.isConnected ? .waiting : .connecting
        }

        return session.isConnected ? .waiting : .disconnected
    }

    // MARK: Data messages

    private func handleDataMessage(_ data: Data, participant: RemoteParticipant?) {
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let kindRaw = json["type"] as? String,
              let kind = DataMessageKind(rawValue: kindRaw) else { return }

        let payload = json["payload"] as? [String: Any] ?? [:]

        switch kind {
        case .mossContext:
            let query = payload["query"] as? String ?? ""
            let rawResults = payload["results"] as? [[String: Any]] ?? []
            let results = rawResults.compactMap { r -> MossResult? in
                guard let text = r["text"] as? String else { return nil }
                return MossResult(
                    id: r["id"] as? String ?? UUID().uuidString,
                    text: text,
                    score: r["score"] as? Double,
                    metadata: r["metadata"] as? [String: String]
                )
            }
            let event = MossContextEvent(query: query, results: results, timestamp: .now)
            mossEvents.insert(event, at: 0)
            if mossEvents.count > 20 { mossEvents.removeLast() }

        case .captureDocument, .documentFrame:
            let docType = payload["doc_type"] as? String ?? "unknown"
            let fields = payload["fields"] as? [String: String] ?? [:]
            let rawText = payload["raw_text"] as? String
            let event = DocumentParseEvent(docType: docType, fields: fields, rawText: rawText, timestamp: .now)
            documentEvents.insert(event, at: 0)
            if documentEvents.count > 10 { documentEvents.removeLast() }
            // Parsed fields are back — stop the analyzing indicator.
            isAnalyzingDocument = false

        case .caseUpdate:
            break

        case .enableVideo:
            guard localVideoTrack == nil else { break }
            Task { try? await setCamera(enabled: true) }
        }
    }

    // MARK: Transcript helpers
}

// MARK: - RoomDelegate

extension LiveKitManager: RoomDelegate {
    nonisolated func room(_ room: Room, participant: RemoteParticipant, didSubscribeTrack publication: RemoteTrackPublication) {
        Task { @MainActor in
            if let audioTrack = publication.track as? RemoteAudioTrack {
                startAudioLevelPolling(track: audioTrack)
                // The agent's audio track just arrived. WebRTC has reconfigured the
                // audio session by this point — re-lock to speaker so the agent is
                // audible through the built-in speaker, not the earpiece.
                try? AVAudioSession.sharedInstance().overrideOutputAudioPort(.speaker)
            }
        }
    }

    nonisolated func room(
        _ room: Room,
        participant: RemoteParticipant?,
        didReceiveData data: Data,
        forTopic topic: String,
        encryptionType: EncryptionType
    ) {
        Task { @MainActor in
            handleDataMessage(data, participant: participant)
        }
    }

    nonisolated func room(_ room: Room, participant: RemoteParticipant, didUpdateMetadata metadata: String?) {
        guard let raw = metadata,
              let data = raw.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let stateStr = json["agent_state"] as? String else { return }

        Task { @MainActor in
            switch stateStr {
            case "listening":   ariaState = .listening
            case "thinking":    ariaState = .thinking
            case "speaking":    ariaState = .speaking
            default:            break
            }
        }
    }

    nonisolated func room(_ room: Room, participant: RemoteParticipant, didUpdateSpeaking isSpeaking: Bool) {
        Task { @MainActor in
            if isSpeaking { ariaState = .speaking }
            else if ariaState == .speaking { ariaState = .listening }
        }
    }

    nonisolated func room(_ room: Room, didDisconnectWithError error: Error?) {
        Task { @MainActor in
            isConnected = false
            ariaState = .disconnected
            audioLevelTask?.cancel()
            if let error { errorMessage = error.localizedDescription }
        }
    }

    nonisolated func room(_ room: Room, participant remoteParticipant: RemoteParticipant, didJoinWithMetadata metadata: String?) {
        Task { @MainActor in
            // Agent joined the room — we're ready
            if ariaState == .waiting { ariaState = .listening }
        }
    }
}
#endif
