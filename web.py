"""
projectiri — NiceGUI Web App

Tarayıcıda açılan modern web arayüzü.
Tüm mevcut scriptleri arka planda subprocess olarak çalıştırır,
çıktıları canlı log paneline akıtır.

Çalıştır:  python web.py
Aç:        http://localhost:8080
"""

import os
import sys
import asyncio
import json
import plistlib
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from nicegui import ui, app

from curator import persona_listesi, PERSONAS

load_dotenv()

ROOT     = Path(__file__).parent
JSON_DIR = ROOT / "eksik_sarkilar"

# ─────────────────────────────────────────────
# MODÜL TANIMI
# ─────────────────────────────────────────────

MODULLER = {
    "personal": {
        "isim": "Personal Playlist",
        "alt":  "Mood + name meaning + zodiac",
        "ikon": "auto_awesome",
        "renk": "#1db954",
        "script": "kisisel_playlist.py",
    },
    "auto": {
        "isim": "Auto Genre Playlists",
        "alt":  "9 genres daily refresh",
        "ikon": "queue_music",
        "renk": "#4a9eff",
        "script": "oto_playlist.py",
    },
    "trend": {
        "isim": "Weekly Trend Playlists",
        "alt":  "Reddit + AI viral names",
        "ikon": "trending_up",
        "renk": "#f7b500",
        "script": "trend_playlist.py",
    },
    "tiktok": {
        "isim": "TikTok Video Generator",
        "alt":  "9:16 MP4 + auto-caption",
        "ikon": "videocam",
        "renk": "#ff4458",
        "script": "tiktok_uretici.py",
    },
    "missing": {
        "isim": "Missing Tracks Finder",
        "alt":  "Spotify ✕ YouTube ✕ MusicBrainz",
        "ikon": "search",
        "renk": "#a855f7",
        "script": "sanatci_eksik.py",
    },
    "yt_playlist": {
        "isim": "YouTube Playlist",
        "alt":  "Missing tracks → YT playlist",
        "ikon": "playlist_add",
        "renk": "#ff4458",
        "script": "yt_playlist_olustur.py",
    },
    "kapak": {
        "isim": "Fill Missing Covers",
        "alt":  "AI generate uncovered playlists",
        "ikon": "image",
        "renk": "#06b6d4",
        "script": "kapak_doldur.py",
    },
    "lock": {
        "isim": "Lock Down Playlists",
        "alt":  "Disable collaborative",
        "ikon": "lock",
        "renk": "#71717a",
        "script": "kapali_yap.py",
    },
}

# ─────────────────────────────────────────────
# SPOTIFY HESAP BİLGİSİ
# ─────────────────────────────────────────────

def hesap_bilgi():
    try:
        from spotify_auth import get_sp, kendi_playlistlerim
        sp = get_sp()
        me   = sp.current_user()
        mine = kendi_playlistlerim(sp, me["id"])
        return me["display_name"], len(mine), True
    except Exception:
        return "Offline", 0, False

# ─────────────────────────────────────────────
# TEMA — her sayfada ilk çağrıda enjekte edilir
# ─────────────────────────────────────────────

