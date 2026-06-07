import SwiftUI

struct TranscriptView: View {
    let messages: [TranscriptMessage]

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 10) {
                    ForEach(messages) { msg in
                        MessageBubble(message: msg)
                            .id(msg.id)
                    }
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
            }
            .onChange(of: messages.count) { _, _ in
                if let last = messages.last {
                    withAnimation(.easeOut(duration: 0.3)) {
                        proxy.scrollTo(last.id, anchor: .bottom)
                    }
                }
            }
        }
    }
}

private struct MessageBubble: View {
    let message: TranscriptMessage

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            if message.isAgent {
                Circle()
                    .fill(Color.white)
                    .frame(width: 24, height: 24)
                    .overlay(
                        Text("A")
                            .font(.system(size: 11, weight: .bold))
                            .foregroundStyle(.black)
                    )
            }

            VStack(alignment: message.isAgent ? .leading : .trailing, spacing: 3) {
                Text(message.text)
                    .font(.cfBody)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(
                        RoundedRectangle(cornerRadius: 16)
                            .fill(message.isAgent
                                  ? Color.white.opacity(0.10)
                                  : Color.white.opacity(0.18))
                    )

                Text(message.timestamp.formatted(.dateTime.hour().minute()))
                    .font(.cfCaption)
                    .foregroundStyle(.white.opacity(0.4))
            }
            .frame(maxWidth: .infinity, alignment: message.isAgent ? .leading : .trailing)

            if !message.isAgent {
                Circle()
                    .fill(Color.white.opacity(0.15))
                    .frame(width: 24, height: 24)
                    .overlay(
                        Image(systemName: "person.fill")
                            .font(.system(size: 12))
                            .foregroundStyle(.white.opacity(0.7))
                    )
            }
        }
    }
}
