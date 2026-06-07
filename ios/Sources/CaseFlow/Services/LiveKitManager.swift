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
    @Published var citedSources: [String] = []
    @Published var latestCaseUpdate: CaseUpdate?
    @Published var cameraEnabled = false
    @Published var capturingDocument = false
    @Published var isMicMuted = false
    @Published var isConnected = false
    @Published var errorMessage: String?

    private let fallbackRoom = Room()
    private let tokenService = TokenService()
    private var session: Session?
    private var sessionObservation: AnyCancellable?
    private let frameCapturer = CameraFrameCapturer()
    private var audioLevelTask: Task<Void, Never>?
    private var capturerAttached = false

    /// Ordered transcription state keyed by LiveKit segment id so partial segments
    /// update in place (matches the web transcript merge behavior).
    private var transcriptOrder: [String] = []
    private var transcriptById: [String: TranscriptMessage] = [:]

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

        try session.setCategory(.playAndRecord, mode: .voiceChat, options: [.defaultToSpeaker, .allowBluetooth])
        try session.setActive(true)
    }

    func disconnect() async {
        audioLevelTask?.cancel()
        audioLevelTask = nil
        sessionObservation?.cancel()
        sessionObservation = nil

        capturerAttached = false
        frameCapturer.reset()

        let activeSession = session
        session = nil

        await activeSession?.end()
        isConnected = false
        cameraEnabled = false
        ariaState = .disconnected
        audioLevel = 0
        transcript = []
        mossEvents = []
        documentEvents = []
    }

    func setCamera(enabled: Bool) async throws {
        try await room.localParticipant.setCamera(enabled: enabled)
        cameraEnabled = enabled
        if enabled {
            attachCapturerIfNeeded()
        } else {
            capturerAttached = false
            frameCapturer.reset()
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

    // MARK: Camera frame capture (Unsiloed trigger)

    private func attachCapturerIfNeeded() {
        guard !capturerAttached else { return }
        guard let track = room.localParticipant.localVideoTracks.first?.track as? LocalVideoTrack else {
            return
        }
        track.add(videoRenderer: frameCapturer)
        capturerAttached = true
    }

    /// Mirrors the web `ensureCameraEnabled`: turn the camera on if needed and give the
    /// track ~1.2s to start publishing frames before capture.
    private func ensureCameraEnabled() async {
        if cameraEnabled, capturerAttached, frameCapturer.hasFrame {
            return
        }
        if !cameraEnabled {
            try? await setCamera(enabled: true)
            try? await Task.sleep(nanoseconds: 1_200_000_000)
        }
        attachCapturerIfNeeded()
    }

    private func handleCaptureDocument(caseId: String?, docType: String, turn: Int?) async {
        guard !docType.isEmpty else { return }
        capturingDocument = true
        defer { capturingDocument = false }

        await ensureCameraEnabled()

        // Poll briefly for a decoded frame to arrive on the renderer thread.
        var dataURL: String?
        for _ in 0..<20 {
            attachCapturerIfNeeded()
            if let url = frameCapturer.latestJPEGDataURL() {
                dataURL = url
                break
            }
            try? await Task.sleep(nanoseconds: 100_000_000)
        }

        guard let imageBase64 = dataURL else {
            errorMessage = "Could not capture a camera frame for \(docType)."
            return
        }

        await publishDocumentFrame(
            caseId: caseId,
            docType: docType,
            turn: turn,
            imageBase64: imageBase64
        )
    }

    private func publishDocumentFrame(
        caseId: String?,
        docType: String,
        turn: Int?,
        imageBase64: String
    ) async {
        var data: [String: Any] = [
            "doc_type": docType,
            "image_base64": imageBase64,
        ]
        if let caseId { data["case_id"] = caseId }
        if let turn { data["turn"] = turn }

        let message: [String: Any] = ["type": "document_frame", "data": data]
        guard let payload = try? JSONSerialization.data(withJSONObject: message) else { return }
        do {
            try await room.localParticipant.publish(
                data: payload,
                options: DataPublishOptions(reliable: true)
            )
        } catch {
            errorMessage = "Failed to send document frame: \(error.localizedDescription)"
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

    private func startAudioLevelPolling() {
        audioLevelTask?.cancel()
        audioLevelTask = Task { [weak self] in
            while !Task.isCancelled {
                await MainActor.run {
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

    private func handleDataMessage(_ packet: Data) {
        guard let json = try? JSONSerialization.jsonObject(with: packet) as? [String: Any],
              let kindRaw = json["type"] as? String else { return }

        // The envelope key is `data` (NOT `payload`).
        let body = json["data"] as? [String: Any] ?? [:]

        guard let kind = DataMessageKind(rawValue: kindRaw) else { return }

        switch kind {
        case .mossContext:
            handleMossContext(body)
        case .documentParse:
            handleDocumentParse(body)
        case .citedSource:
            handleCitedSource(body)
        case .enableVideo:
            Task { try? await setCamera(enabled: true) }
        case .captureDocument:
            let caseId = body["case_id"] as? String
            let docType = body["doc_type"] as? String ?? ""
            let turn = (body["turn"] as? NSNumber)?.intValue
            Task { await handleCaptureDocument(caseId: caseId, docType: docType, turn: turn) }
        case .caseflowUpdate:
            handleCaseflowUpdate(body)
        }
    }

    // MARK: Transcript helpers

    private func handleMossContext(_ data: [String: Any]) {
        let query = data["query"] as? String ?? ""
        let rawMatches = data["matches"] as? [[String: Any]] ?? []
        let results = rawMatches.compactMap { match -> MossResult? in
            guard let text = match["text"] as? String, !text.isEmpty else { return nil }
            return MossResult(
                id: match["id"] as? String ?? UUID().uuidString,
                text: text,
                score: (match["score"] as? NSNumber)?.doubleValue,
                metadata: Self.coerceMetadata(match["metadata"])
            )
        }
        guard !query.isEmpty || !results.isEmpty else { return }
        let timeTaken = (data["time_taken_ms"] as? NSNumber)?.doubleValue
        let event = MossContextEvent(
            query: query,
            results: results,
            timeTakenMs: timeTaken,
            timestamp: Self.date(from: data["timestamp"])
        )
        mossEvents.insert(event, at: 0)
        if mossEvents.count > 20 { mossEvents.removeLast() }
    }

    private func handleDocumentParse(_ data: [String: Any]) {
        guard let docType = data["doc_type"] as? String, !docType.isEmpty else { return }
        let status = DocumentParseStatus(raw: data["status"] as? String)
        let fields = Self.coerceMetadata(data["fields"]) ?? [:]
        let event = DocumentParseEvent(
            docType: docType,
            status: status,
            fields: fields,
            rawText: data["raw_text"] as? String,
            timestamp: Self.date(from: data["timestamp"])
        )
        // Dedupe by docType (parsing → parsed replaces in place), newest first.
        documentEvents.removeAll { $0.docType == docType }
        documentEvents.insert(event, at: 0)
        if documentEvents.count > 6 { documentEvents.removeLast() }
    }

    private func handleCitedSource(_ data: [String: Any]) {
        guard let citationId = data["citation_id"] as? String, !citationId.isEmpty else { return }
        citedSources.removeAll { $0 == citationId }
        citedSources.insert(citationId, at: 0)
        if citedSources.count > 16 { citedSources.removeLast() }
    }

    private func handleCaseflowUpdate(_ data: [String: Any]) {
        let event = data["event"] as? String ?? "update"
        let fields = Self.coerceMetadata(data["payload"]) ?? [:]
        latestCaseUpdate = CaseUpdate(
            caseId: data["case_id"] as? String,
            event: event,
            fields: fields,
            timestamp: Self.date(from: data["timestamp"])
        )
    }

    // MARK: Transcription

    fileprivate func ingest(segments: [TranscriptionSegment], isAgent: Bool) {
        for segment in segments {
            let text = segment.text.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !text.isEmpty else { continue }
            if transcriptById[segment.id] == nil {
                transcriptOrder.append(segment.id)
            }
            transcriptById[segment.id] = TranscriptMessage(
                id: segment.id,
                text: text,
                isAgent: isAgent,
                timestamp: segment.firstReceivedTime
            )
        }
        rebuildTranscript()
    }

    private func rebuildTranscript() {
        if transcriptOrder.count > 200 {
            let overflow = transcriptOrder.count - 200
            let dropped = transcriptOrder.prefix(overflow)
            dropped.forEach { transcriptById.removeValue(forKey: $0) }
            transcriptOrder.removeFirst(overflow)
        }
        transcript = transcriptOrder.compactMap { transcriptById[$0] }
    }

    // MARK: Agent state

    fileprivate func applyAgentState(_ participant: Participant) {
        guard participant.isAgent else { return }
        switch participant.agentState {
        case .listening:
            ariaState = .listening
        case .thinking:
            ariaState = .thinking
        case .speaking:
            ariaState = .speaking
        case .idle:
            if ariaState == .waiting || ariaState == .connecting { ariaState = .listening }
        case .initializing:
            if !ariaState.isActive { ariaState = .waiting }
        }
    }

    // MARK: Helpers

    /// Tolerant decoding: the agent's metadata/fields values are not always strings,
    /// so coerce any JSON scalar to its string representation.
    private static func coerceMetadata(_ value: Any?) -> [String: String]? {
        guard let dict = value as? [String: Any] else { return nil }
        var result: [String: String] = [:]
        for (key, raw) in dict {
            switch raw {
            case let string as String:
                result[key] = string
            case let number as NSNumber:
                result[key] = number.stringValue
            case is NSNull:
                continue
            default:
                result[key] = String(describing: raw)
            }
        }
        return result.isEmpty ? nil : result
    }

    private static func date(from value: Any?) -> Date {
        if let seconds = (value as? NSNumber)?.doubleValue {
            return Date(timeIntervalSince1970: seconds)
        }
        return .now
    }
}

// MARK: - RoomDelegate

extension LiveKitManager: RoomDelegate {
    nonisolated func room(_ room: Room, participant: RemoteParticipant, didSubscribeTrack publication: RemoteTrackPublication) {
        Task { @MainActor in
            if publication.track is RemoteAudioTrack {
                startAudioLevelPolling()
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
            handleDataMessage(data)
        }
    }

    nonisolated func room(
        _ room: Room,
        participant: Participant,
        trackPublication: TrackPublication,
        didReceiveTranscriptionSegments segments: [TranscriptionSegment]
    ) {
        let isAgent = participant.isAgent
        Task { @MainActor in
            ingest(segments: segments, isAgent: isAgent)
        }
    }

    nonisolated func room(_ room: Room, participant: Participant, didUpdateAttributes attributes: [String: String]) {
        Task { @MainActor in
            applyAgentState(participant)
        }
    }

    nonisolated func room(_ room: Room, participantDidConnect participant: RemoteParticipant) {
        Task { @MainActor in
            if participant.isAgent {
                applyAgentState(participant)
                if ariaState == .waiting { ariaState = .listening }
            }
        }
    }

    nonisolated func room(_ room: Room, didUpdateSpeakingParticipants participants: [Participant]) {
        let agentSpeaking = participants.contains { $0.isAgent }
        Task { @MainActor in
            // Supplemental signal to agent-state attributes: keep Aria's speaking
            // indicator responsive even if an attribute update is delayed.
            if agentSpeaking {
                if ariaState.isActive { ariaState = .speaking }
            } else if ariaState == .speaking {
                ariaState = .listening
            }
        }
    }

    nonisolated func room(_ room: Room, didDisconnectWithError error: LiveKitError?) {
        Task { @MainActor in
            isConnected = false
            cameraEnabled = false
            ariaState = .disconnected
            audioLevelTask?.cancel()
            if let error { errorMessage = error.localizedDescription }
        }
    }
}
#endif
