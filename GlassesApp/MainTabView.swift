import SwiftUI

struct MainTabView: View {
    var body: some View {
        TabView {
            PairingView()
                .tabItem {
                    Label("Pair", systemImage: "dot.radiowaves.left.and.right")
                }

            ControlView()
                .tabItem {
                    Label("Control", systemImage: "record.circle")
                }

            RecordingsView()
                .tabItem {
                    Label("Library", systemImage: "folder")
                }
        }
    }
}
