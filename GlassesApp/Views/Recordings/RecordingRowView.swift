import SwiftUI

struct RecordingRowView: View {
    let recording: Recording

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(recording.fileName)
                .font(.headline)
        }
        .padding(.vertical, 4)
    }
}
