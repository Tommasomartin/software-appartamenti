"use strict";

/* ------------------------------------------------------------------ stato */

const stato = {
  righe: [],
  riepilogo: {},
  ipotesi: {},
  portafogli: [],
  orizzonte: 12,
  portafoglioId: "",
  ordine: { campo: "punteggio", crescente: false },
  filtri: { testo: "", tipologia: "", provincia: "", occupazione: "", conservazione: "", semaforo: "", multiplo: 0 },
};

const $ = (sel) => document.querySelector(sel);

/* ------------------------------------------------------------- formattatori */

const euro = (v, decimali = 0) =>
  v === null || v === undefined || Number.isNaN(v)
    ? "—"
    : new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR",
        minimumFractionDigits: decimali, maximumFractionDigits: decimali }).format(v);

const numero = (v, decimali = 0) =>
  v === null || v === undefined || Number.isNaN(v)
    ? "—"
    : new Intl.NumberFormat("it-IT", { minimumFractionDigits: decimali, maximumFractionDigits: decimali }).format(v);

const percento = (v, decimali = 0) =>
  v === null || v === undefined || Number.isNaN(v)
    ? "—"
    : new Intl.NumberFormat("it-IT", { style: "percent", minimumFractionDigits: decimali,
        maximumFractionDigits: decimali }).format(v);

const titolo = (s) => (s ? String(s).replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()) : "—");

function messaggio(testo, tipo = "") {
  document.querySelectorAll(".brindisi").forEach((n) => n.remove());
  const nodo = document.createElement("div");
  nodo.className = `brindisi ${tipo}`;
  nodo.textContent = testo;
  document.body.appendChild(nodo);
  setTimeout(() => nodo.remove(), tipo === "errore" ? 9000 : 4500);
}

/* --------------------------------------------------------------------- api */

async function api(percorso, opzioni = {}) {
  const risposta = await fetch(percorso, opzioni);
  if (!risposta.ok) {
    let dettaglio = `Errore ${risposta.status}`;
    try { dettaglio = (await risposta.json()).detail || dettaglio; } catch (_) {}
    throw new Error(dettaglio);
  }
  return risposta.status === 204 ? null : risposta.json();
}

async function ricarica() {
  const parametri = new URLSearchParams({ orizzonte_mesi: stato.orizzonte });
  if (stato.portafoglioId) parametri.set("portafoglio_id", stato.portafoglioId);
  const dati = await api(`/api/dashboard?${parametri}`);
  stato.righe = dati.righe;
  stato.riepilogo = dati.riepilogo;
  stato.ipotesi = dati.ipotesi;
  stato.portafogli = dati.meta.portafogli;
  disegnaPortafogli();
  popolaFiltri();
  disegnaKpi();
  disegnaTabella();
}

/* ------------------------------------------------------------------- righe */

function righeFiltrate() {
  const f = stato.filtri;
  const cerca = f.testo.trim().toLowerCase();
  return stato.righe.filter(({ immobile: i, prospetto: p }) => {
    if (f.semaforo && p.semaforo !== f.semaforo) return false;
    if (f.tipologia && i.tipologia !== f.tipologia) return false;
    if (f.provincia && i.provincia !== f.provincia) return false;
    if (f.occupazione && i.stato_occupazione !== f.occupazione) return false;
    if (f.conservazione && i.stato_conservazione !== f.conservazione) return false;
    if (f.multiplo && p.multiplo < f.multiplo) return false;
    if (cerca) {
      const testo = [i.lotto, i.comune, i.provincia, i.indirizzo, i.tipologia, i.note]
        .filter(Boolean).join(" ").toLowerCase();
      if (!testo.includes(cerca)) return false;
    }
    return true;
  });
}

function righeOrdinate() {
  const { campo, crescente } = stato.ordine;
  const segno = crescente ? 1 : -1;
  return righeFiltrate().sort((a, b) => {
    const va = a.prospetto[campo] ?? a.immobile[campo];
    const vb = b.prospetto[campo] ?? b.immobile[campo];
    if (typeof va === "string" || typeof vb === "string")
      return String(va ?? "").localeCompare(String(vb ?? ""), "it") * segno;
    return ((va ?? -Infinity) - (vb ?? -Infinity)) * segno;
  });
}

/* --------------------------------------------------------------------- kpi */

