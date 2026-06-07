// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "CaseFlow",
    platforms: [
        .iOS(.v17)
    ],
    products: [
        .library(name: "CaseFlow", targets: ["CaseFlow"]),
    ],
    dependencies: [
        .package(
            url: "https://github.com/livekit/client-sdk-swift",
            from: "2.0.0"
        ),
    ],
    targets: [
        .target(
            name: "CaseFlow",
            dependencies: [
                .product(name: "LiveKit", package: "client-sdk-swift"),
            ],
            path: "Sources/CaseFlow"
        ),
    ]
)

