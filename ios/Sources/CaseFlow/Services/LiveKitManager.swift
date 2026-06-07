#if os(iOS)
import Foundation
import LiveKit
import Combine

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

    let room = Room()
    private let tokenService = TokenService()
    private var audioLevelTask: Task<Void, Never>?

    // MARK: Connect

    func connect(agentMetadata: [String: String] = [:]) async {
        ariaState = .connecting
        errorMessage = nil

        do {
            let details = try await tokenService.fetchConnectionDetails(agentMetadata: agentMetadata)
            let connectOptions = ConnectOptions(autoSubscribe: true)
            let roomOptions = RoomOptions(
                defaultCameraCaptureOptions: CameraCaptureOptions(position: .front),
                defaultAudioCaptureOptions: AudioCaptureOptions()
            )

            room.add(delegate: self)

            try await room.connect(
                url: details.serverUrl,
                token: details.participantToken,
                connectOptions: connectOptions,
                roomOptions: roomOptions
            )

            try await room.localParticipant.setMicrophone(enabled: true)
            isConnected = true
            ariaState = .waiting
        } catch {
            ariaState = .disconnected
            errorMessage = error.localizedDescription
        }
    }

    func disconnect() async {
        audioLevelTask?.cancel()
        audioLevelTask = nil
        await room.disconnect()
        isConnected = false
        ariaState = .disconnected
        audioLevel = 0
    }

    func setCamera(enabled: Bool) async throws {
        try await room.localParticipant.setCamera(enabled: enabled)
    }

    // MARK: Audio level polling

    private func startAudioLevelPolling(track: RemoteAudioTrack) {
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

        case .caseUpdate:
            break

        case .enableVideo:
            Task { try? await setCamera(enabled: true) }
        }
    }

    // MARK: Transcript helpers

    func appendTranscript(text: String, isAgent: Bool) {
        let msg = TranscriptMessage(text: text, isAgent: isAgent, timestamp: .now)
        transcript.append(msg)
        if transcript.count > 100 { transcript.removeFirst() }
    }
}

// MARK: - RoomDelegate

extension LiveKitManager: RoomDelegate {
    nonisolated func room(_ room: Room, participant: RemoteParticipant, didSubscribeTrack publication: RemoteTrackPublication) {
        Task { @MainActor in
            if let audioTrack = publication.track as? RemoteAudioTrack {
                startAudioLevelPolling(track: audioTrack)
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