function disegnaKpi() {
  const r = stato.riepilogo;
  const f = stato.filtri.semaforo;
  const classe = (v) => (v > 0 ? "verde" : v < 0 ? "rosso" : "");
  $("#kpi").innerHTML = `
    <div class="kpi">
      <div class="etichetta">Immobili</div>
      <div class="valore">${numero(r.numero)}</div>
      <div class="sotto">valore a base d'asta ${euro(r.prezzo_base_totale)}</div>
    </div>
    <div class="kpi">
      <div class="etichetta">Priorita'</div>
      <div class="semafori" style="margin-top:6px">
        <div class="pill verde ${f === "verde" ? "attivo" : ""}" data-semaforo="verde">${r.verdi}<small>verdi</small></div>
        <div class="pill giallo ${f === "giallo" ? "attivo" : ""}" data-semaforo="giallo">${r.gialli}<small>gialli</small></div>
        <div class="pill rosso ${f === "rosso" ? "attivo" : ""}" data-semaforo="rosso">${r.rossi}<small>rossi</small></div>
      </div>
    </div>
    <div class="kpi">
      <div class="etichetta">Investimento totale</div>
      <div class="valore">${euro(r.investimento_totale)}</div>
      <div class="sotto">acquisto + costi + ${stato.orizzonte} mesi di gestione</div>
    </div>
    <div class="kpi">
      <div class="etichetta">Incasso netto atteso</div>
      <div class="valore">${euro(r.incasso_netto)}</div>
      <div class="sotto">al netto di provvigioni e spese</div>
    </div>
    <div class="kpi">
      <div class="etichetta">Utile</div>
      <div class="valore ${classe(r.utile)}">${euro(r.utile)}</div>
      <div class="sotto">ROI ${percento(r.roi_medio, 1)}</div>
    </div>
    <div class="kpi">
      <div class="etichetta">Multiplo di portafoglio</div>
      <div class="valore">${numero(r.multiplo_medio, 2)}x</div>
      <div class="sotto">confidenza media ${percento(r.confidenza_media)}</div>
    </div>`;

  $("#kpi").querySelectorAll(".pill").forEach((pill) =>
    pill.addEventListener("click", () => {
      const valore = pill.dataset.semaforo;
      stato.filtri.semaforo = stato.filtri.semaforo === valore ? "" : valore;
      disegnaKpi();
      disegnaTabella();
    })
  );
}

/* ----------------------------------------------------------------- tabella */

const COLONNE = [
  { campo: "lotto", etichetta: "Lotto", sx: true, cella: ({ immobile: i }) =>
      `<span class="etichetta-lotto">${i.lotto || "—"}${i.fab ? ` · FAB ${i.fab}` : ""}</span>
       <span class="sottotesto">${titolo(i.tipologia)}${i.superficie_mq ? ` · ${numero(i.superficie_mq)} mq` : ""}</span>` },
  { campo: "comune", etichetta: "Zona", sx: true, cella: ({ immobile: i }) =>
      `${i.comune || "—"}${i.provincia ? ` (${i.provincia})` : ""}
       <span class="sottotesto">${i.indirizzo || "indirizzo non indicato"}</span>` },
  { campo: "stato_occupazione", etichetta: "Stato", sx: true, cella: ({ immobile: i }) => {
      const occ = i.stato_occupazione;
      const classeOcc = occ === "libero" ? "libero" : occ === "occupato_senza_titolo" ? "abusivo" : occ === "sconosciuto" ? "" : "occupato";
      const cons = i.stato_conservazione;
      const classeCons = cons.startsWith("da_ristrutturare") || cons === "grezzo" ? "rifare" : "";
      return `<span class="tag ${classeOcc}">${titolo(occ)}</span>
              <span class="sottotesto"><span class="tag ${classeCons}">${titolo(cons)}</span></span>`;
    } },
  { campo: "prezzo_base", etichetta: "Prezzo da file", cella: ({ immobile: i }) => euro(i.prezzo_base) },
  { campo: "prezzo_acquisto", etichetta: "Acquisto scontato", cella: ({ prospetto: p }) =>
      `${euro(p.prezzo_acquisto)}<span class="sottotesto">${percento(p.percentuale_acquisto)} del base</span>` },
  { campo: "intermediazione", etichetta: "Intermediazione", cella: ({ prospetto: p }) =>
      `${euro(p.intermediazione)}<span class="sottotesto">esborso ${percento(p.percentuale_esborso_totale)} del base</span>` },
  { campo: "cassa_iniziale", etichetta: "Cassa iniziale", cella: ({ prospetto: p }) =>
      `${euro(p.cassa_iniziale)}<span class="sottotesto">+ ${euro(p.totale_costi_acquisto)} costi</span>` },
  { campo: "mantenimento_netto_annuo", etichetta: "Gestione/anno", cella: ({ prospetto: p }) =>
      `${euro(p.mantenimento_netto_annuo)}<span class="sottotesto">IMU ${euro(p.imu_annua)}</span>` },
  { campo: "valore_mercato_eur_mq", etichetta: "Mercato €/mq", cella: ({ prospetto: p }) =>
      `${euro(p.valore_mercato_eur_mq)}<span class="sottotesto">${p.comparabili?.zona || ""}</span>` },
  { campo: "prezzo_uscita", etichetta: "Prezzo rivendita", cella: ({ prospetto: p }) =>
      `${euro(p.prezzo_uscita)}<span class="sottotesto">netto ${euro(p.incasso_netto)}</span>` },
  { campo: "investimento_totale", etichetta: "Investimento", cella: ({ prospetto: p }) => euro(p.investimento_totale) },
  { campo: "utile", etichetta: "Utile", cella: ({ prospetto: p }) =>
      `<span class="${p.utile > 0 ? "positivo" : "negativo"}">${euro(p.utile)}</span>` },
  { campo: "multiplo", etichetta: "Multiplo", cella: ({ prospetto: p }) =>
      `<strong>${numero(p.multiplo, 2)}x</strong><span class="sottotesto">ROI ${percento(p.roi)}</span>` },
  { campo: "confidenza", etichetta: "Dati", cella: ({ prospetto: p }) =>
      `<span class="barra-confidenza"><i style="width:${Math.round(p.confidenza * 100)}%"></i></span>
       <span class="sottotesto">${percento(p.confidenza)}</span>` },
];

