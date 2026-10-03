"""Carga la informacion inicial de The Diamonds League.

Ejecutar con:  python seed.py   o   flask --app app seed
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from extensions import db
from models import (
    Alliance, Article, Category, Division, DivisionRule, Donation, DonationChannel,
    DonationGoal, LiveStream, Match, MuseumItem, Phase, Player, PromotionSlot, Role, Room,
    RuleEntry, SanctionLevel, Season, SocialLink, StaffMember, Standing, Team, User, log_activity,
)
from utils import slugify, utcnow

# --------------------------------------------------------------------------- #
# Datos base
# --------------------------------------------------------------------------- #
ROOMS = [
    ("01", "DIAMONDS PUBLIC", "https://www.haxball.com/play?c=lnjqtRG-Z-E", "Latam", 12,
     "Diamond", "3v3 + 1 Portero", 95, "", True),
    ("02", "DIAMONDS PUBLIC", "https://www.haxball.com/play?c=lX3wqk3eNlo", "Latam", 12,
     "Diamond", "2v2 Duelos", 90, "", False),
    ("03", "DIAMONDS PUBLIC", "https://www.haxball.com/play?c=1ziccjYd2JU", "Latam", 12,
     "Bermuda", "3v3 Clasico", 110, "DIAMONDS", False),
    ("04", "DIAMONDS PUBLIC", "https://www.haxball.com/play?c=cPP-NvFDXTc", "Latam", 12,
     "Diamond", "Entrenamiento libre", 85, "", False),
    ("05", "DIAMONDS PUBLIC", "https://www.haxball.com/play?c=Fu5CTxD2F-s", "Latam", 12,
     "Wormhole", "1v1 Clasificatorio", 100, "DIAMONDS", True),
]

D1_TEAMS = [
    ("Lexington", "LEX", "DT Santiago", "st_fxx", "Colombia"),
    ("Real Haxball", "RHAX", "DT Pipe", "pipedia_", "Argentina"),
    ("Los Andes", "AND", "DT Kiwi", "kiwi_x5", "Chile"),
    ("Titanes Hax", "TIT", "DT Gordo", "gordop", "Mexico"),
    ("Club Esmeralda", "ESM", "DT Rino", "rino_", "Peru"),
    ("Dynamo FC", "DYN", "DT Fede", "fede_hax", "Argentina"),
    ("Pantera FC", "PNT", "DT Negro", "negroo", "Colombia"),
    ("Deportivo Central", "CEN", "DT Chispa", "chispa_", "Ecuador"),
    ("Casablanca", "CAS", "DT Dona", "dona", "Colombia"),
    ("Norte FC", "NTE", "DT Yaya", "yaya_x5", "Venezuela"),
    ("Union Futbol", "UNI", "DT Milan", "milan_", "Bolivia"),
    ("Deportivo 97", "D97", "DT Beto", "beto_", "Colombia"),
]

D2_TEAMS = [
    ("Deportivo Pereira", "PER", "DT Inuv", "inuv", "Colombia"),
    ("Kiosko FC", "KSK", "DT Rasta", "rasta_", "Colombia"),
    ("Racing Hax", "RAC", "DT Toro", "toro_x5", "Argentina"),
    ("Atletico Diamante", "ATD", "DT Sol", "sol_", "Peru"),
    ("Club Oblea", "OBL", "DT Pipa", "pipi_", "Chile"),
    ("Sporting X5", "SPX", "DT Loco", "loco_", "Mexico"),
    ("Union Deportiva", "UND", "DT Cami", "cami_", "Colombia"),
    ("FC Bazaar", "BZR", "DT Nico", "nico_", "Ecuador"),
]

STAR_PLAYERS = {
    "Lexington": [("Muñoz", "RW", 10, False, 7, 38, 11, 0), ("Oblea Gatona", "GK", 1, False, 7, 0, 0, 10)],
    "Real Haxball": [("Pipe", "MF", 8, True, 7, 9, 14, 0), ("Rana", "FW", 9, False, 7, 11, 4, 0)],
    "Deportivo Pereira": [("Gabinho", "FW", 9, False, 7, 24, 12, 0), ("Chispa", "MF", 5, True, 7, 6, 9, 0)],
    "Kiosko FC": [("Sxra", "GK", 1, False, 7, 0, 0, 9)],
}

FILLER_PLAYERS = ["Loki", "Vega", "Rayo", "Nube", "Cobre", "Zafiro", "Trueno", "Mango",
                  "Pixel", "Rana", "Coyote", "Bala", "Tigre", "Furia", "Nitro", "Quilla"]

# Estadisticas de referencia (Temporada 2)
AWARD_ENTRIES = [
    ("Balon de Oro D2", "premios", "D2", "Gabinho", "Deportivo Pereira", "24 goles y 12 asistencias.", 1, "d2-balon-de-oro.webp"),
    ("Guante de Oro D2", "premios", "D2", "Sxra", "Kiosko FC", "87 minutos y 6 segundos de clean sheet.", 1, "d2-guante-de-oro.webp"),
    ("Bota de Oro D2", "premios", "D2", "Gabinho", "Deportivo Pereira", "24 goles en liga.", 1, "d2-bota-de-oro.webp"),
    ("Balon de Oro D1", "premios", "D1", "Muñoz", "Lexington", "38 goles, 11 asistencias y 7 partidos.", 1, "d1-balon-de-oro.webp"),
    ("Guante de Oro D1", "premios", "D1", "Oblea Gatona", "Lexington", "68 minutos y 15 segundos de clean sheet.", 1, "d1-guante-de-oro.webp"),
    ("Bota de Oro D1", "premios", "D1", "Muñoz", "Lexington", "38 goles en 7 partidos.", 1, "d1-bota-de-oro.webp"),
    ("Ranking Balon de Oro D2", "rankings", "D2", None, None, "Top 5 oficial de la Temporada 2.", 0, "d2-ranking-balon.webp"),
    ("Ranking Guante de Oro D2", "rankings", "D2", None, None, "Top 5 oficial de porteros de la Temporada 2.", 0, "d2-ranking-guante.webp"),
    ("Ranking Bota de Oro D2", "rankings", "D2", None, None, "Top 5 oficial de goleadores de la Temporada 2.", 0, "d2-ranking-bota.webp"),
    ("Ranking Balon de Oro D1", "rankings", "D1", None, None, "Top 5 oficial de la Temporada 2.", 0, "d1-ranking-balon.webp"),
    ("Ranking Guante de Oro D1", "rankings", "D1", None, None, "Top 5 oficial de porteros de la Temporada 2.", 0, "d1-ranking-guante.webp"),
    ("Ranking Bota de Oro D1", "rankings", "D1", None, None, "Top 5 oficial de goleadores de la Temporada 2.", 0, "d1-ranking-bota.webp"),
    ("Mejor Club D2", "campeones", "D2", "Deportivo Pereira", "Deportivo Pereira", "Campeón de División 2 · DT Inuv.", 1, "d2-mejor-club.webp"),
    ("Mejor Club D1", "campeones", "D1", "Lexington", "Lexington", "Campeón de División 1 · DT Santiago.", 1, "d1-mejor-club.webp"),
]

EXTRA_AWARDS = [
    ("Trofeo B'dor Premiation", "trofeos", "LIGA", None, None, "Trofeo general entregado al cierre de la Temporada 2.", 1, "d1-mejor-club.webp"),
    ("Guante de Oro Temporada 1", "premios", "D1", "Rayo", None, "Mejor portero de la primera temporada de la liga.", 1, "d1-guante-de-oro.webp"),
    ("Balon de Plata Temporada 1", "premios", "D2", "Nube", None, "Segundo mejor jugador de la Temporada 1.", 2, "d2-balon-de-oro.webp"),
    ("Mejor AFA Temporada 1", "premios", "D1", "Nitro", None, "Mejor asistencia de la Temporada 1.", 2, "d1-ranking-bota.webp"),
    ("Trofeo de la Temporada 1", "trofeos", "LIGA", None, None, "Trofeo del primer campeon de The Diamonds League.", 1, "d2-mejor-club.webp"),
]

PARTNERS = [
    ("P01", "PARTNER 01", "8JTfxJy66K"),
    ("P02", "PARTNER 02", "UgJUR8CGWu"),
    ("P03", "PARTNER 03", "9ygkmbnjkE"),
    ("P04", "PARTNER 04", "KzuTqBQyht"),
    ("P05", "PARTNER 05", "pBbKeqd9Tc"),
    ("P06", "PARTNER 06", "6NZNfNFwpX"),
    ("P07", "PARTNER 07", "GsxhYXXtGX"),
    ("P08", "PARTNER 08", "Y3QApwH9p7"),
]

STAFF = [
    ("Stefy", "st_fxx", "OWNER", "Owner y direccion", "Owner de The Diamonds League.", "OWNER,DIRECCION", True, 1),
    ("Zshr08", "zshr08", "MASTER", "Master del servidor", "Master del servidor y encargado de la sala.", "MASTER,SALA", False, 2),
    ("Zyrox", "zyrox_0169", "STAFF", "Staff general", None, "STAFF,SOPORTE", False, 3),
    ("Ayala", "juanayala_1", "STAFF", "Analista y calendario", None, "STAFF,DATOS", False, 4),
    ("Shenlong", "stuncito923", "STAFF", "Moderacion", None, "STAFF,MODERACION", False, 5),
]

RULES = [
    ("discord", 1, "RESPETO ANTE TODO", "Respeta a todos los miembros, staff y admins. Cualquier falta de respeto sera sancionada."),
    ("discord", 2, "PROHIBIDO EL SPAM", "No enviar mensajes repetitivos, links sin permiso o flood."),
    ("discord", 3, "CUMPLIR INDICACIONES DEL STAFF", "Las decisiones del staff deben respetarse en todo momento."),
    ("discord", 4, "CERO TOXICIDAD", "Quedan prohibidos los insultos, racismo, discriminacion, acoso o provocaciones."),
    ("discord", 5, "CONTENIDO ADECUADO", "No se permite contenido NSFW, gore o inapropiado."),
    ("discord", 6, "USO CORRECTO DE CANALES", "Habla en los canales correspondientes y evita el desorden."),
    ("discord", 7, "PUBLICIDAD CON AUTORIZACION", "Partners o promociones solo con autorizacion del staff."),
    ("comunidad", 1, "BUENA CONDUCTA", "Mantén un ambiente sano y competitivo."),
    ("comunidad", 2, "EVITAR CONFLICTOS", "Los problemas personales deben resolverse por privado o con staff."),
    ("comunidad", 3, "NO SUPLANTACION", "Esta prohibido hacerse pasar por otro usuario o staff."),
    ("comunidad", 4, "NOMBRES Y PERFILES ADECUADOS", "No usar nombres ofensivos o provocativos."),
]

SANCTIONS = [
    ("ESCALA GENERAL", "general", "Advertencia o Warn\nSilencio o Mute\nExpulsion o Kick\nBaneo o Ban",
     "Las sanciones dependeran de la gravedad de la falta."),
    ("AMARILLA", "yellow", "Conductas antideportivas\nPausas incorrectas\nReclamaciones excesivas",
     "2 amarillas equivalen a 1 roja."),
    ("ROJA", "red", "Insultos graves\nFalta de respeto\nConducta antideportiva grave",
     "Sancion mas posible: suspension."),
]

SOCIALS = [
    ("tiktok", "liga", "TikTok oficial", "@diamondsleague89", "https://www.tiktok.com/@diamondsleague89", "TT", True, 1),
    ("discord", "liga", "Discord de la liga", "diamonds league", "https://discord.gg/kVAjgkeRsC", "DC", True, 2),
    ("haxball", "liga", "HaxBall", "salas de la liga", "https://www.haxball.com", "HX", False, 3),
    ("twitch", "liga", "Twitch de la liga", "diamondsleague", "https://www.twitch.tv/diamondsleague", "TW", False, 4),
    ("instagram", "liga", "Instagram", "@diamondsleague", "https://www.instagram.com/diamondsleague", "IG", False, 5),
    ("x", "liga", "X (Twitter)", "@diamondsleague", "https://x.com/diamondsleague", "X", False, 6),
    ("twitch", "streamer", "Streamer principal", "zshr08", "https://www.twitch.tv/zshr08", "TW", True, 1),
    ("tiktok", "streamer", "Streamer de clips", "stefy_hax", "https://www.tiktok.com/@stefy_hax", "TT", False, 2),
    ("twitch", "streamer", "Cast de partidos", "shenlongcast", "https://www.twitch.tv/shenlongcast", "TW", False, 3),
    ("kick", "streamer", "Kick oficial", "diamondsleague", "https://kick.com/diamondsleague", "KK", False, 4),
]

LIVE_STREAMS = [
    ("Diamonds League — Division 1 Jornada 9", "twitch", "diamondsleague",
     "https://www.twitch.tv/diamondsleague", "Diamond League", "Liga competitiva", True, True, 1240, 1),
    ("Futbol en vivo — Primera linea", "kick", "diamondsleague",
     "https://kick.com/diamondsleague", "FOOTBOL LIVE", "Partido en vivo", True, False, 830, 2),
    ("Copa del Mundo — Repeticion", "twitch", "diamondsleague",
     "https://www.twitch.tv/diamondsleague", "MUNDIAL", "Repeticion comentada", False, False, 0, 3),
    ("Champions de la Liga — Final", "twitch", "diamondsleague",
     "https://www.twitch.tv/diamondsleague", "CHAMPIONS", "Final de temporada", False, False, 0, 4),
]

DONATION_CHANNELS = [
    ("PayPal", "PayPal", "diamondsleague@paypal.me", "Enviar desde tu cuenta PayPal o tarjeta.", "PP", "#1bebf2", 1),
    ("Nequi", "Nequi", "300 123 4567", "Transferencia inmediata desde Colombia.", "NQ", "#a5ff00", 2),
    ("Alias bancario", "Transferencia", "TDL-2026-001", "Conserva el comprobante para validar el aporte.", "TB", "#f427b9", 3),
]

DONATIONS = [
    ("Anonimo diamonds", "Que siga la liga, se nota el esfuerso", 25.0, "PayPal"),
    ("Munoz", "Premio bien ganado crack", 15.0, "Nequi"),
    ("Comunidad Latam", "De nada, para los premios de la T3", 50.0, "PayPal"),
    ("St_fxx", "Apoyo al staff y a los servidores", 40.0, "Transferencia"),
    ("Gabinho", "Vamo D2", 10.0, "Nequi"),
]


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def round_robin(ids: list[int]):
    """Liga todos contra todos en una vuelta. Devuelve listas de journeys."""
    ids = list(ids)
    if len(ids) % 2:
        ids.append(None)
    rounds = []
    n = len(ids)
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = ids[i], ids[n - 1 - i]
            if r % 2:
                a, b = b, a
            if a is not None and b is not None:
                pairs.append((a, b))
        rounds.append(pairs)
        ids = [ids[0]] + [ids[-1]] + ids[1:-1]
    return rounds


def wipe() -> None:
    _clear()


def get_or_create(model, defaults: dict | None = None, **filters):
    row = model.query.filter_by(**filters).first()
    if row is None:
        row = model(**filters, **(defaults or {}))
        db.session.add(row)
    return row


# --------------------------------------------------------------------------- #
# Seed
# --------------------------------------------------------------------------- #
def seed_all(force: bool = False) -> None:
    admin = User.query.filter_by(username="admin").first()
    if admin is None:
        admin = User(username="admin", email="admin@diamondsleague.app", display_name="Administracion",
                     role=Role.ADMIN, is_admin=True, is_premium=True)
        admin.set_password("adminmascapito")
        db.session.add(admin)

    if Season.query.count() and not force:
        db.session.commit()
        print("La base ya tiene datos. Usa --force para recargar.")
        return

    if force:
        _clear()

    admin = db.session.merge(admin)

    # --- Temporada ---------------------------------------------------------- #
    season = get_or_create(Season, number=3, defaults={
        "name": "Temporada 3", "year": "2026", "is_current": True,
        "starts_on": date(2026, 8, 3), "ends_on": date(2026, 11, 30),
        "registration_opens": date(2026, 7, 27), "is_registration_open": True,
        "notes": "Temporada 3 con 2 divisiones, playoffs y dos ascensos.",
    })
    db.session.flush()

    prev = get_or_create(Season, number=2, defaults={
        "name": "Temporada 2", "year": "2025", "is_current": False,
        "starts_on": date(2025, 3, 11), "ends_on": date(2025, 8, 10),
    })
    prev.is_current = False
    db.session.flush()

    # --- Divisiones --------------------------------------------------------- #
    d1 = get_or_create(Division, key="division-one", defaults={
        "season_id": season.id, "name": "Division 1", "short": "D1", "level": 1,
        "teams_count": 12, "journeys_count": 11, "playoffs_slots": 4,
        "relegation_slots": 2, "promotion_slots": 0,
        "modality": "5 VS 5 · X5", "duration": "Dos tiempos de 10:00 + ultima jugada",
        "map_name": "5v5 Diamonds League", "server": "X Hosting", "tolerance": "15 minutos",
        "description": "La categoria principal se juega con 12 equipos, 11 jornadas y playoffs por el titulo.",
        "schedule_note": "11 jornadas, 66 partidos y dos dias de juego por jornada. Documento preparado por Ayala.",
    })
    d2 = get_or_create(Division, key="division-two", defaults={
        "season_id": season.id, "name": "Division 2", "short": "D2", "level": 2,
        "teams_count": 8, "journeys_count": 7, "playoffs_slots": 4,
        "relegation_slots": 0, "promotion_slots": 2,
        "modality": "5 VS 5", "duration": "Dos tiempos de 10:00 + ultima jugada",
        "map_name": "5v5 Diamonds League", "server": "X Hosting", "tolerance": "15 minutos",
        "description": "8 equipos, 7 jornadas, playoffs y dos ascensos a Division 1.",
        "schedule_note": "7 jornadas, 28 partidos y un partido por bloque.",
    })
    db.session.flush()

    _phases(d1, d2)
    _division_rules(d1, d2)
    _promotions(d1, d2)

    # --- Equipos y jugadores ------------------------------------------------ #
    d1_teams = _teams(d1, D1_TEAMS)
    d2_teams = _teams(d2, D2_TEAMS)
    db.session.flush()
    _players(d1_teams + d2_teams)

    # --- Tabla y calendario ------------------------------------------------- #
    _standings(d1, d1_teams)
    _standings(d2, d2_teams)
    _calendar(d1, d1_teams, start=date(2026, 8, 3))
    _calendar(d2, d2_teams, start=date(2026, 8, 4))

    # --- Salas publicas ----------------------------------------------------- #
    for order, (code, name, url, region, maxp, map_name, mode, ping, password, featured) in enumerate(ROOMS, start=1):
        get_or_create(Room, code=code, defaults={
            "name": name, "haxball_url": url, "region": region, "max_players": maxp,
            "map_name": map_name, "mode": mode, "ping": ping, "password": password,
            "is_open": True, "is_featured": featured, "is_pinned": order == 1, "sort_order": order,
            "description": f"Sala publica de entrenamiento {code}. Maximo {maxp} jugadores.",
        })

    # --- Museo -------------------------------------------------------------- #
    _museum()

    # --- Contenido editorial ------------------------------------------------ #
    _articles(admin)

    # --- Alianzas ----------------------------------------------------------- #
    for order, (emblem, name, code) in enumerate(PARTNERS, start=1):
        get_or_create(Alliance, name=name, defaults={
            "kind": "partner", "emblem": emblem, "code": code,
            "url": f"https://discord.gg/{code}", "status": "activa",
            "tagline": "Servidor aliado de The Diamonds League.",
            "description": "Enlace directo al servidor de Discord del partner.",
            "sort_order": order,
        })

    get_or_create(Alliance, name="RushBet", defaults={
        "kind": "affiliate", "emblem": "RB", "status": "proxima",
        "url": "https://discord.gg/kVAjgkeRsC",
        "tagline": "Diamonds League x RushBet",
        "description": ("Acuerdo de afiliacion firmado el 11 de marzo de 2026 con Duque, owner de RushBet. "
                        "La proxima afiliacion une a la liga latam con la liga colombiana."),
        "starts_on": date(2026, 3, 11), "is_featured": True, "sort_order": 0,
    })

    # --- Redes, staff, reglas ---------------------------------------------- #
    _socials()
    _staff()
    for scope, position, title, body in RULES:
        get_or_create(RuleEntry, scope=scope, position=position, title=title, body=body)

    for order, (name, color, items, note) in enumerate(SANCTIONS, start=1):
        get_or_create(SanctionLevel, name=name, defaults={
            "color": color, "items": items, "note": note, "sort_order": order,
        })

    # --- Live de futbol ----------------------------------------------------- #
    for title, platform, channel, watch, league, comp, live, featured, viewers, order in LIVE_STREAMS:
        get_or_create(LiveStream, title=title, defaults={
            "platform": platform, "channel": channel, "watch_url": watch,
            "league": league, "competition": comp, "is_live": live,
            "is_featured": featured, "viewers": viewers, "sort_order": order,
            "language": "es",
            "scheduled_at": utcnow() if live else None,
        })

    # --- Donacion ----------------------------------------------------------- #
    for label, method, account, note, icon, color, order in DONATION_CHANNELS:
        get_or_create(DonationChannel, label=label, defaults={
            "method": method, "account": account, "note": note, "icon": icon,
            "color": color, "is_active": True, "sort_order": order,
        })
    get_or_create(DonationGoal, title="Temporada 3 y premios", defaults={
        "description": "Meta para financiar servidores, premios y el desarrollo de la Temporada 3.",
        "target": 500.0, "is_active": True,
    })
    for offset, (donor, message, amount, channel) in enumerate(DONATIONS):
        get_or_create(Donation, donor_name=donor, defaults={
            "message": message, "amount": amount, "currency": "USD",
            "channel": channel, "is_public": True,
            "donated_at": utcnow() - timedelta(days=offset * 3 + 1),
        })

    db.session.commit()
    _summary()


def _clear() -> None:
    from models import ActivityLog
    for model in (Standing, Match, Player, Team, DivisionRule, PromotionSlot, Phase, Division,
                  Season, MuseumItem, Article, Alliance, SocialLink, StaffMember, RuleEntry,
                  SanctionLevel, LiveStream, Donation, DonationChannel, DonationGoal, Room,
                  ActivityLog):
        db.session.query(model).delete(synchronize_session=False)
    db.session.commit()


# --------------------------------------------------------------------------- #
# Sub-seeds
# --------------------------------------------------------------------------- #
def _phases(d1: Division, d2: Division) -> None:
    rows = [
        Phase(division_id=d1.id, order=1, tag="FASE 1", title="LIGA REGULAR",
              body="Todos contra todos durante 11 jornadas. Victoria 3 puntos, empate 1 punto y derrota 0 puntos.",
              highlight="Clasifican a playoffs los puestos 1, 2, 3 y 4."),
        Phase(division_id=d1.id, order=2, tag="FASE 2", title="PLAYOFFS",
              body="Semifinal 1: 1 vs 4. Semifinal 2: 2 vs 3.",
              highlight="Semifinales a un partido. Final de ida y vuelta."),
        Phase(division_id=d2.id, order=1, tag="LIGA", title="LIGA REGULAR",
              body="Todos contra todos durante 7 jornadas. Victoria 3 puntos, empate 1 punto y derrota 0 puntos.",
              highlight="Clasifican los puestos 1, 2, 3 y 4."),
        Phase(division_id=d2.id, order=2, tag="FASE FINAL", title="PLAYOFFS",
              body="2 vs 3 y 4 vs 1. Las semifinales son unicamente de ida.",
              highlight="La final se juega ida y vuelta."),
    ]
    db.session.add_all(rows)
    db.session.flush()


def _division_rules(d1: Division, d2: Division) -> None:
    common = [
        ("Tolerancia", "15 minutos antes de aplicar W.O."),
        ("W.O.", "Se aplica si un equipo no presenta minimo 4 jugadores."),
        ("Respeto", "Cero toxicidad durante los partidos y en los canales de la liga."),
        ("Resultado y replay", "Al terminar el partido es obligatorio enviar el resultado y la repeticion."),
    ]
    rows = [
        DivisionRule(division_id=d1.id, position=i, title=title, body=body)
        for i, (title, body) in enumerate(common, start=1)
    ]
    rows += [
        DivisionRule(division_id=d2.id, position=i, title=title, body=body)
        for i, (title, body) in enumerate(common[:3], start=1)
    ]
    db.session.add_all(rows)
    db.session.flush()


def _promotions(d1: Division, d2: Division) -> None:
    db.session.add_all([
        PromotionSlot(division_id=d1.id, kind="relegation", tag="11 LUGAR",
                      title="Descenso directo", body="Baja a Division 2 al terminar la liga regular."),
        PromotionSlot(division_id=d1.id, kind="relegation", tag="12 LUGAR",
                      title="Descenso directo", body="Baja a Division 2 al terminar la liga regular."),
        PromotionSlot(division_id=d2.id, kind="promotion", tag="PRIMER ASCENSO",
                      title="1 lugar de la liga", body="Ascenso directo a Division 1."),
        PromotionSlot(division_id=d2.id, kind="promotion", tag="SEGUNDO ASCENSO",
                      title="Ganador de los Playoffs", body="El campeon de playoffs siempre asciende."),
    ])
    db.session.flush()


def _teams(division: Division, rows) -> list[Team]:
    created = []
    for order, (name, short, coach, captain, country) in enumerate(rows, start=1):
        team = get_or_create(Team, name=name, defaults={
            "short": short, "slug": slugify(name), "division_id": division.id,
            "coach": coach, "captain": captain, "country": country,
            "founded_year": str(2020 + (order % 5)),
            "is_active": True, "sort_order": order,
            "description": f"{name} compite en {division.name} de The Diamonds League.",
            "color": ["#1bebf2", "#a5ff00", "#f427b9", "#ffffff"][order % 4],
        })
        created.append(team)
    db.session.flush()
    return created


def _players(teams: list[Team]) -> None:
    db.session.flush()
    for team in teams:
        stars = STAR_PLAYERS.get(team.name)
        if stars:
            for username, position, number, captain, matches, goals, assists, cs in stars:
                db.session.add(Player(
                    team_id=team.id, username=username, position=position, number=number,
                    is_captain=captain, is_active=True, matches=matches, goals=goals,
                    assists=assists, clean_sheets=cs,
                    clean_sheet_seconds=cs * 60 + 15 if cs else 0,
                    haxball_id=username.lower().replace(" ", ""), country=team.country,
                ))
            continue

        base = (hash(team.name) % 6)
        for i in range(5):
            position = ["GK", "DF", "MF", "FW", "MF"][i]
            username = FILLER_PLAYERS[(base + i) % len(FILLER_PLAYERS)]
            db.session.add(Player(
                team_id=team.id, username=username, position=position, number=i + 1,
                is_captain=(i == 0), is_active=True,
                matches=7, goals=max(0, (7 - i * 2 + base % 5)), assists=max(0, (5 - i + base % 3)),
                clean_sheets=2 if position == "GK" else 0,
                clean_sheet_seconds=120 if position == "GK" else 0,
                haxball_id=username.lower(), country=team.country,
            ))
    db.session.flush()


def _standings(division: Division, teams: list[Team]) -> None:
    for order, team in enumerate(teams, start=1):
        wins = max(0, 7 - order // 2)
        draws = 1 if order % 3 == 0 else 0
        row = Standing(division_id=division.id, team_id=team.id, won=wins, drawn=draws,
                       lost=max(0, 7 - wins - draws), goals_for=max(0, 14 - order),
                       goals_against=max(0, order), position=order)
        row.recompute()
        db.session.add(row)
    db.session.flush()


def _calendar(division: Division, teams: list[Team], start: date) -> None:
    ids = [t.id for t in teams]
    rounds = round_robin(ids)
    per_day = 3 if len(teams) > 8 else 2

    for j, pairs in enumerate(rounds, start=1):
        for d in range(2 if len(teams) > 8 else 1):
            day = start + timedelta(days=(j - 1) * 2 + d)
            slot = pairs[d * per_day:(d + 1) * per_day]
            for k, (home, away) in enumerate(slot):
                hour = 19 + d * 2 + k
                db.session.add(Match(
                    division_id=division.id, journey=j, stage="Liga regular", played_on=day,
                    kickoff=f"{hour % 24:02d}:{0 if k % 2 else 30:02d}",
                    home_team_id=home, away_team_id=away, status="scheduled",
                ))
    db.session.flush()


def _museum() -> None:
    teams = {t.name: t.id for t in Team.query.all()}
    order = 0
    for title, category, short, recipient, team_name, description, place, image in AWARD_ENTRIES + EXTRA_AWARDS:
        order += 1
        item = MuseumItem(
            title=title, slug=slugify(title), category=category, division_short=short,
            season_number=3 if category != "trofeos" else 2,
            recipient=recipient, team_id=teams.get(team_name), description=description,
            image=f"uploads/museo/{image}", place=place,
            awarded_on=date(2026, 6, 30) if category != "trofeos" or title.endswith("1") else date(2025, 8, 10),
            is_highlight=category in ("premios", "campeones"),
            sort_order=order,
        )
        db.session.add(item)
    db.session.flush()


def _articles(admin: User) -> None:
    now = utcnow()
    rows = [
        # --- Noticias ------------------------------------------------------- #
        (Category.NEWS, "general", "NUEVA PAGINA DE THE DIAMONDS LEAGUE",
         "Todo el contenido de la liga en un solo lugar.",
         "En esta pagina se reuniran los avisos, resultados, entrevistas y contenido de cada jornada de la liga.",
         "img/diamonds-logo.webp", True, True, 0),
        (Category.NEWS, "general", "RESUMEN DE JORNADA",
         "Resultados, marcadores y resumen de cada jornada.",
         "Aqui publicamos el resumen completo de cada jornada con marcadores, goleadores yHighlights.",
         None, False, False, 1),
        (Category.NEWS, "entrevista", "ENTREVISTAS",
         "Entrevistas con jugadores, capitanes y staff.",
         "Conversaciones con los responsables de cada club de la Division 1 y Division 2.",
         None, False, False, 2),
        (Category.NEWS, "eventos", "PREVIA DE LA JORNADA 9",
         "Lo que se viene este fin de semana en la liga.",
         "Analisis de los cruces y los probables y la cita que definiraa la tabla.",
         None, False, False, 3),
        (Category.NEWS, "premios", "MUÑOZ CABEZA DEL GOLEO",
         "38 goles en 7 partidos y el lleva la punta de la tabla.",
         "El delantero de Lexington sigue con una evolucion que nadie esperaba en esta Temporada 3.",
         None, False, False, 4),
        # --- Anuncios ------------------------------------------------------ #
        (Category.ANNOUNCEMENT, "premios", "PREMIOS DE LA TEMPORADA 2",
         "Ganadores de las principales categorias y clubes campeones.",
         "Se entregaron los ganadores del Balon de Oro, la Bota de Oro y el Guante de Oro de cada division.",
         None, True, True, 0),
        (Category.ANNOUNCEMENT, "inscripcion", "INSCRIPCIONES TEMPORADA 3",
         "Las inscripciones abren el lunes 27 de julio de 2026.",
         "Los equipos y jugadores interesados podran registrarse para participar desde la primera jornada. Cupos limitados.",
         None, True, True, 1),
        (Category.ANNOUNCEMENT, "sanciones", "ACTUALIZACION DEL REGLAMENTO",
         "Nuevas disposiciones para la Temporada 3.",
         "Seactualizan las reglas de conducta en Discord, el protocolo de W.O. y la escala de sanciones.",
         None, False, True, 2),
        (Category.ANNOUNCEMENT, "eventos", "AFILIACION CON RUSHBET",
         "La proxima afiliacion de la liga.",
         "Diamonds League y RushBet unen sus ligas. proximamente mas detalles del acuerdo.",
         None, False, True, 3),
        # --- Informes ------------------------------------------------------ #
        (Category.REPORT, "general", "INFORME DE JORNADA 8",
         "Metricas y estadisticas completas de la jornada 8.",
         "Goles, asistencias, clean sheets y el X5 Ideal de la jornada con todos los numeros.",
         None, False, False, 0),
        (Category.REPORT, "sanciones", "REGISTRO DISCIPLINARIO",
         "Sanciones aplicadas en la Temporada 3.",
         "Detalle de tarjetas, amonestaciones y suspensiones registradas por el staff.",
         None, False, False, 1),
        (Category.REPORT, "eventos", "REPORTE DE AFILIACION",
         "Documento del acuerdo con RushBet.",
         "Resumen del acuerdo, fecha de inicio y alcance de la afiliacion con la liga colombiana.",
         None, False, False, 2),
    ]

    for kind, category, title, summary, body, cover, featured, pinned, offset in rows:
        slug = slugify(title)
        if Article.query.filter_by(slug=slug).first():
            continue
        db.session.add(Article(
            kind=kind, category=category, title=title, slug=slug, summary=summary,
            body=body, cover=cover, is_featured=featured, is_pinned=pinned,
            is_published=True, published_at=now - timedelta(days=offset * 4),
            author_id=admin.id,
        ))
    db.session.flush()


def _socials() -> None:
    for platform, owner, label, handle, url, icon, primary, order in SOCIALS:
        get_or_create(SocialLink, url=url, defaults={
            "platform": platform, "owner": owner, "label": label, "handle": handle,
            "icon": icon, "is_primary": primary, "is_active": True, "sort_order": order,
        })
    db.session.flush()


def _staff() -> None:
    for name, username, role, title, bio, tags, leader, order in STAFF:
        get_or_create(StaffMember, name=name, defaults={
            "username": username, "role": role, "title": title, "bio": bio,
            "tags": tags, "is_leader": leader, "is_active": True, "sort_order": order,
            "discord": username,
        })
    db.session.flush()


def _summary() -> None:
    print("\n" + "=" * 58)
    print("  THE DIAMONDS LEAGUE — datos iniciales cargados")
    print("=" * 58)
    print(f"  Usuarios           : {User.query.count()}")
    print(f"  Temporadas         : {Season.query.count()}")
    print(f"  Divisiones         : {Division.query.count()}")
    print(f"  Equipos            : {Team.query.count()}")
    print(f"  Jugadores          : {Player.query.count()}")
    print(f"  Registros de tabla : {Standing.query.count()}")
    print(f"  Partidos           : {Match.query.count()}")
    print(f"  Salas PUBS         : {Room.query.count()}")
    print(f"  Piezas de museo    : {MuseumItem.query.count()}")
    print(f"  Articulos          : {Article.query.count()}")
    print(f"  Alianzas           : {Alliance.query.count()}")
    print(f"  Redes              : {SocialLink.query.count()}")
    print(f"  Staff              : {StaffMember.query.count()}")
    print(f"  Live de futbol     : {LiveStream.query.count()}")
    print("=" * 58)
    print("  Admin: admin / adminmascapito")
    print("=" * 58 + "\n")


if __name__ == "__main__":
    from app import app, db as _db

    with app.app_context():
        seed_all(force="--force" in __import__("sys").argv)