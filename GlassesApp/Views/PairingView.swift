import SwiftUI

struct PairingView: View {
    @EnvironmentObject var btManager: GlassesBluetoothManager

    @State private var wifiSSIDInput: String = ""
    @State private var wifiPasswordInput: String = ""

    // Which Wi-Fi text field is currently focused (for keyboard control)
    @FocusState private var focusedWifiField: WifiField?

    private enum WifiField {
        case ssid
        case password
    }

    var body: some View {
        NavigationView {
            VStack(spacing: 16) {
                // Connection status
                VStack(spacing: 4) {
                    Text("Pairing")
                        .font(.largeTitle)
                        .bold()

                    Text(statusText)
                        .font(.subheadline)
                        .foregroundColor(.secondary)

                    if let name = btManager.connectedDeviceName,
                       btManager.connectionState == .connected {
                        Text("Connected to: \(name)")
                            .font(.footnote)
                            .foregroundColor(.green)
                    }
                }

                // Wi-Fi status / configuration (only when a device is connected)
                if btManager.connectionState == .connected {
                    wifiSection
                }

                // Scan / connect / disconnect button
                Button(action: {
                    // Dismiss keyboard when tapping the main button
                    focusedWifiField = nil

                    switch btManager.connectionState {
                    case .connected:
                        // If connected, tapping button disconnects
                        btManager.disconnect()

                    case .scanning:
                        // If scanning, tapping button stops scan
                        btManager.stopScan()

                    case .disconnected, .connecting:
                        // If disconnected or connecting, start a fresh scan
                        btManager.startScan()
                    }
                }) {
                    Text(scanButtonTitle)
                        .padding()
                        .frame(maxWidth: .infinity)
                        .background(scanButtonColor)
                        .foregroundColor(.white)
                        .cornerRadius(12)
                }
                .padding(.horizontal)

                // List of discovered devices
                List {
                    if btManager.discoveredDevices.isEmpty {
                        Text("No devices found yet. Tap '\(scanButtonTitle)' to scan.")
                            .foregroundColor(.secondary)
                    } else {
                        Section(header: Text("Discovered Devices")) {
                            ForEach(btManager.discoveredDevices) { device in
                                Button(action: {
                                    // Dismiss keyboard when picking a device
                                    focusedWifiField = nil
                                    btManager.connect(to: device)
                                }) {
                                    HStack {
                                        VStack(alignment: .leading) {
                                            Text(device.name)
                                                .font(.headline)
                                            Text(device.id.uuidString)
                                                .font(.caption2)
                                                .foregroundColor(.secondary)
                                        }
                                        Spacer()
                                        Text("RSSI \(device.rssi)")
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                    }
                                }
                            }
                        }
                    }
                }

                if let error = btManager.lastError {
                    Text("Error: \(error)")
                        .font(.footnote)
                        .foregroundColor(.red)
                        .padding(.top, 4)
                }

                Spacer(minLength: 0)
            }
            .padding(.top)
            .onChange(of: btManager.connectionState) { newValue in
                print("[UI] PairingView connectionState changed to: \(newValue)")
            }
            .navigationBarHidden(true)
            // Tap anywhere in the background (not on controls) to dismiss keyboard
            .background(
                Color.clear
                    .contentShape(Rectangle())
                    .onTapGesture {
                        focusedWifiField = nil
                    }
            )
            // Add a Done button above the keyboard
            .toolbar {
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button("Done") {
                        focusedWifiField = nil
                    }
                }
            }
        }
    }

    // MARK: - UI helpers

    private var statusText: String {
        switch btManager.connectionState {
        case .disconnected:
            return "Not connected"
        case .scanning:
            return "Scanning for devices..."
        case .connecting:
            return "Connecting..."
        case .connected:
            return "Connected"
        }
    }

    private var scanButtonTitle: String {
        switch btManager.connectionState {
        case .connected:
            return "Disconnect"
        case .scanning:
            return "Stop Scan"
        default:
            return "Scan for Devices"
        }
    }

    private var scanButtonColor: Color {
        switch btManager.connectionState {
        case .connected:
            return .red
        case .scanning:
            return .orange
        default:
            return .blue
        }
    }

    private var wifiStateText: String {
        switch btManager.wifiState {
        case .unknown:
            return "Wi-Fi status unknown"
        case .notConfigured:
            return "Wi-Fi not configured"
        case .disconnected:
            return "Wi-Fi not connected"
        case .connecting:
            return "Connecting to Wi-Fi..."
        case .connected:
            if let ssid = btManager.wifiSSID {
                return "Connected to Wi-Fi: \(ssid)"
            } else {
                return "Connected to Wi-Fi"
            }
        }
    }

    private var wifiStateColor: Color {
        switch btManager.wifiState {
        case .connected:
            return .green
        case .connecting:
            return .orange
        case .notConfigured, .disconnected:
            return .red
        case .unknown:
            return .secondary
        }
    }

    // MARK: - Wi-Fi section

    @ViewBuilder
    private var wifiSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header + status
            HStack {
                Image(systemName: "wifi")
                Text("Glasses Wi-Fi")
                    .font(.headline)
                Spacer()
                Text(wifiStateText)
                    .font(.subheadline)
                    .foregroundColor(wifiStateColor)
                    .multilineTextAlignment(.trailing)
            }

            // --- When Wi-Fi is connected: show info + disconnect + then the form ---
            if btManager.wifiState == .connected {
                if let ssid = btManager.wifiSSID {
                    Text("Currently connected to: \(ssid)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                if let ip = btManager.wifiIPAddress {
                    Text("IP address: \(ip)")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }

                HStack {
                    Button(action: {
                        focusedWifiField = nil
                        btManager.requestWifiStatus()
                    }) {
                        Label("Refresh", systemImage: "arrow.clockwise")
                    }

                    Spacer()

                    Button(action: {
                        focusedWifiField = nil
                        btManager.disconnectWifi()
                    }) {
                        if btManager.isWifiBusy {
                            ProgressView()
                        } else {
                            Label("Disconnect", systemImage: "wifi.slash")
                        }
                    }
                    .disabled(btManager.isWifiBusy)
                    .tint(.red)
                }

                Divider()
            } else {
                // Helper text only when not currently connected
                Text("Connect your glasses to the same Wi-Fi network as this iPhone.")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            // --- Original "connect" form (always visible) ---

            Text(btManager.wifiState == .connected ? "Change Wi-Fi network" : "Connect to Wi-Fi")
                .font(.subheadline)
                .bold()

            TextField("Network name (SSID)", text: $wifiSSIDInput)
                .textInputAutocapitalization(.never)
                .disableAutocorrection(true)
                .textFieldStyle(.roundedBorder)
                .focused($focusedWifiField, equals: .ssid)

            SecureField("Password", text: $wifiPasswordInput)
                .textInputAutocapitalization(.never)
                .disableAutocorrection(true)
                .textFieldStyle(.roundedBorder)
                .focused($focusedWifiField, equals: .password)

            HStack {
                Button(action: {
                    focusedWifiField = nil
                    btManager.requestWifiStatus()
                }) {
                    Label("Refresh", systemImage: "arrow.clockwise")
                }

                Spacer()

                Button(action: {
                    focusedWifiField = nil
                    btManager.configureWifi(ssid: wifiSSIDInput,
                                            password: wifiPasswordInput)
                }) {
                    if btManager.isWifiBusy {
                        ProgressView()
                    } else {
                        Label(btManager.wifiState == .connected ? "Switch Network" : "Connect",
                              systemImage: "wifi")
                    }
                }
                .disabled(btManager.isWifiBusy ||
                          wifiSSIDInput.isEmpty ||
                          wifiPasswordInput.isEmpty)
            }

            if let wifiError = btManager.wifiError {
                Text(wifiError)
                    .font(.footnote)
                    .foregroundColor(.red)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
        .padding(.horizontal)
    }
}


