"""
Spotify Analytics Dashboard — Flask web UI.
Çalıştır: python dashboard.py → http://localhost:5000
"""

import sqlite3
import datetime
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)
DB_YOL = "/Users/iri/Desktop/projectiRi/analytics.db"

def db():
    con = sqlite3.connect(DB_YOL)
    con.row_factory = sqlite3.Row
    return con

# ─────────────────────────────────────────────────────────────────────────────
# API ENDPOINT'LER
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/ozet")
def api_ozet():
    """Genel istatistikler: toplam playlist, toplam takipçi, toplam şarkı."""
    con = db()
    son_tarih = con.execute("SELECT MAX(snapshot_date) FROM snapshots").fetchone()[0]
    if not son_tarih:
        return jsonify({"hata": "Henüz snapshot yok. Önce: python analytics_topla.py"})

    rows = con.execute("""
        SELECT * FROM snapshots
        WHERE snapshot_date = ?
        ORDER BY followers DESC
    """, (son_tarih,)).fetchall()

    playlistler = [dict(r) for r in rows]
    toplam_takipci = sum(p["followers"] or 0 for p in playlistler)
    toplam_sarki   = sum(p["tracks_count"] or 0 for p in playlistler)

    # Önceki snapshot ile karşılaştır (büyüme)
    onceki = con.execute("""
        SELECT DISTINCT snapshot_date FROM snapshots
        WHERE snapshot_date < ? ORDER BY snapshot_date DESC LIMIT 1
    """, (son_tarih,)).fetchone()

    buyume = {}
    if onceki:
        eski = con.execute("""
            SELECT playlist_id, followers FROM snapshots
            WHERE snapshot_date = ?
        """, (onceki[0],)).fetchall()
        eski_map = {r["playlist_id"]: r["followers"] for r in eski}
        for p in playlistler:
            p["buyume"] = (p["followers"] or 0) - eski_map.get(p["playlist_id"], 0)

    con.close()
    return jsonify({
        "tarih":          son_tarih,
        "toplam_playlist": len(playlistler),
        "toplam_takipci":  toplam_takipci,
        "toplam_sarki":    toplam_sarki,
        "playlistler":     playlistler,
    })

@app.route("/api/grafik/<playlist_id>")
def api_grafik(playlist_id):
    """Belirli playlist'in zaman içindeki takipçi grafiği."""
    con = db()
    rows = con.execute("""
        SELECT snapshot_date, followers, tracks_count FROM snapshots
        WHERE playlist_id = ?
        ORDER BY snapshot_date
    """, (playlist_id,)).fetchall()
    con.close()
    return jsonify([dict(r) for r in rows])

# ─────────────────────────────────────────────────────────────────────────────
# HTML SAYFA
# ─────────────────────────────────────────────────────────────────────────────