TEMA_CSS = """
<style>
  :root {
    --bg-0: #050505;
    --bg-1: #0a0a0a;
    --bg-2: #0f0f0f;
    --bg-3: #141414;
    --line: #1f1f1f;
    --text: #e6e6e6;
    --text-dim: #6b6b6b;
    --text-faint: #3a3a3a;
    --green: #1db954;
    --green-light: #1ed760;
  }
  body, html, .q-page-container, .q-page {
    background: var(--bg-1) !important;
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', sans-serif;
    margin: 0;
  }
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: var(--bg-0); }
  ::-webkit-scrollbar-thumb { background: var(--line); border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: var(--green); }

  .pi-card {
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: 12px;
    transition: all 0.2s ease;
  }
  .pi-card:hover {
    border-color: var(--green);
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(29, 185, 84, 0.1);
  }

  .pi-label {
    color: var(--text-faint);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 6px;
  }
  .pi-input .q-field__control,
  .pi-input .q-field__inner {
    background: var(--bg-0) !important;
    color: var(--text) !important;
    border-radius: 8px;
  }
  .pi-input .q-field__control:before { border-color: var(--line) !important; }
  .pi-input.q-field--focused .q-field__control:after { border-color: var(--green) !important; }
  .pi-input input, .pi-input .q-field__native { color: var(--text) !important; }

  .pi-nav-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    border-radius: 8px;
    color: var(--text-dim);
    cursor: pointer;
    transition: all 0.15s ease;
    border-left: 2px solid transparent;
    font-size: 14px;
  }
  .pi-nav-item:hover { background: var(--bg-2); color: var(--text); }
  .pi-nav-item.active {
    background: var(--bg-2);
    color: white;
    border-left-color: var(--green);
  }
  .pi-nav-icon { font-size: 18px; }

  .pi-log {
    background: var(--bg-0);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 16px;
    font-family: 'SF Mono', 'Menlo', monospace;
    font-size: 12px;
    color: #b0b0b0;
    overflow-y: auto;
    max-height: 500px;
    white-space: pre-wrap;
  }
  .pi-btn-primary {
    background: var(--green) !important;
    color: black !important;
    font-weight: 600;
    border-radius: 8px;
    text-transform: none;
    letter-spacing: 0;
  }
  .pi-btn-primary:hover { background: var(--green-light) !important; }
  .pi-btn-ghost {
    background: var(--bg-2) !important;
    color: var(--text-dim) !important;
    border: 1px solid var(--line);
    border-radius: 8px;
    text-transform: none;
  }
  .pi-btn-ghost:hover { color: var(--text) !important; border-color: var(--text-dim); }

  .pi-eyebrow {
    color: var(--green);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }
  .pi-title {
    color: white;
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin: 4px 0 8px;
  }
  .pi-subtitle {
    color: var(--text-dim);
    font-size: 14px;
  }
</style>
<link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
"""

def _tema_uygula():
    """Her sayfanın başında çağrılır — CSS + renkleri enjekte eder."""
    ui.colors(
        primary="#1db954",
        secondary="#1ed760",
        accent="#1db954",
        dark="#0a0a0a",
    )
    ui.add_head_html(TEMA_CSS)

# ─────────────────────────────────────────────
# LAYOUT — HEADER + SIDEBAR
# ─────────────────────────────────────────────

def layout(content_fn, active="home"):
    """Standart sayfa düzeni: header + sidebar + content."""
    _tema_uygula()
    adi, pl_sayi, ok = hesap_bilgi()

    with ui.row().classes("w-full h-screen no-wrap gap-0"):
        # ── SIDEBAR ──
        with ui.column().classes("w-60 h-full p-3 gap-1").style(
            "background:#050505; border-right:1px solid #1f1f1f;"
        ):
            # Brand
            with ui.column().classes("gap-0 mb-6 px-2 mt-2"):
                ui.label("projectiri").classes("text-xl font-bold text-white")
                ui.label("spotify automation").style("color:#3a3a3a; font-size:11px")

            # Nav items
            ui.label("MAIN").classes("pi-label mt-2 px-2")
            _nav_item("home",      "Dashboard",   "dashboard",   active)
            _nav_item("analytics", "Analytics",   "insights",    active)
            _nav_item("browser",   "Playlists",   "library_music", active)

            ui.label("MODULES").classes("pi-label mt-4 px-2")
            for kod, m in MODULLER.items():
                _nav_item(kod, m["isim"], m["ikon"], active)

            ui.label("SYSTEM").classes("pi-label mt-4 px-2")
            _nav_item("settings", "Settings",    "settings",    active)

            # Spacer push status to bottom
            ui.element("div").classes("flex-1")

            # Spotify status
            with ui.column().classes("gap-0 p-3 rounded").style(
                "background:#0a0a0a; border:1px solid #1f1f1f"
            ):
                renk = "#1db954" if ok else "#cc4444"
                with ui.row().classes("items-center gap-2"):
                    ui.label("●").style(f"color:{renk}")
                    ui.label(adi).classes("text-sm font-semibold")
                ui.label(f"{pl_sayi} playlist").style("color:#6b6b6b; font-size:12px")

        # ── MAIN ──
        with ui.column().classes("flex-1 h-full overflow-auto").style("background:#0a0a0a"):
            with ui.element("div").classes("p-8 max-w-5xl mx-auto w-full"):
                content_fn()

