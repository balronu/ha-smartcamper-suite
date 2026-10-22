# Phase 2G – Kontrollierter Live-Testplan

## Vorprüfungsstatus

Am 22.10.2026 wurden die OpenClaw-Secret-Metadaten und die lokalen
Umgebungsvariablennamen geprüft. Es ist derzeit kein Tankerkönig-, Petromap-
oder Nakordoni-Testzugang als SecretRef oder Umgebungsvariable vorhanden.
Es wurde kein Secret angefordert und kein Netzwerkaufruf an einen Provider
ausgeführt.

Der Plan ist daher vorbereitet, aber **BLOCKED bis zur separaten Freigabe und
Bereitstellung geeigneter Testzugänge**.

## Endpunkte und Voraussetzungen

| Test | Endpoint | Auth/Berechtigung | Geplante Aufrufe |
|---|---|---|---:|
| Tankerkönig | `GET https://creativecommons.tankerkoenig.de/json/list.php` | persönlicher API-Key; Radius max. 25 km; DE-Kraftstoffe | 1 |
| Petromap | `GET https://api.petromap.eu/v2/places` | Petromap-API-Key im `x-api-key`-Header; freigeschalteter Account | 1 |
| Nakordoni Usage | `GET https://nakordoni.eu/api/v2/account/usage` | Bearer-Key/OAuth-Key; Usage-Abfrage | 1, nicht als Produktabfrage geplant |
| Nakordoni Fuel | `GET https://nakordoni.eu/api/v2/data/fuel-stations` | Bearer-Key/OAuth-Key; genehmigter Markt, z. B. DE | 1 |
| Nakordoni OAuth | `GET /oauth/authorize`, `POST /oauth/token` | freigeschaltete Integration-Client-ID, exakte Redirect-URI, PKCE S256 | nur bei separater OAuth-Freigabe |

Die offiziellen Dokumentationen nennen für Tankerkönig On-Demand-Abfragen und
ein API-Key-Rate-Limit, für Petromap ein Credit-Modell (eine Area-Suche kostet
einen Credit je 20 zurückgegebene Stationen) und für Nakordoni standardmäßig
1.000 Standarddaten-Aufrufe/Tag bei QPS 2. Die konkrete Kontingentlage des
Testzugangs muss vor dem Aufruf über den jeweiligen Account bestätigt werden.

Referenzen:

- https://creativecommons.tankerkoenig.de/
- https://developer.petromap.eu/docs/v2
- https://nakordoni.eu/en/developers/docs/fuel-stations
- https://nakordoni.eu/en/developers/docs

## Ausführungsablauf nach Freigabe

1. SecretRef im geschützten Gateway-Kontext prüfen; Wert niemals in Chat,
   Shell-Ausgabe, Logs, Reports oder Git übernehmen.
2. Vor jedem Test den Kontingent-/Kostenstatus geheimfrei erfassen.
3. Einen einzelnen, kleinen Request mit festem synthetischem Standort,
   `radius_km <= 5` beziehungsweise Tankerkönig `rad <= 5`, Diesel und
   maximal fünf Ergebnissen ausführen.
4. Nur Status, Antwortschema, Ergebnisanzahl, Währung, Provider und
   Kontingent-Header/-felder protokollieren; keine vollständigen Antworten,
   Adressen mit unnötigen Details oder Zugangsdaten speichern.
5. Nakordoni-Usage höchstens einmal vor dem Fuel-Request abfragen. Keine
   Wiederholung, kein automatisches Fallback und kein paralleler Provider-
   Aufruf im Live-Test.
6. Zwei synthetische Fahrzeugprofile mit unterschiedlichen Tracker-IDs und
   demselben Provider-Zugang konfigurieren. Bei identischen Koordinaten muss
   das zweite Profil den lokalen Cache verwenden und darf keinen zusätzlichen
   Provider-Request auslösen.
7. OAuth separat prüfen: bestehende Verbindung lesen, einmalige synthetische
   beziehungsweise freigegebene Token-Erneuerung, danach die bewusste
   Reauth-Aktion. Keine Revocation und kein Zurücksetzen eines produktiven
   Zugangs.
8. Nach dem Test SecretRef entfernen, sofern es ausschließlich für diesen
   Test angelegt wurde, und die Entfernung über die Secret-Metadaten prüfen.

## Abbruchkriterien

- fehlende oder nicht eindeutig genehmigte Berechtigung
- unbekannter Kontingent-/Kostenstatus
- HTTP 401/403, `market_not_allowed`, `quota_exceeded` oder unerwartete
  Antwortstruktur
- sichtbares Secret in Prozessargumenten, Logs oder Artefakten
- Provider fordert weitere Aufrufe, Retry oder OAuth-Revoke

## Erwartete Freigabe

Vor dem ersten echten API-Aufruf benötigt jeder Testzugang:

- Provider und Zweck des Zugangs
- bestätigter Markt beziehungsweise OAuth-Scope
- maximal erlaubte Aufrufzahl und Kosten-/Kontingentgrenze
- Bestätigung, dass der Zugang nicht produktiv verändert, widerrufen oder
  zurückgesetzt werden darf

Bis diese Angaben und eine ausdrückliche Live-Aufruffreigabe vorliegen, bleibt
Phase 2G Stufe 2 **NO-GO für Live-Ausführung**. Die Beta-Empfehlung bleibt
ebenfalls **NO-GO**.