function disegnaTabella() {
  const righe = righeOrdinate();

  $("#intestazioni").innerHTML = COLONNE.map((c) => {
    const attiva = stato.ordine.campo === c.campo;
    const freccia = attiva ? (stato.ordine.crescente ? "▲" : "▼") : "";
    return `<th class="${c.sx ? "sx" : ""}" data-campo="${c.campo}">${c.etichetta} <span class="freccia">${freccia}</span></th>`;
  }).join("");

  $("#intestazioni").querySelectorAll("th").forEach((th) =>
    th.addEventListener("click", () => {
      const campo = th.dataset.campo;
      if (stato.ordine.campo === campo) stato.ordine.crescente = !stato.ordine.crescente;
      else stato.ordine = { campo, crescente: false };
      disegnaTabella();
    })
  );

  $("#corpo").innerHTML = righe.map((r) =>
    `<tr class="${r.prospetto.semaforo}" data-id="${r.immobile.id}">` +
    COLONNE.map((c) => `<td class="${c.sx ? "sx" : ""}">${c.cella(r)}</td>`).join("") +
    "</tr>"
  ).join("");

  $("#corpo").querySelectorAll("tr").forEach((tr) =>
    tr.addEventListener("click", () => apriDettaglio(tr.dataset.id))
  );

  const vuoto = $("#vuoto");
  if (!stato.righe.length) {
    vuoto.className = "vuoto";
    vuoto.innerHTML = `
      <h2>Nessun pool caricato</h2>
      <p>Carica un file Excel, CSV o PDF con l'elenco dei lotti. Le colonne vengono riconosciute
         automaticamente: lotto, FAB, tipologia, comune, superficie, stato di occupazione,
         stato di conservazione e prezzo a base d'asta.</p>
      <p><button class="bottone primario" onclick="document.getElementById('input-file').click()">Carica il primo file</button></p>`;
  } else if (!righe.length) {
    vuoto.className = "vuoto";
    vuoto.innerHTML = `<h2>Nessun immobile corrisponde ai filtri</h2><p>Allarga i criteri di ricerca.</p>`;
  } else {
    vuoto.className = "vuoto nascosto";
  }
}

/* ---------------------------------------------------------------- filtri */

function popolaFiltri() {
  const riempi = (sel, valori, etichetta) => {
    const nodo = $(sel);
    const corrente = nodo.value;
    nodo.innerHTML = `<option value="">${etichetta}</option>` +
      [...new Set(valori)].filter(Boolean).sort()
        .map((v) => `<option value="${v}">${titolo(v)}</option>`).join("");
    nodo.value = corrente;
  };
  const imm = stato.righe.map((r) => r.immobile);
  riempi("#f-tipologia", imm.map((i) => i.tipologia), "Tutte");
  riempi("#f-provincia", imm.map((i) => i.provincia), "Tutte");
  riempi("#f-occupazione", imm.map((i) => i.stato_occupazione), "Tutte");
  riempi("#f-conservazione", imm.map((i) => i.stato_conservazione), "Tutte");
}

function disegnaPortafogli() {
  const nodo = $("#sel-portafoglio");
  nodo.innerHTML = `<option value="">Tutti i portafogli</option>` +
    stato.portafogli.map((p) =>
      `<option value="${p.id}">${p.nome} (${p.numero_immobili})</option>`).join("");
  nodo.value = stato.portafoglioId;
}

/* -------------------------------------------------------- cassetto laterale */

function chiudiCassetto() {
  $("#cassetto").classList.add("nascosto");
  $("#velo").classList.add("nascosto");
}

function apriCassetto(html) {
  $("#cassetto").innerHTML = html;
  $("#cassetto").classList.remove("nascosto");
  $("#velo").classList.remove("nascosto");
  $("#cassetto").scrollTop = 0;
  $("#cassetto").querySelectorAll("[data-chiudi]").forEach((b) =>
    b.addEventListener("click", chiudiCassetto));
}

const voce = (nome, importo, classe = "") =>
  `<div class="voce ${classe}"><span class="nome">${nome}</span><span class="importo">${importo}</span></div>`;

