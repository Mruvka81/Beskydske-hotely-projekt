# ==============================================================================
# PROJEKT C: BESKYDSKÉ HOTELY - Příběh 1: Zrušení rezervací a nevratná sazba
# ==============================================================================
# OTÁZKA: Kolik rezervací z OTA portálů se ruší, jak se to změnilo po zavedení
#         nevratné sazby a mají hotely nevratnou sazbu nabízet víc?
#
# ZÁVĚR (3 věty - po vygenerování grafů doplň přesná čísla z výstupů):
# 1. Situace: Od 1. 3. 2025 vykazují OTA portály nejvyšší míru stornování ze všech
# #    kanálů – u ota_booking se ruší 32,8 % rezervací a u ota_expedia 30,6 % (oproti
# #    13,6 % na webu hotelu), přičemž pozdní storna do 7 dnů před příjezdem připravila
# #    hotely o 3 777 nocí v hodnotě 14,82 mil. Kč.
# # 2. Problém: Nevratná sazba snižuje stornovanost z 22,2 % na pouhých 4,9 % a přináší
# #    delší předstih rezervací (56,8 dne oproti 42,0 dnům) za cenu nižší jen o 255 Kč/noc
# #    (3 512 Kč vs. 3 766 Kč), přesto ji využívá jen 13,9 % hostů (3 190 z 22 891).
# # 3. Doporučení: Hotely by měly na OTA portálech aktivně zvýhodnit nevratnou sazbu
# #    (např. výraznější slevou 10–12 % a garancí pokoje); převedení alespoň 20 %
# #    pozdních storen na nevratnou sazbu zachrání cca 755 nocí a 2,96 mil. Kč tržeb.
# #
# # CO DATA NEPROKAZUJÍ (LIMITY ANALÝZY):
# # Data jsou syntetická a neukazují náklady na provize OTA portálů, provozní marži
# # ani to, kolik hostů by při omezení flexibilní sazby rezervaci vůbec neprovedlo.
# ==============================================================================

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# 1. NASTAVENÍ CESTY K DATŮM (povinné dle zadání)
CESTA = "data/"
VYSTUP = "outputs/"
os.makedirs(VYSTUP, exist_ok=True) # Vytvoří složku outputs, pokud neexistuje

# ==============================================================================
# KROK 1: NAČTENÍ DAT A PRVNÍ KONTROLA
# ==============================================================================
rezervace = pd.read_csv(CESTA + "rezervace.csv")
kurzy = pd.read_csv(CESTA + "kurzy.csv")
# Pokud máš ve složce i hotely.csv, odkomentuj řádek níže:
# hotely = pd.read_csv(CESTA + "hotely.csv")

print(f"Počet načtených rezervací: {len(rezervace)}")
print(rezervace.head(3)) # Ukáže první 3 řádky pro kontrolu

# ==============================================================================
# KROK 2: ČIŠTĚNÍ DAT A PŘÍPRAVA PROMĚNNÝCH
# ==============================================================================

# A) Převod textových datumů na skutečný formát datumu (datetime)
datumove_sloupce = ['booking_date', 'arrival_date', 'departure_date', 'cancel_date']
for col in datumove_sloupce:
    rezervace[col] = pd.to_datetime(rezervace[col], errors='coerce')

# B) Odvození měsíce a roku příjezdu (potřebujeme pro napojení kurzů)
rezervace['rok_prijezdu'] = rezervace['arrival_date'].dt.year
rezervace['mesic_prijezdu'] = rezervace['arrival_date'].dt.month
# Vytvoříme klíč ve formátu 'RRRR-MM' (např. '2025-05')
rezervace['rok_mesic'] = rezervace['arrival_date'].dt.to_period('M').astype(str)

# C) Přepočet měn na Kč podle kurzu v měsíci příjezdu
# Zkontrolujeme názvy sloupců v kurzy.csv (předpokládáme sloupec 'month' nebo 'date')
# Uprav 'month' podle skutečného názvu prvního sloupce v kurzy.csv!
prvni_sloupec_kurzy = kurzy.columns[0]
kurzy['rok_mesic'] = pd.to_datetime(kurzy[prvni_sloupec_kurzy]).dt.to_period('M').astype(str)

# Spojíme tabulku rezervací s kurzy (left join = zachováme všechny rezervace)
pocet_pred_merge = len(rezervace)
df = pd.merge(rezervace, kurzy[['rok_mesic', 'EUR_CZK', 'PLN_CZK']], on='rok_mesic', how='left')

# POVINNÝ ASSERT: Kontrola, že se nám při spojení nerozmnožily řádky
assert len(df) == pocet_pred_merge, "Chyba: Počet řádků po merge kurzů nesedí!"

# Samotný výpočet ceny v CZK
df['price_czk'] = np.where(df['currency'] == 'EUR', df['price_total'] * df['EUR_CZK'],
                  np.where(df['currency'] == 'PLN', df['price_total'] * df['PLN_CZK'],
                           df['price_total']))

