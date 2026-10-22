# Phase 2G – Provider- und OAuth-Integrationstests

## Scope und Ausgangspunkt

Die Prüfung wurde lokal auf `origin/main` nach Phase-2F-Merge-Commit
`c4b8392010ffa68630f606c33da6d9b250174cef` durchgeführt. Arbeitszweig:
`phase-2g-provider-tests`. Es wurden keine produktiven Home-Assistant-Systeme,
VM 104, Stable-Integrationen, Datenbanken, echten Zugangsdaten oder Live-APIs
verwendet. Es wurde kein Push, PR, Tag oder Release erstellt.

## Tatsächlich implementierte Providerpfade

| Provider | Adapter/Endpunkt im Code | Authentisierung | Unterstützte Kraftstoffe |
|---|---|---|---|
| Tankerkönig | `https://creativecommons.tankerkoenig.de/json/list.php` | `apikey`-Parameter und Bearer-Header | `diesel`, `e5`, `e10` |
| Petromap | `https://api.petromap.eu/v2/places` | `x-api-key`-Header | `diesel`, `e5`, `lpg` |
| Nakordoni | `https://nakordoni.eu/api/v2/data/fuel-stations` | Bearer-Header, optional HA-OAuth-Session | `diesel`, `e5`, `e10`, `lpg` |
| Nakordoni-Kontingent | `https://nakordoni.eu/api/v2/account/usage` | Bearer-Header | Quota-/Marktstatus |

Nakordoni-OAuth verwendet HA-PKCE mit den konfigurierten Authorize-/Token-
Endpunkten unter `https://api.nakordoni.dev/oauth/`. Die Tokenverwaltung und
Refresh-Single-Flight-Logik liegt an der HA-/CredentialStore-Grenze.

## Lokale Änderungen

- Transport-Timeouts werden als `FuelUnavailableError` klassifiziert und lösen
  den konfigurierten Provider-Fallback aus.
- Authentisierungs- und Berechtigungsfehler werden beim Suchlauf ebenfalls
  isoliert behandelt, sodass ein nachfolgender aktivierter Provider versucht
  werden kann.
- Neue synthetische Tests decken alle drei Adapter, leere Ergebnisse,
  provider-spezifische Header, HTTP-401, Timeout, Fallback, zwei Fahrzeuge,
  gemeinsame Zugangsdaten und Request-Deduplizierung ab.

## Testergebnisse

- Python-Regression: **59 bestanden, 1 übersprungen**
- Provider-/OAuth-Fokussuite: **13 bestanden**
- Frontend/Vitest: **6 bestanden**
- Frontend-TypeScript-/Bundle-Build: **bestanden**
- Chromium-Kartenprüfung: **bestanden**
- Ruff: **bestanden**
- Compileall, JSON-Validierung, `git diff --check`: **bestanden**
- Hassfest lokal: **NICHT AUSGEFÜHRT**, kein lokales Hassfest/Docker verfügbar
- Gitleaks lokal: **NICHT AUSGEFÜHRT**, kein lokales Gitleaks verfügbar

Die bestehenden Phase-2E-Tests bleiben Teil der Regression und weisen weiterhin
Config-/Options-Flow-Persistenz, Fahrzeugbearbeitung/-löschung, OAuth-
Rekonfiguration, Reload-/Unload- und Modulkoexistenz nach.

## Nachweise aus Stufe 1

- Provider werden nur aus der aktivierten Auswahl beziehungsweise dem
  Fahrzeug-Provider-Modus versucht.
- Providerfähigkeiten verhindern nicht unterstützte Kraftstoffabfragen.
- Leere, ungültige, 401-, 429-, 5xx- und Timeout-Antworten werden synthetisch
  behandelt.
- Ein gemeinsamer Providerzugang kann von zwei Fahrzeugen genutzt werden.
- Gleichzeitige identische Suchanfragen werden über den account-/query-
  bezogenen Cache und Inflight-Lock auf eine Stationsabfrage reduziert.
- Nakordoni-Quota wird für einen gemeinsamen Zugang nur einmal im Cooldown
  geprüft.
- PKCE-Autorisierung, Refresh-Single-Flight, Tokenfehler und Neustart des
  synthetischen CredentialStores sind getestet.
- Die drei Suite-Module bleiben durch die bestehende Regression isoliert.

## Kontrollierter Live-Testplan – Stufe 2

1. **Vorprüfung:** separate Testkonten bzw. minimal berechtigte Schlüssel,
   dokumentierte Kontingente, erlaubte Zielmärkte und ein synthetisches
   Fahrzeugprofil festlegen. Keine produktiven HA-Daten verwenden.
2. **Tankerkönig:** genau eine begrenzte Stationsabfrage mit kleinem Radius und
   einem Kraftstoff; HTTP-Status, Schema und Quota-Verhalten ohne Schlüssel-
   oder Antwortdaten zu protokollieren.
3. **Petromap:** genau eine begrenzte Abfrage mit einem unterstützten
   Kraftstoff; Header, Markt und normalisierte Antwort prüfen.
4. **Nakordoni API:** genau eine OAuth-geschützte Stationsabfrage und – nur
   wenn erforderlich – eine separate Usage-Abfrage; Token nicht loggen.
5. **Nakordoni OAuth:** bestehende Verbindung lesen, anschließend bewusst
   „Verbindung erneuern“ starten, Refresh und Fehlerfall prüfen; danach
   Fahrzeuge, Module und Providerzugänge vergleichen.
6. **Mehrfahrzeugtest:** zwei synthetische Fahrzeuge mit unterschiedlichen
   Trackern und demselben Providerzugang; zuerst nacheinander, dann parallel,
   jeweils mit Reload und Neustart.
7. **Kontingentschutz:** Cache-/Cooldown-Nachweis, keine Wiederholungen,
   kein automatisches Retry bei Fehlern, sofortiger Abbruch bei unerwarteten
   Antworten. Zugangsdaten nach dem Test aus dem geschützten Testkontext
   entfernen und Entfernung verifizieren.

## Offene Punkte und Empfehlung

- Die reale Gültigkeit der dokumentierten Provider-Endpunkte, Kontingente,
  OAuth-Scopes und Testkonto-Berechtigungen ist ohne Live-Freigabe nicht
  nachgewiesen.
- Hassfest und Gitleaks benötigen einen CI-Lauf auf einem später ausdrücklich
  freigegebenen Branch/PR.
- Die aktuelle Stufe ist **lokal technisch bestanden**, aber nicht als
  Beta-Freigabe zu werten.

**Empfehlung:** Stufe 1 ist **GO für kontrollierte Live-Tests**, sofern diese
  separat mit Testzugängen freigegeben werden. Eine neue Beta bleibt bis zum
  erfolgreichen Live-Nachweis von Provider- und Nakordoni-OAuth-Verhalten
  **NO-GO**.
