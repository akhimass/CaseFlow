#if os(iOS)
import Foundation
import CoreImage
import CoreVideo
import UIKit
import LiveKit

/// Attaches to a `LocalVideoTrack` as a `VideoRenderer` and keeps the most recent
/// camera frame so we can grab a still JPEG on demand. This is the iOS equivalent of
/// the web's `canvas.toDataURL('image/jpeg', 0.92)` document-capture path.
///
/// Frames arrive on a background WebRTC thread (`render(frame:)` is `nonisolated`), so
/// the latest pixel buffer is guarded by a lock and the class is `@unchecked Sendable`.
final class CameraFrameCapturer: NSObject, VideoRenderer, @unchecked Sendable {
    private let lock = NSLock()
    private var latestPixelBuffer: CVPixelBuffer?
    private var latestRotation: VideoRotation = ._0
    private let ciContext = CIContext(options: [.useSoftwareRenderer: false])

    // MARK: VideoRenderer (AdaptiveStream hints — not used for capture)

    nonisolated var isAdaptiveStreamEnabled: Bool { false }
    nonisolated var adaptiveStreamSize: CGSize { .zero }

    nonisolated func render(frame: VideoFrame) {
        guard let pixelBuffer = frame.toCVPixelBuffer() else { return }
        lock.lock()
        latestPixelBuffer = pixelBuffer
        latestRotation = frame.rotation
        lock.unlock()
    }

    var hasFrame: Bool {
        lock.lock(); defer { lock.unlock() }
        return latestPixelBuffer != nil
    }

    func reset() {
        lock.lock()
        latestPixelBuffer = nil
        lock.unlock()
    }

    /// Returns the latest frame as a `data:image/jpeg;base64,...` URL string, matching
    /// the shape the web produces, or `nil` if no frame is available yet.
    func latestJPEGDataURL(compressionQuality: CGFloat = 0.92) -> String? {
        lock.lock()
        let pixelBuffer = latestPixelBuffer
        let rotation = latestRotation
        lock.unlock()

        guard let pixelBuffer else { return nil }

        let baseImage = CIImage(cvPixelBuffer: pixelBuffer)
        let orientedImage = baseImage.oriented(Self.orientation(for: rotation))

        guard let cgImage = ciContext.createCGImage(orientedImage, from: orientedImage.extent) else {
            return nil
        }
        let uiImage = UIImage(cgImage: cgImage)
        guard let jpegData = uiImage.jpegData(compressionQuality: compressionQuality) else {
            return nil
        }
        return "data:image/jpeg;base64," + jpegData.base64EncodedString()
    }

    private static func orientation(for rotation: VideoRotation) -> CGImagePropertyOrientation {
        switch rotation {
        case ._0:   return .up
        case ._90:  return .right
        case ._180: return .down
        case ._270: return .left
        }
    }
}
#endif
