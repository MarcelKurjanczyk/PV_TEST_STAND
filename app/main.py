import serial
from serial.tools import list_ports
import json
import csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import threading

def znajdz_port_esp32():
    ports = list(list_ports.comports())
    if not ports:
        raise RuntimeError("Nie znaleziono żadnego portu szeregowego.")

    keywords = ("ESP32", "CP210", "CH340", "USB-SERIAL", "USB UART", "FTDI")
    matching_ports = [
        port for port in ports
        if any(keyword in " ".join(
            filter(None, (port.description, port.manufacturer, port.product))
        ).upper() for keyword in keywords)
    ]

    if len(matching_ports) == 1:
        return matching_ports[0].device
    if len(ports) == 1:
        return ports[0].device
    if len(matching_ports) > 1:
        devices = ", ".join(port.device for port in matching_ports)
        raise RuntimeError(f"Znaleziono kilka portów możliwych dla ESP32: {devices}.")

    devices = ", ".join(port.device for port in ports)
    raise RuntimeError(f"Nie można jednoznacznie znaleźć ESP32. Dostępne porty: {devices}.")

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Stanowisko Testowe Panelu PV")
        self.root.geometry("1600x900")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing) 
        
        # Definicja kolorów
        self.darkBlue = "#2a3b4d"
        self.white = "#ffffff"
        self.grey = "#747070"
        self.lightBlue = "#3498db"
        self.lightBlueActive = "#3498db"
        self.red = "#e44a39"
        self.redActive= "#e74c3c"
        self.green = "#1bbd87"
        self.greenActive ="#2ecc71"
        self.pink = "#8c40ac"
        
        self.root.configure(bg=self.darkBlue)

    # Tworzenie panelu bocznego
        self.leftPanel = tk.Frame(root, bg=self.darkBlue, width=300)
        self.leftPanel.pack(side=tk.LEFT, fill=tk.Y, padx=30, pady=10)
        
        #Label : Status Układu
        tk.Label(self.leftPanel, text="STATUS UKŁADU", font=("Mangal", 12, "bold"), bg=self.darkBlue, fg=self.white).pack(pady=(0, 10))

        #Aktualny Kąt
        tk.Label(self.leftPanel, text="Kąt panelu:", font=("Mangal", 12), bg=self.darkBlue, fg=self.grey).pack()
        self.lblAngle = tk.Label(self.leftPanel, text="--.-°", font=("Mangal", 35, "bold"), bg=self.darkBlue, fg=self.white)
        self.lblAngle.pack(pady=(0, 10))
        
        #Aktualna Temperatura
        tk.Label(self.leftPanel, text="Temperatura panelu:", font=("Mangal", 12), bg=self.darkBlue, fg=self.grey).pack()
        self.lblTemp = tk.Label(self.leftPanel, text="--.- °C", font=("Mangal", 35, "bold"), bg=self.darkBlue, fg=self.white)
        self.lblTemp.pack(pady=(0, 10))
        
        #Moc Chłodzenia
        self.lblFan = tk.Label(self.leftPanel, text="Moc chłodzenia: -%", font=("Mangal", 12), bg=self.darkBlue, fg=self.green)
        self.lblFan.pack(pady=(0, 10))
        
        #Ustawianie Kąta
        tk.Label(self.leftPanel, text="STEROWANIE POZYCJĄ", font=("Mangal", 12, "bold"), bg=self.darkBlue, fg=self.white).pack(pady=(0, 10))
        self.angleVar = tk.DoubleVar(value=0.0)
        self.setAngle = ttk.Spinbox(self.leftPanel, from_=0, to=90, increment=1.8, format="%.1f", textvariable=self.angleVar, font=("Mangal", 14), width=8, justify='center')
        self.setAngle.pack(pady=5)
        self.btnangleVar = tk.Button(self.leftPanel, text="Ustaw Kąt", font=("Mangal", 11, "bold"), bg=self.green, fg="white", activebackground=self.greenActive, relief=tk.FLAT, command=self.wyslij_kat)
        self.btnangleVar.pack(fill=tk.X, pady=(0, 10))
        
        #Ustawianie temperatury
        tk.Label(self.leftPanel, text="STEROWANIE CHŁODZENIEM", font=("Mangal", 12, "bold"), bg=self.darkBlue, fg=self.white).pack(pady=(0,1))
        self.tempVar = tk.DoubleVar(value=100.0)
        self.setTemp = ttk.Spinbox(self.leftPanel, from_=0, to=100, increment=1.0, format="%.1f", textvariable=self.tempVar, font=("Mangal", 14), width=8, justify='center')
        self.setTemp.pack(pady=5)
        self.btnSetTemp = tk.Button(self.leftPanel, text="Ustaw Temperature", font=("Mangal", 12, "bold"), bg=self.green, fg="white", activebackground=self.greenActive, relief=tk.FLAT, command=self.wyslij_temp)
        self.btnSetTemp.pack(fill=tk.X, pady=(0, 40))
        
        #Charakterystyki I-U,P-U 
        self.progressVar = tk.IntVar(value=0)
        self.progressBar = ttk.Progressbar(self.leftPanel, orient="horizontal", mode="determinate", variable=self.progressVar, maximum=100)
        self.progressBar.pack(fill=tk.X, pady=(0, 10))

        self.btnSweep = tk.Button(self.leftPanel, text="ROZPOCZNIJ POMIAR", font=("Mangal", 14, "bold"), bg=self.green, fg=self.white, activebackground=self.greenActive, relief=tk.FLAT, pady=10, command=self.rozpocznij_sweep)
        self.btnSweep.pack(fill=tk.X, pady=(0, 10))

        self.btnAbort = tk.Button(self.leftPanel, text="PRZERWIJ POMIAR", font=("Mangal", 14, "bold"), bg=self.red, fg=self.white, activebackground=self.redActive, relief=tk.FLAT, pady=10, state=tk.DISABLED, disabledforeground=self.grey, command=self.przerwij_sweep)
        self.btnAbort.pack(fill=tk.X)

        #Tryb MPPT
        self.btnMppt = tk.Button(self.leftPanel, text="ROZPOCZNIJ MPPT", font=("Mangal", 14, "bold"), bg=self.green, fg=self.white, activebackground=self.greenActive, relief=tk.FLAT, pady=10, command=self.rozpocznij_mppt)
        self.btnMppt.pack(fill=tk.X, pady=(10, 0))

        #Przycisk zamknięcia aplikacji
        self.btnClose = tk.Button(self.leftPanel, text="ZAMKNIJ APLIKACJĘ", font=("Mangal", 12, "bold"), bg=self.red, fg=self.white, activebackground=self.redActive, relief=tk.FLAT, pady=8, command=self.on_closing)
        self.btnClose.pack(side=tk.BOTTOM, fill=tk.X, pady=(20, 0))

    #Tworzenia panelu wykresów i trybu MPPT 

        self.rightPanel = tk.Frame(root, bg=self.white)
        self.rightPanel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.fig = Figure(figsize=(7, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.powerAx = self.ax.twinx()
        self.fig.tight_layout(pad=5.0)
        
        self.sweepV = []
        self.sweepI = []
        self.sweepP = []
        self.mpptMaxPower = None
        self.mpptMaxVoltage = None
        self.mpptMaxCurrent = None
        self.mpptMaxPwm = None

        #Charakterystyki I-U i P-U
        self.ax.set_title("Charakterystyki Panelu PV (I-U i P-U)", fontsize=16, fontweight='bold', color=self.darkBlue)
        self.ax.set_xlabel("Napięcie U [V]", fontsize=12)
        self.ax.set_ylabel("Prąd I [mA]", fontsize=12, color=self.pink)
        self.powerAx.set_ylabel("Moc P [W]", fontsize=12, color=self.lightBlue)
        self.ax.grid(True, linestyle='--', alpha=0.6)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.rightPanel)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=20, pady=(20, 10))
        
        self.savePanel = tk.Frame(self.rightPanel, bg=self.white)
        self.savePanel.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(0, 20))
        
        self.btnSaveCsv = tk.Button(self.savePanel, text="Eksportuj Dane (.CSV)", font=("Mangal", 11, "bold"), bg=self.lightBlue, fg=self.white, activebackground=self.lightBlueActive, relief=tk.FLAT, state=tk.DISABLED, disabledforeground=self.white, width=20, command=self.zapisz_csv)
        self.btnSaveCsv.pack(side=tk.RIGHT)

        self.btnSavePng = tk.Button(self.savePanel, text="Zapisz Wykres (.PNG)", font=("Mangal", 11, "bold"), bg=self.lightBlue, fg=self.white, activebackground=self.lightBlueActive, relief=tk.FLAT, state=tk.DISABLED, disabledforeground=self.white, width=20, command=self.zapisz_png)
        self.btnSavePng.pack(side=tk.RIGHT, padx=(0, 10))

        #Panel MPPT
        self.mpptFrame = tk.Frame(self.rightPanel, bg=self.white)
        self.mpptTitle = tk.Label(self.mpptFrame, text="MPPT — śledzenie punktu mocy maksymalnej", font=("Mangal", 26, "bold"), bg=self.white, fg=self.darkBlue)
        self.mpptTitle.pack(pady=(55, 30))

        self.mpptTable = tk.Frame(self.mpptFrame, bg=self.white)
        self.mpptTable.pack(pady=(0, 20))
        cell_style = {"bg": self.white, "fg": self.darkBlue}
        tk.Label(self.mpptTable, text="", font=("Mangal", 16, "bold"), width=18, **cell_style).grid(row=0, column=0)
        tk.Label(self.mpptTable, text="TERAZ", font=("Mangal", 16, "bold"), width=22, **cell_style).grid(row=0, column=1)
        tk.Label(self.mpptTable, text="MAKSIMUM", font=("Mangal", 16, "bold"), width=22, **cell_style).grid(row=0, column=2)

        value_style = {"bg": self.white, "fg": self.darkBlue, "width": 22}
        self.mpptPwmLabel = tk.Label(self.mpptTable, text="-- %", font=("Mangal", 22), **value_style)
        self.mpptVoltageLabel = tk.Label(self.mpptTable, text="-- V", font=("Mangal", 22), **value_style)
        self.mpptCurrentLabel = tk.Label(self.mpptTable, text="-- mA", font=("Mangal", 22), **value_style)
        self.mpptPowerLabel = tk.Label(self.mpptTable, text="-- W", font=("Mangal", 24, "bold"), **value_style)
        self.mpptMaxPwmLabel = tk.Label(self.mpptTable, text="-- %", font=("Mangal", 22), **value_style)
        self.mpptMaxVoltageLabel = tk.Label(self.mpptTable, text="-- V", font=("Mangal", 22), **value_style)
        self.mpptMaxCurrentLabel = tk.Label(self.mpptTable, text="-- mA", font=("Mangal", 22), **value_style)
        self.mpptMaxPowerLabel = tk.Label(self.mpptTable, text="-- W", font=("Mangal", 24, "bold"), **value_style)
        self.mpptPowerLabel.config(fg=self.lightBlue)
        self.mpptMaxPowerLabel.config(fg=self.lightBlue)

        for row, name, current_label, max_label in [
            (1, "Moc [W]", self.mpptPowerLabel, self.mpptMaxPowerLabel),
            (2, "Napięcie [V]", self.mpptVoltageLabel, self.mpptMaxVoltageLabel),
            (3, "Prąd [mA]", self.mpptCurrentLabel, self.mpptMaxCurrentLabel),
            (4, "Obciążenie [%]", self.mpptPwmLabel, self.mpptMaxPwmLabel),
        ]:
            tk.Label(self.mpptTable, text=name, font=("Mangal", 16, "bold"), width=18, anchor="e", **cell_style).grid(row=row, column=0)
            current_label.grid(row=row, column=1)
            max_label.grid(row=row, column=2)

        self.btnMpptReset = tk.Button(self.mpptTable, text="WYZERUJ MAKSIMUM", font=("Mangal", 14, "bold"), bg=self.lightBlue, fg=self.white, activebackground=self.lightBlueActive, relief=tk.FLAT, pady=8, command=self.wyzeruj_mppt_max)
        self.btnMpptReset.grid(row=5, column=2, pady=8, ipadx=20)
        self.btnMpptBack = tk.Button(self.mpptFrame, text="POWRÓT DO WYKRESU", font=("Mangal", 18, "bold"), bg=self.red, fg=self.white, activebackground=self.redActive, relief=tk.FLAT, pady=14, command=self.zakoncz_mppt)
        self.btnMpptBack.pack(side=tk.BOTTOM, anchor="e", padx=30, pady=20, ipadx=30)
        
        threading.Thread(target=self.czytaj_serial, daemon=True).start()

    # Funkcja wywoływana przy zamykaniu okna aplikacji
    def on_closing(self):
        try:
            print("Wyłączanie pomiarów i wyjść...")
            ser.write(b"SHUTDOWN\n")
            ser.flush() 
        except:
            pass
        self.root.destroy()

    # Funkcja wysyłająca ustawiony kąt do mikrokontrolera
    def wyslij_kat(self):
        val = self.setAngle.get()
        ser.write(f"ANGLE:{val}\n".encode())

    # Funkcja wysyłająca ustawioną temperaturę do mikrokontrolera
    def wyslij_temp(self):
        val = self.setTemp.get()
        ser.write(f"TEMP:{val}\n".encode())

    # Funkcja rozpoczynająca pomiar charakterystyki I-U i P-U
    def rozpocznij_sweep(self):
        ser.write(b"SWEEP\n")
        self.sweepV.clear()
        self.sweepI.clear()
        self.sweepP.clear()
        self.progressVar.set(0)
        
        self.btnSweep.config(state=tk.DISABLED, text="W TRAKCIE POMIARU...")
        self.btnAbort.config(state=tk.NORMAL)
        self.btnMppt.config(state=tk.DISABLED)
        self.btnSavePng.config(state=tk.DISABLED)
        self.btnSaveCsv.config(state=tk.DISABLED)
        
        self.ax.clear()
        self.powerAx.remove()
        self.powerAx = self.ax.twinx()
        self.ax.set_title("W TRAKCIE POMIARU...", fontsize=14, fontweight='bold', color=self.red)
        self.ax.set_xlabel("Napięcie U [V]", fontsize=12)
        self.ax.set_ylabel("Prąd I [mA]", fontsize=12, color=self.pink)
        self.powerAx.set_ylabel("Moc P [W]", fontsize=12, color=self.lightBlue)
        self.ax.grid(True, linestyle='--', alpha=0.5)
        self.canvas.draw()

    # Funkcja przerywająca pomiar charakterystyk I-U i P-U
    def przerwij_sweep(self):
        ser.write(b"ABORT\n")
        self.btnAbort.config(state=tk.DISABLED)
        self.btnSweep.config(state=tk.NORMAL, text="ROZPOCZNIJ POMIAR")
        self.btnMppt.config(state=tk.NORMAL)
        self.progressVar.set(0)
        
        self.ax.set_title("POMIAR PRZERWANY...", fontsize=14, fontweight='bold', color=self.red)
        self.canvas.draw()

    def rozpocznij_mppt(self):
        ser.write(b"MPPT_START\n")
        self.wyzeruj_mppt_max()
        self.btnSweep.config(state=tk.DISABLED)
        self.btnAbort.config(state=tk.DISABLED)
        self.btnMppt.config(state=tk.DISABLED)
        self.btnSavePng.config(state=tk.DISABLED)
        self.btnSaveCsv.config(state=tk.DISABLED)
        self.canvas.get_tk_widget().pack_forget()
        self.savePanel.pack_forget()
        self.mpptFrame.pack(fill=tk.BOTH, expand=True)

    def zakoncz_mppt(self):
        ser.write(b"MPPT_STOP\n")
        self.mpptFrame.pack_forget()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=20, pady=(20, 10))
        self.savePanel.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(0, 20))
        self.btnSweep.config(state=tk.NORMAL, text="ROZPOCZNIJ POMIAR")
        self.btnMppt.config(state=tk.NORMAL, text="ROZPOCZNIJ MPPT")
        self.progressVar.set(0)

