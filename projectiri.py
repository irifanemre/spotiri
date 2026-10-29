"""
projectiri — Premium Spotify Otomasyon Uygulaması
Tam donanımlı Textual TUI: input modal'ları, log streaming, results paneli.
Hiçbir aksiyon terminale dönmez — her şey app içinde.
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container, VerticalScroll
from textual.widgets import Static, ListView, ListItem, Footer, Input, Log, Button, Select
from textual.reactive import reactive
from textual.screen import ModalScreen

from curator import persona_listesi, cache_stats

load_dotenv()

sys.stdout.write("\033]0;projectiri\007")
sys.stdout.flush()

ROOT = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────
# MODÜL TANIMI
# ─────────────────────────────────────────────

MODULLER = [
    {
        "kod": "personal",  "no": "01",  "ikon": "✦",
        "isim": "Personal Playlist",
        "altbaslik": "AI · Mood + name meaning",
        "aciklama": "İsim, yaş ve ruh haline göre kişiselleştirilmiş bir playlist üretir. İsmin sembolik anlamından AI kapak tasarımı çizilir.",
        "script": "kisisel_playlist.py",
        "input": "personal",
    },
    {
        "kod": "auto",  "no": "02",  "ikon": "◆",
        "isim": "Auto Genre Playlists",
        "altbaslik": "Daily · 9 genres refreshed",
        "aciklama": "DARK DRIVE, GOLDEN HOUR, FUEGO, İSTANBUL GECELERİ ve diğer 5 tür hit skoru sıralı şekilde günceller.",
        "script": "oto_playlist.py",
        "input": "confirm",
    },
    {
        "kod": "trend",  "no": "03",  "ikon": "⬡",
        "isim": "Weekly Trend Playlists",
        "altbaslik": "Reddit + AI · 6 viral playlists",
        "aciklama": "Reddit'ten güncel trendler toplanır, Groq ile yaratıcı playlist isimleri üretilir ve AI kapaklarıyla yayınlanır.",
        "script": "trend_playlist.py",
        "input": "confirm",
    },
    {
        "kod": "tiktok",  "no": "04",  "ikon": "▷",
        "isim": "TikTok Video Generator",
        "altbaslik": "MP4 · 9:16 · auto-caption",
        "aciklama": "Playlist'ten 1080×1920 tanıtım videosu üretir. Caption + hashtag dahil — sadece yüklemen gerek.",
        "script": "tiktok_uretici.py",
        "input": "tiktok",
    },
    {
        "kod": "kapak",  "no": "05",  "ikon": "◐",
        "isim": "Fill Missing Covers",
        "altbaslik": "AI · scan + generate",
        "aciklama": "Kapağı eksik tüm playlist'leri tarar, türe göre Pillow gradient veya AI üretici (Pollinations) ile kapak yükler.",
        "script": "kapak_doldur.py",
        "input": "confirm",
    },
    {
        "kod": "lock",  "no": "06",  "ikon": "◇",
        "isim": "Lock Down Playlists",
        "altbaslik": "Privacy · collaborative = false",
        "aciklama": "Tüm playlist'lerin işbirliği özelliğini kapatır. Public kalır ama dışarıdan kimse ekleme yapamaz.",
        "script": "kapali_yap.py",
        "input": "confirm",
    },
    {
        "kod": "missing",  "no": "07",  "ikon": "⌖",
        "isim": "Missing Tracks Finder",
        "altbaslik": "Spotify ✕ YouTube · cross-reference",
        "aciklama": "Sanatçının Spotify diskografisini YouTube'da view'a göre sıralı geniş aramayla karşılaştırır. Spotify'da olmayan en popüler parçaları listeler. JSON'a kaydeder.",
        "script": "sanatci_eksik.py",
        "input": "missing",
    },
    {
        "kod": "yt_playlist",  "no": "08",  "ikon": "▸",
        "isim": "YouTube Playlist from Missing",
        "altbaslik": "Eksik şarkıları YT playlist'e",
        "aciklama": "eksik_sarkilar/ klasöründeki bir JSON'u seçer, içindeki tüm videoları senin YouTube hesabında özel playlist olarak oluşturur. İlk kullanımda OAuth izni ister.",
        "script": "yt_playlist_olustur.py",
        "input": "yt_playlist",
    },
]

# ─────────────────────────────────────────────
# SPOTIFY HESAP BİLGİSİ
# ─────────────────────────────────────────────

def hesap_bilgi():
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            scope="playlist-read-private user-read-private",
            cache_path=os.path.join(ROOT, ".cache")
        ))
        me      = sp.current_user()
        pl_resp = sp.current_user_playlists(limit=50)
        mine    = [p for p in pl_resp["items"] if p and p["owner"]["id"] == me["id"]]
        return me["display_name"], len(mine)
    except Exception:
        return None, 0

# ─────────────────────────────────────────────
# MODAL EKRANLAR
# ─────────────────────────────────────────────

class BaseModal(ModalScreen[dict]):
    """Tüm modal'lar için ortak temel."""
    BINDINGS = [
        Binding("escape", "cancel", "İptal"),
    ]

    def action_cancel(self) -> None:
        self.dismiss(None)


