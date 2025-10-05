# PiccolaMimì

https://pierazhi.github.io/PiccolaMim-/

## Avvio in locale con backend condiviso

Il progetto ora include un piccolo server Node.js che salva le descrizioni delle foto su disco così che possano essere condivise tra dispositivi diversi.

### Requisiti

* Node.js 18 o superiore

### Installazione dipendenze

```bash
npm install
```

### Avvio dell'applicazione

```bash
npm start
```

Il comando avvia un server Express su `http://localhost:3000` che serve i file statici della galleria e risponde alle richieste REST su `/api/captions`.

Le descrizioni vengono salvate nel file `data/captions.json` (ignorato da Git). Assicurati di eseguire il server in un ambiente con scrittura abilitata per mantenere i dati.