#Funkcja czytająca dane z portu szeregowego
    def czytaj_serial(self):
        while True:
            try:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith('{') and line.endswith('}'):
                    dane = json.loads(line)
                    if "mode" in dane:
                        if dane["mode"] == "status":
                            self.root.after(0, self.update_status, dane['angle'], dane['temp'], dane.get('fan', 0))
                        elif dane["mode"] == "sweep_data":
                            self.sweepV.append(dane['v'])
                            self.sweepI.append(dane['i'])
                            self.sweepP.append(dane.get('p', dane['v'] * dane['i'] / 1000.0))
                        elif dane["mode"] == "progress":
                            self.root.after(0, self.update_progress, dane['p'])
                        elif dane["mode"] == "sweep_end":
                            self.root.after(0, self.draw_final_plot)
                        elif dane["mode"] == "sweep_aborted":
                            self.root.after(0, self.handle_abort)
                        elif dane["mode"] == "mppt_data":
                            self.root.after(0, self.update_mppt, dane)
            except: 
                pass

    # Funkcja aktualizująca status układu
    def update_status(self, angle, temp, fan_pwm):
        self.lblAngle.config(text=f"{angle:.1f}°")
        self.lblTemp.config(text=f"{temp:.1f} °C")
        fanPower = int((fan_pwm / 255.0) * 100)
        self.lblFan.config(text=f"Moc chłodzenia: {fanPower}%")

    # Funkcja aktualizująca pasek postępu podczas pomiaru
    def update_progress(self, percent):
        self.progressVar.set(percent)
        self.btnSweep.config(text=f" W TRAKCIE POMIARU... {percent}%")

    def handle_abort(self):
        self.btnAbort.config(state=tk.DISABLED)
        self.btnSweep.config(state=tk.NORMAL, text="ROZPOCZNIJ POMIAR")
        self.btnMppt.config(state=tk.NORMAL)
        self.progressVar.set(0)

    def update_mppt(self, dane):
        pwm_percent = (dane['pwm'] / 4095.0) * 100.0
        self.mpptPwmLabel.config(text=f"{pwm_percent:.1f} %")
        self.mpptVoltageLabel.config(text=f"{dane['v']:.2f} V")
        self.mpptCurrentLabel.config(text=f"{dane['i']:.2f} mA")
        self.mpptPowerLabel.config(text=f"{dane['p']:.4f} W")

        if self.mpptMaxPower is None or dane['p'] > self.mpptMaxPower:
            self.mpptMaxPower = dane['p']
            self.mpptMaxVoltage = dane['v']
            self.mpptMaxCurrent = dane['i']
            self.mpptMaxPwm = pwm_percent
            self.mpptMaxPowerLabel.config(text=f"{self.mpptMaxPower:.4f} W")
            self.mpptMaxVoltageLabel.config(text=f"{self.mpptMaxVoltage:.2f} V")
            self.mpptMaxCurrentLabel.config(text=f"{self.mpptMaxCurrent:.2f} mA")
            self.mpptMaxPwmLabel.config(text=f"{self.mpptMaxPwm:.1f} %")

    def wyzeruj_mppt_max(self):
        self.mpptMaxPower = None
        self.mpptMaxVoltage = None
        self.mpptMaxCurrent = None
        self.mpptMaxPwm = None
        self.mpptMaxPowerLabel.config(text="-- W")
        self.mpptMaxVoltageLabel.config(text="-- V")
        self.mpptMaxCurrentLabel.config(text="-- mA")
        self.mpptMaxPwmLabel.config(text="-- %")

    # Funkcja rysująca wykres końcowy
    def draw_final_plot(self):
        self.progressVar.set(100)
        self.btnSweep.config(state=tk.NORMAL, text="ROZPOCZNIJ POMIAR")
        self.btnAbort.config(state=tk.DISABLED)
        self.btnMppt.config(state=tk.NORMAL)
   
        self.btnSavePng.config(state=tk.NORMAL)
        self.btnSaveCsv.config(state=tk.NORMAL)
            
        sortedData = sorted(zip(self.sweepV, self.sweepI, self.sweepP))
        sortedV = [val[0] for val in sortedData]
        sortedI = [val[1] for val in sortedData]
        sortedP = [val[2] for val in sortedData]
        
        self.ax.clear()
        self.powerAx.remove()
        self.powerAx = self.ax.twinx()
        self.ax.plot(sortedV, sortedI, marker='o', markersize=4, linestyle='-', color=self.pink, linewidth=2, label="I-U")
        self.powerAx.plot(sortedV, sortedP, marker='s', markersize=4, linestyle='-', color=self.lightBlue, linewidth=2, label="P-U")
        self.ax.set_title("Charakterystyki Panelu PV (I-U i P-U)", fontsize=14, fontweight='bold', color=self.darkBlue)
        self.ax.set_xlabel("Napięcie U [V]", fontsize=12)
        self.ax.set_ylabel("Prąd I [mA]", fontsize=12, color=self.pink)
        self.powerAx.set_ylabel("Moc P [W]", fontsize=12, color=self.lightBlue)
        self.ax.tick_params(axis='y', labelcolor=self.pink)
        self.powerAx.tick_params(axis='y', labelcolor=self.lightBlue)
        lines, labels = self.ax.get_legend_handles_labels()
        powerLines, powerLabels = self.powerAx.get_legend_handles_labels()
        self.ax.legend(lines + powerLines, labels + powerLabels, loc="best")

        self.ax.set_xlim(left=0)
        self.ax.set_ylim(bottom=0)
        self.powerAx.set_ylim(bottom=0)
        self.ax.grid(True, linestyle='--', alpha=0.5)
        self.canvas.draw()

    # FUNKCJE ZAPISU DO PLIKÓW
    def zapisz_png(self):
        filePath = filedialog.asksaveasfilename(
            defaultextension=".png", 
            filetypes=[("Plik PNG", "*.png")],
            title="Zapisz wykres jako"
        )
        if filePath:
            try:
                self.fig.savefig(filePath)
                messagebox.showinfo("Poprawny Zapis", f"Wykres został pomyślnie zapisany w:\n{filePath}")
            except Exception as e:
                messagebox.showerror("Błąd Zapisu", f"Nie udało się zapisać pliku:\n{e}")

    def zapisz_csv(self):
        filePath = filedialog.asksaveasfilename(
            defaultextension=".csv", 
            filetypes=[("Plik CSV", "*.csv")],
            title="Zapisz dane jako"
        )
        if filePath:
            try:
                sortedData = sorted(zip(self.sweepV, self.sweepI, self.sweepP))
                with open(filePath, mode='w', newline='') as file:
                    writer = csv.writer(file, delimiter=';')
                    writer.writerow(["Napiecie U [V]", "Prad I [mA]", "Moc P [W]"])
                    for v, i, p in sortedData:
                        writer.writerow([
                            str(v).replace('.', ','),
                            str(i).replace('.', ','),
                            str(p).replace('.', ',')
                        ])
                messagebox.showinfo("Poprawny Zapis", f"Dane zostały pomyślnie zapisane w:\n{filePath}")
            except Exception as e:
                messagebox.showerror("Błąd Zapisu", f"Nie udało się zapisać pliku:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    try:
        ser = serial.Serial(znajdz_port_esp32(), 115200, timeout=1)
        ser.write(b"WAKE\n")
        ser.flush()
    except (RuntimeError, serial.SerialException) as error:
        messagebox.showerror("Błąd połączenia", str(error))
        root.destroy()
    else:
        app = App(root)
        root.mainloop()