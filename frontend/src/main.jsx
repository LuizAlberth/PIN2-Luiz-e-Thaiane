import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
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
        ? "Demonstração: níveis e gatilho simulados, sem medições da ANA ou da Defesa Civil. Consulte a origem e a data de cada imagem. Diferenças visuais não confirmam uma inundação."
        : replay
          ? "Esta área reúne replays históricos. Alguns usam leituras e cenas reais; os cenários didáticos são identificados em cada evento."
          : "Comparações visuais são evidências informativas. O sistema não emite alertas oficiais nem delimita a área exata de inundação."}
    </span>
  </div>
);
const OfficialStation = ({ station, demo }) =>
  station && (
    <section className="official-station" aria-labelledby="official-station-title">
      <div className="official-station-icon" aria-hidden="true">
        <Icon name="pin" size={25} />
      </div>
      <div className="official-station-copy">
        <span className="caps">ESTAÇÃO OFICIAL DE REFERÊNCIA</span>
        <h3 id="official-station-title">
          {station.name} <span>{station.code}</span>
        </h3>
        <p>
          {station.region} · Bacia {station.basin}. Consulte nível do rio e chuva
          diretamente na Defesa Civil SC. {demo
            ? "As cotas do cenário histórico abaixo são simuladas e não vêm desta estação."
            : "As leituras oficiais atuais estão disponíveis no portal da Defesa Civil."}
        </p>
      </div>
      <a href={station.url} target="_blank" rel="noopener noreferrer">
        Ver leituras oficiais <Icon name="arrow" size={17} />
      </a>
    </section>
  );
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
        As próximas leituras formarão o gráfico de evolução.
      </div>
    );
  let vals = pts.map((x) => x.water_level_cm),
    lo = Math.min(...vals, threshold ?? Infinity) - 20,
    hi = Math.max(...vals, threshold ?? -Infinity) + 20,
    span = hi - lo || 1,
    startTime = new Date(pts[0].observed_at).getTime(),
    timeSpan =
      new Date(pts[pts.length - 1].observed_at).getTime() - startTime || 1,
    coords = pts.map((p) => [
      24 + ((new Date(p.observed_at).getTime() - startTime) * 552) / timeSpan,
      180 - ((p.water_level_cm - lo) / span) * 140,
    ]),
    path = coords
      .map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`)
      .join(" "),
    ty = 180 - ((threshold - lo) / span) * 140;
  return (
    <>
      <svg
        className="graph"
        viewBox="0 0 600 210"
        role="img"
        aria-label="Evolução das leituras e cota de referência"
      >
        <defs>
          <linearGradient id="g" x2="0" y2="1">
            <stop stopColor="#2365aa" stopOpacity=".28" />
            <stop offset="1" stopColor="#2365aa" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[40, 85, 130, 180].map((y) => (
          <line
            key={y}
            x1="24"
            x2="576"
            y1={y}
            y2={y}
            stroke="#e2eae7"
            strokeDasharray="4 6"
          />
        ))}
        <line
          x1="24"
          x2="576"
          y1={ty}
          y2={ty}
          stroke="#cb9657"
          strokeDasharray="6 4"
        />
        <text
          x="575"
          y={Math.max(13, ty - 7)}
          textAnchor="end"
          fill="#a06e36"
          fontSize="12"
        >
          Cota {cm(threshold)}
        </text>
        <path d={`${path} L576 195 L24 195 Z`} fill="url(#g)" />
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
          />
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
    </>
  );
}
function HeroScene({ event, open }) {
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
      <div className="art-topline">
        <span className="art-tag">
          <Icon name="pin" size={13} /> ÁREA PILOTO
        </span>
        <span>N ↑</span>
      </div>
      <div className="art-caption">
        <span>PRESIDENTE GETÚLIO · SC</span>
        <strong>Um olhar sobre o território.</strong>
        <p>
          {scene && !failed
            ? `${scene.source === "CDSE" ? "Copernicus" : "Referência visual"} · ${date(scene.acquired_at, { dateStyle: "medium" })}`
            : "Rios Krauel e dos Índios · área de estudo"}
        </p>
        {scene && !failed && (
          <button className="art-open" onClick={() => open(event.id)}>
            Abrir comparação <Icon name="arrow" size={16} />
          </button>
        )}
      </div>
    </div>
  );
}
function SystemPurpose({ navigate, open, event, demo }) {
  const actions = [
    {
      icon: "wave",
      title: "Acompanhar os níveis",
      description:
        "Consulte a evolução das cotas, a referência de monitoramento e a situação dos dados.",
      label: "Ver monitoramento",
      action: () =>
        document
          .getElementById("monitoramento")
          ?.scrollIntoView({ behavior: "smooth", block: "start" }),
    },
    {
      icon: "layers",
      title: "Comparar as imagens",
      description:
        "Observe o rio antes e depois do gatilho, lado a lado ou por sobreposição de cenas Sentinel.",
      label: "Comparar imagens",
      action: () => (event ? open(event.id) : navigate("events")),
    },
    {
      icon: "shield",
      title: "Consultar as evidências",
      description:
        "Explore eventos e confira as datas, a origem das imagens e os detalhes de cada registro.",
      label: "Explorar histórico",
      action: () => navigate("events"),
    },
  ];
  return (
    <section className="purpose" aria-labelledby="purpose-title">
      <div className="purpose-intro">
        <div className="purpose-icon" aria-hidden="true">
          <Icon name="protection" size={27} />
        </div>
        <div>
          <span className="caps">OBJETIVO DO SISTEMA</span>
          <h2 id="purpose-title">
            Informação para apoiar a análise de inundações.
          </h2>
          <p>
            Reunir níveis dos rios e imagens de satélite de Presidente Getúlio
            para acompanhar o cenário, comparar momentos e consultar evidências
            em um só lugar.
          </p>
        </div>
      </div>
      <div className="purpose-grid">
        {actions.map(({ icon, title, description, label, action }, index) => (
          <article className="purpose-card" key={title}>
            <div className="purpose-card-top">
              <Icon name={icon} size={25} />
              <span>0{index + 1}</span>
            </div>
            <h3>{title}</h3>
            <p>{description}</p>
            <button className="text-link" onClick={action}>
              {label}
              <Icon name="arrow" size={16} />
            </button>
          </article>
        ))}
      </div>
      <div className="purpose-footnote">
        <Icon name="info" size={16} />
        <span>
          {demo
            ? "Modo demonstração: níveis e gatilho simulados. "
            : "Projeto acadêmico de uso informativo. "}
          O sistema não emite alertas oficiais nem substitui as orientações da
          Defesa Civil.
        </span>
      </div>
    </section>
  );
}
function Dashboard({ navigate, open }) {
  let [data, setData] = useState(),
    [readings, setReadings] = useState([]),
    [error, setError] = useState("");
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
    r = data.reading,
    demo = c?.source_mode === "DEMO";
  return (
    <>
      <section className="hero">
        <div className="container hero-grid">
          <div>
            <div className="eyebrow">
              <i /> ANÁLISE DE INUNDAÇÕES · PROJETO ACADÊMICO
            </div>
            <h1>
              Dados do rio.
              <br />
              <em>Evidências à vista.</em>
            </h1>
            <p>
              Acompanhe níveis, compare imagens de satélite e consulte o
              histórico para entender o cenário dos rios em Presidente Getúlio.
            </p>
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
                  ? "Ver comparação recente"
                  : "Explorar eventos"}{" "}
                <Icon name="arrow" size={18} />
              </button>
              <button className="btn ghost" onClick={() => navigate("about")}>
                Como funciona
              </button>
            </div>
          </div>
          <HeroScene event={data.recent_events[0]} open={open} />
        </div>
      </section>
      <main className="container content">
        <SystemPurpose
          navigate={navigate}
          open={open}
          event={data.recent_events[0]}
          demo={demo}
        />
        {data.recent_events[0]?.scenario_title && (
          <section className="historical-callout">
            <div>
              <span className="caps">CASO HISTÓRICO DISPONÍVEL</span>
              <h3>{data.recent_events[0].scenario_title}</h3>
              <p>
                Conheça o episódio de Presidente Getúlio, compare imagens reais
                anteriores e posteriores e consulte as fontes oficiais. Os
                níveis são simulados.
              </p>
            </div>
            <button
              className="btn outline"
              onClick={() => open(data.recent_events[0].id)}
            >
              Abrir caso histórico <Icon name="arrow" size={17} />
            </button>
          </section>
        )}
        <div className="section-head" id="monitoramento">
          <div>
            <span className="caps">VISÃO GERAL</span>
            <h2>Situação do monitoramento</h2>
          </div>
          <span className="muted">
            <Icon name="clock" size={16} /> Consultado em{" "}
            {date(data.updated_at)}
          </span>
        </div>
        <Notice demo={demo} />
        <OfficialStation station={data.official_station} demo={demo} />
        <div className="stats">
          <article className="stat important">
            <span>
              <Icon name="wave" /> {demo ? "Última cota simulada" : "Última leitura válida"}
            </span>
            <strong>{cm(r?.water_level_cm)}</strong>
            <small>
              {r
                ? `Medição em ${date(r.observed_at)}`
                : "Aguardando primeira leitura"}
            </small>
            <Badge tone={data.data_status === "ATUALIZADO" ? "green" : "amber"}>
              {names[data.data_status]}
            </Badge>
          </article>
          <article className="stat">
            <span>
              <Icon name="layers" /> Cota de referência
            </span>
            <strong>{cm(c?.threshold_cm)}</strong>
            <small>{c?.threshold_source || "Nenhuma configuração ativa"}</small>
          </article>
          <article className="stat">
            <span>
              <Icon name="pin" /> {demo ? "Estação do cenário" : "Estação monitorada"}
            </span>
            <strong className="station-number">{c?.station_code || "—"}</strong>
            <small>
              {c?.station_name || "Configure uma estação para começar"}
            </small>
            <small>
              Integração:{" "}
              {names[data.integration_status] || data.integration_status || "—"}
            </small>
          </article>
        </div>
        <div className="dashboard-grid">
          <article className="panel">
            <div className="section-head compact">
              <div>
                <span className="caps">LEITURAS RECENTES</span>
                <h3>{demo ? "Evolução simulada da cota" : "Evolução da cota"}</h3>
              </div>
              <span className="muted">{readings.length} medições</span>
            </div>
            <Graph readings={readings} threshold={c?.threshold_cm} />
          </article>
          <article className="panel context">
            <span className="caps">SOBRE OS DADOS</span>
            <h3>Uma leitura com contexto.</h3>
            <p>
              O gatilho acontece quando uma leitura válida passa de abaixo para
              igual ou acima da cota registrada.{" "}
              {demo
                ? "Nesta demonstração, os níveis são simulados e a comparação usa imagens reais do Sentinel-2."
                : "Depois o sistema busca cenas de radar Sentinel-1 comparáveis."}
            </p>
            <div>
              <Icon name="shield" /> Origem e qualidade preservadas
            </div>
            <div>
              <Icon name="clock" /> Horários no fuso de Brasília
            </div>
            <div>
              <Icon name="image" /> Comparação após processamento
            </div>
          </article>
        </div>
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
            {data.recent_events.map((x) => (
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
        <p>Explore registros publicados e veja a origem de cada evidência.</p>
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
          <p>
            Eventos são publicados quando ao menos uma evidência foi processada.
          </p>
        </div>
      )}
    </main>
  );
}
function sceneUrl(scene, view) {
  return `${scene.image_url}${scene.image_url.includes("?") ? "&" : "?"}view=${view}`;
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
            "O sistema consulta a série telemétrica da ANA e registra cota, horário e qualidade.",
          ],
          [
            "02",
            "Identificar",
            "Uma leitura válida passa de abaixo para igual ou acima da cota configurada.",
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
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const [model, setModel] = useState({
    configs: [],
    events: [],
    jobs: [],
    audit: [],
    integrations: {},
  });
  const [form, setForm] = useState({
    station_code: "83372100",
    river: "Rio Krauel",
    bbox: "",
    threshold_cm: "",
    threshold_source: "",
    threshold_valid_from: new Date().toISOString().slice(0, 10),
    threshold_responsible: "",
    collection_interval_min: 30,
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
    if (token) refresh();
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
      let bbox = form.bbox.split(",").map(Number);
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
        source_mode: "ANA",
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
              role="status"
              className={`form-msg ${message.startsWith("Erro:") ? "error" : ""}`}
            >
              {message}
            </p>
          )}
        </form>
      </main>
    );
  const current = model.configs.find((c) => c.active);
  const fields = [
    ["station_code", "Código ANA"],
    ["river", "Rio"],
    ["bbox", "Área [oeste, sul, leste, norte]"],
    ["threshold_cm", "Cota de referência (cm)"],
    ["threshold_valid_from", "Válida desde"],
    ["threshold_source", "Fonte oficial da cota"],
    ["threshold_responsible", "Responsável pelo cadastro"],
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
          <h1>Painel administrativo</h1>
          <p>
            Piloto Presidente Getúlio · processamento e tentativas auditáveis
          </p>
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
        ].map(([key, label]) => (
          <button
            key={key}
            className={tab === key ? "selected" : ""}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>
      {message && (
        <div
          className={`form-msg ${message.startsWith("Erro") ? "error" : ""}`}
          role="status"
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
                  ? `${current.station_code} · cota ${cm(current.threshold_cm)} · versão ${current.version}`
                  : "Ative uma configuração real ou a demonstração."}
              </p>
              <Badge tone={current?.source_mode === "DEMO" ? "amber" : "green"}>
                {current?.source_mode === "DEMO"
                  ? "Simulação"
                  : current
                    ? "ANA"
                    : "Inativa"}
              </Badge>
            </article>
            <article className="panel">
              <span className="caps">INTEGRAÇÕES</span>
              <h3>Disponibilidade</h3>
              <p>
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
          {current?.source_mode === "ANA" && (
            <>
              <button
                className="btn outline top-gap"
                disabled={busy}
                onClick={() =>
                  perform(async () => {
                    await api("/admin/collect", { method: "POST" });
                    return "Coleta solicitada ao worker.";
                  })
                }
              >
                Coletar agora
              </button>
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
            </>
          )}
        </>
      )}
      {tab === "config" && (
        <div className="form-layout">
          <article className="panel">
            <span className="caps">MODO REAL</span>
            <h3>Ativar nova configuração</h3>
            <p>
              A estação e as cotas são conferidas na ANA antes de ativar. Cada
              alteração cria uma versão.
            </p>
            <div className="form-grid">
              {fields.map(([key, label]) => (
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
                    value={form[key]}
                    onChange={(e) =>
                      setForm({ ...form, [key]: e.target.value })
                    }
                  />
                </label>
              ))}
            </div>
            <div className="form-actions">
              <button
                className="btn outline"
                disabled={busy || !model.integrations.ana_configured}
                onClick={inspect}
              >
                Consultar estação e preencher área
              </button>
              <button
                className="btn primary"
                disabled={busy || !model.integrations.ana_configured}
                onClick={activate}
              >
                Validar e ativar <Icon name="arrow" size={18} />
              </button>
            </div>
            {!model.integrations.ana_configured && (
              <p className="hint">
                Configure ANA_IDENTIFICADOR e ANA_SENHA no servidor para
                habilitar o modo real.
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
                    <Badge tone={c.active ? "green" : "neutral"}>
                      {c.active ? "Ativa" : "Encerrada"}
                    </Badge>
                  </div>
                  <small>
                    {date(c.valid_from)} · {c.source_mode}
                  </small>
                  <p>
                    Cota {cm(c.threshold_cm)} · {c.threshold_source}
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
                  <th>Versão</th>
                  <th>Tentativas</th>
                  <th>Próxima execução / erro</th>
                </tr>
              </thead>
              <tbody>
                {model.jobs.map((j) => (
                  <tr key={j.id}>
                    <td>{j.kind}</td>
                    <td>{names[j.status] || j.status}</td>
                    <td>v{j.version}</td>
                    <td>{j.attempts}</td>
                    <td>{j.last_error || date(j.scheduled_for)}</td>
                  </tr>
                ))}
                {!model.jobs.length && (
                  <tr>
                    <td colSpan="5">Nenhum job criado.</td>
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
                  <th>Responsável</th>
                  <th>Ação</th>
                  <th>Detalhes</th>
                </tr>
              </thead>
              <tbody>
                {model.audit.map((a, i) => (
                  <tr key={i}>
                    <td>{date(a.created_at)}</td>
                    <td>{a.actor}</td>
                    <td>{a.action.replaceAll("_", " ")}</td>
                    <td>
                      <code>{JSON.stringify(a.details)}</code>
                    </td>
                  </tr>
                ))}
                {!model.audit.length && (
                  <tr>
                    <td colSpan="4">Sem registros.</td>
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
function App() {
  const parse = () =>
    location.hash.startsWith("#/evento/")
      ? { page: "detail", id: location.hash.split("/")[2] }
      : { page: location.hash.replace("#/", "") || "dashboard" };
  let [route, setRoute] = useState(parse);
  useEffect(() => {
    let fn = () => setRoute(parse());
    addEventListener("hashchange", fn);
    return () => removeEventListener("hashchange", fn);
  }, []);
  const go = (page) => {
      location.hash = `/${page}`;
      scrollTo(0, 0);
    },
    open = (id) => {
      location.hash = `/evento/${id}`;
      scrollTo(0, 0);
    };
  return (
    <>
      <header className="site-header">
        <div className="container nav">
          <button
            className="brand"
            onClick={() => go("dashboard")}
            aria-label="Ir ao painel"
          >
            <span className="brand-icon">
              <Icon name="protection" size={25} />
            </span>
            <span>
              MANCHA<span className="brand-slash">/</span>INUNDAÇÃO
              <small>PROJETO ACADÊMICO · SC</small>
            </span>
          </button>
          <nav aria-label="Navegação principal">
            <button
              className={route.page === "dashboard" ? "active" : ""}
              onClick={() => go("dashboard")}
            >
              Painel
            </button>
            <button
              className={
                ["events", "detail"].includes(route.page) ? "active" : ""
              }
              onClick={() => go("events")}
            >
              Eventos
            </button>
            <button
              className={route.page === "about" ? "active" : ""}
              onClick={() => go("about")}
            >
              Sobre
            </button>
            <button
              className={`nav-admin ${route.page === "admin" ? "active" : ""}`}
              onClick={() => go("admin")}
            >
              Admin <Icon name="arrow" size={15} />
            </button>
          </nav>
        </div>
      </header>
      {route.page === "events" ? (
        <Events open={open} />
      ) : route.page === "detail" ? (
        <Detail id={route.id} navigate={go} />
      ) : route.page === "admin" ? (
        <Admin open={open} />
      ) : route.page === "about" ? (
        <About />
      ) : (
        <Dashboard navigate={go} open={open} />
      )}
      <footer>
        <div className="container footer-inner">
          <div>
            <strong>MANCHA/INUNDAÇÃO</strong>
            <span>Presidente Getúlio · Santa Catarina</span>
          </div>
          <p>
            Projeto acadêmico de apoio à análise · Não substitui informações
            oficiais da Defesa Civil.
          </p>
        </div>
      </footer>
    </>
  );
}
createRoot(document.getElementById("root")).render(<App />);
