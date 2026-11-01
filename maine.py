import sqlite3
from datetime import datetime
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner

# --- INICIALIZACE DATABÁZE ---
def inicializuj_databazi():
    conn = sqlite3.connect("fleet_servis_pro.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vozidla (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spz TEXT UNIQUE,
            model TEXT,
            pobocka TEXT,              -- 'Pobočka A' nebo 'Pobočka B'
            stav TEXT DEFAULT 'V provozu', -- 'V provozu', 'Odstaveno', 'V servisu'
            pneu TEXT,
            sklad_pneu TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS servisy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auto_spz TEXT,
            pobocka TEXT,
            datum_od TEXT,             -- Formát YYYY-MM-DD pro řazení v DB
            datum_do TEXT,             -- Vyplní se při ukončení
            duvod TEXT,
            nahradni_spz TEXT,
            datum_vraceni_nahradni TEXT, -- Kdy se má vrátit náhradní auto
            aktivni INTEGER DEFAULT 1,  -- 1 = aktuální, 0 = v historii (archiv)
            FOREIGN KEY(auto_spz) REFERENCES vozidla(spz)
        )
    """)
    conn.commit()
    conn.close()

# --- POMOCNÉ FUNKCE PRO DATUM ---
def zformatuj_datum_pro_db(datum_str):
    try:
        dt = datetime.strptime(datum_str.strip(), "%d.%m.%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return ""

def zformatuj_datum_z_db(datum_db):
    if not datum_db:
        return ""
    try:
        dt = datetime.strptime(datum_db, "%Y-%m-%d")
        return dt.strftime("%d.%m.%Y")
    except ValueError:
        return datum_db

# --- OBRAZOVKY ---

# 1. Hlavní rozcestník
class HlavniRozcestnik(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=40, spacing=20)
        
        layout.add_widget(Label(text="Fleet Servis - Hlavní rozcestník", font_size=26, bold=True, size_hint_y=0.2))
        
        btn_pob_a = Button(text="🏢 Vstoupit do: POBOČKA A", size_hint_y=0.15, background_color=(0.2, 0.6, 1, 1))
        btn_pob_a.bind(on_press=lambda x: self.otevri_pobocku("Pobočka A"))
        layout.add_widget(btn_pob_a)
        
        btn_pob_b = Button(text="🏢 Vstoupit do: POBOČKA B", size_hint_y=0.15, background_color=(0.2, 0.6, 1, 1))
        btn_pob_b.bind(on_press=lambda x: self.otevri_pobocku("Pobočka B"))
        layout.add_widget(btn_pob_b)
        
        btn_historie = Button(text="🔍 Komplet historie & Filtry servisu", size_hint_y=0.15, background_color=(0.7, 0.7, 0.7, 1))
        btn_historie.bind(on_press=self.jdi_na_historii)
        layout.add_widget(btn_historie)
        
        self.add_widget(layout)

    def otevri_pobocku(self, nazev_pobocky):
        pob_screen = self.manager.get_screen('pobocka')
        pob_screen.nastav_pobocku(nazev_pobocky)
        self.manager.current = 'pobocka'

    def jdi_na_historii(self, instance):
        self.manager.current = 'historie'
        self.manager.get_screen('historie').reset_a_hledej()


# 2. Správa Pobočky (Všechna auta na jednom místě)
class SpravaPobocky(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pobocka = ""
        self.layout = BoxLayout(orientation='vertical', padding=15, spacing=10)
        
        self.lbl_titul = Label(text="", font_size=22, bold=True, size_hint_y=0.08)
        self.layout.add_widget(self.lbl_titul)
        
        # Horní akční řádek
        box_akce = BoxLayout(orientation='horizontal', size_hint_y=0.08, spacing=10)
        btn_poslat = Button(text="🔧 Poslat auto do servisu", background_color=(0.9, 0.3, 0.3, 1))
        btn_poslat.bind(on_press=self.jdi_poslat_servis)
        btn_pridat = Button(text="➕ Přidat nové auto", background_color=(0.3, 0.8, 0.3, 1))
        btn_pridat.bind(on_press=self.jdi_pridat_auto)
        box_akce.add_widget(btn_poslat)
        box_akce.add_widget(btn_pridat)
        self.layout.add_widget(box_akce)
        
        # Seznam aut
        self.scroll = ScrollView()
        self.seznam = BoxLayout(orientation='vertical', spacing=10, size_hint_y=None)
        self.seznam.bind(minimum_height=self.seznam.setter('height'))
        self.scroll.add_widget(self.seznam)
        self.layout.add_widget(self.scroll)
        
        btn_zpet = Button(text="⬅️ Zpět na hlavní rozcestník", size_hint_y=0.08)
        btn_zpet.bind(on_press=self.zpet)
        self.layout.add_widget(btn_zpet)
        
        self.add_widget(self.layout)

    def nastav_pobocku(self, nazev):
        self.pobocka = nazev
        self.lbl_titul.text = f"Přehled vozového parku: {nazev}"
        self.nacti_vozidla()

    def nacti_vozidla(self):
        self.seznam.clear_widgets()
        conn = sqlite3.connect("fleet_servis_pro.db")
        cursor = conn.cursor()
        
        query = """
            SELECT v.spz, v.model, v.stav, v.pneu, s.id, s.nahradni_spz, s.datum_vraceni_nahradni 
            FROM vozidla v
            LEFT JOIN servisy s ON v.spz = s.auto_spz AND s.aktivni = 1
            WHERE v.pobocka = ?
        """
        cursor.execute(query, (self.pobocka,))
        auta = cursor.fetchall()
        
        dnes = datetime.now().date()
        
        for auto in auta:
            spz, model, stav, pneu, servis_id, n_spz, n_datum_vraceni = auto
            box_auta = BoxLayout(orientation='vertical', size_hint_y=None, height=130, padding=8)
            
            if stav == "V servisu":
                barva_nahradni = "[color=ffffff]"
                info_pujceni = ""
                if n_spz:
                    info_pujceni = f" | Náhradní: {n_spz}"
                    if n_datum_vraceni:
                        info_pujceni += f" (Vrátit: {zformatuj_datum_z_db(n_datum_vraceni)})"
                        try:
                            dt_vraceni = datetime.strptime(n_datum_vraceni, "%Y-%m-%d").date()
                            rozdil = (dt_vraceni - dnes).days
                            if rozdil < 0:
                                barva_nahradni = "[color=ff3333]" # Červená - zpoždění
                            elif rozdil <= 2:
                                barva_nahradni = "[color=ffaa00]" # Oranžová - blíží se
                            else:
                                barva_nahradni = "[color=33ff33]" # Zelená - dostatek času
                        except ValueError:
                            pass
                else:
                    info_pujceni = " | Bez náhradního vozu"
                
                text_auta = f"❌ [b]{spz}[/b] ({model}) - [color=ff3333]V SERVISU[/color]{barva_nahradni}{info_pujceni}[/color]\n Obutí: {pneu}"
                lbl = Label(text=text_auta, size_hint_y=0.5, halign="left", valign="middle", markup=True)
                lbl.bind(size=lbl.setter('text_size'))
                box_auta.add_widget(lbl)
                
                box_btn = BoxLayout(orientation='horizontal', size_hint_y=0.5, spacing=8)
                btn_n = Button(text="🔄 Náhradní vůz")
                btn_n.bind(on_press=lambda x, sid=servis_id, s=spz, ns=n_spz, nd=n_datum_vraceni: self.popup_nahradni(sid, s, ns, nd))
                btn_v = Button(text="✅ Návrat ze servisu", background_color=(0, 0.7, 0, 1))
                btn_v.bind(on_press=lambda x, sid=servis_id, s=spz: self.vratit_ze_servisu(sid, s))
                box_btn.add_widget(btn_n)
                box_btn.add_widget(btn_v)
                box_auta.add_widget(box_btn)
                
            elif stav == "Odstaveno":
                text_auta = f"⚠️ [b]{spz}[/b] ({model}) - [color=ffaa00]ODSTAVENO[/color]\n Obutí: {pneu}"
                lbl = Label(text=text_auta, size_hint_y=0.5, halign="left", valign="middle", markup=True)
                lbl.bind(size=lbl.setter('text_size'))
                box_auta.add_widget(lbl)
                
                btn_aktivovat = Button(text="🚀 Vrátit auto do provozu", size_hint_y=0.5)
                btn_aktivovat.bind(on_press=lambda x, s=spz: self.zmen_stav_auta(s, "V provozu"))
                box_auta.add_widget(btn_aktivovat)
                
            else: # V provozu
                text_auta = f"✅ [b]{spz}[/b] ({model}) - [color=33ff33]V provozu[/color]\n Obutí: {pneu}"
                lbl = Label(text=text_auta, size_hint_y=0.5, halign="left", valign="middle", markup=True)
                lbl.bind(size=lbl.setter('text_size'))
                box_auta.add_widget(lbl)
                
                btn_odstavit = Button(text="⚠️ Odstavit vozidlo", size_hint_y=0.5)
                btn_odstavit.bind(on_press=lambda x, s=spz: self.zmen_stav_auta(s, "Odstaveno"))
                box_auta.add_widget(btn_odstavit)
                
            self.seznam.add_widget(box_auta)
        conn.close()

    def zmen_stav_auta(self, spz, novy_stav):
        conn = sqlite3.connect("fleet_servis_pro.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE vozidla SET stav = ? WHERE spz = ?", (novy_stav, spz))
        conn.commit()
        conn.close()
        self.nacti_vozidla()

    def popup_nahradni(self, servis_id, spz_auta, akt_spz, akt_datum):
        obsah = BoxLayout(orientation='vertical', padding=10, spacing=10)
        obsah.add_widget(Label(text=f"Náhradní auto pro {spz_auta}:"))
        
        vstup_spz = TextInput(text=akt_spz if akt_spz else "", hint_text="SPZ náhradního auta", multiline=False, size_hint_y=0.25)
