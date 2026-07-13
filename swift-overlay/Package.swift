// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "CareerCopilotOverlay",
    platforms: [.macOS(.v12)],
    targets: [
        .executableTarget(
            name: "CareerCopilotOverlay",
            path: "Sources/CareerCopilotOverlay"
        )
    ]
)