# D) Řešení podivných řádků (rozhodnutí zdůvodněná v komentáři)
# 1. adults == 0 -> zjevná chyba zadání (pokoj bez dospělé osoby), vyřazujeme
df = df[df['adults'] > 0].copy()

# 2. nights == 0 -> denní wellness pobyty (nejsou to přenocování, zkreslily by cenu za noc ADR)
#    Pro analýzu ubytování a stornování nocí je vyřadíme.
df = df[df['nights'] > 0].copy()

# 3. price_total == 0 -> dárkové vouchery / věrnostní pobyty zdarma. Necháváme je v datech
#    pro počty rezervací, ale dáme pozor u průměrné ceny.
# 4. prázdné guest_id -> anonymní rezervace z OTA portálů (Booking, Expedia). Necháváme!

# E) Výpočet nových sloupců podle zadání
# Předstih rezervace (kolik dní před příjezdem si host pobyt objednal)
df['predstih_dni'] = (df['arrival_date'] - df['booking_date']).dt.days

# Skutečná tržba v Kč: počítá se JEN u stavu 'dokonceno' (zrušené peníze nepřinesly)
df['trzba_czk'] = np.where(df['status'] == 'dokonceno', df['price_czk'], 0)

# Průměrná cena za noc (ADR - Average Daily Rate) u dokončených pobytů
df['adr_czk'] = np.where(df['status'] == 'dokonceno', df['trzba_czk'] / df['nights'], np.nan)

# Příznak zrušení (1 = zrušeno nebo no_show, 0 = dokončeno)
df['je_zruseno'] = np.where(df['status'].isin(['zruseno', 'no_show']), 1, 0)

# Jak dlouho před příjezdem došlo ke zrušení (pro zjištění "pozdních storen")
df['storno_pred_prijezdem_dni'] = (df['arrival_date'] - df['cancel_date']).dt.days

print(f"Počet čistých rezervací pro analýzu: {len(df)}")
# ==============================================================================
# KROK 3: ANALÝZA PRO PŘÍBĚH 1 (Zrušení rezervací a nevratná sazba)
# ==============================================================================

# Férové srovnání: bereme jen rezervace vytvořené (booking_date) od 1. 3. 2025,
# protože před tímto datem nevratná sazba v nabídce hotelů vůbec neexistovala.
df_po_zmene = df[df['booking_date'] >= '2025-03-01'].copy()

# --- 1. TABULKA A GRAF: Míra zrušení podle prodejního kanálu ---
kanaly = df_po_zmene.groupby('channel').agg(
    pocet=('booking_id', 'count'),
    zruseno_pocet=('je_zruseno', 'sum'),
    zruseno_pct=('je_zruseno', lambda x: x.mean() * 100)
).reset_index().sort_values('zruseno_pct', ascending=True)

# Kontrola součtu (povinný assert dle zadání)
assert kanaly['pocet'].sum() == len(df_po_zmene), "Chyba v součtu rezervací po kanálech!"

print("\n--- Míra zrušení podle kanálu (rezervace od 1. 3. 2025) ---")
print(kanaly.to_string(index=False))

# Zjistíme hodnoty pro dynamický titulek
top_kanal = kanaly.iloc[-1]['channel']
top_pct = kanaly.iloc[-1]['zruseno_pct']
min_kanal = kanaly.iloc[0]['channel']
min_pct = kanaly.iloc[0]['zruseno_pct']

fig, ax = plt.subplots(figsize=(9, 4.8))
barvy = ['#B0B0B0' if c != top_kanal else '#D9534F' for c in kanaly['channel']]
bars = ax.barh(kanaly['channel'], kanaly['zruseno_pct'], color=barvy, height=0.6)

# Popisky hodnot přímo v grafu místo legendy (včetně n = velikost skupiny)
for bar, (_, row) in zip(bars, kanaly.iterrows()):
    ax.text(bar.get_width() + 0.4, bar.get_y() + bar.get_height()/2,
            f"{row['zruseno_pct']:.1f} % (n={int(row['pocet']):,})".replace(',', ' '),
            va='center', fontsize=9.5,
            fontweight='bold' if row['channel'] == top_kanal else 'normal')

ax.set_xlim(0, top_pct + 9)
ax.set_xlabel("Podíl zrušených rezervací a no-show (%)")
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

slovo = "více" if top_pct > min_pct else "stejně"
ax.set_title(f"Kanál {top_kanal} má nejvyšší stornovanost ({top_pct:.1f} %), výrazně {slovo} než {min_kanal} ({min_pct:.1f} %)",
             fontsize=10, fontweight='bold', loc='left', pad=15)

plt.tight_layout()
plt.savefig(VYSTUP + "graf1_storna_dle_kanalu.png", dpi=150)
plt.close() # Zavře graf, aby vyskakovací okna nebrzdila běh skriptu

# --- 2. TABULKA A GRAF: Srovnání flexibilní vs. nevratné sazby ---
sazby = df_po_zmene.groupby('rate_plan').agg(
    pocet=('booking_id', 'count'),
    zruseno_pct=('je_zruseno', lambda x: x.mean() * 100),
    prumerne_adr=('adr_czk', 'mean'),
    prumerny_predstih=('predstih_dni', 'mean')
).reset_index()