def _nav_item(route_id, label, icon, active):
    is_active = "active" if route_id == active else ""
    href      = "/" if route_id == "home" else f"/{route_id}"
    with ui.element("div").classes(f"pi-nav-item {is_active}").on(
        "click", lambda r=href: ui.navigate.to(r)
    ):
        ui.html(f'<span class="material-icons pi-nav-icon">{icon}</span>')
        ui.label(label)

# Material icons fontu zaten TEMA_CSS içinde

# ─────────────────────────────────────────────
# SUBPROCESS RUNNER (asenkron, log akışıyla)
# ─────────────────────────────────────────────

async def script_calistir(script: str, args: list, log_widget):
    """Subprocess'i çalıştır, stdout'u log_widget'a stream et.
    Widget kapatılırsa sessizce sonlandır."""

    def _push(msg):
        """Widget silinmişse hata fırlatmadan ignore et."""
        try:
            log_widget.push(msg)
        except Exception:
            pass

    def _notify(msg, tip="info"):
        try:
            ui.notify(msg, type=tip, position="top-right")
        except Exception:
            pass

    try:
        log_widget.clear()
    except Exception:
        return  # widget zaten silinmiş

    _push(f"$ python {script} {' '.join(args)}\n")
    komut = [sys.executable, "-u", str(ROOT / script)] + args
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *komut,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(ROOT),
        )
        async for raw in proc.stdout:
            satir = raw.decode("utf-8", errors="replace").rstrip()
            _push(satir)
        await proc.wait()
        if proc.returncode == 0:
            _push("\n✓ TAMAMLANDI")
            _notify("Tamamlandı", "positive")
        else:
            _push(f"\n✗ HATA (exit {proc.returncode})")
            _notify(f"Hata: exit {proc.returncode}", "negative")
    except asyncio.CancelledError:
        # Kullanıcı sayfa kapattı, subprocess'i temizle
        if proc and proc.returncode is None:
            try: proc.kill()
            except Exception: pass
        raise
    except Exception as e:
        _push(f"\n[HATA] {e}")
        _notify(str(e), "negative")

# ─────────────────────────────────────────────
# COMMON UI HELPERS
# ─────────────────────────────────────────────

def page_header(eyebrow, title, subtitle=""):
    ui.label(eyebrow).classes("pi-eyebrow")
    ui.label(title).classes("pi-title")
    if subtitle:
        ui.label(subtitle).classes("pi-subtitle")

def card(content_fn):
    with ui.element("div").classes("pi-card p-6 mb-4"):
        content_fn()

def log_panel():
    """Çıktı için Log widget'ı, push() ile satır eklenir."""
    lg = ui.log(max_lines=500).classes("pi-log w-full")
    return lg

# ─────────────────────────────────────────────
# SAYFA: DASHBOARD
# ─────────────────────────────────────────────

@ui.page("/")
def home_page():
    def content():
        page_header("OVERVIEW", "Dashboard", "Tüm modüllere hızlı erişim")

        with ui.grid(columns=2).classes("w-full gap-4 mt-4"):
            for kod, m in MODULLER.items():
                with ui.element("div").classes("pi-card p-5 cursor-pointer").on(
                    "click", lambda k=kod: ui.navigate.to(f"/{k}")
                ):
                    with ui.row().classes("items-start gap-4 no-wrap"):
                        ui.html(
                            f'<span class="material-icons" style="font-size:32px;color:{m["renk"]}">{m["ikon"]}</span>'
                        )
                        with ui.column().classes("gap-1 flex-1"):
                            ui.label(m["isim"]).classes("text-white font-semibold text-base")
                            ui.label(m["alt"]).style("color:#6b6b6b; font-size:13px")

    layout(content, active="home")

# ─────────────────────────────────────────────
# SAYFA: PERSONAL PLAYLIST
# ─────────────────────────────────────────────

