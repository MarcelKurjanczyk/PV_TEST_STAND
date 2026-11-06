## Stanowisko laboratoryjne do badania paneli fotowoltaicznych

Repozytorium zawiera oprogramowanie stanowiska laboratoryjnego opracowanego w ramach pracy inżynierskiej, przeznaczonego do wyznaczania i analizy charakterystyk elektrycznych panelu fotowoltaicznego w kontrolowanych warunkach oświetlenia i temperatury, a także do testowania algorytmu śledzenia punktu mocy maksymalnej (MPPT).

## Funkcjonalność

- Wyznaczanie charakterystyk prądowo-napięciowych (I-U) oraz mocowo-napięciowych (P-U).
- Implementacja algorytmu śledzenia punktu mocy maksymalnej (MPPT).
- Regulacja temperatury panelu za pomocą regulatora PI.
- Zmiana kąta ustawienia panelu przy użyciu silnika krokowego.
- Monitorowanie parametrów pracy stanowiska.
- Wizualizacja wyników pomiarowych oraz ich zapis do plików CSV i PNG.

## Oprogramowanie

**ESP32 (C++)**

Program mikrokontrolera opracowano w środowisku PlatformIO z wykorzystaniem frameworka Arduino. Odpowiada za sterowanie układami stanowiska, wykonywanie pomiarów oraz realizację algorytmu MPPT.

**Aplikacja komputerowa (Python)**

Aplikacja wykorzystuje biblioteki Tkinter, Matplotlib i PySerial. Umożliwia obsługę stanowiska, prezentację wyników oraz komunikację z mikrokontrolerem.

## Struktura repozytorium

- `src/` – kod źródłowy programu ESP32.
- `app/` – aplikacja komputerowa Python.
- `platformio.ini` – konfiguracja projektu PlatformIO.


## Uruchomienie

Przed uruchomieniem należy podłączyć ESP32 i zainstalować odpowiedni sterownik USB, jeśli nie został zainstalowany automatycznie przez system Windows.
Jeżeli podłączonych jest kilka urządzeń szeregowych i aplikacja nie może jednoznacznie rozpoznać ESP32, wyświetli komunikat z dostępnymi portami.
Prędkość transmisji `115200` musi być zgodna z konfiguracją programu mikrokontrolera.

### Program ESP32

Do kompilacji i wgrania programu mikrokontrolera wymagane jest środowisko PlatformIO. Po podłączeniu ESP32 należy wybrać właściwy port szeregowy, a następnie uruchomić kompilację i wgrywanie programu.

### Zbudowanie aplikacji `.exe`

Po pobraniu repozytorium należy zainstalować Python oraz wymagane biblioteki aplikacji:

```powershell
python -m pip install pyserial matplotlib pyinstaller
```

Następnie, w głównym folderze repozytorium, należy zbudować plik wykonywalny:

```powershell
python -m PyInstaller --onefile --windowed --name PanelPV app\main.py
```

Gotowy plik zostanie zapisany w folderze `dist/PanelPV.exe`. Do uruchomienia tego pliku na komputerze użytkownika Python ani dodatkowe biblioteki nie są wymagane.