print("\n--- Srovnání flexibilní a nevratné sazby (od 1. 3. 2025) ---")
print(sazby.to_string(index=False))

fig, ax = plt.subplots(figsize=(7.5, 4.5))
barvy_sazby = ['#2E86C1' if r == 'nevratna' else '#B0B0B0' for r in sazby['rate_plan']]
bars = ax.bar(sazby['rate_plan'], sazby['prumerne_adr'], color=barvy_sazby, width=0.45)

for bar, (_, row) in zip(bars, sazby.iterrows()):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 40,
            f"{row['prumerne_adr']:,.0f} Kč\n(n={int(row['pocet']):,})".replace(',', ' '),
            ha='center', va='bottom', fontsize=10,
            fontweight='bold' if row['rate_plan'] == 'nevratna' else 'normal')

ax.set_ylim(0, sazby['prumerne_adr'].max() * 1.25) # Osa u sloupců musí začínat od 0
ax.set_ylabel("Průměrná cena za noc (Kč)")
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

adr_flex = sazby.loc[sazby['rate_plan'] == 'flexibilni', 'prumerne_adr'].values[0]
adr_nevr = sazby.loc[sazby['rate_plan'] == 'nevratna', 'prumerne_adr'].values[0]
rozdil_adr = abs(adr_flex - adr_nevr)
smer_ceny = "levnější" if adr_nevr < adr_flex else "dražší"

ax.set_title(f"Nevratná sazba je v průměru o {rozdil_adr:,.0f} Kč/noc {smer_ceny} než flexibilní".replace(',', ' '),
             fontsize=11.5, fontweight='bold', loc='left', pad=15)

plt.tight_layout()
plt.savefig(VYSTUP + "graf2_adr_dle_sazby.png", dpi=150)
plt.close()

# --- 3. GRAF (ČÁROVÝ): Vývoj podílu nevratné sazby v čase od března 2025 ---
df_po_zmene['mesic_vytvoreni'] = df_po_zmene['booking_date'].dt.to_period('M').astype(str)
df_po_zmene['je_nevratna'] = np.where(df_po_zmene['rate_plan'] == 'nevratna', 100, 0)

vyvoj = df_po_zmene.groupby('mesic_vytvoreni').agg(
    podil_nevratne=('je_nevratna', 'mean'),
    pocet=('booking_id', 'count')
).reset_index()

fig, ax = plt.subplots(figsize=(10, 4.5))
ax.plot(vyvoj['mesic_vytvoreni'], vyvoj['podil_nevratne'], marker='o', color='#2E86C1', linewidth=2.5)

# Popisek první a poslední hodnoty přímo v grafu
prvni_val = vyvoj.iloc[0]['podil_nevratne']
posledni_val = vyvoj.iloc[-1]['podil_nevratne']
ax.text(0, prvni_val + 1, f"{prvni_val:.1f} %", ha='center', fontsize=9.5, color='#555555')
ax.text(len(vyvoj)-1, posledni_val + 1, f"{posledni_val:.1f} %", ha='center', fontsize=10, fontweight='bold', color='#2E86C1')

ax.set_ylim(0, max(vyvoj['podil_nevratne']) + 8)
ax.set_ylabel("Podíl nevratné sazby na všech rezervacích (%)")
ax.set_xlabel("Měsíc vytvoření rezervace")
plt.xticks(rotation=45)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

trend_slovo = "vzrostl" if posledni_val > prvni_val else "klesl"
ax.set_title(f"Podíl nevratné sazby {trend_slovo} z {prvni_val:.1f} % v březnu 2025 na {posledni_val:.1f} % na konci období",
             fontsize=11.5, fontweight='bold', loc='left', pad=15)

plt.tight_layout()
plt.savefig(VYSTUP + "graf3_vyvoj_nevratne_sazby.png", dpi=150)
plt.close()

# --- 4. DOPAD POZDNÍCH STOREN A EXPORT SOUHRNNÉ TABULKY ---
pozdni_storna = df_po_zmene[(df_po_zmene['status'] == 'zruseno') & (df_po_zmene['storno_pred_prijezdem_dni'] <= 7)]
ztracene_noci = int(pozdni_storna['nights'].sum())
ushla_trzba = pozdni_storna['price_czk'].sum()

print("\n--- Dopad pozdních storen (<= 7 dní před příjezdem) od 1. 3. 2025 ---")
print(f"Počet pozdních storen: {len(pozdni_storna):,}".replace(',', ' '))
print(f"Zrušené noci: {ztracene_noci:,}".replace(',', ' '))
print(f"Hodnota zrušených pobytů: {ushla_trzba:,.0f} Kč".replace(',', ' '))

# Uložení souhrnné tabulky do outputs/ (splňuje požadavek na CSV výstup)
kanaly.to_csv(VYSTUP + "souhrn_kanaly_storna.csv", index=False)
print("\nHotovo! Grafy a tabulka byly uloženy do složky outputs/.")