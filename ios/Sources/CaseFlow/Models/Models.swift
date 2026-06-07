import Foundation

// MARK: - Token API

struct ConnectionDetails: Codable {
    let serverUrl: String
    let roomName: String
    let participantName: String
    let participantToken: String
}

// MARK: - LiveKit Data Messages

enum DataMessageKind: String, Codable {
    case mossContext = "moss_context"
    case captureDocument = "capture_document"
    case enableVideo = "enable_video"
    case documentFrame = "document_frame"
    case caseUpdate = "case_update"
}

struct MossContextEvent: Identifiable {
    let id = UUID()
    let query: String
    let results: [MossResult]
    let timestamp: Date
}

struct MossResult: Identifiable, Codable {
    let id: String
    let text: String
    let score: Double?
    let metadata: [String: String]?
}

struct DocumentParseEvent: Identifiable {
    let id = UUID()
    let docType: String
    let fields: [String: String]
    let rawText: String?
    let timestamp: Date
}

struct CaseUpdatePayload: Codable {
    let caseId: String?
    let status: String?
    let fields: [String: String]?
}

// MARK: - Agent state

enum AriaState: String {
    case connecting
    case waiting       // connected, agent not yet in room
    case listening
    case thinking
    case speaking
    case disconnected

    var label: String {
        switch self {
        case .connecting:   return "Connecting…"
        case .waiting:      return "Waiting for Aria…"
        case .listening:    return "Aria is listening"
        case .thinking:     return "Aria is thinking"
        case .speaking:     return "Aria is speaking"
        case .disconnected: return "Disconnected"
        }
    }

    var isActive: Bool {
        [.listening, .thinking, .speaking].contains(self)
    }
}

// MARK: - Transcript

struct TranscriptMessage: Identifiable {
    let id = UUID()
    let text: String
    let isAgent: Bool
    let timestamp: Date
}
