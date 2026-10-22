# SmartCamper Suite – Phase 2E Integrationsprüfung

Datum: 2026-10-22  
Ausgangsbasis: lokaler Commit `aa9b480589a0df24c441ea627718a2035e2f810d`  
Zielversion der Prüfung: Home Assistant 2026.10.1

## Ergebnis

**NO-GO für eine neue Beta.**

Die zentrale Config-/Options-Flow-Architektur funktioniert im echten Home-Assistant-
ConfigEntriesFlowManager der Zielversion mit synthetischen Daten. Die Prüfung hat
jedoch einen HA-2026.10.1-Kompatibilitätsfehler in optionalen numerischen Feldern
gefunden und lokal korrigiert. Der echte HA-Frontend-Kartenpicker sowie Hassfest,
Gitleaks und die finale CI sind in dieser isolierten Umgebung noch nicht als
vollständige Gates nachgewiesen.

## Lokal korrigierte Befunde

### Optionale Fahrzeugmaße

HA 2026.10.1 validiert `default=None` für `NumberSelector`-Felder nicht als leeren
Wert. Dadurch brach der echte Flow beim ersten Fahrzeug ohne gespeicherte Maße ab.
`_vehicle_schema()` verwendet jetzt für leere optionale Werte ein `vol.Optional`
ohne Default und setzt einen Default nur bei bereits gespeicherten Werten.

### Bewusste Nakordoni-Verbindungserneuerung

Der Config Flow implementiert `SOURCE_RECONFIGURE`. Bei einem bestehenden
Nakordoni-OAuth-Eintrag wird der externe OAuth-Schritt gestartet; nach erfolgreichem
Tokenaustausch wird nur der Token im bestehenden Config Entry aktualisiert.
Fahrzeuge, Providerkonten und Optionen bleiben dabei erhalten. Ohne Nakordoni-OAuth
wird der Reconfigure-Versuch kontrolliert abgebrochen. Der Pfad ist mit synthetischem
Token und ohne Netzwerkautorisierung getestet.

## Integrationsprüfung mit echtem HA-Flow-Manager

Die Tests liefen in einem separaten lokalen venv mit Python 3.14.2 und
Home Assistant 2026.10.1. VM 104 wurde nicht angesprochen.

| Prüfung | Ergebnis | Nachweis |
|---|---|---|
| Config Flow initialisieren | PASS | Echter `ConfigEntriesFlowManager`, Provider → Zugang → Fahrzeuge → Module → Allgemein |
| Zwei Fahrzeuge anlegen | PASS | `Wohnmobil` mit synthetischem Tracker und `Opel` mit eigenem synthetischem Tracker |
| Gemeinsame Providerzugänge | PASS | Ein globaler Tankerkönig-/Nakordoni-Zugang; keine fahrzeugbezogene Duplizierung |
| Options Flow editieren | PASS | `Wohnmobil` zu `Wohnmobil XL` geändert, zweites Fahrzeug anschließend entfernt |
| Provider beim Fahrzeugwechsel | PASS | Providerliste blieb `tankerkoenig`, `nakordoni` |
| Speicherung / Neustart | PASS im isolierten Harness | Nach explizitem Flush des HA-Config-Entry-Stores wurden Fahrzeug- und Provideroptionen nach neuem HA-Objekt wieder geladen |
| OAuth-Erneuerung | PASS für Flow-Vertrag | Neuer synthetischer Token ersetzt den alten; Optionen bleiben unverändert |
| Beta.3-Kompatibilität | RISIKO BEKANNT | Ein Config Entry bleibt ein Parent-Entry; keine automatische Migration oder Legacy-Importierung |

Die Persistenzprüfung verwendete den privaten Store-Flush nur, um in einem
minimalen Inline-Harness die normale HA-Debounce-Speicherung deterministisch vor
dem künstlichen Neustart abzuwarten. Dies verändert keinen Produktcode.

## Lovelace-Prüfung