async function apriDettaglio(id) {
  const riga = stato.righe.find((r) => r.immobile.id === id);
  if (!riga) return;
  const { immobile: i, prospetto: p, link: l } = riga;
  const c = p.comparabili || {};
  const serie = c.serie || {};
  const mesi = p.orizzonte_mesi;

  const avvisi = [...(p.motivazioni || []), ...(p.warning || [])];

  apriCassetto(`
    <header>
      <div style="flex:1">
        <h2>${i.lotto || "Lotto"} ${i.fab ? `· FAB ${i.fab}` : ""}</h2>
        <div class="nota-fonte">${titolo(i.tipologia)} · ${i.indirizzo || ""} ${i.comune ? `· ${i.comune} (${i.provincia})` : ""}</div>
      </div>
      <span class="distintivo ${p.semaforo}">${p.semaforo}</span>
      <button class="bottone piccolo" data-chiudi>Chiudi</button>
    </header>

    <div class="corpo">
      <div class="griglia-3">
        <div class="mini"><div class="etichetta">Multiplo</div><div class="valore">${numero(p.multiplo, 2)}x</div></div>
        <div class="mini"><div class="etichetta">Utile a ${mesi} mesi</div>
          <div class="valore" style="color:${p.utile > 0 ? "var(--verde)" : "var(--rosso)"}">${euro(p.utile)}</div></div>
        <div class="mini"><div class="etichetta">ROI annualizzato</div><div class="valore">${percento(p.roi_annualizzato)}</div></div>
      </div>

      ${avvisi.length ? `<div>${avvisi.map((a) => `<div class="avviso">${a}</div>`).join("")}</div>` : ""}

      <div class="blocco">
        <h3>Posizione</h3>
        <div class="bottoni-mappa">
          <a class="bottone" href="${l.google_maps}" target="_blank" rel="noopener">📍 Google Maps</a>
          <a class="bottone" href="${l.google_earth}" target="_blank" rel="noopener">🌍 Google Earth</a>
          <a class="bottone" href="${l.satellite}" target="_blank" rel="noopener">🛰 Satellite</a>
          <a class="bottone" href="${l.street_view}" target="_blank" rel="noopener">👁 Street View</a>
          <a class="bottone" href="${l.quotazioni_omi}" target="_blank" rel="noopener">📊 Quotazioni OMI</a>
        </div>
        ${l.ha_coordinate === "no"
          ? `<div class="nota-fonte" style="margin-top:9px">Coordinate assenti nel file: i link cercano l'indirizzo.
             Aggiungi latitudine e longitudine qui sotto per puntare esattamente sul punto.</div>` : ""}
      </div>

      <div class="blocco">
        <h3>1. Acquisto</h3>
        ${voce("Prezzo a base d'asta (da file)", euro(i.prezzo_base))}
        ${voce(`Prezzo di acquisto — FAB ${i.fab ?? "n.d."} al ${percento(p.percentuale_acquisto)}`, euro(p.prezzo_acquisto))}
        ${voce(`Intermediazione (${percento(stato.ipotesi.acquisto.intermediazione_pct)} del valore a base d'asta)`, euro(p.intermediazione))}
        ${voce("<strong>Esborso su valore a base d'asta</strong>", `<strong>${percento(p.percentuale_esborso_totale)}</strong>`)}
        ${voce(`Imposta di registro (${percento(stato.ipotesi.acquisto.imposta_registro_pct)}, acquisto da fondo)`, euro(p.imposta_registro))}
        ${voce("Imposte ipotecaria e catastale", euro(p.imposte_fisse))}
        ${voce("Notaio (onorario + IVA + spese)", euro(p.notaio))}
        ${voce(`Provvigione agenzia acquisto (${percento(stato.ipotesi.acquisto.commissione_agenzia_acquisto_pct)})`, euro(p.commissione_acquisto))}
        ${voce("Due diligence, perizia, visure", euro(p.altri_costi_acquisto))}
        ${voce("Ristrutturazione stimata", euro(p.capex_ristrutturazione))}
        ${voce("Cassa iniziale", euro(p.cassa_iniziale), "totale")}
      </div>

      <div class="blocco">
        <h3>2. Costi di mantenimento — piu' teniamo, piu' costa</h3>
        ${voce(`IMU annua <span class="sottotesto">${p.imu_metodo}</span>`, euro(p.imu_annua))}
        ${Object.entries(p.oneri_dettaglio || {}).map(([k, v]) => voce(titolo(k), euro(v))).join("")}
        ${p.ricavo_locazione_annuo > 0 ? voce("Ricavo da locazione (netto gestione e sfitto)", `− ${euro(p.ricavo_locazione_annuo)}`) : ""}
        ${voce("Costo netto annuo", euro(p.mantenimento_netto_annuo), "totale")}
        <div class="griglia-3" style="margin-top:12px">
          <div class="mini"><div class="etichetta">3 mesi</div><div class="valore">${euro(p.mantenimento_per_orizzonte.m3)}</div></div>
          <div class="mini"><div class="etichetta">6 mesi</div><div class="valore">${euro(p.mantenimento_per_orizzonte.m6)}</div></div>
          <div class="mini"><div class="etichetta">12 mesi</div><div class="valore">${euro(p.mantenimento_per_orizzonte.m12)}</div></div>
        </div>
      </div>

      <div class="blocco">
        <h3>3. Mercato di zona — prezzi al mq per periodo</h3>
        <div class="griglia-3">
          <div class="mini"><div class="etichetta">${c.etichette?.m3 || "3 mesi"}</div><div class="valore">${euro(serie.m3)}</div></div>
          <div class="mini"><div class="etichetta">${c.etichette?.m6 || "6 mesi"}</div><div class="valore">${euro(serie.m6)}</div></div>
          <div class="mini"><div class="etichetta">${c.etichette?.m12 || "12 mesi"}</div><div class="valore">${euro(serie.m12)}</div></div>
        </div>
        <div style="margin-top:12px">
          ${voce("Intervallo di zona", `${euro(c.eur_mq_min)} — ${euro(c.eur_mq_max)} /mq`)}
          ${voce("Variazione annua", percento(c.variazione_annua, 1))}
          ${voce("Zona di riferimento", c.zona || "—")}
        </div>
        <div class="nota-fonte" style="margin-top:10px">
          Fonte: ${c.fonte} · affidabilita' <strong>${c.affidabilita}</strong>.
          ${(c.note || []).join(" ")}
        </div>
      </div>

      <div class="blocco">
        <h3>4. Rivendita</h3>
        ${voce(`Valore di mercato lordo (${numero(i.superficie_mq)} mq × ${euro(p.valore_mercato_eur_mq)})`, euro(p.valore_mercato_lordo))}
        ${Object.entries(p.coefficienti_applicati || {}).filter(([k]) => !k.startsWith("_"))
            .map(([k, v]) => voce(`Rettifica ${titolo(k)}`, `× ${numero(v, 2)}`)).join("")}
        ${voce(`Rivendita da regola commerciale (valore file − ${percento(stato.ipotesi.uscita.sconto_su_valore_file_pct)})`,
               euro(p.prezzo_uscita_da_file))}
        ${voce("Rivendita da comparabili di zona", euro(p.prezzo_uscita_da_mercato))}
        ${voce(`Prezzo di rivendita adottato <span class="sottotesto">metodo: ${p.metodo_uscita}</span>`,
               euro(p.prezzo_uscita), "totale")}
        ${voce(`Provvigione agenzia vendita (${percento(stato.ipotesi.uscita.commissione_agenzia_vendita_pct)})`, `− ${euro(p.commissione_vendita)}`)}
        ${voce("Marketing, APE e pratiche", `− ${euro(p.costi_uscita)}`)}
        ${p.tassazione_plusvalenza > 0 ? voce("Tassazione plusvalenza", `− ${euro(p.tassazione_plusvalenza)}`) : ""}
        ${voce("Incasso netto", euro(p.incasso_netto), "totale")}
      </div>

      <div class="blocco">
        <h3>5. Risultato a ${mesi} mesi</h3>
        ${voce("Investimento totale", euro(p.investimento_totale))}
        ${voce("Incasso netto", euro(p.incasso_netto))}
        ${voce("Utile", euro(p.utile), "totale")}
        <div class="griglia-3" style="margin-top:12px">
          <div class="mini"><div class="etichetta">Multiplo</div><div class="valore">${numero(p.multiplo, 2)}x</div></div>
          <div class="mini"><div class="etichetta">Margine su ricavo</div><div class="valore">${percento(p.margine_su_ricavo)}</div></div>
          <div class="mini"><div class="etichetta">Prezzo di pareggio</div><div class="valore">${euro(p.prezzo_pareggio)}</div></div>
        </div>
      </div>

      <div class="blocco">
        <h3>Correggi i dati letti dal file</h3>
        <div class="nota-fonte" style="margin-bottom:10px">
          Se il file riportava un dato sbagliato o mancante, correggilo qui: il prospetto si ricalcola subito.
        </div>
        <div class="griglia-2" id="correzioni">
          ${campoCorrezione("superficie_mq", "Superficie mq", i.superficie_mq, "number")}
          ${campoCorrezione("prezzo_base", "Prezzo da file", i.prezzo_base, "number")}
          ${campoCorrezione("fab", "FAB", i.fab, "number")}
          ${campoSelect("tipologia", "Tipologia", i.tipologia,
              ["residenziale","ufficio","ricettivo","capannone","commerciale","box","terreno","altro"])}
          ${campoSelect("stato_occupazione", "Occupazione", i.stato_occupazione,
              ["libero","occupato","occupato_senza_titolo","parzialmente_occupato","sconosciuto"])}
          ${campoSelect("stato_conservazione", "Conservazione", i.stato_conservazione,
              ["nuovo","buono","da_ristrutturare","da_ristrutturare_totale","grezzo","sconosciuto"])}
          ${campoCorrezione("rendita_catastale", "Rendita catastale", i.rendita_catastale, "number")}
          ${campoCorrezione("canone_annuo", "Canone annuo", i.canone_annuo, "number")}
          ${i.tipologia === "terreno" ? campoSelect("destinazione_terreno", "Destinazione", i.destinazione_terreno,
              ["edificabile","agricolo","industriale","sconosciuto"]) : ""}
          ${i.tipologia === "terreno" ? campoCorrezione("indice_edificabilita", "Indice edif. mq/mq", i.indice_edificabilita, "number") : ""}
          ${campoCorrezione("comune", "Comune", i.comune, "text")}
          ${campoCorrezione("provincia", "Provincia (sigla)", i.provincia, "text")}
          ${campoCorrezione("lat", "Latitudine", i.lat, "number")}
          ${campoCorrezione("lng", "Longitudine", i.lng, "number")}
        </div>
        <button class="bottone primario" id="btn-salva-correzioni" style="margin-top:12px">Salva e ricalcola</button>
      </div>

      <div class="blocco">
        <h3>Dati originali dal file</h3>
        <div class="nota-fonte">
          ${Object.entries(i.raw || {}).map(([k, v]) => `<div><strong>${k}:</strong> ${v}</div>`).join("") || "—"}
        </div>
      </div>
    </div>`);

  $("#btn-salva-correzioni").addEventListener("click", async () => {
    const modifiche = {};
    $("#correzioni").querySelectorAll("[data-campo]").forEach((el) => {
      modifiche[el.dataset.campo] = el.value === "" ? null : el.value;
    });
    try {
      await api(`/api/immobile/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(modifiche),
      });
      await ricarica();
      apriDettaglio(id);
      messaggio("Dati aggiornati e prospetto ricalcolato.", "ok");
    } catch (e) {
      messaggio(e.message, "errore");
    }
  });
}