SAYFA = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>Spotify Analytics</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, sans-serif; }
  body { background: #0a0a0a; color: #fff; padding: 30px; }
  h1 { font-size: 32px; margin-bottom: 8px; }
  .tarih { color: #888; margin-bottom: 30px; }
  .ozet { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 40px; }
  .kart { background: #1a1a1a; padding: 24px; border-radius: 12px; border: 1px solid #2a2a2a; }
  .kart-baslik { color: #888; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; }
  .kart-deger { font-size: 36px; font-weight: 700; margin-top: 8px; color: #1ed760; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
  .pl { background: #1a1a1a; padding: 16px; border-radius: 12px; border: 1px solid #2a2a2a;
        display: flex; gap: 14px; transition: transform .15s; cursor: pointer; }
  .pl:hover { transform: translateY(-2px); border-color: #1ed760; }
  .pl img { width: 80px; height: 80px; border-radius: 6px; object-fit: cover; flex-shrink: 0; }
  .pl-bilgi { flex: 1; min-width: 0; }
  .pl-ad { font-weight: 600; font-size: 15px; margin-bottom: 6px;
           white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pl-stat { color: #888; font-size: 12px; display: flex; gap: 12px; }
  .pl-stat .v { color: #fff; }
  .buyume-pozitif { color: #1ed760; font-weight: 600; }
  .buyume-sifir   { color: #555; }
  .buyume-negatif { color: #ff4444; font-weight: 600; }
  #grafik-modal { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                  background: rgba(0,0,0,0.85); z-index: 100; padding: 40px;
                  align-items: center; justify-content: center; }
  #grafik-modal.acik { display: flex; }
  #grafik-icerik { background: #1a1a1a; padding: 30px; border-radius: 12px;
                   width: 90%; max-width: 900px; }
  #grafik-baslik { font-size: 22px; margin-bottom: 20px; }
  #kapat { float: right; background: none; border: none; color: #888;
           font-size: 24px; cursor: pointer; }
  .yok { padding: 60px; text-align: center; color: #888; }
</style>
</head>
<body>

<h1>Spotify Analytics</h1>
<div class="tarih" id="tarih">Yükleniyor…</div>

<div class="ozet" id="ozet"></div>

<h2 style="margin-bottom: 16px;">Playlist Performansı</h2>
<div class="grid" id="liste"></div>

<div id="grafik-modal" onclick="if(event.target.id==='grafik-modal')kapat()">
  <div id="grafik-icerik">
    <button id="kapat" onclick="kapat()">×</button>
    <div id="grafik-baslik"></div>
    <canvas id="grafik" height="80"></canvas>
  </div>
</div>

<script>
let chart;

async function yukle() {
  const r = await fetch('/api/ozet');
  const d = await r.json();
  if (d.hata) {
    document.getElementById('liste').innerHTML = '<div class="yok">' + d.hata + '</div>';
    return;
  }

  document.getElementById('tarih').textContent = 'Son güncelleme: ' + d.tarih;

  document.getElementById('ozet').innerHTML = `
    <div class="kart"><div class="kart-baslik">Toplam Playlist</div><div class="kart-deger">${d.toplam_playlist}</div></div>
    <div class="kart"><div class="kart-baslik">Toplam Takipçi</div><div class="kart-deger">${d.toplam_takipci}</div></div>
    <div class="kart"><div class="kart-baslik">Toplam Şarkı</div><div class="kart-deger">${d.toplam_sarki}</div></div>
  `;

  document.getElementById('liste').innerHTML = d.playlistler.map(p => {
    const b = p.buyume;
    let buyumeHTML = '';
    if (b !== undefined) {
      const cls = b > 0 ? 'buyume-pozitif' : (b < 0 ? 'buyume-negatif' : 'buyume-sifir');
      const isaret = b > 0 ? '+' : '';
      buyumeHTML = `<span class="${cls}">${isaret}${b}</span>`;
    }
    return `
    <div class="pl" onclick="grafikGoster('${p.playlist_id}', '${p.playlist_name.replace(/'/g,"\\'")}')">
      <img src="${p.cover_url || ''}" alt="">
      <div class="pl-bilgi">
        <div class="pl-ad">${p.playlist_name}</div>
        <div class="pl-stat">
          <span><span class="v">${p.followers || 0}</span> takipçi ${buyumeHTML}</span>
          <span><span class="v">${p.tracks_count || 0}</span> şarkı</span>
        </div>
      </div>
    </div>`;
  }).join('');
}

async function grafikGoster(id, isim) {
  const r = await fetch('/api/grafik/' + id);
  const data = await r.json();
  document.getElementById('grafik-baslik').textContent = isim;
  document.getElementById('grafik-modal').classList.add('acik');

  if (chart) chart.destroy();
  const ctx = document.getElementById('grafik').getContext('2d');
  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map(d => d.snapshot_date),
      datasets: [{
        label: 'Takipçi',
        data: data.map(d => d.followers),
        borderColor: '#1ed760',
        backgroundColor: 'rgba(30, 215, 96, 0.1)',
        fill: true,
        tension: 0.3
      }]
    },
    options: {
      responsive: true,
      scales: {
        y: { ticks: { color: '#888' }, grid: { color: '#2a2a2a' } },
        x: { ticks: { color: '#888' }, grid: { color: '#2a2a2a' } }
      },
      plugins: { legend: { labels: { color: '#fff' } } }
    }
  });
}

function kapat() {
  document.getElementById('grafik-modal').classList.remove('acik');
}

yukle();
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(SAYFA)

if __name__ == "__main__":
    print("\nDashboard: http://localhost:5000\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
