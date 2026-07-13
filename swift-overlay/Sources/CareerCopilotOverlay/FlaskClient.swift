import Foundation

class FlaskClient {
    let baseURL = "http://127.0.0.1:5000"
    var currentSessionId: String?
    var onAnswerReceived: ((String) -> Void)?
    var pollTimer: Timer?

    func startPolling() {
        pollTimer = Timer.scheduledTimer(
            withTimeInterval: 2.0,
            repeats: true
        ) { [weak self] _ in
            self?.fetchLatestAnswer()
        }
    }

    func fetchLatestAnswer() {
        guard let sessionId = currentSessionId else {
            fetchCurrentSession()
            return
        }

        let url = URL(string: "\(baseURL)/api/session/\(sessionId)")!
        URLSession.shared.dataTask(with: url) { [weak self] data, _, _ in
            guard let data = data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let overlay = json["overlay"] as? [String: Any] else { return }

            let body = overlay["body"] as? String
            let headline = overlay["headline"] as? String
            guard let answer = body ?? headline, !answer.isEmpty else { return }

            DispatchQueue.main.async {
                self?.onAnswerReceived?(answer)
            }
        }.resume()
    }

    func fetchCurrentSession() {
        let url = URL(string: "\(baseURL)/api/sessions/recent?limit=1")!
        URLSession.shared.dataTask(with: url) { [weak self] data, _, _ in
            guard let data = data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let sessions = json["sessions"] as? [[String: Any]],
                  let first = sessions.first,
                  let id = first["session_id"] as? String,
                  !id.isEmpty else { return }
            self?.currentSessionId = id
        }.resume()
    }

    func triggerListen() {
        guard let sessionId = currentSessionId else { return }
        var request = URLRequest(
            url: URL(string: "\(baseURL)/api/session/\(sessionId)/listen")!
        )
        request.httpMethod = "POST"
        request.httpBody = try? JSONSerialization.data(withJSONObject: [String: Any]())
        request.setValue("application/json",
                        forHTTPHeaderField: "Content-Type")
        URLSession.shared.dataTask(with: request).resume()
    }
}
