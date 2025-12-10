import SwiftUI
import AVKit

struct RecordingsView: View {
    @EnvironmentObject var btManager: GlassesBluetoothManager

    var body: some View {
        NavigationView {
            Group {
                if btManager.connectionState != .connected {
                    Text("Connect to your glasses to view recordings.")
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                        .padding()

                } else if btManager.isLoadingRecordings && btManager.recordings.isEmpty {
                    ProgressView("Loading recordings…")

                } else if let error = btManager.recordingsError,
                          btManager.recordings.isEmpty {
                    VStack(spacing: 8) {
                        Text("Error")
                            .font(.headline)
                        Text(error)
                            .multilineTextAlignment(.center)
                        Button("Retry") {
                            btManager.requestRecordings(reset: true)
                        }
                        .padding(.top, 8)
                    }
                    .padding()

                } else if btManager.recordings.isEmpty {
                    VStack(spacing: 8) {
                        Text("No recordings found.")
                            .foregroundColor(.secondary)
                        Button("Refresh") {
                            btManager.requestRecordings(reset: true)
                        }
                    }

                } else {
                    List {
                        ForEach(btManager.recordings) { rec in
                            NavigationLink(destination: RecordingPlayerView(recording: rec)) {
                                RecordingRowView(recording: rec)
                            }
                        }

                        if btManager.hasMoreRecordings {
                            HStack {
                                Spacer()
                                if btManager.isLoadingRecordings {
                                    ProgressView()
                                        .padding()
                                } else {
                                    Button("Load more") {
                                        btManager.requestRecordings(reset: false)
                                    }
                                    .padding()
                                }
                                Spacer()
                            }
                        }
                    }
                    .refreshable {
                        btManager.requestRecordings(reset: true)
                    }
                }
            }
            .navigationTitle("Recordings")
        }
        .onAppear {
            if btManager.connectionState == .connected,
               btManager.recordings.isEmpty {
                btManager.requestRecordings(reset: true)
            }
        }
    }
}

