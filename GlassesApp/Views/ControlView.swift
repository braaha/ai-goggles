import SwiftUI

struct ControlView: View {
    @EnvironmentObject var btManager: GlassesBluetoothManager

    private let intervalOptions = [1, 5, 15, 30, 60]
    @State private var selectedIntervalMinutes = 15

    
    var body: some View {
        VStack(spacing: 20) {
            Text("Recording Control")
                .font(.largeTitle)
                .bold()

            VStack(spacing: 8) {
                Text("Connection: \(connectionText)")
                    .font(.headline)

                Text("Recording state: \(btManager.recordingState.rawValue)")
                    .font(.subheadline)
                    .foregroundColor(recordingColor)
            }
            .padding(.bottom, 8)

            VStack(alignment: .leading, spacing: 8) {
                Text("Recording Interval")
                    .font(.subheadline)

                Picker("Recording Interval", selection: $selectedIntervalMinutes) {
                    ForEach(intervalOptions, id: \.self) { minutes in
                        Text("\(minutes) minute\(minutes == 1 ? "" : "s")")
                            .tag(minutes)
                    }
                }
                .pickerStyle(.menu)
            }
            .padding(.horizontal)

            Button(action: {
                if btManager.recordingState == .recording {
                    btManager.stopRecording()
                } else {
                    let seconds = selectedIntervalMinutes * 60
                    btManager.startRecording(intervalSeconds: seconds)
                }
            }) {
                Text(btManager.recordingState == .recording ? "Stop Recording" : "Start Recording")
                    .padding()
                    .frame(maxWidth: .infinity)
                    .background(btManager.recordingState == .recording ? Color.red : Color.green)
                    .foregroundColor(.white)
                    .cornerRadius(12)
            }
            .padding(.horizontal)
            .disabled(btManager.connectionState != .connected)

            if let error = btManager.lastError {
                Text("Error: \(error)")
                    .font(.footnote)
                    .foregroundColor(.red)
                    .padding(.top, 8)
            }

            Spacer()
        }
        .padding()
    }

    private var connectionText: String {
        switch btManager.connectionState {
        case .disconnected: return "Disconnected"
        case .scanning:     return "Scanning..."
        case .connecting:   return "Connecting..."
        case .connected:    return "Connected"
        }
    }

    private var recordingColor: Color {
        switch btManager.recordingState {
        case .recording: return .red
        case .idle:      return .green
        case .unknown:   return .gray
        }
    }
}

struct ControlView_Previews: PreviewProvider {
    static var previews: some View {
        ControlView()
            .environmentObject(GlassesBluetoothManager())
    }
}