@ui.page("/personal")
def personal_page():
    def content():
        m = MODULLER["personal"]
        page_header(m["alt"].upper(), m["isim"],
                    "İsim · doğum tarihi · ruh hali → AI tasarımı kişisel playlist + AI kapak")

        def render_form():
            isim    = ui.input("İsim", placeholder="örn. İrem").props("dark dense outlined").classes("pi-input w-full")
            dogum   = ui.input("Doğum Tarihi (GG.AA.YYYY)", placeholder="örn. 15.06.2002").props("dark dense outlined").classes("pi-input w-full mt-3")
            his     = ui.input("Ruh Hali / Tarif", placeholder="örn. yorgun ama mutluyum, biraz nostaljik").props("dark dense outlined").classes("pi-input w-full mt-3")
            persona_opts = {kod: f"{etk}" for kod, etk, _ in persona_listesi()}
            persona = ui.select(persona_opts, value="default", label="Küratör Persona").props("dark dense outlined").classes("pi-input w-full mt-3")

            async def submit():
                if not isim.value or not dogum.value or not his.value:
                    ui.notify("Tüm alanları doldur", type="warning", position="top-right")
                    return
                args = [
                    "--isim",    isim.value,
                    "--dogum",   dogum.value,
                    "--his",     his.value,
                    "--persona", persona.value,
                ]
                await script_calistir(m["script"], args, log)

            with ui.row().classes("gap-3 mt-5"):
                ui.button("Oluştur", on_click=submit).classes("pi-btn-primary")

        card(render_form)
        ui.label("ÇIKTI").classes("pi-label mt-6")
        log = log_panel()

    layout(content, active="personal")

# ─────────────────────────────────────────────
# SAYFA: MISSING TRACKS
# ─────────────────────────────────────────────

@ui.page("/missing")
def missing_page():
    def content():
        m = MODULLER["missing"]
        page_header(m["alt"].upper(), m["isim"],
                    "Sanatçının Spotify + MusicBrainz tam diskografisini YouTube ile karşılaştırır")

        def render_form():
            sanatcilar = ui.input(
                "Sanatçı(lar) — virgülle ayır",
                placeholder="örn. Şebnem Ferah, Mor ve Ötesi, Teoman"
            ).props("dark dense outlined").classes("pi-input w-full")

            async def submit():
                if not sanatcilar.value.strip():
                    ui.notify("En az 1 sanatçı gir", type="warning", position="top-right")
                    return
                liste = [s.strip() for s in sanatcilar.value.split(",") if s.strip()]
                tmp = ROOT / ".tmp_sanatcilar.txt"
                tmp.write_text("\n".join(liste))
                await script_calistir(m["script"], ["--dosya", str(tmp)], log)

            ui.button("Tara", on_click=submit).classes("pi-btn-primary mt-5")

        card(render_form)
        ui.label("ÇIKTI").classes("pi-label mt-6")
        log = log_panel()

    layout(content, active="missing")

# ─────────────────────────────────────────────
# SAYFA: YOUTUBE PLAYLIST FROM MISSING
# ─────────────────────────────────────────────

@ui.page("/yt_playlist")
def yt_playlist_page():
    def content():
        m = MODULLER["yt_playlist"]
        page_header(m["alt"].upper(), m["isim"],
                    "Bir JSON dosyası seç, içindeki videoları YouTube'da playlist olarak oluştur")

        def render_form():
            if not JSON_DIR.exists():
                ui.label("Önce Missing Tracks Finder çalıştır").style("color:#cc4444")
                return

            dosyalar = sorted(
                [f.name for f in JSON_DIR.iterdir() if f.suffix == ".json"],
                key=lambda n: (JSON_DIR / n).stat().st_mtime,
                reverse=True,
            )
            if not dosyalar:
                ui.label("eksik_sarkilar/ klasörü boş — önce Missing Tracks Finder çalıştır").style("color:#cc4444")
                return

            json_sel = ui.select(
                {d: d.replace(".json", "") for d in dosyalar},
                value=dosyalar[0],
                label="JSON dosyası"
            ).props("dark dense outlined").classes("pi-input w-full")

            gizli = ui.select(
                {"private": "Private (sadece sen)", "public": "Public (herkese açık)"},
                value="private", label="Gizlilik"
            ).props("dark dense outlined").classes("pi-input w-full mt-3")

            async def submit():
                args = ["--json", str(JSON_DIR / json_sel.value)]
                if gizli.value == "public":
                    args.append("--public")
                await script_calistir(m["script"], args, log)

            ui.button("Playlist Oluştur", on_click=submit).classes("pi-btn-primary mt-5")

        card(render_form)
        ui.label("ÇIKTI").classes("pi-label mt-6")
        log = log_panel()

    layout(content, active="yt_playlist")

