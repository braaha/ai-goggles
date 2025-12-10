import SwiftUI
import CoreBluetooth
import Network
import BackgroundTasks
import AVFoundation

@main
struct GlassesAppApp: App {
    
    @StateObject private var btManager = GlassesBluetoothManager()
    
    var body: some Scene {
        WindowGroup {
            MainTabView()
                .environmentObject(btManager)
        }
    }
}
