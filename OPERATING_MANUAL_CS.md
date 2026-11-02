# Universal Procurement Agent – uživatelský manuál

## 1. Účel

Universal Procurement Agent je osobní procurement copilot určený pro podporu strategických i operativních nákupních úkolů napříč různými zaměstnavateli, kategoriemi a odvětvími.

Agent pomáhá s:

- přípravou RFQ / RFP,
- porovnáním dodavatelských nabídek,
- TCO analýzou,
- přípravou na vyjednávání s dodavatelem,
- category strategy,
- spend baseline analýzou,
- review dodavatelského portfolia,
- supplier scorecardy,
- commercial contract review,
- protinávrhy dodavatelům,
- analýzou Excel procurement dat,
- analýzou dodavatelských e-mailů,
- review Word/PDF dokumentů,
- management reportingem.

Agent je záměrně nezávislý na konkrétním zaměstnavateli. Firemní kontext má být dodán pouze přes company profile nebo přímo v konkrétním zadání.

---

## 2. Základní princip používání

Pro nejlepší výsledky vždy uveď:

1. co chceš analyzovat,
2. vstupní data nebo dokument,
3. očekávaný výstup,
4. požadovanou úroveň detailu.

Příklad:

```text
Analyzuj tuto dodavatelskou nabídku.
Chci standardní procurement review s riziky, chybějícími údaji, doporučením a dalšími kroky.
```

---

## 3. Úrovně výstupu

Agent podporuje tři úrovně výstupu.

### Short / stručně

Použij, když chceš krátkou manažerskou odpověď.

Používej formulace:

```text
stručně
manažersky
pro vedení
executive summary
max. 1 strana
```

### Standard

Výchozí režim.

Použij pro běžnou procurement práci:

```text
standardní analýza
strukturovaně
včetně rizik a doporučení
```

### Detailed / detailně

Použij, když potřebuješ kompletní pracovní dokument.

Používej formulace:

```text
detailně
kompletní analýza
včetně tabulek
pracovní dokument
připrav podklad
```

---

## 4. Doporučená struktura promptu

Používej tuto strukturu:

```text
Úkol:
[Co má agent udělat]

Kontext:
[Krátké vysvětlení situace]

Vstupní data:
[Text / tabulka / soubor / e-mail / nabídka]

Chci:
1. uvést použité oficiální skilly,
2. oddělit analytické kroky,
3. připravit výstup v požadované struktuře,
4. uvést rizika,
5. dát doporučení,
6. navrhnout další kroky.

Výstup:
[stručně / standardně / detailně]
```

---

## 5. RFQ / RFP úkoly

Použij při přípravě dodavatelské poptávky, tendru nebo RFQ balíčku.

Příklad promptu:

```text
Připrav RFQ pro kategorii obalový materiál.

Kontext:
- potřebujeme oslovit 3 dodavatele
- chceme srovnatelné nabídky
- zatím nemáme jednotné ceny ani specifikace

Chci:
1. uvést použité skilly,
2. připravit RFQ e-mail,
3. navrhnout odpovědní tabulku pro dodavatele,
4. navrhnout hodnoticí kritéria,
5. vypsat chybějící vstupy.
```

Očekávané skilly:

- RFQ / RFP Preparation
- Procurement Category Strategy
- Supplier Portfolio Review
- Excel Procurement Analysis, pokud je potřeba odpovědní matice

---

## 6. Porovnání dodavatelských nabídek

Použij při porovnávání nabídek dodavatelů.

Příklad promptu:

```text
Porovnej tyto dvě nabídky:

Dodavatel A:
Cena 100 EUR / ks
Incoterms EXW
Lead time 4 týdny
Platební podmínky 30 dní
MOQ 1 000 ks

Dodavatel B:
Cena 108 EUR / ks
Incoterms DAP závod
Lead time 2 týdny
Platební podmínky 60 dní
MOQ 500 ks

Roční objem je 5 000 ks.

Chci:
1. uvést použité skilly,
2. připravit porovnávací tabulku,
3. upozornit na rizika neporovnatelnosti,
4. vysvětlit TCO dopad,
5. doporučit další krok.
```

Očekávané skilly:

- Supplier Quotation Comparison
- TCO Analysis
- Management Procurement Reporting, pokud je potřeba výstup pro vedení

---

## 7. Excel procurement analysis

Použij při nahrání nebo popisu Excel souborů.

Typické soubory:

- ceníky
- RFQ matice
- spend data
- supplier scorecardy
- seznamy dodavatelů
- TCO modely
- objednávková data
- fakturační data

