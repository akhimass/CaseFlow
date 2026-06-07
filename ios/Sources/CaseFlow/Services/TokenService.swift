import Foundation
import LiveKit

actor TokenService {
    // Point this at your local dev server or Vercel deployment.
    // Override via Info.plist key "CASEFLOW_API_URL" or set directly here.
    static var baseURL: URL = {
        if let raw = Bundle.main.object(forInfoDictionaryKey: "CASEFLOW_API_URL") as? String,
           let url = URL(string: raw) {
            return url
        }
        return URL(string: "https://caseflowy.com")!
    }()

    func fetchConnectionDetails(agentMetadata: [String: String] = [:]) async throws -> ConnectionDetails {
        let url = Self.baseURL.appendingPathComponent("api/token")

#if !targetEnvironment(simulator)
        if let host = url.host, host == "localhost" || host == "127.0.0.1" {
            throw TokenError.httpError(
                "CASEFLOW_API_URL points to \(url.absoluteString). On a physical iPhone, point it at your Mac's LAN address or a deployed frontend so the app can fetch LiveKit tokens."
            )
        }
#endif

        var request = URLRequest(url: url, timeoutInterval: 30)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = [:]
        if !agentMetadata.isEmpty {
            body["agent_metadata"] = agentMetadata
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            let msg = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw TokenError.httpError(msg)
        }

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(ConnectionDetails.self, from: data)
    }
}

extension TokenService: TokenSourceFixed {
    func fetch() async throws -> TokenSourceResponse {
        let details = try await fetchConnectionDetails()
        return TokenSourceResponse(
            serverURL: URL(string: details.serverUrl)!,
            participantToken: details.participantToken,
            participantName: details.participantName,
            roomName: details.roomName
        )
    }
}

enum TokenError: LocalizedError {
    case httpError(String)
    var errorDescription: String? {
        switch self {
        case .httpError(let msg): return "Token request failed: \(msg)"
        }
    }
}
