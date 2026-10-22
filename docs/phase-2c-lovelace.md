# Route Planner in `custom:smartcamper-card`

Die Route-Ansicht verwendet dieselbe Karte wie Mobile Fuel Stations:

```yaml
type: custom:smartcamper-card
module: route_planner
vehicle_id: <stabile-suite-fahrzeug-id>
origin:
  latitude: 50.0
  longitude: 8.0
destination:
  latitude: 51.0
  longitude: 9.0
```

Nach einer expliziten Berechnung zeigt die Karte Geometrie, Entfernung,
Fahrzeit, Provider, Beta-/Restriktionswarnungen und Mautmetadaten. Ein
Zwischenstopp kann in der Karte hinzugefügt oder entfernt werden.

## Export und Navigation

Die drei Buttons erzeugen direkt im Browser valide GPX-1.1-Dateien:

- **GPX-Route** enthält Start, Zwischenstopps und Ziel als `<rte>`.
- **GPX-Track** enthält die Provider-Geometrie als `<trk>`.
- **GPX kombiniert** enthält beide Varianten.

Der Download ist lokal und überträgt keine Credentials. Für Sygic ist der
GPX-Download der dokumentierte Übergabepfad; die Ziel-App kann die Route mit
eigenen Kartendaten neu berechnen.

**Im Navi öffnen** nutzt auf iOS `maps://`, auf Android `geo:` und auf dem
Desktop OpenStreetMap-Directions. Zwischenstopps werden über diese generischen
Links nicht behauptet übertragen; für die vollständige Folge ist GPX zu
verwenden. Fahrzeugmaße und Gewicht müssen in der externen Navigation geprüft
werden.