const campoCorrezione = (campo, etichetta, valore, tipo) =>
  `<label class="campo">${etichetta}
     <input type="${tipo}" data-campo="${campo}" value="${valore ?? ""}" ${tipo === "number" ? 'step="any"' : ""}>
   </label>`;

const campoSelect = (campo, etichetta, valore, opzioni) =>
  `<label class="campo">${etichetta}
     <select data-campo="${campo}">
       ${opzioni.map((o) => `<option value="${o}" ${o === valore ? "selected" : ""}>${titolo(o)}</option>`).join("")}
     </select>
   </label>`;

/* -------------------------------------------------------------- ipotesi */

function apriIpotesi() {
  const ip = stato.ipotesi;
  const scala = ip.fab.scala;
  const num = (percorso, etichetta, passo = "0.01", suffisso = "") =>
    `<label class="campo">${etichetta}${suffisso}
       <input type="number" step="${passo}" data-ipotesi="${percorso}" value="${percorso.split(".").reduce((o, k) => o[k], ip)}">
     </label>`;

  apriCassetto(`
    <header>
      <div style="flex:1"><h2>Ipotesi di calcolo</h2>
        <div class="nota-fonte">Valgono per tutto il portafoglio. Salvate nel database.</div></div>
      <button class="bottone piccolo" data-chiudi>Chiudi</button>
    </header>
    <div class="corpo">
      <div class="blocco">
        <h3>Scala FAB — quanto paghiamo del prezzo a base d'asta</h3>
        <div class="nota-fonte" style="margin-bottom:10px">
          FAB basso = piu' sconto (paghiamo meno). Esempio: 0,30 su FAB 1 significa che compriamo
          al 30% del valore scritto nel file.
        </div>
        <div class="scala-fab">
          ${Object.keys(scala).sort((a, b) => a - b).map((k) =>
            `<label>FAB ${k}<input type="number" step="0.01" min="0" max="1" data-fab="${k}" value="${scala[k]}"></label>`).join("")}
        </div>
        <div style="margin-top:10px">${num("fab.percentuale_se_fab_assente", "Percentuale se il FAB non e' indicato")}</div>
      </div>

      <div class="blocco">
        <h3>Costi di acquisto</h3>
        <div class="griglia-2">
          ${num("acquisto.imposta_registro_pct", "Imposta di registro (acquisto da fondo)")}
          ${num("acquisto.intermediazione_pct", "Intermediazione (sul valore del file)")}
          ${num("acquisto.commissione_agenzia_acquisto_pct", "Provvigione agenzia acquisto")}
          ${num("acquisto.due_diligence_fissa", "Due diligence", "50")}
          ${num("acquisto.perizia_fissa", "Perizia", "50")}
          ${num("acquisto.visure_volture_fissa", "Visure e volture", "50")}
          ${num("acquisto.notaio_spese_accessorie", "Notaio — spese accessorie", "50")}
        </div>
      </div>

      <div class="blocco">
        <h3>Rivendita</h3>
        <label class="campo" style="margin-bottom:10px">Come si stima il prezzo di rivendita
          <select id="sel-metodo-uscita">
            <option value="file">Valore del file meno lo sconto (regola commerciale)</option>
            <option value="mercato">Stima sui comparabili di zona</option>
            <option value="prudenziale">Il minore fra i due</option>
          </select>
        </label>
        <div class="griglia-2">
          ${num("uscita.sconto_su_valore_file_pct", "Sconto di rivendita sul valore del file")}
          ${num("uscita.commissione_agenzia_vendita_pct", "Provvigione agenzia vendita")}
          ${num("uscita.sconto_trattativa_pct", "Sconto medio in trattativa")}
          ${num("uscita.spese_marketing_fisse", "Spese marketing", "50")}
          ${num("uscita.ape_e_pratiche_fisse", "APE e pratiche", "50")}
          ${num("uscita.aliquota_plusvalenza_pct", "Aliquota plusvalenza")}
        </div>
        <label class="campo" style="margin-top:10px;flex-direction:row;align-items:center;gap:8px">
          <input type="checkbox" id="chk-plusvalenza" ${ip.uscita.applica_tassazione_plusvalenza ? "checked" : ""}>
          Applica la tassazione sulla plusvalenza
        </label>
      </div>

      <div class="blocco">
        <h3>Mantenimento</h3>
        <div class="griglia-2">
          ${num("mantenimento.gestione_pct_su_canone", "Costi di gestione sul canone")}
          ${num("mantenimento.sfitto_pct_su_canone", "Rischio sfitto sul canone")}
          ${num("mantenimento.costo_capitale_annuo_pct", "Costo del capitale annuo")}
        </div>
        <label class="campo" style="margin-top:10px;flex-direction:row;align-items:center;gap:8px">
          <input type="checkbox" id="chk-tari" ${ip.mantenimento.applica_tari_se_libero ? "checked" : ""}>
          Conteggia la TARI anche sugli immobili liberi
        </label>
      </div>

      <div class="blocco">
        <h3>Soglie del semaforo</h3>
        <div class="griglia-3">
          ${num("soglie_semaforo.verde.multiplo_min", "Verde: multiplo min", "0.1")}
          ${num("soglie_semaforo.verde.roi_min", "Verde: ROI min", "0.05")}
          ${num("soglie_semaforo.verde.utile_min", "Verde: utile min €", "1000")}
          ${num("soglie_semaforo.giallo.multiplo_min", "Giallo: multiplo min", "0.1")}
          ${num("soglie_semaforo.giallo.roi_min", "Giallo: ROI min", "0.05")}
          ${num("soglie_semaforo.giallo.utile_min", "Giallo: utile min €", "1000")}
        </div>
      </div>

      <div style="display:flex;gap:10px">
        <button class="bottone primario" id="btn-salva-ipotesi">Salva e ricalcola tutto</button>
        <button class="bottone pericolo" id="btn-reset-ipotesi">Ripristina i valori di default</button>
      </div>
    </div>`);

  $("#sel-metodo-uscita").value = ip.uscita.metodo || "file";

  $("#btn-salva-ipotesi").addEventListener("click", async () => {
    const nuove = JSON.parse(JSON.stringify(stato.ipotesi));
    $("#cassetto").querySelectorAll("[data-ipotesi]").forEach((el) => {
      const parti = el.dataset.ipotesi.split(".");
      const ultimo = parti.pop();
      parti.reduce((o, k) => o[k], nuove)[ultimo] = parseFloat(el.value) || 0;
    });
    $("#cassetto").querySelectorAll("[data-fab]").forEach((el) => {
      nuove.fab.scala[el.dataset.fab] = parseFloat(el.value) || 0;
    });
    nuove.uscita.applica_tassazione_plusvalenza = $("#chk-plusvalenza").checked;
    nuove.uscita.metodo = $("#sel-metodo-uscita").value;
    nuove.mantenimento.applica_tari_se_libero = $("#chk-tari").checked;
    try {
      await api("/api/ipotesi", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(nuove),
      });
      await ricarica();
      chiudiCassetto();
      messaggio("Ipotesi salvate: tutto il portafoglio e' stato ricalcolato.", "ok");
    } catch (e) { messaggio(e.message, "errore"); }
  });

  $("#btn-reset-ipotesi").addEventListener("click", async () => {
    await api("/api/ipotesi/reset", { method: "POST" });
    await ricarica();
    apriIpotesi();
    messaggio("Ipotesi riportate ai valori di default.", "ok");
  });
}