Příklad promptu:

```text
Analyzuj tento Excel jako RFQ matici.

Chci:
1. zkontrolovat strukturu dat,
2. najít chybějící nebo nekonzistentní údaje,
3. porovnat dodavatele,
4. upozornit na rozdílné jednotky, měny a Incoterms,
5. připravit management summary.
```

Očekávané skilly:

- Excel Procurement Analysis
- Supplier Quotation Comparison
- TCO Analysis
- Management Procurement Reporting

Důležité pravidlo:

```text
Savings nepočítat bez jasné baseline.
```

---

## 8. Email procurement analysis

Použij při vložení dodavatelských e-mailů nebo e-mailových vláken.

Příklad promptu:

```text
Analyzuj tento e-mail od dodavatele:

"Dobrý den, potvrzujeme cenu 2,40 EUR/ks. Cena platí 14 dní. Dodání EXW, lead time 4 týdny, MOQ 5 000 ks. Platba 100 % předem. Technickou specifikaci a certifikáty zašleme později."

Chci:
1. shrnout e-mail,
2. vytáhnout klíčové procurement informace,
3. rozlišit potvrzené závazky a nejasnosti,
4. vypsat rizika,
5. navrhnout odpověď dodavateli.
```

Očekávané skilly:

- Email Procurement Analysis
- Contract Commercial Review
- Supplier Counterproposal

---

## 9. Word / PDF document review

Použij při kontrole:

- dodavatelských nabídek
- PDF obchodních podmínek
- Word smluv
- datasheetů
- technických specifikací
- SDS / REACH dokumentů
- certifikátů
- dodavatelských prezentací

Příklad promptu:

```text
Zkontroluj tento PDF dokument z procurement pohledu.

Chci:
1. shrnout dokument,
2. vytáhnout klíčové obchodní a technické informace,
3. vypsat red flags,
4. uvést chybějící body,
5. doporučit další kroky pro buyera.
```

Očekávané skilly:

- Document Review Word PDF
- Contract Commercial Review, pokud dokument obsahuje obchodní podmínky
- Supplier Counterproposal, pokud je potřeba odpověď dodavateli

---

## 10. Contract commercial review

Použij při kontrole dodavatelských obchodních podmínek.

Příklad promptu:

```text
Zkontroluj tyto obchodní podmínky:

- cena platná 14 dní
- dodání EXW
- platba 14 dní předem
- MOQ 5 000 ks
- reklamace do 3 dnů
- chybí SLA
- smlouva se automaticky prodlužuje o 12 měsíců

Chci:
1. commercial contract review,
2. red flags,
3. risk rating,
4. vyjednávací body,
5. doporučené další kroky.
```

Očekávané skilly:

- Contract Commercial Review
- Supplier Counterproposal
- Negotiation Brief, pokud je potřeba vyjednávací strategie

Důležité pravidlo:

```text
Agent neposkytuje finální právní stanovisko. Právní formulace musí potvrdit legal.
```

---

## 11. Supplier counterproposal

Použij při přípravě odpovědi dodavateli.

Příklad promptu:

```text
Připrav dodavateli profesionální e-mail s protinávrhem.

Požadované změny:
- EXW změnit na DAP závod
- platbu 100 % předem změnit na 30 dní po dodání
- prodloužit platnost ceny na 60 dní
- snížit MOQ na 1 000 ks
- doplnit SLA
- prodloužit reklamační lhůtu na 15 pracovních dnů

Chci:
1. vyjednávací tón,
2. e-mail dodavateli,
3. must-have požadavky,
4. fallback pozici.
```

Očekávané skilly:

- Supplier Counterproposal
- Contract Commercial Review
- Negotiation Brief

Důležité pravidlo:

```text
Fallback pozici neuvádět dodavateli hned v první odpovědi, pokud to uživatel výslovně nechce.
```

---

## 12. Category strategy

Použij pro strategické řízení nákupních kategorií.

Příklad promptu:

```text
Připrav management summary pro novou kategorii obalový materiál.

Kontext:
- kategorie není centrálně řízená
- nakupuje se od lokálních dodavatelů
- nejsou jednotné ceny ani specifikace
- není jasná spend baseline

Chci:
1. popsat současný stav,
2. navrhnout category strategy,
3. navrhnout spend baseline postup,
4. navrhnout supplier portfolio review,
5. vypsat quick wins,
6. navrhnout 90denní roadmapu,
7. připravit executive summary.
```

Očekávané skilly:

