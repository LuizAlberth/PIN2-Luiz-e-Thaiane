import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
import "./imagery.css";
const api = async (path, options = {}) => {
  const token = sessionStorage.getItem("pin2_token"),
    r = await fetch(`/api${path}`, {
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  let data;
  try {
    data = await r.json();
  } catch {
    data = {};
  }
  if (!r.ok)
    throw Error(
      typeof data.detail === "string" ? data.detail : `Erro ${r.status}`,
    );
  return data;
};
const date = (x, o = { dateStyle: "medium", timeStyle: "short" }) =>
  x
    ? new Intl.DateTimeFormat("pt-BR", {
        timeZone: "America/Sao_Paulo",
        ...o,
      }).format(new Date(x))
    : "—";
const cm = (x) =>
  x == null
    ? "—"
    : `${Number(x).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} cm`;
const meters = (x) =>
  x == null ? "—" : `${(Number(x) / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} m`;
const referenceNames = {
  ATENCAO: 'Atenção', ALERTA: 'Alerta', TRANSBORDAMENTO: 'Transbordamento/inundação',
  EMERGENCIA: 'Emergência', OUTRA: 'Outra referência técnica',
  NAO_CLASSIFICADA: 'Sem categoria local cadastrada', SIMULACAO: 'Simulação',
};
const referenceName = (kind) => referenceNames[kind] || 'Sem categoria local cadastrada';
const names = {
  ATUALIZADO: "Atualizado",
  ATRASADO: "Dado atrasado",
  INDISPONIVEL: "Sem dados",
  DISPONIVEL: "Disponível",
  PARCIAL: "Parcial",
  AGUARDANDO_IMAGEM: "Aguardando imagens",
  FALHOU: "Falhou",
  PENDENTE: "Pendente",
  CONCLUIDO: "Concluído",
  AGUARDANDO_RETRY: "Nova tentativa",
  EM_EXECUCAO: "Em execução",
  SIMULADA: "Simulada",
  SEM_CREDENCIAIS: "Sem credenciais",
  AGUARDANDO_DADOS: "Aguardando dados",
  FALHA: "Falha",
};
const Icon = ({ name, size = 20 }) => {
  let paths = {
    wave: (
      <>
        <path d="M2 13c3.2 0 3.2-3 6.4-3s3.2 3 6.4 3 3.2-3 6.4-3M2 18c3.2 0 3.2-3 6.4-3s3.2 3 6.4 3 3.2-3 6.4-3" />
      </>
    ),
    arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
    pin: (
      <>
        <path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z" />
        <circle cx="12" cy="10" r="2.5" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    layers: (
      <>
        <path d="m2 8 10-5 10 5-10 5L2 8Zm0 4 10 5 10-5M2 16l10 5 10-5" />
      </>
    ),
    shield: (
      <>
        <path d="M12 2 4 5v6c0 5.4 3.3 8.9 8 11 4.7-2.1 8-5.6 8-11V5l-8-3Z" />
        <path d="m9 12 2 2 4-4" />
      </>
    ),
    protection: (
      <>
        <path d="M12 2 3 6v6c0 4.5 3.4 8 9 10 5.6-2 9-5.5 9-10V6l-9-4Z" />
        <path d="m12 7 5 8H7l5-8Z" fill="currentColor" stroke="none" />
      </>
    ),
    image: (
      <>
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <circle cx="8" cy="8" r="1" />
        <path d="m3 17 5-5 4 4 3-3 6 6" />
      </>
    ),
    info: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v6M12 7h.01" />
      </>
    ),
    lock: (
      <>
        <rect x="5" y="10" width="14" height="11" rx="2" />
        <path d="M8 10V7a4 4 0 0 1 8 0v3" />
      </>
    ),
    refresh: (
      <>
        <path d="M20 7v5h-5M4 17v-5h5M5.5 9a7 7 0 0 1 12-2l2.5 5M4 12l2.5 5a7 7 0 0 0 12-2" />
      </>
    ),
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
};
const Badge = ({ children, tone = "neutral" }) => (
  <span className={`badge ${tone}`}>{children}</span>
);
const Notice = ({ demo = false, replay = false }) => (
  <div className={`notice ${demo || replay ? "demo" : ""}`}>
    <Icon name="info" size={18} />
    <span>
      {demo
        ? "Cotas simuladas. Imagens Sentinel-2 reais de antes e depois, fora do pico da enchente."
        : replay
          ? "Esta área reúne replays históricos. Alguns usam leituras e cenas reais; os cenários didáticos são identificados em cada evento."
          : "Comparações visuais são evidências informativas. O sistema não emite alertas oficiais nem delimita a área exata de inundação."}
    </span>
  </div>
);
function useLiveStation() {
  const [live, setLive] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const load = () => api("/stations/dcsc-00043")
      .then((value) => { if (active) { setLive(value); setError(""); } })
      .catch((e) => { if (active) { setLive(null); setError(e.message); } });
    load();
    const timer = setInterval(load, 60000);
    return () => { active = false; clearInterval(timer); };
  }, []);
  return { live, error };
}
function useMonitorStatus() {
  const [status, setStatus] = useState(null);
  useEffect(() => {
    let active = true;
    const load = () => api('/status').then((value) => { if (active) setStatus(value); }).catch(() => {});
    load();
    const timer = setInterval(load, 60000);
    return () => { active = false; clearInterval(timer); };
  }, []);
  return status;
}
function LiveStation({ live, error, station, monitor, compact = false }) {
  const current = live?.latest;
  const configuredReference = monitor?.config?.source_mode === 'DCSC' ? monitor.config : null;
  return (
    <section className={`live-station ${compact ? "compact" : ""}`} id={!compact ? "monitoramento" : undefined}>
      <div className="live-station-head">
        <div>
          <span className="caps">LEITURA PÚBLICA · DEFESA CIVIL SC</span>
          <h2>Rio dos Índios <small>{station?.code || "DCSC-00043"}</small></h2>
        </div>
        <a href="https://pdc.presidentegetulio.sc.gov.br/monitoramento" target="_blank" rel="noopener noreferrer">
          Portal municipal <Icon name="arrow" size={16} />
        </a>
      </div>
      <div className="live-station-body">
        <div className="live-reading">
          <strong>{meters(current?.water_level_cm)}</strong>
          <span className={`data-state ${live?.status === "ATUALIZADO" ? "fresh" : ""}`}>
            {live?.status === "ATUALIZADO" ? "Leitura recente" : live?.status === "ATRASADO" ? "Leitura antiga" : "Sem leitura"}
          </span>
          <small>{current ? `Publicado em ${date(current.observed_at)}` : "Consultando fonte municipal…"}</small>
        </div>
        {!compact && <div className="live-chart">
          <span className="caps">COMO O NÍVEL DO RIO MUDOU</span>
          <Graph readings={live?.items || []} threshold={null} />
          {configuredReference && <small>Referência cadastrada: {meters(configuredReference.threshold_cm)} · {referenceName(configuredReference.threshold_kind)}. {configuredReference.trigger_enabled === false ? 'Valor anterior de exemplo: novos gatilhos suspensos até o Admin cadastrar uma cota local.' : 'Valor informado pelo Admin para esta estação.'} Não é alerta oficial.</small>}
        </div>}
      </div>
      {error && !current && <div className="error inline-error" role="alert"><strong>Leitura indisponível.</strong> {error}</div>}
      <div className="live-source">
        <span>Fonte: dados DCSC-00043 reproduzidos pelo portal municipal. Horário acima é o de publicação na base.</span>
        <a href={station?.url || "https://monitoramento.defesacivil.sc.gov.br/estacao/DCSC-00043"} target="_blank" rel="noopener noreferrer">Estação original ↗</a>
      </div>
    </section>
  );
}
const EventCard = ({ item, open }) => (
  <button className="event-card" onClick={() => open(item.id)}>
    <div className="event-top">
      <span>
        {date(item.started_at, {
          day: "2-digit",
          month: "short",
          year: "numeric",
        })}
      </span>
      <Badge tone={item.status === "DISPONIVEL" ? "green" : "amber"}>
        {names[item.status] || item.status}
      </Badge>
    </div>
    {item.scenario_title && (
      <span className="event-scenario">{item.scenario_title}</span>
    )}
    <strong>{cm(item.trigger_level_cm)}</strong>
    <small>
      {item.mode === "SIMULACAO" ? "Cota simulada no gatilho" : "Cota no gatilho"}
      {" · referência "}{cm(item.threshold_cm)}
    </small>
    <div className="event-bottom">
      <span>
        <Icon name="pin" size={15} />
        {item.station_name}
      </span>
      <Icon name="arrow" size={18} />
    </div>
  </button>
);
function Graph({ readings, threshold }) {
  let pts = [...readings].reverse().filter((r) => r.water_level_cm != null);
  if (pts.length < 2)
    return (
      <div className="graph-empty">
        Ainda não há duas leituras com nível para mostrar a evolução.
      </div>
    );
  let vals = pts.map((x) => x.water_level_cm),
    observedMin = Math.min(...vals, threshold ?? Infinity),
    observedMax = Math.max(...vals, threshold ?? -Infinity),
    padding = Math.max(10, (observedMax - observedMin) * 0.12),
    lo = observedMin - padding,
    hi = observedMax + padding,
    span = hi - lo || 1,
    startTime = new Date(pts[0].observed_at).getTime(),
    timeSpan =
      new Date(pts[pts.length - 1].observed_at).getTime() - startTime || 1,
    coords = pts.map((p) => [
      66 + ((new Date(p.observed_at).getTime() - startTime) * 514) / timeSpan,
      168 - ((p.water_level_cm - lo) / span) * 128,
    ]),
    path = coords
      .map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`)
      .join(" "),
    ty = 168 - ((threshold - lo) / span) * 128,
    change = pts.at(-1).water_level_cm - pts[0].water_level_cm,
    trend = change > 0.5 ? `Subiu ${cm(change)}` : change < -0.5 ? `Baixou ${cm(-change)}` : "Permaneceu estável",
    levelAt = (y) => meters(lo + ((168 - y) / 128) * span);
  return (
    <>
      <div className="graph-summary"><strong>{trend}</strong><span>nas leituras exibidas</span></div>
      <svg
        className="graph"
        viewBox="0 0 600 210"
        role="img"
        aria-label={`Evolução do nível do rio, em metros. ${trend}.${threshold == null ? "" : ` Referência de ${meters(threshold)}.`}`}
      >
        <defs>
          <linearGradient id="g" x2="0" y2="1">
            <stop stopColor="#2365aa" stopOpacity=".28" />
            <stop offset="1" stopColor="#2365aa" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[40, 104, 168].map((y) => <g key={y}>
          <text x="4" y={y + 4} fill="#52646b" fontSize="11">{levelAt(y)}</text>
          <line x1="66" x2="580" y1={y} y2={y} stroke="#dce4e6" strokeDasharray="4 6" />
        </g>)}
        {threshold != null && <>
          <line x1="66" x2="580" y1={ty} y2={ty} stroke="#8f6a50" strokeDasharray="6 4" />
          <text x="578" y={Math.max(13, ty - 7)} textAnchor="end" fill="#76563d" fontSize="12">Referência {meters(threshold)}</text>
        </>}
        <path d={`${path} L580 168 L66 168 Z`} fill="url(#g)" />
        <path
          d={path}
          fill="none"
          stroke="#2365aa"
          strokeWidth="3"
          strokeLinecap="round"
        />
        {coords.map(([x, y], i) => (
          <circle
            key={i}
            cx={x}
            cy={y}
            r="3"
            fill="white"
            stroke="#2365aa"
            strokeWidth="2"
          ><title>{`${date(pts[i].observed_at)}: ${meters(pts[i].water_level_cm)}`}</title></circle>
        ))}
      </svg>
      <div className="graph-axis">
        <span>
          {date(pts[0].observed_at, {
            day: "2-digit",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
        <span>
          {date(pts.at(-1).observed_at, {
            day: "2-digit",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
      <p className="graph-guide">Linha mais alta = nível do rio mais alto. Valores em metros.</p>
    </>
  );
}
function HeroScene({ event }) {
  const [scene, setScene] = useState(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    setScene(null);
    setFailed(false);
    if (event?.id) {
      api(`/events/${event.id}`)
        .then((detail) => {
          if (active)
            setScene(detail.scenes.BASELINE || detail.scenes.POST_EVENT);
        })
        .catch(() => active && setFailed(true));
    }
    return () => {
      active = false;
    };
  }, [event?.id]);
  return (
    <div className={`hero-art ${scene && !failed ? "has-scene" : ""}`}>
      {scene && !failed ? (
        <img
          className="hero-scene"
          src={scene.image_url}
          alt="Imagem de satélite da área piloto em Presidente Getúlio"
          onError={() => setFailed(true)}
        />
      ) : (
        <div className="hero-placeholder" aria-hidden="true">
          <Icon name="protection" size={100} />
        </div>
      )}
      <div className="art-caption">
        <span>
          {scene && !failed
            ? `Área de estudo · Copernicus · ${date(scene.acquired_at, { dateStyle: "medium" })}`
            : "Rios Krauel e dos Índios · área de estudo"}
        </span>
      </div>
    </div>
  );
}
function SystemPurpose({ navigate, open, event }) {
  return (
    <section className="purpose" aria-labelledby="purpose-title">
      <div>
        <span className="caps">OBJETIVO</span>
        <h2 id="purpose-title">Acompanhar o rio e consultar imagens de eventos.</h2>
      </div>
      <div className="purpose-actions">
        <button onClick={() => document.getElementById("monitoramento")?.scrollIntoView({ behavior: "smooth" })}>Ver nível atual</button>
        <button onClick={() => event ? open(event.id) : navigate("events")}>Comparar imagens</button>
        <button onClick={() => navigate("events")}>Consultar eventos</button>
      </div>
    </section>
  );
}
function Dashboard({ navigate, open }) {
  let [data, setData] = useState(),
    [readings, setReadings] = useState([]),
    [error, setError] = useState("");
  const { live, error: liveError } = useLiveStation();
  useEffect(() => {
    let active = true;
    let load = () =>
      Promise.all([api("/status"), api("/readings")])
        .then(([a, b]) => {
          if (active) {
            setData(a);
            setReadings(b.items);
          }
        })
        .catch((e) => active && setError(e.message));
    load();
    let timer = setInterval(load, 30000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);
  if (error)
    return (
      <main className="container section">
        <div className="error">{error}</div>
      </main>
    );
  if (!data)
    return <main className="container section">Carregando painel…</main>;
  let c = data.config,
    r = data.reading;
  return (
    <>
      <section className="hero">
        <div className="container hero-grid">
          <div>
            <div className="eyebrow">PRESIDENTE GETÚLIO · SC</div>
            <h1>Monitoramento fluvial</h1>
            <p>Leituras públicas e comparação de imagens de satélite.</p>
            <div className="hero-actions">
              <button
                className="btn primary"
                onClick={() =>
                  data.recent_events.length
                    ? open(data.recent_events[0].id)
                    : navigate("events")
                }
              >
                {data.recent_events.length
                  ? "Ver comparação de 2023"
                  : "Explorar eventos"}{" "}
                <Icon name="arrow" size={18} />
              </button>
              <button className="btn ghost" onClick={() => navigate("about")}>
                Sobre o projeto
              </button>
            </div>
          </div>
          <HeroScene event={data.recent_events[0]} />
        </div>
      </section>
      <main className="container content">
        <SystemPurpose
          navigate={navigate}
          open={open}
          event={data.recent_events[0]}
        />
        <LiveStation live={live} error={liveError} station={data.official_station} />
        <div className="section-head demo-section-head">
          <div>
            <span className="caps">CENÁRIO HISTÓRICO · DADOS SIMULADOS</span>
            <h2>Novembro de 2023</h2>
          </div>
        </div>
        <article className="panel scenario-panel">
          <div className="scenario-summary">
            <div><span className="caps">ÚLTIMA COTA SIMULADA</span><strong>{cm(r?.water_level_cm)}</strong></div>
            <div><span className="caps">REFERÊNCIA SIMULADA</span><strong>{cm(c?.threshold_cm)}</strong></div>
            <p>O episódio foi documentado em 2023. O gráfico usa valores didáticos; as imagens são cenas reais de antes e depois.</p>
          </div>
          <Graph readings={readings} threshold={c?.threshold_cm} />
          <a className="source-link" href="https://www2.tjsc.jus.br/web/tjsc/atos-normativos-e-suspensao-de-prazos-e-expediente/presidente-getulio/portaria_2023115.pdf" target="_blank" rel="noopener noreferrer">Documento da ocorrência ↗</a>
        </article>
        <div className="section-head events-head">
          <div>
            <span className="caps">HISTÓRICO</span>
            <h2>Eventos recentes</h2>
          </div>
          <button className="text-link" onClick={() => navigate("events")}>
            Ver todos <Icon name="arrow" size={18} />
          </button>
        </div>
        {data.recent_events.length ? (
          <div className="event-grid">
            {data.recent_events.slice(0, 1).map((x) => (
              <EventCard key={x.id} item={x} open={open} />
            ))}
          </div>
        ) : (
          <div className="empty">
            <Icon name="layers" size={28} />
            <h3>Nenhum evento publicado</h3>
            <p>
              {c
                ? "Eventos aparecem quando houver passagem de cota e evidências processadas."
                : "O administrador pode iniciar uma demonstração para conhecer o fluxo."}
            </p>
          </div>
        )}
      </main>
    </>
  );
}
function Events({ open }) {
  let [mode, setMode] = useState("SIMULACAO"),
    [data, setData] = useState(),
    [error, setError] = useState("");
  const { live, error: liveError } = useLiveStation();
  useEffect(() => {
    setData(null);
    setError("");
    api(`/events?mode=${mode}`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [mode]);
  return (
    <main className="container section">
      <div className="page-head">
        <span className="caps">CONSULTA PÚBLICA</span>
        <h1>Histórico de eventos</h1>
        <p>Ocorrências publicadas e sua origem.</p>
      </div>
      <div className="tabs" role="tablist">
        <button
          role="tab"
          aria-selected={mode === "AO_VIVO"}
          className={mode === "AO_VIVO" ? "selected" : ""}
          onClick={() => setMode("AO_VIVO")}
        >
          Monitoramento real
        </button>
        <button
          role="tab"
          aria-selected={mode === "SIMULACAO"}
          className={mode === "SIMULACAO" ? "selected" : ""}
          onClick={() => setMode("SIMULACAO")}
        >
          Demonstrações
        </button>
      </div>
      {mode === "AO_VIVO" && <LiveStation live={live} error={liveError} station={live?.station} compact />}
      {mode === "SIMULACAO" && <Notice replay />}
      {error && <div className="error">{error}</div>}
      {!data ? (
        <div className="loading">Carregando eventos…</div>
      ) : data.items.length ? (
        <>
          <p className="muted list-count">
            {data.total} evento(s) publicado(s)
          </p>
          <div className="event-grid">
            {data.items.map((x) => (
              <EventCard key={x.id} item={x} open={open} />
            ))}
          </div>
        </>
      ) : (
        <div className="empty">
          <Icon name="image" size={28} />
          <h3>Nenhum evento neste modo</h3>
          <p>{mode === "AO_VIVO" ? "Há leitura real acima, mas nenhum evento com imagens foi publicado neste modo." : "Nenhuma demonstração publicada."}</p>
        </div>
      )}
    </main>
  );
}
function sceneUrl(scene, view) {
  return `${scene.image_url}${scene.image_url.includes("?") ? "&" : "?"}view=${view}`;
}
function DownloadLinks({ url, name }) {
  return <div className="image-downloads"><span>Baixar PNG:</span>{[1, 2, 4].map((scale) =>
    <a key={scale} href={`${url}${url.includes('?') ? '&' : '?'}scale=${scale}`} download={`${name}-${scale}x.png`}>{scale === 1 ? 'Original' : `${scale}×`}</a>)}
  </div>;
}
function scaledImageUrl(url, scale) {
  return `${url}${url.includes('?') ? '&' : '?'}scale=${scale}`;
}
const googleMapsEmbedKey = (import.meta.env.VITE_GOOGLE_MAPS_EMBED_API_KEY || '').trim();

function mapFocus(bbox, viewport) {
  const [west, south, east, north] = bbox;
  const x = viewport ? (viewport.scrollLeft + viewport.clientWidth / 2) / viewport.scrollWidth : .5;
  const y = viewport ? (viewport.scrollTop + viewport.clientHeight / 2) / viewport.scrollHeight : .5;
  return {
    lat: +(north - Math.min(1, Math.max(0, y)) * (north - south)).toFixed(6),
    lon: +(west + Math.min(1, Math.max(0, x)) * (east - west)).toFixed(6),
  };
}
function imageFocus(bbox, lon, lat) {
  const [west, south, east, north] = bbox;
  return { x: (lon - west) / (east - west), y: (north - lat) / (north - south) };
}
function nearestWaterwayFocus(bbox, features) {
  let chosen = { x: .5, y: .5 }, distance = Infinity;
  for (const feature of features || []) {
    const geometry = feature.geometry;
    const lines = geometry?.type === 'LineString' ? [geometry.coordinates] : geometry?.type === 'MultiLineString' ? geometry.coordinates : [];
    for (const line of lines) for (const [lon, lat] of line) {
      const point = imageFocus(bbox, lon, lat);
      const candidate = (point.x - .5) ** 2 + (point.y - .5) ** 2;
      if (candidate < distance && point.x >= 0 && point.x <= 1 && point.y >= 0 && point.y <= 1) {
        chosen = point; distance = candidate;
      }
    }
  }
  return chosen;
}

function MapReference({ bbox, viewport, scale }) {
  const [open, setOpen] = useState(false);
  const [focus, setFocus] = useState(null);
  if (!Array.isArray(bbox) || bbox.length !== 4 || !bbox.every(Number.isFinite)) return null;
  const center = focus || mapFocus(bbox);
  const zoom = 15 + Math.round(Math.log2(scale));
  const coordinates = `${center.lat},${center.lon}`;
  const mapsUrl = `https://www.google.com/maps/@?${new URLSearchParams({ api: '1', map_action: 'map', center: coordinates, zoom: String(zoom), basemap: 'satellite' })}`;
  const embedUrl = googleMapsEmbedKey && `https://www.google.com/maps/embed/v1/view?${new URLSearchParams({ key: googleMapsEmbedKey, center: coordinates, zoom: String(zoom), maptype: 'satellite', language: 'pt-BR' })}`;
  const updateFocus = () => setFocus(mapFocus(bbox, viewport.current));
  return <aside className="map-reference" aria-label="Referência cartográfica separada da imagem Sentinel">
    <button type="button" className="map-reference-toggle" aria-expanded={open} onClick={() => { if (!open) updateFocus(); setOpen(!open); }}>
      {open ? 'Ocultar contexto Google Maps' : 'Ver contexto Google Maps'}
    </button>
    {open && <div className="map-reference-content">
      <strong>Referência cartográfica</strong>
      <p>Imagem Google: data da captura não informada; apenas contexto cartográfico. O rio deste período deve ser avaliado na imagem Sentinel acima.</p>
      <div className="map-reference-actions">
        <button type="button" onClick={updateFocus}>Centralizar no trecho visível</button>
        <a href={mapsUrl} target="_blank" rel="noreferrer">Abrir no Google Maps ↗</a>
      </div>
      {embedUrl ? <iframe key={embedUrl} title={`Contexto Google Maps em ${coordinates}`} src={embedUrl} loading="lazy" referrerPolicy="strict-origin-when-cross-origin" allowFullScreen />
        : <p className="map-reference-unconfigured">O mapa integrado depende de uma chave da Maps Embed API. Use o link acima para consultar este ponto no Google Maps.</p>}
    </div>}
  </aside>;
}
function roadPaths(road, bbox) {
  const [west, south, east, north] = bbox;
  const lines = road.geometry.type === 'LineString' ? [road.geometry.coordinates] : road.geometry.coordinates;
  return lines.map((line) => line.map(([lon, lat]) =>
    `${((lon - west) / (east - west) * 1024).toFixed(1)},${((north - lat) / (north - south) * 1024).toFixed(1)}`).join(' '));
}
function RoadOverlay({ roads, bbox, selectedRoads, onToggle, showRoads }) {
  if (!roads?.length || !bbox) return null;
  return <svg className="roads-overlay" viewBox="0 0 1024 1024" preserveAspectRatio="none" aria-label="Trechos de ruas cartografadas; selecione para o relatório">
    {roads.flatMap((road) => roadPaths(road, bbox).map((points, index) => <g key={`${road.id}-${index}`}>
      {(showRoads || selectedRoads.includes(road.id)) && <polyline className={selectedRoads.includes(road.id) ? 'road-marked' : 'road-unmarked'} points={points} />}
      {showRoads && <polyline className="road-click-target" points={points} role="button" tabIndex="0" aria-label={`${selectedRoads.includes(road.id) ? 'Desmarcar' : 'Marcar'} ${road.properties.name}`} onClick={() => onToggle(road.id)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onToggle(road.id); } }} />}
    </g>))}
  </svg>;
}
function viewportCenter(element) {
  if (!element?.scrollWidth || !element?.scrollHeight) return { x: .5, y: .5 };
  return {
    x: (element.scrollLeft + element.clientWidth / 2) / element.scrollWidth,
    y: (element.scrollTop + element.clientHeight / 2) / element.scrollHeight,
  };
}
function centerViewport(element, center) {
  if (!element) return;
  element.scrollLeft = center.x * element.scrollWidth - element.clientWidth / 2;
  element.scrollTop = center.y * element.scrollHeight - element.clientHeight / 2;
}
function useLinkedImages() {
  const [linked, setLinked] = useState(true);
  const controller = useRef(null);
  if (!controller.current) controller.current = {
    linked: true,
    viewers: new Map(),
    register(id, viewer) {
      const first = this.viewers.values().next().value;
      this.viewers.set(id, viewer);
      if (this.linked && first) viewer.applyView(first.getView());
      return () => this.viewers.delete(id);
    },
    publish(id, view) {
      if (!this.linked) return;
      for (const [otherId, viewer] of this.viewers) if (otherId !== id) viewer.applyView(view);
    },
    align() {
      const first = this.viewers.entries().next().value;
      if (first) this.publish(first[0], first[1].getView());
    },
  };
  function toggle() {
    const next = !linked;
    controller.current.linked = next;
    setLinked(next);
    if (next) controller.current.align();
  }
  return { linked, toggle, controller: controller.current };
}
function ZoomableImage({ url, alt, roads, bbox, selectedRoads = [], onToggleRoad, showRoads = false,
  onAvailability, syncController, syncId, focus = { x: .5, y: .5 }, focusLabel = 'Focar no trecho' }) {
  const [scale, setScale] = useState(1);
  const viewport = useRef(null);
  const drag = useRef(null);
  const scaleRef = useRef(scale);
  const centerRef = useRef({ x: .5, y: .5 });
  const applying = useRef(false);
  scaleRef.current = scale;
  useLayoutEffect(() => {
    const element = viewport.current;
    if (element) {
      centerViewport(element, centerRef.current);
      if (!applying.current) syncController?.publish(syncId, { scale, ...viewportCenter(element) });
      else requestAnimationFrame(() => { applying.current = false; });
    }
  }, [scale, url]);
  useEffect(() => syncController?.register(syncId, {
    getView: () => ({ scale: scaleRef.current, ...viewportCenter(viewport.current) }),
    applyView: (view) => {
      if (![1, 2, 4].includes(view.scale)) return;
      applying.current = true;
      centerRef.current = { x: view.x, y: view.y };
      if (scaleRef.current !== view.scale) setScale(view.scale);
      else {
        centerViewport(viewport.current, centerRef.current);
        requestAnimationFrame(() => { applying.current = false; });
      }
    },
  }), [syncController, syncId]);
  function changeScale(value) {
    centerRef.current = viewportCenter(viewport.current);
    setScale(value);
  }
  function focusArea() {
    centerRef.current = focus;
    if (scale === 2) {
      centerViewport(viewport.current, focus);
      syncController?.publish(syncId, { scale, ...viewportCenter(viewport.current) });
    } else setScale(2);
  }
  function startDrag(event) {
    if (scale === 1 || event.target.closest?.('.road-click-target')) return;
    const element = viewport.current;
    drag.current = { x: event.clientX, y: event.clientY, left: element.scrollLeft, top: element.scrollTop };
    element.setPointerCapture(event.pointerId);
  }
  function moveDrag(event) {
    if (!drag.current) return;
    const element = viewport.current;
    element.scrollLeft = drag.current.left - (event.clientX - drag.current.x);
    element.scrollTop = drag.current.top - (event.clientY - drag.current.y);
  }
  return <div className="image-viewer">
    <div className="image-viewer-toolbar" aria-label="Ampliação interativa"><span>Visualizar</span>{[1, 2, 4].map((value) => <button key={value} type="button" aria-pressed={scale === value} className={scale === value ? 'active' : ''} onClick={() => changeScale(value)}>{value === 1 ? 'Ajustar à tela' : `${value}×`}</button>)}<button type="button" onClick={focusArea}>{focusLabel}</button><small>{scale > 1 ? 'Arraste para explorar' : 'Amplie para examinar'}</small></div>
    <div className={`image-viewport ${scale > 1 ? 'is-zoomed' : ''}`} ref={viewport} onScroll={(event) => {
      centerRef.current = viewportCenter(event.currentTarget);
      if (!applying.current) syncController?.publish(syncId, { scale: scaleRef.current, ...centerRef.current });
    }} onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
      <div className="image-canvas" style={{ width: `${scale * 100}%` }}>
        <img src={scaledImageUrl(url, scale)} alt={alt} onLoad={() => { centerViewport(viewport.current, centerRef.current); onAvailability?.(true); }} onError={() => onAvailability?.(false)} />
        {onToggleRoad && <RoadOverlay roads={roads} bbox={bbox} selectedRoads={selectedRoads} onToggle={onToggleRoad} showRoads={showRoads} />}
      </div>
    </div>
    <MapReference bbox={bbox} viewport={viewport} scale={scale} />
  </div>;
}
function SceneCard({ scene, label, view }) {
  const optical = scene?.collection === "sentinel-2-l2a";
  return (
    <article className="scene-card">
      <div className="scene-head">
        <span>{label}</span>
        <Badge tone={scene ? "green" : "amber"}>
          {scene ? "Disponível" : "Pendente"}
        </Badge>
      </div>
      {scene ? (
        <>
          <div className="scene-img">
            <a
              href={sceneUrl(scene, view)}
              target="_blank"
              rel="noreferrer"
              title="Abrir imagem em tamanho completo"
            >
              <img
                src={sceneUrl(scene, view)}
                alt={`${optical ? "Sentinel-2 · rios Krauel e dos Índios" : "Cena"} · ${label.toLowerCase()}`}
              />
            </a>
          </div>
          <div className="scene-body">
            <strong>{date(scene.acquired_at)}</strong>
            <span>
              {scene.source === "CDSE"
                ? `Copernicus · ${optical ? "Sentinel-2 L2A" : "Sentinel-1 GRD"}`
                : "Ilustração legada · inicie uma nova demonstração"}
            </span>
            <small>{scene.provider_product_id}</small>
            <div className="scene-tags">
              <span>{scene.instrument_mode}</span>
              <span>{scene.polarization}</span>
              <span>{scene.orbit_direction}</span>
              <span>v{scene.version}</span>
            </div>
            <small>{scene.selection_reason}</small>
            {scene.local_cloud_percent != null && (
              <small>Nuvens na área: {scene.local_cloud_percent}%</small>
            )}
            <a href={sceneUrl(scene, view)} target="_blank" rel="noreferrer">
              Ampliar imagem ↗
            </a>
          </div>
        </>
      ) : (
        <div className="scene-missing">
          <Icon name="image" size={30} />
          <strong>Cena indisponível</strong>
          <span>
            A busca segue dentro da janela definida ou foi encerrada sem cena
            compatível.
          </span>
        </div>
      )}
    </article>
  );
}
function HistoricalContext({ context }) {
  return (
    <section className="historical-context" aria-labelledby="history-title">
      <span className="caps">
        OCORRÊNCIA REAL · REPLAY COM NÍVEIS SIMULADOS
      </span>
      <h2 id="history-title">{context.title}</h2>
      <p>{context.summary}</p>
      <div className="historical-timeline">
        {context.timeline.map((item) => (
          <article className={`history-step ${item.kind}`} key={item.date}>
            <span>
              {date(item.date + "T12:00:00Z", { dateStyle: "medium" })}
              {item.end
                ? ` a ${date(item.end + "T12:00:00Z", { dateStyle: "medium" })}`
                : ""}
            </span>
            <h3>{item.title}</h3>
            <p>{item.detail}</p>
          </article>
        ))}
      </div>
      <p>{context.imagery_note}</p>
      <p className="history-cloud-note">
        <Icon name="info" size={17} />
        {context.cloud_note}
      </p>
      <div className="history-sources">
        Fontes oficiais:{" "}
        {context.sources.map((source) => (
          <a
            key={source.url}
            href={source.url}
            target="_blank"
            rel="noreferrer"
          >
            {source.title} ↗
          </a>
        ))}
      </div>
    </section>
  );
}
function Detail({ id, navigate }) {
  let [data, setData] = useState(),
    [error, setError] = useState(""),
    [overlay, setOverlay] = useState(false),
    [view, setView] = useState("default"),
    [split, setSplit] = useState(50);
  useEffect(() => {
    setView("default");
    setError("");
    setData(undefined);
    let active = true;
    let load = () =>
      api(`/events/${id}`)
        .then((d) => active && setData(d))
        .catch((e) => active && setError(e.message));
    load();
    let timer = setInterval(load, 20000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [id]);
  if (error)
    return (
      <main className="container section">
        <button className="back" onClick={() => navigate("events")}>
          ← Voltar
        </button>
        <div className="error">{error}</div>
      </main>
    );
  if (!data)
    return <main className="container section">Carregando evento…</main>;
  let b = data.scenes.BASELINE,
    a = data.scenes.POST_EVENT,
    demo = data.source_mode === "DEMO",
    replay = data.mode === "SIMULACAO" && !demo,
    history = data.snapshot.historical_context;
  return (
    <main className="container section">
      <button className="back" onClick={() => navigate("events")}>
        ← Voltar aos eventos
      </button>
      <div className="detail-head">
        <div>
          <span className="caps">
            REGISTRO DE EVENTO ·{" "}
            {data.mode === "SIMULACAO" ? "SIMULAÇÃO" : "MONITORAMENTO REAL"}
          </span>
          <h1>Comparação de evidências</h1>
          <p>
            {data.station_name} · {date(data.started_at)}
          </p>
        </div>
        <Badge tone={data.status === "DISPONIVEL" ? "green" : "amber"}>
          {names[data.status] || data.status}
        </Badge>
      </div>
      <Notice demo={demo} replay={replay} />
      {history && <HistoricalContext context={history} />}
      <div className="detail-stats">
        {[
          ["COTA NO GATILHO", cm(data.trigger_level_cm)],
          ["REFERÊNCIA", cm(data.threshold_cm)],
          ["CONFIGURAÇÃO", `v${data.config_version}`],
          [
            "ENCERRAMENTO",
            data.ended_at ? date(data.ended_at) : "Em andamento",
          ],
        ].map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <div className="section-head comparison-head">
        <div>
          <span className="caps">EVIDÊNCIA VISUAL · ANTES E DEPOIS</span>
          <h2>Olhe as duas cenas</h2>
        </div>
        {b && a && (
          <div className="segmented">
            <button
              className={!overlay ? "active" : ""}
              onClick={() => setOverlay(false)}
            >
              Lado a lado
            </button>
            <button
              className={overlay ? "active" : ""}
              onClick={() => setOverlay(true)}
            >
              Sobrepor
            </button>
          </div>
        )}
      </div>
      {b?.has_natural && a?.has_natural && (
        <div className="water-controls">
          <div className="segmented" aria-label="Visualização do Sentinel-2">
            <button
              className={view === "default" ? "active" : ""}
              onClick={() => setView("default")}
            >
              Água destacada
            </button>
            <button
              className={view === "natural" ? "active" : ""}
              onClick={() => setView("natural")}
            >
              Cor natural
            </button>
          </div>
          <p>
            <span className="water-swatch" /> Azul: possível água detectada por
            NDWI/SCL, incluindo rios e lagoas. Resolução nativa de 10–20 m; pode
            omitir trechos estreitos ou classificar outros alvos. Norte ↑ ·
            recorte de cerca de 2,2 km.
          </p>
          <p>
            Imagens reais de Presidente Getúlio. Os níveis e o gatilho são
            simulados; as datas das cenas não representam uma captura do pico da
            enchente.
          </p>
        </div>
      )}
      {overlay && b && a ? (
        <div className="overlay-shell">
          <div className="overlay-img">
            <img src={sceneUrl(b, view)} alt="Cena anterior" />
            <div style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}>
              <img src={sceneUrl(a, view)} alt="Cena posterior" />
            </div>
            <i style={{ left: `${split}%` }} />
          </div>
          <label>
            Deslize para comparar
            <input
              type="range"
              min="0"
              max="100"
              value={split}
              onChange={(e) => setSplit(+e.target.value)}
              aria-label="Proporção da imagem posterior"
            />
          </label>
          <div className="graph-axis">
            <span>← Antes · {date(b.acquired_at)}</span>
            <span>Depois · {date(a.acquired_at)} →</span>
          </div>
        </div>
      ) : (
        <div className="scene-grid">
          <SceneCard
            scene={b}
            label={b?.label || "Antes do gatilho"}
            view={view}
          />
          <SceneCard
            scene={a}
            label={a?.label || "Depois do gatilho"}
            view={view}
          />
        </div>
      )}
      {data.status === "PARCIAL" && (
        <div className="notice demo">
          Comparação parcial. A ausência de uma cena não significa ausência de
          inundação. {data.failure_summary}
        </div>
      )}
      <div className="detail-grid">
        <article className="panel">
          <span className="caps">RASTREABILIDADE</span>
          <h3>De onde vêm os dados</h3>
          <dl className="facts">
            <div>
              <dt>Estação</dt>
              <dd>
                {data.station_name} ({data.station_code})
              </dd>
            </div>
            <div>
              <dt>Leitura de gatilho</dt>
              <dd>
                {date(data.trigger_reading?.observed_at)} ·{" "}
                {data.trigger_reading?.quality_status}
              </dd>
            </div>
            <div>
              <dt>Fonte da cota</dt>
              <dd>{data.snapshot.threshold_source}</dd>
            </div>
            <div>
              <dt>Área</dt>
              <dd>EPSG:4326 · {data.snapshot.bbox.join(" · ")}</dd>
            </div>
            <div>
              <dt>Modo</dt>
              <dd>
                {demo
                  ? "Simulação didática"
                  : replay
                    ? "Replay histórico da ANA"
                    : "Monitoramento real"}
              </dd>
            </div>
          </dl>
        </article>
        <article className="panel context">
          <span className="caps">LEITURA RESPONSÁVEL</span>
          <h3>O que esta comparação permite?</h3>
          <p>
            Observe diferenças visuais entre cenas da mesma área. A imagem de
            satélite depende de resolução, nuvens, órbita e processamento. Uma
            diferença visual, por si só, não confirma nem delimita uma
            inundação.
          </p>
          <div>
            <Icon name="shield" /> Uso informativo e acadêmico
          </div>
          <div>
            <Icon name="layers" /> Origem e versões preservadas
          </div>
        </article>
      </div>
    </main>
  );
}
function About() {
  return (
    <main className="container section">
      <div className="page-head">
        <span className="caps">SOBRE O PROJETO</span>
        <h1>Como o sistema funciona</h1>
        <p>
          Da leitura de uma estação ao registro visual de um evento fluvial.
        </p>
      </div>
      <div className="steps">
        {[
          [
            "01",
            "Coletar",
            "O painel coleta a série pública DCSC-00043. O administrador cadastra a cota local e sua fonte; isso não substitui um alerta oficial.",
          ],
          [
            "02",
            "Identificar",
            "Após uma leitura abaixo, duas leituras seguidas acima da referência criam um registro indicativo.",
          ],
          [
            "03",
            "Buscar",
            "Cenas Sentinel-1 anteriores (30 a 15 dias) e posteriores (até 15 dias) são procuradas no Copernicus.",
          ],
          [
            "04",
            "Comparar",
            "As imagens processadas com a mesma área e parâmetros são exibidas com datas e origem.",
          ],
        ].map(([n, title, description]) => (
          <div className="step" key={n}>
            <span>{n}</span>
            <div>
              <h3>{title}</h3>
              <p>{description}</p>
            </div>
          </div>
        ))}
      </div>
      <Notice />
      <article className="panel about-panel">
        <h3>O que significa “simulação”?</h3>
        <p>
          O modo de demonstração usa níveis e gatilho simulados com imagens
          reais do Sentinel-2, obtidas no Copernicus e salvas com datas e
          produtos de origem. É possível comparar cor natural e destaque
          espectral da água. O modo real exige credenciais e uma cota com fonte
          oficial.
        </p>
      </article>
    </main>
  );
}
function Admin({ open }) {
  const [token, setToken] = useState(sessionStorage.getItem("pin2_token")),
    [password, setPassword] = useState(""),
    [tab, setTab] = useState("overview"),
    [help, setHelp] = useState(null),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const { live: stationLive } = useLiveStation();
  const [model, setModel] = useState({
    configs: [],
    events: [],
    jobs: [],
    audit: [],
    integrations: {},
  });
  const [sourceMode, setSourceMode] = useState('DCSC');
  const [form, setForm] = useState({
    station_code: "DCSC-00043",
    river: "Rio dos Índios",
    bbox: "",
    threshold_cm: "",
    threshold_kind: "",
    threshold_source: "",
    threshold_valid_from: new Date().toISOString().slice(0, 10),
    threshold_responsible: "",
    collection_interval_min: 5,
    baseline_min_days: 15,
    baseline_max_days: 30,
    post_window_days: 15,
  });
  const refresh = () =>
    Promise.all(
      [
        "/admin/configs",
        "/admin/events",
        "/admin/jobs",
        "/admin/audit",
        "/admin/integrations",
      ].map((path) => api(path)),
    )
      .then(([configs, events, jobs, audit, integrations]) =>
        setModel({ configs, events, jobs, audit, integrations }),
      )
      .catch((e) => {
        if (/Sessão|Autenticação|Credenciais/.test(e.message)) {
          sessionStorage.removeItem("pin2_token");
          setToken(null);
        }
        setMessage(`Erro: ${e.message}`);
      });
  useEffect(() => {
    if (!token) return;
    refresh();
    const timer = setInterval(refresh, 15000);
    return () => clearInterval(timer);
  }, [token]);
  async function perform(fn) {
    setBusy(true);
    setMessage("");
    try {
      setMessage(await fn());
      if (sessionStorage.getItem("pin2_token")) await refresh();
    } catch (e) {
      setMessage(`Erro: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }
  function login(e) {
    e.preventDefault();
    perform(async () => {
      let result = await api("/auth/admin", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      sessionStorage.setItem("pin2_token", result.token);
      setToken(result.token);
      setPassword("");
      return `Bem-vindo, ${result.user.display_name}.`;
    });
  }
  function inspect() {
    perform(async () => {
      let r = await api(`/admin/station/${form.station_code}`);
      if (!r.station) throw Error("Estação não encontrada");
      let lat = +r.station.Latitude,
        lon = +r.station.Longitude;
      if (!Number.isFinite(lat) || !Number.isFinite(lon))
        throw Error("Coordenadas ausentes");
      let dx = 2.5 / (111.32 * Math.cos((lat * Math.PI) / 180)),
        dy = 2.5 / 111.32;
      setForm({
        ...form,
        bbox: [lon - dx, lat - dy, lon + dx, lat + dy]
          .map((v) => v.toFixed(5))
          .join(", "),
      });
      return `${r.station.Estacao_Nome}: ${r.recent_readings} leituras recentes; ${r.has_level ? "cota disponível" : "sem cota recente"}. Área preenchida.`;
    });
  }
  function activate() {
    perform(async () => {
      if (!form.threshold_kind || !form.threshold_cm || !form.threshold_source.trim() || !form.threshold_responsible.trim())
        throw Error('Informe categoria, valor, documento de origem e responsável pela cota local');
      let bbox = sourceMode === 'DCSC' ? [-49.632, -27.048, -49.610, -27.0285] : form.bbox.split(",").map(Number);
      if (bbox.length !== 4 || bbox.some((v) => !Number.isFinite(v)))
        throw Error("Informe oeste, sul, leste, norte");
      let payload = {
        ...form,
        bbox,
        threshold_cm: +form.threshold_cm,
        collection_interval_min: +form.collection_interval_min,
        baseline_min_days: +form.baseline_min_days,
        baseline_max_days: +form.baseline_max_days,
        post_window_days: +form.post_window_days,
        threshold_valid_from: new Date(
          `${form.threshold_valid_from}T00:00:00-03:00`,
        ).toISOString(),
        station_code: sourceMode === 'DCSC' ? 'DCSC-00043' : form.station_code,
        river: sourceMode === 'DCSC' ? 'Rio dos Índios' : form.river,
        source_mode: sourceMode,
      };
      let r = await api("/admin/configs", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      return `Configuração v${r.version} ativada.`;
    });
  }
  if (!token)
    return (
      <main className="container login-layout">
        <div>
          <span className="caps">ÁREA RESTRITA</span>
          <h1>Administração do piloto</h1>
          <p>
            Configure a estação, acompanhe o processamento e execute
            demonstrações com origem identificada.
          </p>
          <div className="login-art">
            <Icon name="shield" size={36} /> Acesso autorizado apenas para a
            equipe do projeto.
          </div>
        </div>
        <form className="login-card" onSubmit={login}>
          <div className="login-icon">
            <Icon name="lock" />
          </div>
          <h2>Entrar</h2>
          <p className="login-hint">
            Informe sua senha individual para acessar a administração.
          </p>
          <label>
            Senha
            <input
              type="password"
              required
              autoFocus
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <button className="btn primary full" disabled={busy}>
            Acessar painel <Icon name="arrow" size={18} />
          </button>
          {message && (
            <p
              role={message.startsWith("Erro:") ? "alert" : "status"}
              className={`form-msg ${message.startsWith("Erro:") ? "error" : ""}`}
            >
              {message}
            </p>
          )}
        </form>
      </main>
    );
  const current = model.configs.find((c) => c.active);
  const lastCollection = model.jobs.find((j) => j.kind === "COLLECT");
  const jobsById = Object.fromEntries(model.jobs.map((j) => [j.id, j]));
  const helpText = {
    overview: "Confira a configuração ativa, as integrações e os eventos registrados. Coletar agora consulta a estação; um evento real só aparece se as leituras cruzarem a referência configurada.",
    config: "Escolha a fonte da estação. Cadastre o tipo e o valor da cota local em centímetros, o documento que a sustenta, o responsável e a validade; depois clique em Validar e ativar. A COBRADE classifica desastres, mas não fornece cotas para esta estação.",
    jobs: "Cada linha mostra quando o trabalho entrou na fila, a última tentativa e o resultado. A coleta busca leituras; eventos dependem de cruzamento da referência. Erros e próximas tentativas aparecem aqui.",
    audit: "Registra quem solicitou uma coleta, alterou uma configuração ou iniciou uma demonstração, com data e detalhes para consulta.",
  };
  const fields = [
    ["station_code", "Código ANA"],
    ["river", "Rio"],
    ["bbox", "Área [oeste, sul, leste, norte]"],
    ["threshold_cm", "Valor da cota local (cm)"],
    ["threshold_valid_from", "Válida desde"],
    ["threshold_source", "Documento ou estudo que definiu a cota"],
    ["threshold_responsible", "Responsável pelo cadastro"],
    ["collection_interval_min", "Coleta (minutos)"],
    ["baseline_min_days", "Referência: mínimo de dias antes"],
    ["baseline_max_days", "Referência: máximo de dias antes"],
    ["post_window_days", "Janela posterior (dias)"],
  ];
  const dcscFields = [
    ["threshold_cm", "Valor da cota local (cm)"],
    ["threshold_source", "Documento ou estudo que definiu a cota"],
    ["threshold_responsible", "Responsável pelo cadastro"],
    ["threshold_valid_from", "Válida desde"],
    ["collection_interval_min", "Coleta (minutos)"],
    ["baseline_min_days", "Referência: mínimo de dias antes"],
    ["baseline_max_days", "Referência: máximo de dias antes"],
    ["post_window_days", "Janela posterior (dias)"],
  ];
  return (
    <main className="container section">
      <div className="admin-head">
        <div>
          <span className="caps">GESTÃO DO PROJETO</span>
          <div className="admin-title-row"><h1>Painel administrativo</h1><button type="button" className="admin-info-button" title="Como configurar uma situação completa" aria-label="Como configurar uma situação completa" aria-expanded={help === "setup"} onClick={() => setHelp(help === "setup" ? null : "setup")}><Icon name="info" size={19} /></button></div>
        </div>
        <button
          className="btn outline"
          onClick={() => {
            sessionStorage.removeItem("pin2_token");
            setToken(null);
          }}
        >
          Sair da conta
        </button>
      </div>
      <div className="tabs admin-tabs">
        {[
          ["overview", "Visão geral"],
          ["config", "Configuração"],
          ["jobs", "Processamento"],
          ["audit", "Auditoria"],
        ].map(([key, label]) => <div className="admin-tab-item" key={key}>
          <button className={tab === key ? "selected" : ""} onClick={() => { setTab(key); setHelp(null); }}>{label}</button>
          <button type="button" className="admin-tab-info" title={`Sobre ${label}`} aria-label={`Sobre ${label}`} aria-expanded={help === key} onClick={() => { setTab(key); setHelp(help === key ? null : key); }}><Icon name="info" size={16} /></button>
        </div>)}
      </div>
      {help && <div className="admin-help-panel" role="note">
        {help === "setup" ? <><strong>Configurar uma situação completa</strong><ol>
          <li>Em Configuração, escolha a estação, o tipo de cota local, seu valor, a fonte, o responsável e a validade. Ative a configuração.</li>
          <li>Na Visão geral, clique em Coletar agora. Confira data, leitura e resultado na aba Processamento.</li>
          <li>Um evento indicativo nasce após uma leitura abaixo e duas leituras seguidas acima da referência em até 30 minutos. Se o rio estiver abaixo, nenhum evento será criado.</li>
          <li>Quando houver evento, acompanhe imagens e tentativas em Processamento; consulte a ação em Auditoria.</li>
        </ol></> : <><strong>{({ overview: "Visão geral", config: "Configuração", jobs: "Processamento", audit: "Auditoria" })[help]}</strong><p>{helpText[help]}</p></>}
      </div>}
      {message && (
        <div
          className={`form-msg ${message.startsWith("Erro") ? "error" : ""}`}
          role={message.startsWith("Erro") ? "alert" : "status"}
        >
          {message}
        </div>
      )}
      {tab === "overview" && (
        <>
          <div className="admin-grid">
            <article className="panel">
              <span className="caps">CONFIGURAÇÃO ATIVA</span>
              <h3>{current?.station_name || "Nenhuma estação ativa"}</h3>
              <p>
                {current
                  ? `${current.station_code} · ${referenceName(current.threshold_kind)}: ${cm(current.threshold_cm)} · versão ${current.version}`
                  : "Ative uma configuração real ou a demonstração."}
              </p>
              <Badge tone={current?.source_mode === "DEMO" || current?.trigger_enabled === false ? "amber" : "green"}>
                {current?.trigger_enabled === false ? 'Cota pendente' : current?.source_mode === "DEMO"
                  ? "Simulação"
                  : current
                    ? current.source_mode
                    : "Inativa"}
              </Badge>
            </article>
            <article className="panel">
              <span className="caps">INTEGRAÇÕES</span>
              <h3>Disponibilidade</h3>
              <p>
                Defesa Civil DCSC: {model.integrations.dcsc_configured ? "acesso configurado" : "sem acesso"}
                <br />
                ANA:{" "}
                {model.integrations.ana_configured
                  ? "configurada"
                  : "sem credenciais"}
                <br />
                Copernicus:{" "}
                {model.integrations.cdse_configured
                  ? "configurado"
                  : "sem credenciais"}
                <br />
                Última verificação das imagens: {date(model.integrations.satellite_checked_at)}
                <br />
                Imagens: {model.integrations.object_storage || "—"}
              </p>
            </article>
          </div>
          <div className="panel demo-box">
            <div>
              <span className="caps">DEMONSTRAÇÃO REPRODUZÍVEL</span>
              <h3>Enchentes de novembro de 2023</h3>
              <p>
                Simula o episódio documentado de 16 e 17/11/2023, com cenas
                reais de 05/11 e 15/12. Os níveis são fictícios e as imagens
                mostram referências de antes e depois, fora do pico da enchente.
              </p>
            </div>
            <button
              className="btn primary"
              disabled={busy}
              onClick={() =>
                perform(async () => {
                  await api("/admin/demo", { method: "POST" });
                  return "Demonstração iniciada. Aguarde o processamento das imagens.";
                })
              }
            >
              Iniciar demonstração <Icon name="arrow" size={17} />
            </button>
          </div>
          <div className="section-head">
            <div>
              <span className="caps">ACOMPANHAMENTO</span>
              <h2>Eventos registrados</h2>
            </div>
            <button className="text-link" onClick={refresh}>
              <Icon name="refresh" size={17} /> Atualizar
            </button>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Instante</th>
                  <th>Modo</th>
                  <th>Cota</th>
                  <th>Estado</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {model.events.map((e) => (
                  <tr key={e.id}>
                    <td>{date(e.started_at)}</td>
                    <td>{e.mode === "SIMULACAO" ? "Simulação" : "Ao vivo"}</td>
                    <td>{cm(e.trigger_level_cm)}</td>
                    <td>{names[e.status] || e.status}</td>
                    <td>
                      <button className="table-link" onClick={() => open(e.id)}>
                        Abrir
                      </button>{" "}
                      ·{" "}
                      <button
                        className="table-link"
                        disabled={busy}
                        onClick={() =>
                          perform(async () => {
                            let r = await api(
                              `/admin/events/${e.id}/reprocess`,
                              { method: "POST" },
                            );
                            return `Tentativa v${r.version} criada.`;
                          })
                        }
                      >
                        Reprocessar
                      </button>
                    </td>
                  </tr>
                ))}
                {!model.events.length && (
                  <tr>
                    <td colSpan="5">
                      Nenhum evento. Inicie a demonstração ou configure a
                      coleta.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {current?.source_mode === "DEMO" && (
            <button
              className="btn outline top-gap"
              disabled={busy}
              onClick={() =>
                perform(async () => {
                  let r = await api("/admin/replay", {
                    method: "POST",
                    body: "{}",
                  });
                  return `${r.inserted} leituras simuladas registradas.`;
                })
              }
            >
              Repetir cenário histórico
            </button>
          )}
          {['ANA', 'DCSC'].includes(current?.source_mode) && (
            <>
              <button
                className="btn outline top-gap"
                disabled={busy}
                onClick={() =>
                  perform(async () => {
                    const result = await api("/admin/collect", { method: "POST" });
                    setTab("jobs");
                    setHelp(null);
                    return result.already_running
                      ? "Já existe uma coleta em execução. Acompanhe o resultado nesta aba."
                      : "Coleta agendada. O resultado aparecerá nesta aba após a execução.";
                  })
                }
              >
                Coletar agora
              </button>
              <p className="collection-explainer">Coletar consulta a estação; o evento depende do cruzamento da referência. {current.trigger_enabled === false ? 'Novos gatilhos estão suspensos: substitua o valor anterior de exemplo por uma cota local documentada em Configuração.' : current.source_mode === "DCSC" && stationLive?.latest?.water_level_cm != null && <>Leitura publicada: <strong>{cm(stationLive.latest.water_level_cm)}</strong>; referência configurada: <strong>{cm(current.threshold_cm)}</strong>.</>}</p>
              {lastCollection && <div className="collection-status" role="status"><strong>Última coleta</strong><span>{lastCollection.last_attempt_at ? date(lastCollection.last_attempt_at) : "Aguardando primeira execução"}</span><Badge tone={lastCollection.last_attempt_status === "SUCESSO" ? "green" : "amber"}>{lastCollection.last_attempt_status === "SUCESSO" ? "Executada" : lastCollection.last_error ? "Erro" : "Na fila"}</Badge>{lastCollection.last_result && <small>{lastCollection.last_result.inserted} novas leituras · {lastCollection.last_result.events_created?.length || 0} eventos criados</small>}{lastCollection.last_error && <small className="collection-error">{lastCollection.last_error}</small>}</div>}
              {current?.source_mode === "ANA" && <>
              <div className="replay-field">
                <label>
                  Data histórica da ANA
                  <input type="date" id="replay-date" />
                </label>
                <button
                  className="btn outline"
                  disabled={busy}
                  onClick={() =>
                    perform(async () => {
                      let d = document.getElementById("replay-date").value;
                      if (!d) throw Error("Informe a data");
                      let r = await api("/admin/replay", {
                        method: "POST",
                        body: JSON.stringify({
                          date: new Date(`${d}T12:00:00-03:00`).toISOString(),
                        }),
                      });
                      return `${r.inserted} leituras históricas registradas.`;
                    })
                  }
                >
                  Executar replay
                </button>
              </div>
              </>}
            </>
          )}
        </>
      )}
      {tab === "config" && (
        <div className="form-layout">
          <article className="panel">
            <span className="caps">COLETA AO VIVO</span>
            <h3>Ativar nova configuração</h3>
            <label className="source-choice">Fonte de leitura<select value={sourceMode} onChange={(e) => {const mode=e.target.value;setSourceMode(mode);setForm({...form,station_code:mode==='DCSC'?'DCSC-00043':'83372100',river:mode==='DCSC'?'Rio dos Índios':'Rio Krauel',bbox:'',threshold_cm:'',threshold_kind:'',threshold_source:'',threshold_responsible:''});}}><option value="DCSC">Defesa Civil DCSC-00043</option><option value="ANA">ANA (requer credenciais)</option></select></label>
            <p className="admin-source-note">{sourceMode === 'DCSC' ? 'Cadastre uma cota definida para a estação DCSC-00043 por sua equipe. O sistema cria apenas registros indicativos após o cruzamento da cota; não emite alerta oficial.' : 'ANA exige credenciais, estação fluviométrica operante, leitura recente e cota local documentada.'} A <a href="https://www.gov.br/mdr/pt-br/centrais-de-conteudo/publicacoes/protecao-e-defesa-civil-sedec/DOCU_cobrade2.pdf" target="_blank" rel="noreferrer">COBRADE</a> classifica inundações, enxurradas e alagamentos; não define centímetros para a estação.</p>
            <label className="source-choice">Tipo da referência local<select value={form.threshold_kind} onChange={(e) => setForm({...form, threshold_kind:e.target.value})} required><option value="">Selecione o tipo</option>{['ATENCAO','ALERTA','TRANSBORDAMENTO','EMERGENCIA','OUTRA'].map((kind) => <option key={kind} value={kind}>{referenceName(kind)}</option>)}</select></label>
            <div className="form-grid">
              {(sourceMode === 'DCSC' ? dcscFields : fields).map(([key, label]) => (
                <label
                  key={key}
                  className={
                    ["bbox", "threshold_source"].includes(key) ? "wide" : ""
                  }
                >
                  {label}
                  <input
                    type={
                      key === "threshold_valid_from"
                        ? "date"
                        : [
                              "threshold_cm",
                              "collection_interval_min",
                              "baseline_min_days",
                              "baseline_max_days",
                              "post_window_days",
                            ].includes(key)
                          ? "number"
                          : "text"
                    }
                    step={key === "threshold_cm" ? "0.01" : undefined}
                    min={key === "threshold_cm" ? "0.01" : undefined}
                    placeholder={key === 'threshold_source' ? 'Plano, levantamento de campo ou estudo hidrológico' : key === 'threshold_responsible' ? 'Nome e função' : undefined}
                    value={form[key]}
                    onChange={(e) =>
                      setForm({ ...form, [key]: e.target.value })
                    }
                  />
                </label>
              ))}
            </div>
            <div className="form-actions">
              {sourceMode === 'ANA' && <button
                className="btn outline"
                disabled={busy || !model.integrations.ana_configured}
                onClick={inspect}
              >
                Consultar estação e preencher área
              </button>}
              <button
                className="btn primary"
                disabled={busy || !(sourceMode === 'DCSC' ? model.integrations.dcsc_configured : model.integrations.ana_configured)}
                onClick={activate}
              >
                Validar e ativar <Icon name="arrow" size={18} />
              </button>
            </div>
            {sourceMode === 'ANA' && !model.integrations.ana_configured && (
              <p className="hint">
                ANA_IDENTIFICADOR e ANA_SENHA estão vazios. Selecione Defesa Civil DCSC-00043 para ativar a coleta sem ANA.
              </p>
            )}
          </article>
          <article className="panel">
            <span className="caps">HISTÓRICO</span>
            <h3>Configurações</h3>
            <div className="version-list">
              {model.configs.map((c) => (
                <div key={c.id}>
                  <div>
                    <strong>
                      v{c.version} · {c.station_code}
                    </strong>
                    <Badge tone={c.active && c.trigger_enabled === false ? "amber" : c.active ? "green" : "neutral"}>
                      {c.active && c.trigger_enabled === false ? "Coleta ativa · gatilho suspenso" : c.active ? "Ativa" : "Encerrada"}
                    </Badge>
                  </div>
                  <small>
                    {date(c.valid_from)} · {c.source_mode}
                  </small>
                  <p>
                    {referenceName(c.threshold_kind)} · {cm(c.threshold_cm)} · {c.threshold_source}
                  </p>
                </div>
              ))}
              {!model.configs.length && <p>Nenhuma versão criada.</p>}
            </div>
          </article>
        </div>
      )}
      {tab === "jobs" && (
        <>
          <div className="section-head">
            <div>
              <span className="caps">FILA PERSISTENTE</span>
              <h2>Jobs recentes</h2>
            </div>
            <button className="text-link" onClick={refresh}>
              <Icon name="refresh" size={17} /> Atualizar
            </button>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Operação</th>
                  <th>Estado</th>
                  <th>Criado em</th>
                  <th>Última execução</th>
                  <th>Tentativas</th>
                  <th>Resultado / próxima coleta</th>
                </tr>
              </thead>
              <tbody>
                {model.jobs.map((j) => (
                  <tr key={j.id}>
                    <td>{({ COLLECT: "Coleta de leituras", BASELINE: "Imagem anterior", POST_EVENT: "Imagem posterior" })[j.kind] || j.kind}<small className="job-version">v{j.version}</small></td>
                    <td>{j.kind === "COLLECT" && j.status === "PENDENTE" && j.last_attempt_status === "SUCESSO" ? "Próxima coleta agendada" : names[j.status] || j.status}</td>
                    <td>{date(j.created_at)}</td>
                    <td>{date(j.last_attempt_at)}</td>
                    <td>{j.attempts}</td>
                    <td>{j.last_error ? <span className="job-error">Erro: {j.last_error}</span> : j.last_result ? <span>{j.last_result.inserted} leituras novas · {j.last_result.events_created?.length || 0} eventos criados{j.last_result.latest_level_cm != null && <> · nível {cm(j.last_result.latest_level_cm)}</>}</span> : j.status === "CONCLUIDO" ? "Concluído" : "Aguardando execução"}{["PENDENTE", "AGUARDANDO_RETRY"].includes(j.status) && <small className="job-next">Próxima execução: {date(j.scheduled_for)}</small>}</td>
                  </tr>
                ))}
                {!model.jobs.length && (
                  <tr>
                    <td colSpan="6">Nenhum job criado.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
      {tab === "audit" && (
        <>
          <div className="section-head">
            <div>
              <span className="caps">HISTÓRICO</span>
              <h2>Alterações e solicitações</h2>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Quando</th>
                  <th>Job criado em</th>
                  <th>Responsável</th>
                  <th>Ação</th>
                  <th>Detalhes</th>
                </tr>
              </thead>
              <tbody>
                {model.audit.map((a, i) => (
                  <tr key={i}>
                    <td>{date(a.created_at)}</td>
                    <td>{a.details?.job_id ? date(jobsById[a.details.job_id]?.created_at) : "—"}</td>
                    <td>{a.actor}</td>
                    <td>{a.action.replaceAll("_", " ")}</td>
                    <td>
                      <code>{JSON.stringify(a.details)}</code>
                    </td>
                  </tr>
                ))}
                {!model.audit.length && (
                  <tr>
                    <td colSpan="5">Sem registros.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </main>
  );
}
function useRecentSatellite() {
  const [pair, setPair] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const load = () => api("/satellite/latest")
      .then((value) => { if (active) { setPair(value); setError(""); } })
      .catch((e) => { if (active) setError(e.message); });
    load();
    const timer = setInterval(load, 300000);
    return () => { active = false; clearInterval(timer); };
  }, []);
  return { pair, error };
}

function RecentCompare({ pair, error }) {
  const [view, setView] = useState("default");
  const [overlay, setOverlay] = useState(false);
  const [split, setSplit] = useState(50);
  const [overlayScale, setOverlayScale] = useState(1);
  const overlayViewport = useRef(null);
  const overlayDrag = useRef(null);
  const linkedImages = useLinkedImages();
  useEffect(() => {
    const element = overlayViewport.current;
    if (element) {
      element.scrollLeft = (element.scrollWidth - element.clientWidth) / 2;
      element.scrollTop = (element.scrollHeight - element.clientHeight) / 2;
    }
  }, [overlayScale, overlay, view]);
  const scenes = pair?.scenes || [];
  return (
    <section className="latest-section" id="imagens">
      <div className="landing-section-head">
        <div>
          <span className="caps">MONITORAMENTO REAL · COPERNICUS SENTINEL-2</span>
          <h2>Imagens recentes utilizáveis</h2>
          <p>Mesmo recorte dos rios Krauel e dos Índios. Duas passagens com pouca nebulosidade para comparar a paisagem.</p>
        </div>
        {scenes.length === 2 && <div className="latest-controls">
          <div className="segmented" aria-label="Visualização das imagens">
            <button className={view === "default" ? "active" : ""} onClick={() => setView("default")}>Água destacada</button>
            <button className={view === "natural" ? "active" : ""} onClick={() => setView("natural")}>Cor natural</button>
          </div>
          <div className="segmented" aria-label="Modo de comparação">
            <button className={!overlay ? "active" : ""} onClick={() => setOverlay(false)}>Lado a lado</button>
            <button className={overlay ? "active" : ""} onClick={() => { setOverlay(true); setOverlayScale(1); }}>Sobrepor</button>
          </div>
        </div>}
      </div>
      {error ? <p className="error" role="alert">{error}</p> : !pair ? <p className="data-message">Consultando as imagens…</p>
        : !pair.available ? <p className="data-message">{pair.reason}</p>
        : <>
          {!overlay && <label className="compare-lock"><input type="checkbox" checked={linkedImages.linked} onChange={linkedImages.toggle} /> Sincronizar zoom e posição <span>{linkedImages.linked ? 'As duas datas acompanham o arrasto' : 'Cada data pode ser movida separadamente'}</span></label>}
          {overlay ? <div className="latest-overlay">
            <div className="image-viewer-toolbar" aria-label="Ampliação da sobreposição"><span>Visualizar</span>{[1, 2, 4].map((value) => <button key={value} type="button" aria-pressed={overlayScale === value} className={overlayScale === value ? 'active' : ''} onClick={() => setOverlayScale(value)}>{value === 1 ? 'Ajustar à tela' : `${value}×`}</button>)}</div>
            <div className={`latest-overlay-viewport ${overlayScale > 1 ? 'is-zoomed' : ''}`} ref={overlayViewport}
              onPointerDown={(event) => { if (overlayScale === 1) return; const el = overlayViewport.current; overlayDrag.current = { x: event.clientX, y: event.clientY, left: el.scrollLeft, top: el.scrollTop }; el.setPointerCapture(event.pointerId); }}
              onPointerMove={(event) => { if (!overlayDrag.current) return; const el = overlayViewport.current; el.scrollLeft = overlayDrag.current.left - (event.clientX - overlayDrag.current.x); el.scrollTop = overlayDrag.current.top - (event.clientY - overlayDrag.current.y); }}
              onPointerUp={() => { overlayDrag.current = null; }} onPointerCancel={() => { overlayDrag.current = null; }}>
              <div className="latest-overlay-images" style={{ width: `${overlayScale * 100}%` }}>
                <img src={scaledImageUrl(scenes[0].images[view], overlayScale)} alt={`Rio dos Índios em ${date(scenes[0].acquired_at, { dateStyle: "medium" })}`} />
                <div style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}><img src={scaledImageUrl(scenes[1].images[view], overlayScale)} alt={`Rio dos Índios em ${date(scenes[1].acquired_at, { dateStyle: "medium" })}`} /></div>
                <i style={{ left: `${split}%` }} />
              </div>
            </div>
            <label>Deslize para comparar as datas<input type="range" min="0" max="100" value={split} onChange={(e) => setSplit(+e.target.value)} /></label>
            <MapReference bbox={pair.bbox} viewport={overlayViewport} scale={overlayScale} />
          </div> : <div className="latest-pair">
            {scenes.map((scene, index) => <figure key={scene.product_id}>
              <ZoomableImage url={scene.images[view]} bbox={pair.bbox} alt={`Rio dos Índios na passagem de ${date(scene.acquired_at, { dateStyle: "medium" })}`} syncController={linkedImages.controller} syncId={scene.product_id} focus={imageFocus(pair.bbox, -49.6215927, -27.0372597)} focusLabel="Focar no rio" />
              <figcaption><strong>{index === 0 ? "Passagem anterior" : "Passagem mais recente utilizável"}</strong><span>{date(scene.acquired_at, { dateStyle: "medium" })} · {scene.river_obscured_percent == null ? `${scene.cloud_percent}% encoberto no recorte` : `${scene.river_obscured_percent}% encoberto no rio`}</span><DownloadLinks url={scene.images[view]} name={`rio-dos-indios-${scene.acquired_at.slice(0,10)}`} /></figcaption>
            </figure>)}
          </div>}
          <div className="latest-notes">
            <p>{pair.latest_pass ? `Última passagem catalogada: ${date(pair.latest_pass.acquired_at, { dateStyle: "medium" })} (${pair.latest_pass.tile_cloud_percent}% de nuvens no tile).` : ""} A comparação usa as últimas passagens com até 10% de pixels encobertos ou inválidos no recorte.{pair.rejected && <> <a className="rejected-link" href={pair.rejected.image_url} target="_blank" rel="noreferrer">Ver imagem encoberta de {date(pair.rejected.acquired_at, { dateStyle: "medium" })} ({pair.rejected.obscured_percent}% do recorte) ↗</a></>}</p>
            <p>O destaque azul combina análise espectral do Sentinel-2 com a referência GIS dos rios de <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors (ODbL)</a>. Indica possível água, não comprova inundação. Resolução nativa de 10–20 m. Catálogo consultado em {date(pair.checked_at)}.</p>
            <p><a href="/api/gis/rivers" download="rios-area-piloto.geojson">Baixar traçado GIS dos rios (GeoJSON)</a></p>
          </div>
          <p className="upscale-note">Amplie na própria página para examinar o recorte. 2× e 4× interpolam pixels, sem acrescentar detalhes medidos pelo satélite.</p>
        </>}
    </section>
  );
}

function PeriodSearch() {
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [lat, setLat] = useState('');
  const [lon, setLon] = useState('');
  const [results, setResults] = useState(null);
  const [selected, setSelected] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [searchError, setSearchError] = useState(false);
  const [view, setView] = useState('default');
  const [searchedCoords, setSearchedCoords] = useState('');
  const [area, setArea] = useState(null);
  const [areaLoading, setAreaLoading] = useState(false);
  const [areaError, setAreaError] = useState('');
  const searchRequest = useRef(0);
  const linkedImages = useLinkedImages();
  async function submit(event) {
    event.preventDefault();
    const request = ++searchRequest.current;
    setLoading(true); setMessage(''); setSearchError(false); setResults(null); setSelected([]); setArea(null); setAreaError('');
    try {
      const coords = lat !== '' || lon !== '' ? `&lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}` : '';
      const data = await api(`/satellite/search?start=${start}&end=${end}${coords}`);
      if (request !== searchRequest.current) return;
      setResults(data);
      setSearchedCoords(coords);
      if (!data.scenes.length) setMessage('Nenhuma passagem encontrada neste período ou até 15 dias ao redor.');
      setAreaLoading(true);
      api(`/gis/area${coords ? `?${coords.slice(1)}` : ''}`)
        .then((value) => { if (request === searchRequest.current) setArea(value); })
        .catch((error) => { if (request === searchRequest.current) setAreaError(error.message); })
        .finally(() => { if (request === searchRequest.current) setAreaLoading(false); });
    } catch (error) { setMessage(error.message); setSearchError(true); }
    finally { setLoading(false); }
  }
  function toggle(scene) {
    setSelected((current) => current.some((item) => item.product_id === scene.product_id)
      ? current.filter((item) => item.product_id !== scene.product_id)
      : [...current.slice(-1), scene]);
  }
  const locationQuery = searchedCoords;
  return <section className="period-search" aria-labelledby="period-title">
    <div className="landing-section-head"><div><span className="caps">ACERVO COPERNICUS</span><h2 id="period-title">Comparar datas e coordenadas</h2><p>Informe um período de até 60 dias e selecione duas passagens. As coordenadas são opcionais; vazias, usam a área piloto da estação.</p></div></div>
    <form className="period-form" onSubmit={submit}>
      <label>De<input type="date" value={start} max={new Date().toISOString().slice(0,10)} required onChange={(e) => setStart(e.target.value)} /></label>
      <label>Até<input type="date" value={end} max={new Date().toISOString().slice(0,10)} required onChange={(e) => setEnd(e.target.value)} /></label>
      <label>Latitude<input type="number" step="any" min="-56" max="83" value={lat} placeholder="-27.038" onChange={(e) => setLat(e.target.value)} /></label>
      <label>Longitude<input type="number" step="any" min="-179.98" max="179.98" value={lon} placeholder="-49.621" onChange={(e) => setLon(e.target.value)} /></label>
      <button className="btn primary" disabled={loading}>{loading ? 'Consultando…' : 'Buscar passagens'}</button>
    </form>
    {message && <p className={searchError ? 'image-error' : 'data-message'} role={searchError ? 'alert' : 'status'}>{message}</p>}
    {results && <><p className="search-note">{results.scenes.length} datas encontradas. Selecione duas. Centro do recorte: {((results.bbox[1] + results.bbox[3]) / 2).toFixed(5)}, {((results.bbox[0] + results.bbox[2]) / 2).toFixed(5)}. A porcentagem de nuvens abaixo é do tile inteiro; cada imagem é verificada no recorte antes de abrir.</p>
      <div className="search-results">{results.scenes.map((scene) => <button type="button" key={scene.product_id} aria-pressed={selected.some((item) => item.product_id === scene.product_id)} className={selected.some((item) => item.product_id === scene.product_id) ? 'selected' : ''} onClick={() => toggle(scene)}>
        <strong>{date(scene.acquired_at, {dateStyle:'medium'})}</strong><span>{scene.in_period ? 'No período' : `${scene.distance_days} dia(s) do período`}</span><small>{scene.tile_cloud_percent == null ? 'Nuvens não informadas' : `${scene.tile_cloud_percent}% nuvens no tile`}</small><small>{scene.footprint_coverage_percent == null ? 'Cobertura a verificar' : `${scene.footprint_coverage_percent}% do recorte coberto pelo produto`}</small>
      </button>)}</div>
      {selected.length > 0 && <><div className="segmented search-view" aria-label="Visualização das imagens"><button className={view === 'default' ? 'active' : ''} onClick={() => setView('default')}>Água destacada</button><button className={view === 'natural' ? 'active' : ''} onClick={() => setView('natural')}>Cor natural</button></div>
        {areaLoading && <p className="search-note" role="status">Consultando rios e ruas no GIS desta localização…</p>}
        {areaError && <p className="gis-warning" role="status">Ruas do OpenStreetMap indisponíveis agora: {areaError}. Você ainda pode anotar uma rua manualmente.</p>}
        {area?.status && area.status !== 'available' && <p className="gis-warning" role="status">{area.message || 'Cartografia indisponível para este recorte.'} Você ainda pode anotar uma rua manualmente.</p>}
        {selected.length === 2 && <label className="compare-lock"><input type="checkbox" checked={linkedImages.linked} onChange={linkedImages.toggle} /> Sincronizar zoom e posição <span>{linkedImages.linked ? 'As duas datas acompanham o arrasto' : 'Cada data pode ser movida separadamente'}</span></label>}
        <div className="search-comparison">{[...selected].sort((a, b) => a.acquired_at.localeCompare(b.acquired_at)).map((scene) => <SearchImage key={`${scene.product_id}-${view}-${results.bbox.join(',')}`} scene={scene} view={view} locationQuery={locationQuery} bbox={results.bbox} area={area} syncController={linkedImages.controller} />)}</div><p className="upscale-note">Amplie e anote as ruas no próprio painel; baixe o PNG só quando precisar. Quando a cartografia está disponível, o destaque de água combina a análise espectral com a referência GIS desta localização. Dados cartográficos: <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors (ODbL)</a>. A comparação visual não comprova inundação.</p></>}
    </>}
  </section>;
}

function readImpactDraft(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || '[]');
    return Array.isArray(value) ? value.filter((item) => item && typeof item.id === 'string' && typeof item.name === 'string') : [];
  } catch { return []; }
}
function downloadImpactCsv(items, scene, bbox) {
  const escapeCell = (value, numeric = false) => `"${(numeric ? String(value ?? '') : String(value ?? '').replace(/^[=+@-]/, "'$&")).replace(/"/g, '""')}"`;
  const rows = [['data_da_imagem', 'produto_copernicus', 'latitude', 'longitude', 'rua_ou_trecho', 'id_osm', 'origem', 'situacao'],
    ...items.map((item) => [scene.acquired_at.slice(0, 10), scene.product_id,
      ((bbox[1] + bbox[3]) / 2).toFixed(6), ((bbox[0] + bbox[2]) / 2).toFixed(6),
      item.name, item.source === 'OpenStreetMap' ? item.id : '', item.source, 'Impacto informado manualmente; requer verificação em campo'])];
  const blob = new Blob(['\uFEFF', rows.map((row) => row.map((value, index) => escapeCell(value, index === 2 || index === 3)).join(';')).join('\r\n')], { type: 'text/csv;charset=utf-8' });
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl; link.download = `ruas-anotadas-${scene.acquired_at.slice(0,10)}.csv`;
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
function SearchImage({ scene, view, locationQuery, bbox, area, syncController }) {
  const [inspection, setInspection] = useState(null);
  const [inspectionError, setInspectionError] = useState('');
  const [imageLoaded, setImageLoaded] = useState(null);
  const [manualName, setManualName] = useState('');
  const [roadId, setRoadId] = useState('');
  const [showRoads, setShowRoads] = useState(false);
  const draftKey = `pin2-impact-${scene.product_id}-${bbox.join(',')}`;
  const [marked, setMarked] = useState(() => readImpactDraft(draftKey));
  useEffect(() => { try { localStorage.setItem(draftKey, JSON.stringify(marked)); } catch { /* CSV export remains available. */ } }, [draftKey, marked]);
  const preview = `/api/satellite/search/preview/${encodeURIComponent(scene.product_id)}?view=${view}${locationQuery}`;
  const roads = area?.roads?.features?.filter((road) => road.id && road.properties?.name && ['LineString', 'MultiLineString'].includes(road.geometry?.type)) || [];
  const markedIds = marked.filter((item) => item.source === 'OpenStreetMap').map((item) => item.id);
  const filename = `sentinel-${scene.acquired_at.slice(0,10)}-lat${((bbox[1] + bbox[3]) / 2).toFixed(5)}-lon${((bbox[0] + bbox[2]) / 2).toFixed(5)}`;
  useEffect(() => {
    let active = true;
    setInspection(null); setInspectionError(''); setImageLoaded(null);
    api(`/satellite/search/inspect/${encodeURIComponent(scene.product_id)}?${locationQuery.slice(1)}`)
      .then((value) => { if (active) setInspection(value); })
      .catch((error) => { if (active) setInspectionError(error.message); });
    return () => { active = false; };
  }, [scene.product_id, locationQuery]);
  function toggleRoad(id) {
    const road = roads.find((item) => item.id === id);
    if (!road) return;
    setMarked((current) => current.some((item) => item.id === id)
      ? current.filter((item) => item.id !== id)
      : [...current, { id, name: road.properties.name, source: 'OpenStreetMap' }]);
  }
  function addManual(event) {
    event.preventDefault();
    const name = manualName.trim();
    if (!name) return;
    setMarked((current) => [...current, { id: `manual-${Date.now()}-${Math.random().toString(36).slice(2,8)}`, name, source: 'Anotação manual' }]);
    setManualName('');
  }
  return <figure className={`search-preview ${inspection?.available === false || inspectionError ? 'unavailable' : ''}`}>
    <figcaption><strong>{date(scene.acquired_at, {dateStyle:'medium'})}</strong><small>Produto: {scene.product_id}</small><small>{scene.tile_cloud_percent != null ? `${scene.tile_cloud_percent}% de nuvens informado para o tile inteiro` : 'Nebulosidade do tile não informada'}</small></figcaption>
    {!inspection && !inspectionError && <p className="image-processing" role="status">Verificando pixels e cobertura neste recorte…</p>}
    {inspectionError && <p className="image-error" role="alert"><strong>Não foi possível verificar esta imagem.</strong> {inspectionError}</p>}
    {inspection?.available === false && <p className="image-error" role="status"><strong>Imagem indisponível neste recorte.</strong> {inspection.reason || 'Escolha outra passagem.'} {inspection.local_no_data_percent != null && `${inspection.local_no_data_percent}% do recorte sem dados do satélite.`} {inspection.local_obscured_percent != null && `${inspection.local_obscured_percent}% de pixels encobertos ou sem dados no recorte.`}</p>}
    {inspection?.available && <>
      {inspection.local_no_data_percent != null && <small className="image-local-quality">Neste recorte: {inspection.local_no_data_percent}% sem dados; {inspection.local_obscured_percent}% encobertos ou sem dados.</small>}
      <ZoomableImage url={preview} alt={`Imagem Sentinel-2 de ${date(scene.acquired_at, {dateStyle:'medium'})}`} roads={roads} bbox={bbox} selectedRoads={markedIds} onToggleRoad={toggleRoad} showRoads={showRoads} onAvailability={setImageLoaded} syncController={syncController} syncId={scene.product_id} focus={nearestWaterwayFocus(bbox, area?.waterways?.features)} focusLabel={area?.waterways?.features?.length ? 'Focar no rio' : 'Focar no centro'} />
      {imageLoaded === false && <p className="image-error" role="alert">A imagem foi aprovada, mas o arquivo não pôde ser aberto agora. Tente novamente.</p>}
      {imageLoaded && <DownloadLinks url={preview} name={filename} />}
      <div className="impact-register">
        <strong>Ruas impactadas para relatório</strong>
        <p>Marque trechos no mapa ou selecione uma rua. Este é um registro manual para verificação em campo; a imagem não identifica impacto automaticamente.</p>
        {roads.length > 0 && <label className="impact-show-roads"><input type="checkbox" checked={showRoads} onChange={(event) => setShowRoads(event.target.checked)} /> Mostrar trechos cartografados na imagem</label>}
        {roads.length > 0 && <div className="impact-add"><select aria-label="Trecho de rua no GIS" value={roadId} onChange={(event) => setRoadId(event.target.value)}><option value="">Selecione um trecho cartografado</option>{roads.map((road) => <option key={road.id} value={road.id}>{road.properties.name} · {road.id}</option>)}</select><button type="button" disabled={!roadId} onClick={() => { toggleRoad(roadId); setRoadId(''); }}>Marcar trecho</button></div>}
        <form className="impact-add" onSubmit={addManual}><input aria-label="Nome de rua não cartografada" value={manualName} maxLength={120} onChange={(event) => setManualName(event.target.value)} placeholder="Outra rua ou referência local" /><button type="submit" disabled={!manualName.trim()}>Adicionar</button></form>
        {marked.length > 0 ? <><ul className="impact-list">{marked.map((item) => <li key={item.id}><span>{item.name}<small>{item.source === 'OpenStreetMap' ? `Trecho ${item.id}` : item.source}</small></span><button type="button" aria-label={`Remover ${item.name}`} onClick={() => setMarked((current) => current.filter((other) => other.id !== item.id))}>Remover</button></li>)}</ul><button type="button" className="impact-export" onClick={() => downloadImpactCsv(marked, scene, bbox)}>Baixar ruas anotadas (CSV)</button></> : <small>Nenhuma rua anotada para esta data.</small>}
        <small className="impact-local-note">Rascunho salvo neste navegador. Faça o download do CSV para compartilhar.</small>
      </div>
    </>}
  </figure>;
}

function CaseModal({ id, onClose }) {
  const [caseData, setCaseData] = useState(null);
  const [error, setError] = useState("");
  const [view, setView] = useState("default");
  useEffect(() => {
    let active = true;
    api(id === 'history-2023' ? '/historical/2023' : `/events/${id}`).then((value) => { if (active) setCaseData(value); })
      .catch((e) => { if (active) setError(e.message); });
    const closeOnEscape = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", closeOnEscape);
    return () => { active = false; document.removeEventListener("keydown", closeOnEscape); };
  }, [id, onClose]);
  const context = caseData?.snapshot?.historical_context;
  return <div className="case-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
    <div className="case-dialog" role="dialog" aria-modal="true" aria-labelledby="case-title">
      <button className="case-close" onClick={onClose} aria-label="Fechar detalhes">×</button>
      {error ? <p className="error">{error}</p> : !caseData ? <p>Carregando registro…</p> : <>
        <span className="caps">{caseData.mode === "SIMULACAO" ? "CURIOSIDADE HISTÓRICA · COTAS SIMULADAS" : caseData.source_mode === 'DCSC' ? 'REGISTRO INDICATIVO · DCSC' : "EVENTO MONITORADO"}</span>
        <h2 id="case-title">{context?.title || "Registro de evento"}</h2>
        <p>{context?.summary || `${caseData.station_name} · ${date(caseData.started_at)}`}</p>
        {caseData.mode === "SIMULACAO" && <p className="case-caution">A ocorrência foi documentada, mas as cotas deste replay são didáticas. As imagens mostram datas próximas, não o pico da enchente.</p>}
        {caseData.source_mode === 'DCSC' && <p className="case-caution">Gatilho calculado a partir de leitura pública e cota cadastrada para esta estação ({referenceName(caseData.snapshot?.threshold_kind)}). Não é alerta oficial da Defesa Civil.</p>}
        {caseData.scenes.BASELINE?.has_natural && caseData.scenes.POST_EVENT?.has_natural && <div className="segmented" aria-label="Visualização histórica">
          <button className={view === "default" ? "active" : ""} onClick={() => setView("default")}>Água destacada</button>
          <button className={view === "natural" ? "active" : ""} onClick={() => setView("natural")}>Cor natural</button>
        </div>}
        <div className="case-scenes">
          {[["BASELINE", "Antes"], ["POST_EVENT", "Depois"]].map(([role, label]) => {
            const scene = caseData.scenes[role];
            return scene && <figure key={role}><ZoomableImage url={sceneUrl(scene, view)} alt={`${label}: rio e entorno em ${date(scene.acquired_at, { dateStyle: "medium" })}`} /><figcaption>{label} · {date(scene.acquired_at, { dateStyle: "medium" })}<DownloadLinks url={sceneUrl(scene, view)} name={`rio-dos-indios-${scene.acquired_at.slice(0,10)}`} /></figcaption></figure>;
          })}
        </div>
        {(caseData.scenes.BASELINE || caseData.scenes.POST_EVENT) && <p className="upscale-note">Ampliação 2×/4× por interpolação para apresentação; a resolução do sensor não muda.</p>}
        {!caseData.scenes.BASELINE && !caseData.scenes.POST_EVENT && <p className="data-message">Gatilho registrado. As imagens Sentinel-1 do período ainda estão em processamento ou indisponíveis.</p>}
        {caseData.failure_summary && <p className="data-message">{caseData.failure_summary}</p>}
        {context?.sources && <div className="case-sources">{context.sources.map((source) => <a key={source.url} href={source.url} target="_blank" rel="noreferrer">{source.title} ↗</a>)}</div>}
      </>}
    </div>
  </div>;
}

function App() {
  const { live, error: liveError } = useLiveStation();
  const monitor = useMonitorStatus();
  const { pair, error: pairError } = useRecentSatellite();
  const [realEvents, setRealEvents] = useState([]);
  const [openCase, setOpenCase] = useState(null);
  const [showAdmin, setShowAdmin] = useState(false);
  useEffect(() => {
    let active = true;
    const load = () => api('/events?mode=AO_VIVO').then((value) => { if (active) setRealEvents(value.items); }).catch(() => {});
    load();
    const timer = setInterval(load, 60000);
    return () => { active = false; clearInterval(timer); };
  }, []);
  const closeCase = React.useCallback(() => setOpenCase(null), []);
  return <>
    <header className="site-header" id="inicio"><div className="container nav landing-nav">
      <a className="brand" href="#inicio" aria-label="Voltar ao início"><span className="brand-icon"><Icon name="protection" size={25} /></span><span>MANCHA<span className="brand-slash">/</span>INUNDAÇÃO<small>APOIO À ANÁLISE · DEFESA CIVIL</small></span></a>
      <nav aria-label="Navegação principal"><a href="#monitoramento">Nível do rio</a><a href="#imagens">Imagens</a><a href="#historia">História</a><button className="nav-admin" onClick={() => { setShowAdmin((value) => !value); setTimeout(() => document.getElementById('admin')?.scrollIntoView({ behavior: 'smooth' }), 0); }}>Admin</button></nav>
    </div></header>
    <main>
      <section className="landing-intro"><div className="container"><span className="caps">MONITORAMENTO FLUVIAL · ÁREA DE ESTUDO</span><h1>Nível do rio e imagens de satélite</h1><p>Acompanhe a estação da área piloto ou escolha coordenadas e duas datas para comparar imagens do Copernicus.</p></div></section>
      <div className="container landing-content"><LiveStation live={live} error={liveError} station={live?.station} monitor={monitor} /><RecentCompare pair={pair} error={pairError} /><PeriodSearch />
        {realEvents.length > 0 && <section className="landing-events" id="eventos"><div className="landing-section-head"><div><span className="caps">REGISTROS</span><h2>Eventos monitorados</h2></div></div><div className="event-grid">{realEvents.slice(0, 3).map((event) => <EventCard key={event.id} item={event} open={setOpenCase} />)}</div></section>}
        <section className="landing-history" id="historia"><div><span className="caps">CURIOSIDADE HISTÓRICA</span><h2>Enchente de novembro de 2023</h2><p>Um episódio documentado com imagens Sentinel-2 de antes e depois. Os níveis do replay são simulados.</p><button className="btn ghost" onClick={() => setOpenCase('history-2023')}>Ver história e imagens <Icon name="arrow" size={17} /></button></div><img src="/api/historical/2023/image/BASELINE?view=default" alt="Vista de Presidente Getúlio antes da enchente de 2023" /></section>
        <section className="landing-method" id="sobre"><span className="caps">COMO LER O PAINEL</span><p>O nível vem da estação DCSC-00043 reproduzida pelo <a href="https://pdc.presidentegetulio.sc.gov.br/monitoramento" target="_blank" rel="noreferrer">portal municipal</a>. As imagens vêm do Copernicus. Diferenças visuais não confirmam uma inundação nem substituem alertas oficiais.</p></section>
      </div>
    </main>
    {showAdmin && <section id="admin" className="landing-admin"><Admin open={setOpenCase} /></section>}
    <footer><div className="container footer-inner"><div><strong>MANCHA/INUNDAÇÃO</strong><span>Área piloto · estação DCSC-00043</span></div><p>Projeto acadêmico de apoio à análise · Consulte a Defesa Civil para orientações oficiais.</p></div></footer>
    {openCase && <CaseModal id={openCase} onClose={closeCase} />}
  </>;
}
createRoot(document.getElementById("root")).render(<App />);