# ─────────────────────────────────────────────
# SAYFA: TIKTOK
# ─────────────────────────────────────────────

@ui.page("/tiktok")
def tiktok_page():
    def content():
        m = MODULLER["tiktok"]
        page_header(m["alt"].upper(), m["isim"],
                    "Playlist'ten 1080×1920 MP4 + caption üretir, TikTok'a yüklemeye hazır")

        def render_form():
            sayi = ui.input("Kaç video?", value="1").props("dark dense outlined").classes("pi-input w-full")
            pl   = ui.input("Belirli playlist (boş = rastgele)",
                            placeholder="örn. DARK DRIVE").props("dark dense outlined").classes("pi-input w-full mt-3")

            async def submit():
                args = ["--sayi", sayi.value or "1"]
                if pl.value.strip():
                    args += ["--playlist", pl.value.strip()]
                await script_calistir(m["script"], args, log)

            ui.button("Üret", on_click=submit).classes("pi-btn-primary mt-5")

        card(render_form)
        ui.label("ÇIKTI").classes("pi-label mt-6")
        log = log_panel()

    layout(content, active="tiktok")

# ─────────────────────────────────────────────
# SAYFA: BASİT ÇALIŞTIRICILAR (auto / trend / kapak / lock)
# ─────────────────────────────────────────────

def basit_sayfa(kod):
    @ui.page(f"/{kod}")
    def _page():
        def content():
            m = MODULLER[kod]
            page_header(m["alt"].upper(), m["isim"],
                        "Tek tıkla başlat — modül kendi mantığını çalıştırır")

            log_ref = {"log": None}

            async def submit():
                await script_calistir(m["script"], [], log_ref["log"])

            def render():
                ui.button(f"Başlat — {m['isim']}", on_click=submit).classes("pi-btn-primary")

            card(render)
            ui.label("ÇIKTI").classes("pi-label mt-6")
            log_ref["log"] = log_panel()

        layout(content, active=kod)

for k in ["auto", "trend", "kapak", "lock"]:
    basit_sayfa(k)

# ─────────────────────────────────────────────
# SAYFA: ANALYTICS DASHBOARD
# ─────────────────────────────────────────────

@ui.page("/analytics")
def analytics_page():
    import analitik

    def content():
        page_header("INSIGHTS", "Analytics", "Playlist'lerinin büyümesini izle")

        # Snapshot butonu
        async def snapshot_al_async():
            with ui.dialog() as d, ui.card().classes("pi-card p-4"):
                ui.label("Snapshot alınıyor...").classes("text-white")
                spinner = ui.spinner(color="primary")
            d.open()
            try:
                # Subprocess'de çalıştır
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, "-u", str(ROOT / "analitik.py"), "snapshot",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=str(ROOT),
                )
                await proc.wait()
                ui.notify("Snapshot kaydedildi", type="positive", position="top-right")
            finally:
                d.close()
                ui.navigate.reload()

        with ui.row().classes("gap-3 mb-4"):
            ui.button("Yeni Snapshot Al", icon="camera_alt",
                      on_click=snapshot_al_async).classes("pi-btn-primary")

        # Özet istatistik
        try:
            stat = analitik.toplam_istatistik()
        except Exception:
            stat = {"playlist_sayisi": 0, "toplam_takipci": 0, "toplam_sarki": 0, "en_buyuk": None}

        with ui.grid(columns=3).classes("w-full gap-4 mb-6"):
            for etk, deger in [
                ("PLAYLIST",  stat["playlist_sayisi"]),
                ("TAKİPÇİ",   stat["toplam_takipci"]),
                ("ŞARKI",     stat["toplam_sarki"]),
            ]:
                with ui.element("div").classes("pi-card p-5"):
                    ui.label(etk).classes("pi-label")
                    ui.label(str(deger)).classes("text-3xl font-bold text-white mt-1")

        # Tablo
        rows = []
        try:
            for r in analitik.son_snapshot():
                buyume = analitik.buyume_skoru(r["playlist_id"], gun=7)
                rows.append({
                    "isim":    r["playlist_name"][:50],
                    "takipci": r["followers"] or 0,
                    "sarki":   r["track_count"] or 0,
                    "buyume":  f"+{buyume}" if buyume > 0 else str(buyume),
                    "guncel":  r["timestamp"][:16].replace("T", " "),
                })
        except Exception:
            pass

        if rows:
            ui.label("PLAYLIST PERFORMANSI").classes("pi-label mb-2")
            ui.table(
                columns=[
                    {"name": "isim",    "label": "Playlist",  "field": "isim",    "align": "left"},
                    {"name": "takipci", "label": "Takipçi",   "field": "takipci", "align": "right"},
                    {"name": "sarki",   "label": "Şarkı",     "field": "sarki",   "align": "right"},
                    {"name": "buyume",  "label": "7g Δ",      "field": "buyume",  "align": "right"},
                    {"name": "guncel",  "label": "Güncel",    "field": "guncel",  "align": "right"},
                ],
                rows=rows,
                pagination=20,
            ).props("dark dense flat").classes("w-full")
        else:
            with ui.element("div").classes("pi-card p-8 text-center"):
                ui.label("Henüz veri yok. 'Yeni Snapshot Al' tıkla.").style("color:#6b6b6b")

    layout(content, active="analytics")

