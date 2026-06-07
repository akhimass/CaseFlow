import Foundation

// MARK: - Token API

struct ConnectionDetails: Codable {
    let serverUrl: String
    let roomName: String
    let participantName: String
    let participantToken: String
}

// MARK: - LiveKit Data Messages
//
// Every LiveKit data packet from the agent is `{ "type": <string>, "data": <object> }`.
// These are the agent → client message types the Python agent actually publishes
// (see `agent-py/src/agent.py`, `video_capture.py`, `case_broadcast.py`).
// `document_frame` is OUTBOUND only (client → agent) and is therefore not listed here.

enum DataMessageKind: String, Codable {
    case mossContext = "moss_context"
    case documentParse = "document_parse"
    case citedSource = "cited_source"
    case enableVideo = "enable_video"
    case captureDocument = "capture_document"
    case caseflowUpdate = "caseflow_update"
}

struct MossContextEvent: Identifiable {
    let id = UUID()
    let query: String
    let results: [MossResult]
    let timeTakenMs: Double?
    let timestamp: Date

    init(query: String, results: [MossResult], timeTakenMs: Double? = nil, timestamp: Date) {
        self.query = query
        self.results = results
        self.timeTakenMs = timeTakenMs
        self.timestamp = timestamp
    }
}

struct MossResult: Identifiable, Codable {
    let id: String
    let text: String
    let score: Double?
    let metadata: [String: String]?
}

enum DocumentParseStatus: String, Codable {
    case parsing
    case parsed
    case error

    init(raw: String?) {
        switch raw {
        case "parsed": self = .parsed
        case "error": self = .error
        default: self = .parsing
        }
    }
}

struct DocumentParseEvent: Identifiable {
    let id = UUID()
    let docType: String
    let status: DocumentParseStatus
    let fields: [String: String]
    let rawText: String?
    let timestamp: Date
}

/// Latest live case-field update from the agent (`caseflow_update`).
struct CaseUpdate {
    let caseId: String?
    let event: String
    let fields: [String: String]
    let timestamp: Date
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
    let id: String
    let text: String
    let isAgent: Bool
    let timestamp: Date

    init(id: String = UUID().uuidString, text: String, isAgent: Bool, timestamp: Date) {
        self.id = id
        self.text = text
        self.isAgent = isAgent
        self.timestamp = timestamp
    }
}