| Prüfung | Ergebnis |
|---|---|
| TypeScript-Build / Bundle | PASS |
| `window.customCards` mit barem Typ `smartcamper-card` | PASS im vorhandenen Browser-Harness |
| `getStubConfig()` ohne `type` | PASS im vorhandenen Browser-Harness |
| Visueller Editor im Bundle-Harness | PASS |
| Echte HA-Frontend-Instanz mit Kartenpicker und Editor | **BLOCKED / nicht vollständig nachgewiesen** |

Der vorhandene Browser-Test ist ein isolierter Bundle-/DOM-Test. Der Versuch, eine
vollständige HA-Frontend-Bootstrap-Instanz in diesem Lauf reproduzierbar zu starten,
war wegen des dafür erforderlichen vollständigen HA-Loader-/HTTP-Lebenszyklus nicht
als sauberer, gebundener E2E-Test abschließbar. Daher wird der Kartenpicker nicht als
releasefähiger PASS bewertet.

## Testgates

### PASS

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .phase2e-ha-venv/bin/python -m pytest -q`
  → **56 passed, 1 skipped**
- `tests/test_ha_lifecycle.py` nach OAuth-Erweiterung → **5 passed**
- Frontend Vitest → **6 passed**
- TypeScript-Check und Bundle-Build → **PASS**
- Gebundelter Browser-Kartentest → **PASS**
- `compileall` → **PASS**
- JSON-Validierung von Manifest, strings und DE/EN-Übersetzungen → **PASS**
- `git diff --check` → **PASS**

### BLOCKED / NOT RUN

- Hassfest → nicht ausgeführt; HA 2026.10.1 enthält kein lokales
  `homeassistant.scripts.hassfest`-Modul und kein separates Hassfest-Executable war
  installiert.
- Gitleaks → nicht ausgeführt; Binary lokal nicht vorhanden.
- GitHub-CI → nicht ausgeführt; kein Push und kein PR gemäß Freigabegrenze.
- Vollständiger echter HA-Frontend-Kartenpicker → nicht als belastbarer E2E-PASS
  nachgewiesen.
- Live-Nakordoni-OAuth, echte Providerabfragen und echte API-Schlüssel → bewusst
  nicht ausgeführt.

Die lokalen Warnungen stammen aus HA-/aiohttp-/Python-3.14-Abhängigkeiten und sind
keine Testfehler.

## Beta.3-Kompatibilität und Migration

- Bestehende Beta.3-Daten werden im bestehenden Parent-Config-Entry gelesen.
- Fahrzeuge behalten ihre gespeicherten `vehicle_id`-Werte.
- API-Schlüssel bleiben im HA-Config-Entry-Datenbereich und werden bei leerem
  Passwortfeld nicht überschrieben; Testberichte und Logs verwenden nur synthetische
  Werte.
- Die Datenbank- und Legacy-Importpfade wurden nicht automatisch ausgeführt.
- Es gibt keine automatische Migration auf HA-Config-Subentries. Das ist bewusst so,
  weil eine Migration bestehender Beta.3-Entries ohne produktive Datenfreigabe nicht
  verantwortbar wäre.
- Das bisherige Versionsschema bleibt `VERSION = 1`; die lokale Korrektur ist daher
  kein veröffentlichter Versionswechsel.

## Arbeits- und Veröffentlichungsstatus

- Lokale Korrekturen und Tests sind erlaubt und wurden durchgeführt.
- Kein Push, kein PR, kein Tag und kein Release.
- Stable-Integrationen, VM 104, Proxmox, produktive Datenbanken und produktive
  Home-Assistant-Konfigurationen blieben unverändert.
- Der lokale Commit nach Abschluss der Prüfungen wird separat ausgewiesen; der
  Ausgangscommit bleibt oben nachvollziehbar.

## Empfehlung

Weiterhin **NO-GO**. Vor einer neuen Beta sind mindestens erforderlich:

1. Hassfest und Gitleaks in einer reproduzierbaren CI-/Tool-Umgebung ausführen.
2. Den echten HA-Frontend-Kartenpicker und visuellen Editor in einer isolierten,
   vollständig gestarteten HA-Instanz nachweisen.
3. Die komplette Prüfung auf dem finalen lokalen Commit wiederholen.
4. Erst danach einen Prüfbericht zur separaten Freigabe von Push, PR und Release
   vorlegen.
