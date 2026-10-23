# SmartCamper Suite Branding

## Freigegebene Quelle

Die Quelldatei `docs/assets/smartcamper-suite-logo-set.png` wurde am
2026-10-22 vom Projektinhaber bereitgestellt und für die Repository-, HACS-
und Home-Assistant-Darstellung freigegeben. Sie wird unverändert als
Repository-Banner aufbewahrt. Aus demselben Bild wurden die HA-Varianten
deterministisch zugeschnitten und skaliert; es wurde kein alternatives Logo
festgelegt.

Quelle: `SmartCamper_Suite_Logo-Set.png` (1536×1024, RGBA)

| Datei | Zweck | Größe | SHA-256 |
|---|---|---:|---|
| `custom_components/smartcamper_suite/brand/icon.png` | lokales HA-Icon | 256×256 | `51784023b25cf08e19a49385a11c23783cc06b08ecfe8cac8faa67ae7b8b18be` |
| `custom_components/smartcamper_suite/brand/icon@2x.png` | lokales HA-Icon 2× | 512×512 | `8a8f88a327bae96b269308a23af308ef1579d22debbcf73c7214c7128690d774` |
| `custom_components/smartcamper_suite/brand/logo.png` | lokales HA-Logo | 256×222 | `8626aa8ea71c1ae910caa9bb7450370cc677e3d130838c2e6444ee2653e8def6` |
| `custom_components/smartcamper_suite/brand/logo@2x.png` | lokales HA-Logo 2× | 512×444 | `3d776f273d06f3afe76799176b6256fc5df57f25da300d3768bf36779d2c21a6` |

Die vier Modulbilder unter `docs/assets/module-*.svg` sind einfache,
repository-eigene Vektorillustrationen ohne externe Marken- oder
Screenshot-Abhängigkeit. Sie beschreiben den aktuellen Entwicklungsstand;
nicht implementierte Module werden in der README ausdrücklich als Platzhalter
gekennzeichnet.

## Pfade und Grenzen

Home Assistant 2026.3+ liest lokale Custom-Integration-Brandingdateien aus
`custom_components/smartcamper_suite/brand/`; ein `manifest.json`-Brandingfeld
ist dafür nicht erforderlich. HACS-Metadaten und die öffentliche
`brands.home-assistant.io`-CDN-Anzeige sind davon getrennt. Es wurde kein
offizieller `home-assistant/brands`-PR erstellt und keine CDN-Verfügbarkeit
behauptet.

Die Bildfreigabe des Projektinhabers ist dokumentiert; eine separate
markenrechtliche Prüfung der abgebildeten Wort-/Bildmarken ersetzt sie nicht.

## Prüfstand für Beta 0.3.0-beta.5

- Die GitHub-README verwendet ausschließlich relative, case-sensitive Pfade
  auf `docs/assets/` und `docs/images/`; die referenzierten Dateien werden im
  Repository und im HACS-Archiv geprüft.
- Die vier UI-Screenshots unter `docs/images/` stammen aus dem isolierten
  Chromium-Fixture mit synthetischen Home-Assistant-Daten. Für die zentrale
  Fahrzeugverwaltung existiert noch kein vollständiger HA-UI-Fixture; dafür
  wird kein Bild behauptet.
- Das HACS-Archiv enthält die lokalen `brand/`-Dateien. HACS-Kataloganzeige,
  lokale HA-Brandingauslieferung und die öffentliche
  `brands.home-assistant.io`-CDN sind getrennte Pfade.
- Eine offizielle CDN-Verfügbarkeit oder ein offizieller Brands-Merge wurde
  nicht behauptet. Nach Update ist ein HA-Neustart und ein harter Browser-
  Refresh erforderlich, bevor lokale Brandingdateien bewertet werden können.
