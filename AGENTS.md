# Instrukcje dla Agentów AI

To repozytorium zawiera platformę do zarządzania routerami sieciowymi przez SSH o nazwie SSH Network Manager.

Agenci muszą komunikować się z użytkownikiem wyłącznie w języku polskim.

Agenci muszą przestrzegać poniższych zasad podczas generowania kodu lub modyfikowania projektu.

## Cel Projektu

SSH Network Manager pomaga administratorom sieciowym:

- konfigurować routery OpenWrt i Teltonika przez interfejs webowy
- monitorować status urządzeń i podłączonych klientów
- zarządzać DHCP, WiFi, LAN i regułami port forwardingu
- wykonywać polecenia diagnostyczne bez ręcznego logowania przez terminal SSH

System priorytetowo traktuje poprawność wykonywanych komend, bezpieczeństwo połączeń SSH oraz czytelność konfiguracji urządzeń.

## Architektura Rdzenia

Frontend Aplikacja Flask z szablonami Jinja2.

Backend Flask z warstwą wykonującą polecenia SSH przez paramiko.

Komunikacja z urządzeniem Wszystkie operacje są wykonywane na żywo przez SSH na routerze docelowym.

Stan aplikacji Aplikacja nie posiada własnej bazy danych. Konfiguracja jest pobierana z routera w czasie rzeczywistym.

Pełna dokumentacja architektury jest dostępna w: docs/architecture.md

## Zasady Programowania

Agenci AI muszą przestrzegać następujących zasad:

### Utrzymuj prostotę systemu

Unikaj niepotrzebnych abstrakcji. Preferuj jasny, czytelny kod.

### Przestrzegaj struktury domenowej

Kod backendu musi być zgodny ze strukturą aplikacji Flask. Każdy moduł funkcjonalny musi znajdować się wewnątrz: app/

Przykładowe moduły: routes, ssh_utils, templates

### Separacja warstw

Kod musi być zgodny z architekturą warstwową:

- routes.py → punkty końcowe HTTP i obsługa formularzy
- ssh_utils.py → wykonywanie komend SSH i parsowanie wyników
- templates/ → renderowanie widoków Jinja2

Logika wykonywania komend SSH nie może być umieszczana bezpośrednio w trasach (routes).

### Unikaj dużych kontrolerów

Trasy powinny pozostawać małe i delegować logikę do funkcji w ssh_utils.py.

### Konsekwentne nazewnictwo

Używaj spójnego nazewnictwa w całym projekcie.

Przykłady: get_dhcp_data, set_lan_config, add_port_forwarding, remove_dhcp_reservation

Unikaj niespójnego nazewnictwa, takiego jak: fetchDhcp, lanUpdate, portFwdAdd

## Zasady Wykonywania Komend SSH

Komendy SSH są krytyczną częścią aplikacji.

Zasady:

- każdy argument pochodzący od użytkownika musi być escapowany przed wstawieniem do komendy shellowej
- komendy modyfikujące konfigurację muszą zawierać uci commit oraz odpowiedni restart serwisu
- nigdy nie wykonuj komend o nieznanych skutkach bez potwierdzenia użytkownika

Wszystkie komendy SSH muszą przechodzić przez funkcje w app/ssh_utils.py.

## Zasady Bezpieczeństwa

To jest aplikacja administracyjna z dostępem do urządzeń sieciowych. Agenci muszą przestrzegać następujących zasad bezpieczeństwa:

- nigdy nie loguj haseł SSH ani treści sesji
- nigdy nie zapisuj haseł w plikach konfiguracyjnych ani w repozytorium
- zawsze waliduj formaty MAC, IP, hostname przed wykonaniem komendy
- zawsze używaj shlex.quote dla argumentów wstrzykiwanych do komend
- unikaj akceptowania kluczy hostów bez weryfikacji w środowisku produkcyjnym

## Zasady Wydajności

Aplikacja musi pozostać responsywna podczas pracy administratora. Ważne ograniczenia:

- unikaj otwierania nowego połączenia SSH dla każdej komendy w tej samej operacji
- preferuj jedną komendę zwracającą pełny wynik nad wieloma komendami pobierającymi pojedyncze pola
- unikaj długich operacji blokujących bez informacji zwrotnej w UI
- używaj timeoutów na połączeniach paramiko

## Zasady UI/UX

Frontend musi priorytetowo traktować czytelność i jednoznaczność operacji. Ważne zasady:

- jednoznaczne komunikaty po wykonaniu komendy (sukces lub błąd z opisem)
- walidacja formularza po stronie klienta przed wysłaniem do backendu
- wyraźne odróżnienie operacji odwracalnych od nieodwracalnych
- spójny układ widoków dla wszystkich modułów konfiguracyjnych

## Zasady Konfiguracji Urządzeń

Konfiguracja urządzeń odbywa się przez UCI w OpenWrt i Teltonika. Zasady:

- zawsze używaj uci commit po zmianie wartości
- zawsze restartuj odpowiedni serwis po commicie (dnsmasq, network, firewall, system)
- unikaj wykonywania komend specyficznych dla jednego modelu bez wykrycia urządzenia
- definiuj poprawne mapowania interfejsów iwinfo na sekcje UCI wireless

## Kod Generowany przez AI

Podczas generowania kodu agenci muszą:

- przestrzegać struktury projektu
- pisać czytelny kod
- dołączać komentarze dla złożonej logiki parsowania
- unikać wprowadzania niepotrzebnych frameworków

## Dokumentacja

Agenci muszą aktualizować dokumentację przy wprowadzaniu nowych modułów. Istotne pliki: docs/architecture.md, README.md

## Przyszłe Funkcje

System może w przyszłości zawierać:

- zarządzanie wieloma urządzeniami z jednego panelu
- bazę danych PostgreSQL przechowującą listę urządzeń i historię operacji
- REST API w FastAPI obok obecnego interfejsu Flask
- frontend SPA w React komunikujący się z REST API
- alerty webhook po zdarzeniach na urządzeniu
- konfigurację jako kod w formacie YAML

Agenci powinni projektować kod w sposób umożliwiający dodanie tych funkcji w przyszłości.

## Aktualny Stan Projektu (stan na 25.04.2026)

Projekt jest w fazie monolitu Flask z renderowaniem po stronie serwera. Obsługuje pojedyncze połączenie z routerem na sesję użytkownika.

### Zaimplementowane Moduły (app/)

- routes: Trasy HTTP dla każdego widoku konfiguracyjnego.
- ssh_utils: Funkcje wykonujące komendy SSH oraz parsery wyników.
- templates: Widoki Jinja2 z dziedziczeniem z base.html oraz CSS variables.

### Obsługiwane Operacje

- Połączenie SSH z routerem przez formularz logowania.
- DHCP: konfiguracja zakresu, czasu dzierżawy, rezerwacje statyczne.
- WiFi: zmiana SSID, hasła, szyfrowania per radio (default_radio0, default_radio1).
- LAN: konfiguracja IP, netmask, gateway, DNS oraz autodetekcja portów.
- LTE: parametry sygnału z AT+QENG, AT+CSQ, AT+QNWINFO dla urządzeń Teltonika.
- Hostname: pobieranie i zmiana z walidacją wzorca.
- Port forwarding: dodawanie, listowanie, usuwanie reguł firewall.
- Status urządzenia: CPU, RAM, uptime, load average, interfejsy.
- Lista urządzeń: ARP table z dopasowaniem nazw z DHCP leases.
- Konsola SSH: dowolna komenda wykonywana na routerze.

## Kluczowe Decyzje Architektoniczne

### Brak Lokalnej Bazy Danych

Aby priorytetowo traktować zgodność stanu z urządzeniem, aplikacja nie posiada własnej bazy danych. Każde wyświetlenie strony pobiera aktualny stan przez SSH.

Konsekwencje:

- interfejs zawsze pokazuje stan zgodny z routerem
- zmiany wprowadzone z poziomu CLI przez innego administratora są od razu widoczne
- brak bazy oznacza brak możliwości zarządzania wieloma urządzeniami w obecnej architekturze

### Architektura Warstwowa

Każdy moduł musi ściśle przestrzegać:

- routes.py: Trasy Flask, walidacja formularzy, wybór szablonu.
- ssh_utils.py: Wykonywanie komend SSH oraz parsowanie wyników.
- templates/: Szablony Jinja2 dziedziczące z base.html.
- static/: Style CSS oraz zasoby statyczne.

### Mapowanie Interfejsów iwinfo na UCI

Operacje na WiFi wymagają mapowania nazwy interfejsu z iwinfo (np. phy0, wlan0) na sekcję UCI (wireless.default_radio0). Mapowanie jest zaimplementowane w funkcji update_wifi_config w app/ssh_utils.py.

### Autodetekcja Topologii Portów

Funkcja get_ports_info parsuje wyjście swconfig oraz definicje VLAN z UCI w celu automatycznego rozpoznania ról portów (LAN, WAN, CPU). Pozwala to na obsługę różnych modeli routerów bez konfiguracji per model.
