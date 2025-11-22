# EduChat – Ein empathischer Begleiter für berufliche Perspektiven

## Executive Summary
EduChat ist ein empathisches, KI-gestütztes Empfehlungssystem in Chat-Form, das arbeitsuchende Menschen dabei unterstützt, passende Weiterbildungen und berufliche Perspektiven zu finden.
Im Zentrum steht eine verständliche und nahbare Kommunikation, die Nutzer:innen dabei hilft, ihre beruflichen Möglichkeiten besser einzuordnen. Ziel des Projekts ist es, Orientierung zu schaffen, Fehlentscheidungen zu reduzieren und nachhaltige berufliche Wege aufzuzeigen, die zu den Fähigkeiten und Lebenssituationen der Anwender:innen passen.

## Ziele des Projekts
EduChat soll die komplexe und oft unübersichtliche Weiterbildungslandschaft in Deutschland transparenter, zugänglicher und persönlicher machen. Das System soll den Nutzer:innen helfen, Qualifizierungen zu finden, die wirklich zu ihren Kompetenzen und zudem zu den Anforderungen des Arbeitsmarktes passen. 
Gleichzeitig bietet es dem Arbeitsamt und Jobcentern eine strukturierte und ressourcenschonende Unterstützung, indem es erste Empfehlungen übernimmt und somit die Beratungsprozesse entlastet. 
Durch fundierte und nachhaltige Vorschläge soll EduChat Arbeitssuchenden oder von Arbeitslosigkeit bedrohten Personen eine Chance geben, optimistisch in den Arbeitsmarkt zurückzukehren. 

Die empathische Kommunikation senkt dabei die Hemmschwelle der Akzeptanz, da verständliche und zugewandte Erläuterungen Nutzer:innen offener für neue berufliche Perspektiven macht.

## Anwendung und Nutzung


Zukunftiges Frontend sollte deshalb bewusst einfach und freundlich gestaltet sein, sodass auch Menschen mit wenig digitaler Erfahrung problemlos damit interagieren können. Perspektivisch sollen Bildungsanbieter ihre Weiterbildungen selbst einpflegen können.

**Repository:** [https://github.com/LauraWozniak/Educhat]

## Entwicklungsstand
Aktuell befindet sich EduChat im Prototyp-Status. Erste Module führen bereits authentische, empathische Gespräche und geben nachvollziehbare Empfehlungen.
Derzeit wird einen Scraper genutzt der einmal täglich die Daten der Plattform von Arbeitsamt scraped und somit die Qdrant Datenbank mit context befüllt.
**Source:** [https://mein-now.de/weiterbildungssuche/?ziel=erwerb&sw=weiterbildung]

Das nächste konkrete Ziel ist die Fertigstellung eines voll funktionsfähigen Proof of Concept mit einem sauberen einfach zu benutzenden Frontend (beispielsweise mit Streamlit) und die Einbinding der Scrapers um die Dummy Daten mit echten Weiterbildungsangeboten  

## Projektdetails
Der chat basiered auf Chatgpt in kombination von einer Qdrant Vectordatenbank gefüllt mit Dummy Daten aus staatlichen Quellen.

## Innovation
EduChat schließt eine Lücke, die viele internationale Plattformen übersehen: Die deutsche Weiterbildungs- und Arbeitsmarktlandschaft ist komplex, kleinteilig und stark reguliert. Während andere Systeme häufig universelle oder primär IT-bezogene Karrierepfade empfehlen, versteht EduChat die Vielfalt deutscher Branchen, regionaler Unterschiede und staatlicher Förderlogiken.


## Wirkung (Impact)
EduChat schafft für Arbeitsuchende einen realen Mehrwert, indem es Orientierung, emotionale Unterstützung und realistische Perspektiven bietet. 
Gleichzeitig profitiert der Staat  durch die reduzierung von Fehlförderungen und entlastet die persöhnliche Beratungszeit. 

Die Nutzer:innen werden nicht bevormundet, sondern akiv in den Entscheidungsprozess eingebunden, was ihre Motivation und Selbstwirksamkeit steigert. 

Unternehmen erhalten Bewerber:innen, deren Qualifikationen besser zu tatsächlichen Bedarfen passen, wodurch der gesamte Arbeitsmarkt effizienter wird. Insgesamt trägt das Projekt dazu bei, staatliche Investitionen in Weiterbildung effektiver einzusetzen und soziale Teilhabe zu stärken.

## Technische Exzellenz
Derzeit implementiert ist eine Vektordatenbank-Integration mit Basis-Chat-Funktionalität. 
Geplant sind KI-gestützte Semantische Suche, automatische Kursdaten-Akquisition und REST-APIs für erweiterte Nutzungsszenarien. Die Anwendung besteht aus mehreren micro services die über Docker laufen und über Kubernetes orchestriert werden, wodurch die Grundarchitektur für skalierbare Bildungsberatung angelegt ist.

## Ethik, Transparenz und Inklusion
Das Projekt legt großen Wert auf faire und nicht-diskriminierende Empfehlungen.
EduChat verfolgt das Prinzip, jede Person individuell zu betrachten und keine voreiligen Schlüsse aus sensiblen Daten zu ziehen. Alle Vorschläge werden transparent begründet, um Vertrauen und Nachvollziehbarkeit sicherzustellen. 


## Zukunftsvision
Ein Barrierearmes Frontend für die Nutzer und ein System das durch kontinuierliches Lernen immer präziser Weiterbildungen empfehlen kann und historische Erfolgsverläufe nutzt, um noch passendere Vorschläge zu generieren.

Obwohl EduChat derzeit als universitatives Studentenprojekt entwickelt wird, ist es bewusst so konzipiert, dass es sich zu einer realen, skalierbaren Lösung für den deutschen Staat weiterentwickeln ließe. 
