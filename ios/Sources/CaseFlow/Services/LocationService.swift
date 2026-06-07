#if os(iOS)
import CoreLocation
import Combine

@MainActor
final class LocationService: NSObject, ObservableObject {
    @Published var city: String = ""
    @Published var state: String = ""
    @Published var status: LocationStatus = .idle

    enum LocationStatus {
        case idle, requesting, resolving, resolved, denied, failed(String)
    }

    private let manager = CLLocationManager()
    private let geocoder = CLGeocoder()

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
    }

    func requestLocation() {
        switch manager.authorizationStatus {
        case .notDetermined:
            status = .requesting
            manager.requestWhenInUseAuthorization()
        case .authorizedWhenInUse, .authorizedAlways:
            fetch()
        case .denied, .restricted:
            status = .denied
        @unknown default:
            status = .denied
        }
    }

    private func fetch() {
        status = .resolving
        manager.requestLocation()
    }

    private func reverseGeocode(_ location: CLLocation) {
        geocoder.reverseGeocodeLocation(location) { [weak self] placemarks, error in
            guard let self else { return }
            Task { @MainActor in
                if let placemark = placemarks?.first {
                    self.city = placemark.locality ?? placemark.subAdministrativeArea ?? ""
                    self.state = placemark.administrativeArea ?? ""
                    self.status = .resolved
                } else {
                    self.status = .failed(error?.localizedDescription ?? "Could not determine location")
                }
            }
        }
    }
}

extension LocationService: CLLocationManagerDelegate {
    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        Task { @MainActor in
            switch manager.authorizationStatus {
            case .authorizedWhenInUse, .authorizedAlways:
                self.fetch()
            case .denied, .restricted:
                self.status = .denied
            default:
                break
            }
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let location = locations.last else { return }
        Task { @MainActor in
            self.reverseGeocode(location)
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor in
            self.status = .failed(error.localizedDescription)
        }
    }
}
#endif