# ─────────────────────────────────────────────
# SAYFA: PLAYLIST BROWSER
# ─────────────────────────────────────────────

@ui.page("/browser")
def browser_page():
    def content():
        page_header("LIBRARY", "Playlists", "Tüm playlist'lerin tek ekranda")

        # Spotify'dan playlist'leri çek
        try:
            from spotify_auth import get_sp, kendi_playlistlerim
            sp   = get_sp()
            me   = sp.current_user()
            mine = kendi_playlistlerim(sp, me["id"])
        except Exception as e:
            ui.label(f"Spotify bağlantı hatası: {e}").style("color:#cc4444")
            return

        # Arama
        search = {"q": ""}

        def render_grid():
            grid.clear()
            with grid:
                with ui.grid(columns=3).classes("w-full gap-4"):
                    for p in mine:
                        if search["q"].lower() not in p["name"].lower():
                            continue
                        imgs  = p.get("images") or []
                        cover = imgs[0]["url"] if imgs else None
                        sp_url = p["external_urls"]["spotify"]
                        with ui.element("div").classes(
                            "pi-card overflow-hidden cursor-pointer"
                        ).on("click", lambda u=sp_url: ui.navigate.to(u)):
                            if cover:
                                ui.html(
                                    f'<img src="{cover}" style="width:100%;height:200px;object-fit:cover;display:block"/>'
                                )
                            else:
                                ui.element("div").style(
                                    "width:100%;height:200px;background:linear-gradient(135deg,#1db954,#0a0a0a)"
                                )
                            with ui.column().classes("p-4 gap-1"):
                                ui.label(p["name"][:40]).classes("text-white font-semibold text-sm")
                                ad = "Public" if p.get("public") else "Private"
                                ui.label(ad).style("color:#6b6b6b; font-size:11px")

        # Arama input'u
        def on_search(e):
            search["q"] = e.value or ""
            render_grid()

        ui.input("Ara", placeholder="playlist adı...",
                 on_change=on_search).props("dark dense outlined").classes("pi-input w-full mb-4")

        grid = ui.element("div").classes("w-full")
        render_grid()

    layout(content, active="browser")

# ─────────────────────────────────────────────
# SAYFA: SETTINGS
# ─────────────────────────────────────────────