class PersonalInputModal(BaseModal):
    """Kişisel playlist için: isim + yaş + mood"""

    def compose(self) -> ComposeResult:
        with Container(classes="modal-box"):
            yield Static("PERSONAL PLAYLIST", classes="modal-eyebrow")
            yield Static("Sana özel bir mood haritası", classes="modal-title")
            yield Static(
                "İsmin · yaşın · ne hissediyorsun? AI bunları okuyup ismin sembolik "
                "anlamıyla harmanlayarak playlist + AI kapak üretir.",
                classes="modal-desc"
            )

            yield Static("İSİM", classes="field-label")
            yield Input(placeholder="örn. İrem", id="f-isim", classes="field-input")

            yield Static("DOĞUM TARİHİ  (GG.AA.YYYY)", classes="field-label")
            yield Input(placeholder="örn. 15.06.2002", id="f-dogum", classes="field-input")

            yield Static("RUH HALİ / TARİF", classes="field-label")
            yield Input(
                placeholder="örn. yorgun ama mutluyum, biraz nostaljik",
                id="f-his", classes="field-input"
            )

            yield Static("KÜRATÖR PERSONA", classes="field-label")
            persona_opts = [(f"{etk} — {ack}", kod) for kod, etk, ack in persona_listesi()]
            yield Select(persona_opts, id="f-persona", value="default", allow_blank=False)

            with Horizontal(classes="modal-actions"):
                yield Button("İptal", id="cancel-btn", classes="btn-ghost")
                yield Button("Oluştur", id="submit-btn", classes="btn-primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "submit-btn":
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Son alandayken enter basılırsa gönder
        if event.input.id == "f-his":
            self._submit()

    def _submit(self) -> None:
        from burc import tarih_parse
        isim    = self.query_one("#f-isim",    Input).value.strip()
        dogum   = self.query_one("#f-dogum",   Input).value.strip()
        his     = self.query_one("#f-his",     Input).value.strip()
        persona = self.query_one("#f-persona", Select).value or "default"

        if not isim or not dogum or not his:
            self.app.bell()
            return

        # Doğum tarihini validate et
        if tarih_parse(dogum) is None:
            self.app.bell()
            return

        self.dismiss({"isim": isim, "dogum": dogum, "his": his, "persona": persona})


class MissingTracksModal(BaseModal):
    """Sanatçı seçimi — tek sanatçı veya dosyadan liste"""

    def compose(self) -> ComposeResult:
        with Container(classes="modal-box"):
            yield Static("MISSING TRACKS FINDER", classes="modal-eyebrow")
            yield Static("Spotify'da olmayan YouTube şarkıları", classes="modal-title")
            yield Static(
                "Tek sanatçı adı gir veya birden fazla sanatçı için "
                "virgülle ayırarak yaz. Sonuç: eksik_sarkilar/ klasörüne JSON.",
                classes="modal-desc"
            )

            yield Static("SANATÇI(LAR)  ·  virgülle ayır", classes="field-label")
            yield Input(
                placeholder="örn. Tarkan veya Tarkan, Sezen Aksu, Mor ve Ötesi",
                id="f-sanatcilar", classes="field-input"
            )

            with Horizontal(classes="modal-actions"):
                yield Button("İptal", id="cancel-btn", classes="btn-ghost")
                yield Button("Tara", id="submit-btn", classes="btn-primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "submit-btn":
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        ham  = self.query_one("#f-sanatcilar", Input).value.strip()
        if not ham:
            self.app.bell()
            return
        sanatcilar = [s.strip() for s in ham.split(",") if s.strip()]
        self.dismiss({"sanatcilar": sanatcilar})


class YTPlaylistModal(BaseModal):
    """eksik_sarkilar/ klasöründen JSON seçimi"""

    def compose(self) -> ComposeResult:
        with Container(classes="modal-box"):
            yield Static("YOUTUBE PLAYLIST", classes="modal-eyebrow")
            yield Static("Eksik şarkıları YT'a aktar", classes="modal-title")
            yield Static(
                "eksik_sarkilar/ klasöründeki JSON dosyasını seç. "
                "İçindeki tüm videolar senin YouTube hesabında "
                "özel playlist olarak oluşturulur.",
                classes="modal-desc"
            )

            json_dir = os.path.join(ROOT, "eksik_sarkilar")
            dosyalar = []
            if os.path.isdir(json_dir):
                dosyalar = sorted(
                    [f for f in os.listdir(json_dir) if f.endswith(".json")],
                    key=lambda f: os.path.getmtime(os.path.join(json_dir, f)),
                    reverse=True,
                )

            if not dosyalar:
                yield Static(
                    "[#cc4444]Klasör boş — önce Missing Tracks Finder çalıştır.[/]",
                    classes="field-label"
                )
            else:
                yield Static("JSON DOSYASI", classes="field-label")
                opts = [(d.replace(".json", ""), d) for d in dosyalar]
                yield Select(opts, id="f-json", value=dosyalar[0], allow_blank=False)

                yield Static("PLAYLIST GİZLİLİĞİ", classes="field-label")
                yield Select(
                    [("Private (sadece sen)", "private"),
                     ("Public (herkese açık)", "public")],
                    id="f-public", value="private", allow_blank=False
                )

            with Horizontal(classes="modal-actions"):
                yield Button("İptal", id="cancel-btn", classes="btn-ghost")
                if dosyalar:
                    yield Button("Oluştur", id="submit-btn", classes="btn-primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "submit-btn":
            try:
                dosya = self.query_one("#f-json",   Select).value
                gizli = self.query_one("#f-public", Select).value
            except Exception:
                self.app.bell()
                return
            self.dismiss({"json": dosya, "public": gizli == "public"})


class TikTokInputModal(BaseModal):
    def compose(self) -> ComposeResult:
        with Container(classes="modal-box"):
            yield Static("TIKTOK VIDEO", classes="modal-eyebrow")
            yield Static("Tanıtım videosu üretici", classes="modal-title")
            yield Static(
                "Playlist'lerinden 9:16 MP4 + caption üretir. Hazırı TikTok'a yüklersin.",
                classes="modal-desc"
            )

            yield Static("KAÇ VİDEO?", classes="field-label")
            yield Input(value="1", id="f-sayi", classes="field-input")

            yield Static("BELİRLİ PLAYLİST? (boş = rastgele)", classes="field-label")
            yield Input(placeholder="örn. DARK DRIVE", id="f-pl", classes="field-input")

            with Horizontal(classes="modal-actions"):
                yield Button("İptal", id="cancel-btn", classes="btn-ghost")
                yield Button("Üret", id="submit-btn", classes="btn-primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "submit-btn":
            sayi = self.query_one("#f-sayi", Input).value or "1"
            pl   = self.query_one("#f-pl",   Input).value or ""
            self.dismiss({"sayi": sayi, "playlist": pl})


class ConfirmModal(BaseModal):
    def __init__(self, baslik: str, mesaj: str):
        super().__init__()
        self.baslik = baslik
        self.mesaj  = mesaj

    def compose(self) -> ComposeResult:
        with Container(classes="modal-box"):
            yield Static("ONAY", classes="modal-eyebrow")
            yield Static(self.baslik, classes="modal-title")
            yield Static(self.mesaj, classes="modal-desc")
            with Horizontal(classes="modal-actions"):
                yield Button("İptal", id="cancel-btn", classes="btn-ghost")
                yield Button("Başlat", id="submit-btn", classes="btn-primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "submit-btn":
            self.dismiss({"onay": True})


# ─────────────────────────────────────────────
# ANA UYGULAMA
# ─────────────────────────────────────────────

class ProjectiriApp(App):
    CSS = """
    Screen { background: #0a0a0a; color: #e6e6e6; }

    /* ── HEADER ── */
    #header-bar {
        height: 4; padding: 1 4;
        border-bottom: solid #1a1a1a;
    }
    #brand-stack { width: 1fr; }
    #brand        { color: #ffffff; text-style: bold; }
    #brand-sub    { color: #4a4a4a; }
    #account-info { color: #6b6b6b; text-align: right; width: auto; }

    /* ── BODY ── */
    #body { layout: horizontal; height: 1fr; }

    #sidebar {
        width: 42;
        background: #050505;
        border-right: solid #1a1a1a;
        padding: 1 0;
    }
    #sidebar-title {
        color: #4a4a4a;
        padding: 1 3 1 3;
        text-style: bold;
    }
    ListView           { background: #050505; }
    ListView:focus     { background: #050505; }
    ListItem {
        padding: 1 3;
        background: #050505;
        color: #888888;
        border-left: solid #050505;
    }
    ListItem.--highlight {
        background: #0f0f0f;
        color: #ffffff;
        border-left: solid #1db954;
    }
    ListItem:hover { background: #0a0a0a; }

    /* ── MAIN PANEL ── */
    #main-panel { width: 1fr; padding: 3 6; background: #0a0a0a; }
    .module-eyebrow { color: #1db954; text-style: bold; margin-bottom: 1; }
    .module-title   { color: #ffffff; text-style: bold; }
    .module-subtitle{ color: #6b6b6b; margin-bottom: 2; }
    .module-description { color: #b0b0b0; margin-bottom: 3; }
    .module-meta-label  { color: #4a4a4a; }
    .module-meta-value  { color: #888888; }
    .cta-bar {
        margin-top: 3;
        padding: 1 2;
        background: #0f0f0f;
        border-left: solid #1db954;
        color: #d0d0d0;
    }
    .cta-key { color: #1db954; text-style: bold; }

    /* ── LOG (çalışma sırasında) ── */
    #log-panel {
        background: #050505;
        border: solid #1a1a1a;
        height: 1fr;
        margin-top: 2;
    }
    Log {
        background: #050505;
        color: #b0b0b0;
        scrollbar-color: #1db954 #050505;
    }
    .log-status {
        color: #1db954;
        text-style: bold;
        padding: 1 2;
        background: #0a0a0a;
    }
    .log-status-done    { color: #1db954; }
    .log-status-running { color: #d4a017; }
    .log-status-error   { color: #cc4444; }

    /* ── MODAL ── */
    BaseModal { align: center middle; }
    .modal-box {
        background: #0f0f0f;
        border: solid #1f1f1f;
        padding: 2 3;
        width: 64;
        height: auto;
    }
    .modal-eyebrow { color: #1db954; text-style: bold; margin-bottom: 1; }
    .modal-title   { color: #ffffff; text-style: bold; margin-bottom: 1; }
    .modal-desc    { color: #6b6b6b; margin-bottom: 2; }
    .field-label   { color: #4a4a4a; text-style: bold; margin-top: 1; }
    .field-input {
        background: #050505; color: #ffffff;
        border: solid #1f1f1f;
        margin-top: 0;
    }
    .field-input:focus { border: solid #1db954; }

    Select {
        background: #050505;
        color: #ffffff;
        border: solid #1f1f1f;
    }
    Select:focus { border: solid #1db954; }
    Select > SelectCurrent {
        background: #050505;
        color: #ffffff;
    }
    Select OptionList {
        background: #0f0f0f;
        color: #d0d0d0;
        border: solid #1db954;
    }

    .modal-actions { margin-top: 2; height: 3; align: right middle; }
    .btn-primary {
        background: #1db954; color: #000000;
        text-style: bold;
        border: none; margin-left: 2;
    }
    .btn-primary:hover { background: #1ed760; }
    .btn-ghost {
        background: #0f0f0f; color: #888888;
        border: solid #2a2a2a;
    }
    .btn-ghost:hover { background: #1a1a1a; color: #d0d0d0; }

    /* ── FOOTER ── */
    Footer { background: #050505; color: #4a4a4a; }
    Footer > .footer--key { color: #1db954; }
    """

    BINDINGS = [
        Binding("q",      "quit",          "Quit",   priority=True),
        Binding("enter",  "run_selected",  "Run"),
        Binding("escape", "back_to_menu",  "Back"),
        Binding("up",     "cursor_up",     "↑", show=False),
        Binding("down",   "cursor_down",   "↓", show=False),
        Binding("j",      "cursor_down",   "↓", show=False),
        Binding("k",      "cursor_up",     "↑", show=False),
    ]

    secili_indeks: reactive[int] = reactive(0)
    calisiyor: reactive[bool]    = reactive(False)

    def compose(self) -> ComposeResult:
        with Container(id="root"):
            # Header
            with Horizontal(id="header-bar"):
                with Vertical(id="brand-stack"):
                    yield Static("projectiri", id="brand")
                    yield Static("spotify automation suite", id="brand-sub")
                yield Static(self._hesap_metni(), id="account-info")

            # Body
            with Horizontal(id="body"):
                with Vertical(id="sidebar"):
                    yield Static("MODÜLLER", id="sidebar-title")
                    items = []
                    for m in MODULLER:
                        items.append(ListItem(
                            Static(
                                f"[#4a4a4a]{m['no']}[/]   [#888]{m['ikon']}[/]  "
                                f"[bold]{m['isim']}[/]\n"
                                f"            [#3a3a3a]{m['altbaslik']}[/]"
                            )
                        ))
                    yield ListView(*items, id="module-list", initial_index=0)
                yield VerticalScroll(id="main-panel")

        yield Footer()

    def on_mount(self) -> None:
        self._render_module_info(0)

    def _hesap_metni(self):
        adi, sayi = hesap_bilgi()
        if adi:
            return (
                f"[#1db954]●[/]  [#d0d0d0]{adi}[/]    "
                f"[#2a2a2a]│[/]    [#6b6b6b]{sayi} playlist[/]"
            )
        return "[#cc4444]●[/]  [#6b6b6b]Spotify offline[/]"

    def _render_module_info(self, indeks: int):
        panel = self.query_one("#main-panel", VerticalScroll)
        panel.remove_children()
        m = MODULLER[indeks]

        panel.mount(Static(f"MODÜL {m['no']}", classes="module-eyebrow"))
        panel.mount(Static(m["isim"], classes="module-title"))
        panel.mount(Static(m["altbaslik"], classes="module-subtitle"))
        panel.mount(Static(m["aciklama"], classes="module-description"))

        meta = Horizontal()
        panel.mount(meta)
        meta.mount(Static("SCRIPT  ", classes="module-meta-label"))
        meta.mount(Static(m["script"], classes="module-meta-value"))

        panel.mount(Static(
            "[bold]⏎[/]  [#1db954 bold]ENTER[/]   →   Çalıştır",
            classes="cta-bar"
        ))

    async def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.index is None or self.calisiyor:
            return
        self.secili_indeks = event.list_view.index
        self._render_module_info(self.secili_indeks)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.action_run_selected()

    # ── AKSİYON ÇALIŞTIRMA ──

    async def _modal_al(self, modul):
        tip = modul.get("input")
        if tip == "personal":
            return await self.push_screen_wait(PersonalInputModal())
        if tip == "tiktok":
            return await self.push_screen_wait(TikTokInputModal())
        if tip == "missing":
            return await self.push_screen_wait(MissingTracksModal())
        if tip == "yt_playlist":
            return await self.push_screen_wait(YTPlaylistModal())
        if tip == "confirm":
            return await self.push_screen_wait(
                ConfirmModal(modul["isim"], modul["aciklama"])
            )
        return {}

    def action_run_selected(self) -> None:
        if self.calisiyor:
            return
        modul = MODULLER[self.secili_indeks]
        self.run_worker(self._modul_calistir(modul), exclusive=True)

    async def _modul_calistir(self, modul):
        # Modal'dan input al
        sonuc = await self._modal_al(modul)
        if sonuc is None:
            return  # iptal

        # Argümanları hazırla
        args = []
        if modul["kod"] == "personal":
            args = [
                "--isim",    sonuc["isim"],
                "--dogum",   sonuc["dogum"],
                "--his",     sonuc["his"],
                "--persona", sonuc.get("persona", "default"),
            ]
        elif modul["kod"] == "tiktok":
            args = ["--sayi", sonuc["sayi"]]
            if sonuc["playlist"]:
                args += ["--playlist", sonuc["playlist"]]
        elif modul["kod"] == "missing":
            sanatcilar = sonuc.get("sanatcilar", [])
            if not sanatcilar:
                self.calisiyor = False
                return
            tmp = os.path.join(ROOT, ".tmp_sanatcilar.txt")
            with open(tmp, "w", encoding="utf-8") as f:
                f.write("\n".join(sanatcilar))
            args = ["--dosya", tmp]
        elif modul["kod"] == "yt_playlist":
            json_dosya = os.path.join(ROOT, "eksik_sarkilar", sonuc["json"])
            args = ["--json", json_dosya]
            if sonuc.get("public"):
                args.append("--public")

        # Log paneli aç
        self.calisiyor = True
        panel = self.query_one("#main-panel", VerticalScroll)
        panel.remove_children()

        panel.mount(Static(f"ÇALIŞIYOR · {modul['no']}", classes="module-eyebrow log-status-running"))
        panel.mount(Static(modul["isim"], classes="module-title"))
        status = Static("● Başlatılıyor...", classes="log-status log-status-running")
        panel.mount(status)
        log = Log(id="log-panel", auto_scroll=True)
        panel.mount(log)

        # Subprocess + stream
        komut = [sys.executable, "-u", os.path.join(ROOT, modul["script"])] + args
        try:
            proc = await asyncio.create_subprocess_exec(
                *komut,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=ROOT,
            )
            async for line in proc.stdout:
                log.write_line(line.decode("utf-8", errors="replace").rstrip())
            await proc.wait()
            kod = proc.returncode
        except Exception as e:
            log.write_line(f"[HATA] {e}")
            kod = -1

        if kod == 0:
            status.update("● TAMAMLANDI")
            status.remove_class("log-status-running")
            status.add_class("log-status-done")
        else:
            status.update(f"● HATA (exit {kod})")
            status.remove_class("log-status-running")
            status.add_class("log-status-error")

        panel.mount(Static(
            "[#1db954 bold]ESC[/] geri dön    [#1db954 bold]Q[/] çık",
            classes="cta-bar"
        ))

        self.calisiyor = False

    def action_back_to_menu(self) -> None:
        if self.calisiyor:
            return
        self._render_module_info(self.secili_indeks)

    def action_cursor_up(self) -> None:
        if self.calisiyor: return
        self.query_one("#module-list", ListView).action_cursor_up()

    def action_cursor_down(self) -> None:
        if self.calisiyor: return
        self.query_one("#module-list", ListView).action_cursor_down()


if __name__ == "__main__":
    ProjectiriApp().run()
