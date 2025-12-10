import SwiftUI
import AVKit
import AVFAudio
import Combine

final class RecordingPlayerViewModel: ObservableObject {
    @Published var player: AVPlayer?

    func configureAudioSession() {
        let session = AVAudioSession.sharedInstance()
        do {
            try session.setCategory(.playback, mode: .moviePlayback, options: [])
            try session.setActive(true)
        } catch {
            print("Audio session setup failed:", error)
        }
    }

    func setURLIfNeeded(_ url: URL) {
        guard player == nil else { return }

        let newPlayer = AVPlayer(url: url)
        newPlayer.isMuted = false
        player = newPlayer
    }

    func playFromStart() {
        guard let player = player else { return }
        player.seek(to: .zero)
        player.play()
    }

    func pause() {
        player?.pause()
    }
}

struct RecordingPlayerView: View {
    let recording: Recording
    @EnvironmentObject var btManager: GlassesBluetoothManager
    @StateObject private var viewModel = RecordingPlayerViewModel()

    var body: some View {
        VStack {
            if let player = viewModel.player {
                VideoPlayer(player: player)
                    .onAppear {
                        viewModel.playFromStart()
                    }
                    .onDisappear {
                        viewModel.pause()
                    }

            } else if let error = btManager.playbackURLError {
                Text(error)
                    .foregroundColor(.red)
                    .multilineTextAlignment(.center)
                    .padding()

            } else {
                ProgressView("Loading video…")
            }
        }
        .navigationTitle("Recording")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            viewModel.configureAudioSession()

            if viewModel.player == nil {
                btManager.requestPlaybackURL(for: recording)
            }
        }
        .onChange(of: btManager.playbackURL) { newURL in
            guard let url = newURL else { return }

            viewModel.setURLIfNeeded(url)
            viewModel.playFromStart()
        }
    }
}