/* ---------------------------------------------------------------- fonti */

async function apriFonti() {
  const rif = await api("/api/riferimenti");
  apriCassetto(`
    <header>
      <div style="flex:1"><h2>Fonti dei dati</h2>
        <div class="nota-fonte">Da dove arriva ogni numero che non viene dal tuo file.</div></div>
      <button class="bottone piccolo" data-chiudi>Chiudi</button>
    </header>
    <div class="corpo">
      <div class="avviso">Le stime di mercato incluse sono una <strong>baseline interna</strong>, non un dato
        certificato. Per decisioni di acquisto sostituiscile con le quotazioni OMI ufficiali o con i tuoi
        comparabili rilevati sul posto.</div>

      <div class="blocco">
        <h3>Valori di mercato</h3>
        <div class="nota-fonte">
          <p><strong>Fonte attuale:</strong> ${rif.comparabili_utente_attivi
            ? "CSV comparabili caricato da te (ha la precedenza sulla baseline)."
            : rif.mercato.fonte}</p>
          <p><strong>Aggiornamento:</strong> ${rif.mercato.aggiornamento}</p>
          <p>${rif.mercato.come_sostituirla}</p>
        </div>
        <div class="bottoni-mappa" style="margin-top:12px">
          <a class="bottone piccolo" href="/api/comparabili/modello.csv">Scarica modello CSV</a>
          <button class="bottone piccolo" id="btn-carica-comp">Carica i tuoi comparabili</button>
          ${rif.comparabili_utente_attivi
            ? `<button class="bottone piccolo pericolo" id="btn-rimuovi-comp">Rimuovi e torna alla baseline</button>` : ""}
        </div>
        <input type="file" id="input-comp" class="nascosto" accept=".csv">
      </div>

      <div class="blocco">
        <h3>IMU e oneri</h3>
        <div class="nota-fonte">
          <p><strong>Aliquote:</strong> ${rif.imu.fonte_aliquote}</p>
          <p><strong>Rendite:</strong> ${rif.imu.fonte_rendite}</p>
          <p>${rif.imu.avvertenza}</p>
        </div>
      </div>

      <div class="blocco">
        <h3>Verifiche consigliate prima di offrire</h3>
        <div class="nota-fonte">
          <p>1. Quotazione OMI della zona esatta (non solo del comune).</p>
          <p>2. Aliquota IMU deliberata dal Comune per l'anno in corso.</p>
          <p>3. Per i terreni: indice di edificabilita' sul PRG comunale.</p>
          <p>4. Per gli occupati: contratto, scadenza, morosita' e diritto di prelazione.</p>
          <p>5. Conformita' urbanistica e catastale prima del rogito.</p>
        </div>
      </div>
    </div>`);

  $("#btn-carica-comp")?.addEventListener("click", () => $("#input-comp").click());
  $("#input-comp")?.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const dati = new FormData();
    dati.append("file", file);
    try {
      const esito = await api("/api/comparabili", { method: "POST", body: dati });
      await ricarica();
      apriFonti();
      messaggio(`Caricati ${esito.righe_caricate} comparabili: ora hanno la precedenza sulla baseline.`, "ok");
    } catch (err) { messaggio(err.message, "errore"); }
  });
  $("#btn-rimuovi-comp")?.addEventListener("click", async () => {
    await api("/api/comparabili", { method: "DELETE" });
    await ricarica();
    apriFonti();
    messaggio("Comparabili rimossi: si torna alla baseline interna.", "ok");
  });
}

