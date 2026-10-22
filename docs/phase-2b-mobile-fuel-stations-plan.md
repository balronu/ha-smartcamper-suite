# Phase 2B – Mobile Fuel Stations: technischer Umsetzungsplan

**Status:** Implementierung auf dem Entwicklungsbranch, Review ausstehend
**Stand:** 22.10.2026  
**Suite-Basis:** \`main\` bei \`652613565e5088dd62bf39ab80be94e5ba1880e5\`  
**Referenz:** Mobile Fuel Stations \`v0.8.4\`, Commit \`13da23a87d10af753d68af51bfee9694446c1036\`

## 1. Ziel und Grenzen

Phase 2B übernimmt die Tankstellenfunktionen in das vorhandene, zentral verwaltete
\`fuel_stations\`-Modul der SmartCamper Suite. Die drei Quellprojekte bleiben
unverändert. Die Übernahme ist eine fachliche Neuimplementierung auf Basis der
verifizierten Stable-Referenz, kein unkontrolliertes Kopieren der alten
Integration.

Nicht enthalten sind produktive Installationen, Datenmigration ohne ausdrückliche
Bestätigung, Live-Provider-Aufrufe, echte Credentials, ein Release oder eine
HACS-Veröffentlichung.

## 2. Verifizierte Ausgangsbasis

Der Stable-Stand \`v0.8.4\` enthält:

- Tankerkönig, Petromap und Nakordoni sowie Auto-/Fallback-Policy.
- Normalisierte Stationen, Kraftstoffauflösung und Fehlerklassen für
  Authentifizierung, Berechtigungen, Credits, Rate-Limits, Netzwerk und
  ungültige Antworten.
- Radius-, Kraftstoff-, Stationsanzahl-, Sortier-, Aktualisierungs-, Bewegungs-
  und adaptive Aktualisierungslogik.
- Persistierten erfolgreichen Suchzustand, Startup-Recovery und secret-freie
  Diagnostik.
- Config-/Options-Flow, Legacy-Entry-Migration, Sensoren sowie Services für
  manuellen Refresh und Fetch-Modus.
- Nakordoni OAuth2-PKCE mit Home-Assistant-OAuth-Helfern; die HA-Session stellt
  Tokenpersistenz und Single-Flight-Refresh über einen Lock bereit.
- Lovelace-Modi **Detailed**, **Compact** und **Individual**, konfigurierbare
  Felder, Dichte, Trennlinien, Sortierung und **Highlights + Liste**.

## 3. Übernahmematrix

| Quelle v0.8.4 | Suite Phase 2B | Entscheidung |
|---|---|---|
| \`api.py\`: Station, Merge, Sortierung | Suite-Domainmodelle und Fuel-Service | Provider-neutral übernehmen |
| \`providers/base.py\`: Query, Capability, Fehler | zentrale Provider Registry/API-Policy | Gemeinsame Suite-Typen; Adapter gekapselt |
| Tankerkönig, Petromap, Nakordoni | Registry-Adapter | Request-/Response-Mapping per Contract-Test |
| \`coordinator.py\`: Polling, Bewegung, Cache, Recovery | \`FuelStationsRuntime\` | Runtime pro Modul, Lifecycle über Suite-Kern |
| Config-/Options-Flow | zentraler Suite-Entry plus Moduloptionen | Zugangsdaten zentral, Präferenzen fahrzeugbezogen |
| \`oauth2.py\` | zentrale Authentifizierungsverwaltung | Kein doppelter Token-Speicher |
| Sensoren und Services | Suite-Entity-/Service-Schicht | Entity-/Service-Kompatibilität bewusst entscheiden |
| Lovelace-Karte | Renderer des \`smartcamper-card\` | Eine gemeinsame Ressource |
| Legacy-Migration | expliziter, isolierter Adapter | Erst Dry-Run/Preview, dann Opt-in |

Nicht übernommen werden alte Domainnamen, doppelte HTTP-Sessions, doppelte
Credential-Speicher und nicht belegte providerbezogene Annahmen.

## 4. Umsetzungsschritte

### 2B-A – Vertrags- und Verhaltensinventar

1. Stable-Referenz in einer Testmatrix erfassen: Provider, Kraftstoffe,
   Länderabdeckung, Radiusgrenzen, Fehler und Fallback-Reihenfolge.
2. Sensor-, Service-, Karten- und Optionsdaten als Kompatibilitätsverträge
   beschreiben.
3. Abweichungen zwischen Suite-Kern und Quelle als ADR festhalten.

### 2B-B – Gemeinsame Daten- und Provider-Schicht

1. \`VehicleProfile.id\` als stabile Identität für jede Suche verwenden.
2. Fahrzeugsunabhängigen \`ProviderAccount\` mit \`credential_id\`, Provider-ID,
   Aktivstatus und Capability-Metadaten einführen.
3. Adapter ausschließlich über die zentrale Registry erzeugen.
4. Query/Result-Typen mit Fahrzeug-ID, Koordinaten, Radius, Kraftstoffliste,
   Limit, Sortierung und Provider-Konto definieren.
5. Alle drei Provider mit synthetischen Transporten gegen diesen Vertrag testen.

### 2B-C – Credentials und OAuth2

1. API-Keys nur zentral speichern; mehrere Fahrzeuge referenzieren dasselbe
   Provider-Konto.
2. Ersetzen, Entfernen, Deaktivieren und fehlende Berechtigungen als atomare,
   secret-freie Statusübergänge testen.
3. Nakordoni OAuth2-PKCE über die exakten Stable-Endpunkte implementieren und testen:
   Ablauf mit Sicherheitsabstand, persistente Wiederherstellung ohne Logging,
   \`asyncio.Lock\`/Single-Flight je Credential, parallele Requests mit genau
   einer Erneuerung, ungültiger Refresh-Token, 401, 403, Rate-Limit und Netzwerk.
4. Die synthetischen PKCE-/Refresh-Verträge sind grün; eine echte Provider-E2E-
   Autorisierung bleibt ohne Credentials bewusst ungetestet und ist keine
   Aussage über eine erfolgreiche Produktionsfreischaltung.

### 2B-D – Fahrzeugbezogene Suche und Runtime

1. Pro Fahrzeug \`gps_tracker_entity\`, \`fuel_types\` und \`radius_km\` speichern;
   globale Defaults sind nur Initialwerte.
2. Zwei Fahrzeuge mit unterschiedlichen Trackern und demselben globalen
   Provider-Konto unabhängig suchbar machen.
3. Trackerwechsel darf weder API-Key-Eingabe noch Credential-Kopie auslösen.
4. Cache-Schlüssel müssen Fahrzeug-ID, Koordinatenkontext, Kraftstoff, Radius
   und Provider berücksichtigen.
5. Deaktivierte Runtime besitzt keine Polling-, Bewegungs- oder Recovery-Aufgabe;
   Fehler werden auf das Tankstellenmodul isoliert.
6. Bewegungs-, manueller und adaptiver Fetch-Modus werden erst nach dem
   fachlichen Suchvertrag angeschlossen.

### 2B-E – Lovelace

1. \`custom:smartcamper-card\` erhält ein Fuel-Stations-Modul ohne zweite
   Static-Path- oder Ressourcenregistrierung.
2. Detailed, Compact, Individual, Header-/Stationsfelder, Dichte, Trennlinien,
   Sortierung, Kraftstoff und Highlights + Liste als Modulkonfiguration abbilden.
3. Editor nutzt stabile Fahrzeug- und Modul-IDs; fehlende/archivierte Fahrzeuge
   und deaktivierte Module werden sauber dargestellt.
4. Reload, wiederholte Initialisierung und HA-Neustart ergeben genau eine
   Ressource, einen Static Path und keine doppelten Listener.
5. Vitest/TypeScript und möglichst ein isolierter Browser-Test prüfen auch
   schmale Breiten, lange Namen und fehlende Daten.

### 2B-F – Sichere spätere Migration

1. Legacy-Entries nur lesend erkennen und eine Import-Vorschau mit Provider,
   Optionen, Trackerbezug und Konflikten erzeugen.
2. Ohne Opt-in nichts verändern; Geheimnisse nie in Logs, Diagnosen oder Tests.
3. Vor dem Schreiben einen HA-Sicherungspunkt bzw. Wiederherstellungspunkt
   verlangen.
4. Import idempotent, mit stabilen Ziel-IDs und getesteter Abbruch-/Rollback-
   Möglichkeit implementieren; altes Entry zunächst nicht löschen.
5. Produktiver Migrationslauf erst nach separater Freigabe.

### 2B-G – Abnahme

Die Implementierung endet erst nach HA-Lifecycle-, Provider-Contract-,
Frontend-/Browser-, Hassfest-, Ruff-, Typ-, Compileall-, JSON-, Secret- und
Diff-Prüfungen. Release, HACS und produktive Installation bleiben außerhalb.

## 5. Teststrategie ohne echte Zugangsdaten

- Fake-HTTP-Transporte für alle Provider; keine Live-URLs oder echten Schlüssel.
- HA-Fixtures für Entry-Erstellung, Setup, Unload, Reload, Neustart, Options-
  änderung und Fehlerisolation.
- Zwei synthetische Fahrzeuge mit Tracker A/B, gleichem Konto, verschiedenen
  Kraftstoffen und Radien.
- Registry-Tests für Registrierung, Änderung, Deaktivierung, Key-Rotation,
  Entfernung und fehlende Berechtigungen.
- OAuth-Tests für Datenmodell, Ablauf, parallelen Refresh und Redaction; die
  noch fehlende produktive Erneuerung bleibt bis zur Implementierung explizit rot.
- Provider-Contract-Tests für Normalisierung, Fallback, keine Ergebnisse,
  ungültige Antworten, 401/403, 429, Credits, Timeout und Netzwerkfehler.
- SQLite-Tests für Schema-Version, Transaktionen, Wiederanlauf, korrupte Daten,
  unterbrochenen Write, Parallelzugriff und sauberes Schließen.
- Karten-/Browser-Tests für Ressourcenduplikate, Reload, Auswahl, fehlende
  Fahrzeuge, deaktivierte Module und alle drei v0.8.4-Darstellungen.

## 6. Risiken und Abhängigkeiten

1. **OAuth2:** Der Quellstand liefert das PKCE-Modell; Token-Lifecycle,
   Persistenz und Single-Flight der Suite müssen separat nachgewiesen werden.
2. **Providerlimits:** Petromap-Credits, Nakordoni-Märkte/Quoten und
   Tankerkönig-Ratenlimits müssen auch bei mehreren Fahrzeugen gelten.
3. **Fallback:** Auth-/Berechtigungsfehler dürfen nicht als „keine Tankstellen“
   erscheinen; nur zulässige Fehler lösen einen nächsten Provider aus.
4. **HA-APIs:** Config-Entry-, OAuth- und Frontend-APIs sind versionsabhängig;
   Zielversion und Hassfest gehören verbindlich ins CI.
5. **Kartenkompatibilität:** Alte YAML-Konfiguration benötigt einen Adapter oder
   eine bewusst versionierte Migrationsentscheidung.
6. **Datenmodell:** Globale Legacy-Optionen lassen sich nicht immer gefahrlos
   mehreren Fahrzeugen zuordnen.
7. **Cache/Rate-Limit:** Fahrzeug-ID und Credential-ID müssen getrennt bleiben,
   damit gemeinsame Zugänge keine falschen Ergebnisse oder Mehrfachrequests
   erzeugen.

## 7. Abnahmekriterien für Phase 2B

1. Quellrepositories unverändert; Implementierung reproduzierbar gegen
   \`v0.8.4\`/\`13da23a\` geprüft.
2. Tankerkönig, Petromap und Nakordoni liefern über die zentrale Registry
   normalisierte Ergebnisse; Capability- und Fallback-Tests sind grün.
3. Ein Provider-Konto wird von mindestens zwei Fahrzeugen gemeinsam genutzt;
   Key-Eingabe, Rotation und Entfernung erfolgen zentral.
4. Zwei Fahrzeuge mit verschiedenen Trackern, Kraftstofflisten und Radien
   liefern getrennte Ergebnisse; Trackerwechsel ändert keine ID/Credentials.
5. Alle relevanten v0.8.4-Kartenmodi und Optionen sind verfügbar; Editor,
   fehlende Fahrzeuge, deaktivierte Module, Reload und Neustart sind getestet.
6. OAuth2-PKCE inklusive Persistenz, Ablauf, parallelem Refresh, Fehlern und
   Secret-Redaction ist implementiert und getestet, bevor OAuth aktiv wird.
7. Deaktivierung, Unload, Reload und Modulfehler erzeugen keine fremde
   Hintergrundaktivität oder Ausfälle anderer Module.
8. SQLite- und Neustarttests weisen Versionierung, Transaktionen, Parallelzugriff,
   korrupte Daten und sauberes Schließen nach; keine Travel-Journal-Datenbank.
9. Legacy-Dry-Run ist vollständig, idempotent, ohne Opt-in nicht mutierend und
   besitzt einen getesteten Abbruch-/Rollback-Pfad.
10. CI ist grün: HA-Tests, Hassfest, Ruff, Typprüfung, Compileall, JSON,
    Frontend/Browser, Security und \`git diff --check\`, ohne echte Credentials.
11. Deutsch-first/Englisch-supplementäre Dokumentation nennt Provider-, OAuth-,
    Migrations- und Kompatibilitätsgrenzen.

## 8. Offene Entscheidungen vor der Implementierungsfreigabe

- Auto-Reihenfolge verbindlich beibehalten oder zentral konfigurierbar?
- Welche Nakordoni-Scopes und Provider-Konten werden freigeschaltet?
- Alte Kartenkonfiguration automatisch adaptieren oder per Import-Assistent?
- Welche Defaults gelten für neue Fahrzeuge bei globalen Legacy-Optionen?
- Sollen alte Sensor-/Service-Entity-IDs zeitweise gespiegelt werden?

**Freigabestatus:** Die Implementierung ist nach ausdrücklicher Freigabe des
Auftraggebers gestartet; Review und Merge stehen noch aus.

## 9. Umsetzungsabweichungen und aktueller Status

Die Implementierung wurde nach der ausdrücklichen Phase-2B-Freigabe begonnen.
Die drei Provider-Adapter, fahrzeugbezogene Fuel-Einstellungen, Runtime,
Sensoren, Credential-Services, Nakordoni-PKCE-Registrierung, transaktionaler
Legacy-Import und die Kartenansicht sind nun als Kandidat implementiert. Die
anderen Module bleiben Platzhalter.

Bewusste Abweichungen vom Plan:

- Die Provider-Transportgrenze ist ein synthetischer, injizierbarer Contract;
  die HA-Runtime bindet ihn an die gemeinsame HA-aiohttp-Session. Es gibt
  keinen separaten Client pro Fahrzeug.
- OAuth nutzt die exakten Stable-Endpunkte und HA-PKCE-/Session-Helfer. Eine
  echte Autorisierung und ein providerseitiger Widerrufsfall bleiben ohne
  Credentials ungetestet; keine Scopes oder Endpunkte wurden erfunden.
- Die Legacy-Migration ist jetzt opt-in ausführbar, transaktional und rollback-
  fähig; sie schreibt weiterhin keine produktiven Config Entries, verändert
  keine Dashboards und löscht kein altes Entry.
- Die Kartenansicht deckt Stationsfelder, Multi-Fuel-Preise, Sortierung,
  Ergebnislimit, Status- und Ladefehler ab. Historische Highlights-, Logo-,
  Diagnose- und Navigationsoptionen der v0.8.4 sind noch kein vollständiger
  Kompatibilitätsnachweis.