@ui.page("/settings")
def settings_page():
    def content():
        page_header("CONFIG", "Settings", "API'ler, zamanlama, persona")

        # ── .env editörü ──
        ui.label("API KEYS & ENVIRONMENT").classes("pi-label mt-2")

        env_path = ROOT / ".env"
        env_data = {}
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    env_data[k.strip()] = v.strip()

        SECRET = {"SPOTIPY_CLIENT_SECRET", "GROQ_API_KEY", "GOOGLE_API_KEY",
                  "YOUTUBE_API_KEY", "GOOGLE_CLIENT_SECRET"}

        def mask(v):
            if not v or len(v) < 8: return v
            return v[:4] + "•" * (len(v) - 8) + v[-4:]

        with ui.element("div").classes("pi-card p-5"):
            inputs = {}
            for k, v in env_data.items():
                show_value = mask(v) if k in SECRET else v
                inp = ui.input(k, value=show_value).props("dark dense outlined").classes("pi-input w-full mb-2")
                inputs[k] = (inp, v, k in SECRET)

            def kaydet():
                yeni_satirlar = []
                for k, (inp, eski, gizli) in inputs.items():
                    deger = inp.value
                    # Eğer gizliyse ve hâlâ maskelenmiş haldeyse → değiştirme
                    if gizli and "•" in deger:
                        deger = eski
                    yeni_satirlar.append(f"{k}={deger}")
                env_path.write_text("\n".join(yeni_satirlar) + "\n")
                ui.notify(".env güncellendi", type="positive", position="top-right")

            ui.button("Kaydet", on_click=kaydet).classes("pi-btn-primary mt-3")

        # ── Zamanlanmış işler (launchd) ──
        # cron macOS'ta Masaüstü'ne erişemediği için tetiklenmiyordu;
        # işler ~/Library/LaunchAgents altındaki launchd ajanlarına taşındı.
        ui.label("SCHEDULED JOBS").classes("pi-label mt-6")

        GUNLER = {0: "Pazar", 1: "Pazartesi", 2: "Salı", 3: "Çarşamba",
                  4: "Perşembe", 5: "Cuma", 6: "Cumartesi"}

        def zaman_metni(takvim):
            if isinstance(takvim, dict):
                takvim = [takvim]
            parcalar = []
            for t in takvim or []:
                gun = GUNLER.get(t.get("Weekday"), "her gün")
                parcalar.append(f"{gun} {t.get('Hour', 0):02d}:{t.get('Minute', 0):02d}")
            return " · ".join(parcalar) or "tetikleyici yok"

        try:
            yuklu   = subprocess.run(["launchctl", "list"], capture_output=True, text=True).stdout
            ajanlar = sorted((Path.home() / "Library/LaunchAgents").glob("com.iri.projectiri.*.plist"))
        except Exception:
            yuklu, ajanlar = "", []

        with ui.element("div").classes("pi-card p-5"):
            if ajanlar:
                for yol in ajanlar:
                    try:
                        with open(yol, "rb") as f:
                            ajan = plistlib.load(f)
                    except Exception:
                        continue
                    etiket = ajan.get("Label", yol.stem)
                    komut  = " ".join(Path(a).name for a in ajan.get("ProgramArguments", [])[1:])
                    aktif  = etiket in yuklu
                    with ui.row().classes("items-center justify-between mb-2"):
                        with ui.column().classes("gap-0"):
                            ui.label(zaman_metni(ajan.get("StartCalendarInterval"))).style(
                                "color:#1db954; font-family:monospace; font-size:13px")
                            ui.label(f"{komut} · {etiket}").style("color:#6b6b6b; font-size:12px")
                        ui.icon("check_circle" if aktif else "error_outline").style(
                            f"color:{'#1db954' if aktif else '#cc4444'}")
            else:
                ui.label("Zamanlanmış iş tanımlı değil").style("color:#6b6b6b")

        # ── Persona açıklamaları ──
        ui.label("CURATOR PERSONAS").classes("pi-label mt-6")
        with ui.element("div").classes("pi-card p-5"):
            for kod, etk, ack in persona_listesi():
                with ui.row().classes("items-start justify-between mb-3"):
                    with ui.column().classes("gap-0"):
                        ui.label(etk).classes("text-white font-semibold text-sm")
                        ui.label(ack).style("color:#6b6b6b; font-size:13px")
                    p = PERSONAS[kod]
                    detay = f"Pop {p['min_popularity']}-{p['max_popularity']} · {p['min_yil']}+"
                    if "max_yil" in p:
                        detay = f"Pop {p['min_popularity']}-{p['max_popularity']} · {p['min_yil']}-{p['max_yil']}"
                    ui.label(detay).style("color:#3a3a3a; font-family:monospace; font-size:11px")

    layout(content, active="settings")

# ─────────────────────────────────────────────
# ÇALIŞTIR
# ─────────────────────────────────────────────

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="projectiri",
        port=8080,
        favicon="🎵",
        dark=True,
        reload=False,
        show=True,           # Tarayıcıyı otomatik aç
        storage_secret="projectiri-local-secret",
    )