/* ------------------------------------------------------------------ avvio */

function collega() {
  $("#btn-carica").addEventListener("click", () => $("#input-file").click());

  $("#input-file").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const bottone = $("#btn-carica");
    bottone.disabled = true;
    bottone.innerHTML = '<span class="caricamento"></span> Analisi in corso...';
    const dati = new FormData();
    dati.append("file", file);
    try {
      const esito = await api("/api/carica", { method: "POST", body: dati });
      stato.portafoglioId = String(esito.portafoglio_id);
      await ricarica();
      const ignorate = esito.diagnostica.flatMap((d) => d.colonne_ignorate || []);
      messaggio(
        `Importati ${esito.immobili_importati} immobili da ${esito.nome}.` +
        (ignorate.length ? ` Colonne non riconosciute: ${ignorate.slice(0, 5).join(", ")}.` : ""),
        "ok"
      );
    } catch (err) {
      messaggio(err.message, "errore");
    } finally {
      bottone.disabled = false;
      bottone.textContent = "Carica file pool";
      e.target.value = "";
    }
  });

  $("#sel-portafoglio").addEventListener("change", async (e) => {
    stato.portafoglioId = e.target.value;
    await ricarica();
  });

  $("#sel-orizzonte").addEventListener("change", async (e) => {
    stato.orizzonte = parseInt(e.target.value, 10);
    await ricarica();
  });

  $("#btn-esporta").addEventListener("click", () => {
    const parametri = new URLSearchParams({ orizzonte_mesi: stato.orizzonte });
    if (stato.portafoglioId) parametri.set("portafoglio_id", stato.portafoglioId);
    window.location = `/api/esporta.xlsx?${parametri}`;
  });

  $("#btn-ipotesi").addEventListener("click", apriIpotesi);
  $("#btn-fonti").addEventListener("click", apriFonti);
  $("#velo").addEventListener("click", chiudiCassetto);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") chiudiCassetto(); });

  const campiFiltro = {
    "#f-testo": "testo", "#f-tipologia": "tipologia", "#f-provincia": "provincia",
    "#f-occupazione": "occupazione", "#f-conservazione": "conservazione",
  };
  for (const [sel, chiave] of Object.entries(campiFiltro)) {
    $(sel).addEventListener("input", (e) => {
      stato.filtri[chiave] = e.target.value;
      disegnaTabella();
    });
  }
  $("#f-multiplo").addEventListener("input", (e) => {
    stato.filtri.multiplo = parseFloat(e.target.value) || 0;
    disegnaTabella();
  });
  $("#btn-azzera-filtri").addEventListener("click", () => {
    stato.filtri = { testo: "", tipologia: "", provincia: "", occupazione: "", conservazione: "", semaforo: "", multiplo: 0 };
    document.querySelectorAll(".filtri input, .filtri select").forEach((el) => (el.value = ""));
    disegnaKpi();
    disegnaTabella();
  });
}

collega();
ricarica().catch((e) => messaggio(e.message, "errore"));