- Procurement Category Strategy
- Spend Baseline Analysis
- Supplier Portfolio Review
- Management Procurement Reporting

---

## 13. Supplier scorecard

Použij pro hodnocení výkonnosti dodavatelů.

Příklad promptu:

```text
Připrav supplier scorecard.

Dodavatel A:
- spend 500 000 EUR
- OTIF 92 %
- 8 reklamací za rok
- lead time 4 týdny
- platební podmínky 30 dní
- compliance dokumentace kompletní

Dodavatel B:
- spend 420 000 EUR
- OTIF 98 %
- 2 reklamace za rok
- lead time 2 týdny
- platební podmínky 60 dní
- compliance dokumentace částečně chybí

Chci:
1. supplier scorecard,
2. supplier status,
3. rizika,
4. doporučené další kroky.
```

Očekávané skilly:

- Supplier Scorecard
- Supplier Portfolio Review
- Management Procurement Reporting

---

## 14. Management reporting

Použij při přípravě výstupů pro vedení nebo board.

Příklad promptu:

```text
Připrav krátké management summary pro vedení.

Téma:
[stručně popsat situaci]

Chci:
1. hlavní sdělení,
2. finanční dopad,
3. rizika,
4. doporučené rozhodnutí,
5. další kroky.
```

Očekávané skilly:

- Management Procurement Reporting
- Další podpůrné skilly podle typu úkolu

Doporučený výstup:

```text
Krátký, manažerský, rozhodovací.
```

---

## 15. Procurement Task Router

Použij, když je úkol komplexní nebo smíšený.

Příklad promptu:

```text
Otestuj Procurement Task Router.

Mám e-mail od dodavatele s nabídkou a zároveň PDF obchodních podmínek.

Chci:
1. určit typ procurement úkolu,
2. vybrat primární skill,
3. vybrat podpůrné skilly,
4. navrhnout workflow,
5. říct, jaký výstup má buyer dostat.
```

Očekávaný skill:

- Procurement Task Router

Podpůrné skilly se vybírají podle typu vstupu.

---

## 16. Pravidla kvality dat

Agent musí vždy kontrolovat:

- jednotku měření,
- měnu,
- Incoterms,
- logistické náklady,
- platební podmínky,
- MOQ,
- lead time,
- platnost nabídky,
- technickou porovnatelnost,
- compliance dokumentaci,
- baseline,
- závislost na dodavateli,
- kvalitu zdrojového dokumentu.

Nedoporučuj dodavatele pouze podle nejnižší jednotkové ceny.

---

## 17. Pravidla důvěrnosti

Vysoce důvěrné informace zaměstnavatele neukládej do GitHub skillů.

Používej:

```text
company-profiles/current-employer-profile.md
```

pouze pro kontrolovaný firemní kontext.

Vyhýbej se ukládání:

- důvěrných dodavatelských cen,
- interních smluv,
- osobních údajů,
- citlivých vyjednávání,
- zákaznických důvěrných dat,
- právních stanovisek,
- HR citlivých informací.

U citlivých úkolů vkládej pouze nezbytné minimum kontextu.

---

## 18. Aktualizace agenta

Aktuální workflow:

1. Uprav nebo přidej `SKILL.md` v GitHubu.
2. Aktualizuj `skills.yaml`.
3. Vytvoř novou ZIP verzi.
4. Nahraj ZIP do Custom GPT Knowledge.
5. Otestuj nový skill.

Doporučené verzování:

```text
v1.0 počáteční skilly
v1.1 spend baseline + supplier portfolio
v1.2 supplier scorecard
v1.3 contract commercial review
v1.4 supplier counterproposal
v1.5 Word/PDF document review
v1.6 Excel + email analysis
v1.7 procurement task router
```

---

## 19. Dobré příklady promptů

### Krátký výstup pro management

```text
Připrav executive summary pro vedení. Stručně, max. 1 strana.
```

### Standardní výstup pro buyera

```text
Připrav standardní procurement analýzu s riziky, doporučením a dalšími kroky.
```

### Detailní pracovní dokument

```text
Připrav detailní pracovní dokument včetně tabulek, předpokladů, rizik a akčního plánu.
```

### E-mail pro dodavatele

```text
Připrav profesionální e-mail dodavateli. Tón standardní, věcný, neagresivní.
```

---

## 20. Finální pravidlo

Agent podporuje nákupní rozhodování, ale finální obchodní závazky, nominace dodavatele, schvalování smluv a právní interpretace musí vždy potvrdit odpovědný člověk.
