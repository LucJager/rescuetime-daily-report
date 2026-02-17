#!/usr/bin/env python3
"""Script de rapport quotidien RescueTime envoyé par email via Resend."""

import os
import requests
from datetime import datetime, timedelta
from collections import defaultdict

RESCUETIME_API_KEY = os.environ.get("RESCUETIME_API_KEY")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
EMAIL_TO = os.environ.get("EMAIL_TO", "lucjager67@gmail.com")

PROD_COLORS = {2: "#16a34a", 1: "#3b82f6", 0: "#9ca3af", -1: "#f97316", -2: "#ef4444"}
PROD_LABELS = {2: "Très productif", 1: "Productif", 0: "Neutre", -1: "Distrayant", -2: "Très distrayant"}

def get_rescuetime_data(date=None):
  """Récupère les données RescueTime pour une date donnée."""
  if date is None:
    date = datetime.now().strftime("%Y-%m-%d")
  params = {
    "key": RESCUETIME_API_KEY, "perspective": "interval", "resolution_time": "hour",
    "restrict_begin": date, "restrict_end": date, "format": "json"
  }
  response = requests.get("https://www.rescuetime.com/anapi/data", params=params)
  response.raise_for_status()
  return response.json()

def get_summary(data):
  """Retourne un résumé simple (totaux) des données."""
  total = productive = distracting = 0
  for row in data.get("rows", []):
    secs, prod = row[1], row[5]
    total += secs
    if prod >= 1: productive += secs
    elif prod <= -1: distracting += secs
  return {"total": total, "productive": productive, "distracting": distracting}

def fmt(seconds):
  """Formate une durée en heures et minutes."""
  h, m = seconds // 3600, (seconds % 3600) // 60
  return f"{h}h{m:02d}" if h > 0 else f"{m}min"

def generate_report(data, yesterday_summary=None):
  """Génère le rapport HTML."""
  rows = data.get("rows", [])
  if not rows:
    return "<p>Aucune donnée RescueTime disponible pour aujourd'hui.</p>"

  hourly = defaultdict(lambda: {"activities": [], "total": 0, "productive": 0, "distracting": 0})
  categories = defaultdict(int)
  activities = defaultdict(lambda: {"seconds": 0, "prod_scores": defaultdict(int)})
  total_time = total_productive = total_distracting = 0

  for row in rows:
    ts, secs, _, name, cat, prod = row[0], row[1], row[2], row[3], row[4], row[5]
    hour = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%H"))
    hourly[hour]["activities"].append({"name": name, "seconds": secs, "productivity": prod})
    hourly[hour]["total"] += secs
    categories[cat] += secs
    activities[name]["seconds"] += secs
    activities[name]["prod_scores"][prod] += secs
    total_time += secs
    if prod >= 1:
      hourly[hour]["productive"] += secs
      total_productive += secs
    elif prod <= -1:
      hourly[hour]["distracting"] += secs
      total_distracting += secs

  today = datetime.now().strftime("%d/%m/%Y")
  pct_prod = total_productive * 100 // total_time if total_time else 0
  pct_dist = total_distracting * 100 // total_time if total_time else 0
  active_hours = sorted(hourly.keys())
  max_act_secs = max(i["seconds"] for i in activities.values()) if activities else 1

  # Styles réutilisables
  CARD = "background:white;border-radius:12px;padding:20px;margin-bottom:16px;"
  H2 = "margin:0 0 16px;font-size:18px;color:#1e293b;"
  TH = "text-align:left;padding:8px 10px;font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;border-bottom:2px solid #e2e8f0;"
  TD = "padding:10px;border-bottom:1px solid #f1f5f9;font-size:14px;"

  h = f'<div style="max-width:600px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;">'

  # Header
  h += f'''<div style="background:linear-gradient(135deg,#1e293b,#334155);border-radius:12px;padding:24px;color:white;text-align:center;margin-bottom:16px;">
    <div style="font-size:28px;font-weight:700;">📊 Rapport RescueTime</div>
    <div style="opacity:0.8;font-size:15px;margin-top:4px;">{today}</div></div>'''

  # Stats
  h += f'''<table width="100%" cellpadding="0" cellspacing="6" style="margin-bottom:4px;"><tr>
    <td style="background:white;border-radius:10px;padding:16px;text-align:center;width:33%;">
      <div style="font-size:26px;font-weight:700;color:#1e293b;">{fmt(total_time)}</div>
      <div style="color:#64748b;font-size:13px;">Total</div></td>
    <td style="background:white;border-radius:10px;padding:16px;text-align:center;width:33%;">
      <div style="font-size:26px;font-weight:700;color:#16a34a;">{fmt(total_productive)}</div>
      <div style="color:#64748b;font-size:13px;">Productif · {pct_prod}%</div></td>
    <td style="background:white;border-radius:10px;padding:16px;text-align:center;width:33%;">
      <div style="font-size:26px;font-weight:700;color:#ef4444;">{fmt(total_distracting)}</div>
      <div style="color:#64748b;font-size:13px;">Distrayant · {pct_dist}%</div></td>
  </tr></table>'''

  # Barre de progression
  h += f'''<div style="background:#e2e8f0;border-radius:8px;height:10px;overflow:hidden;margin-bottom:20px;">
    <div style="background:#16a34a;height:100%;width:{pct_prod}%;float:left;"></div>
    <div style="background:#ef4444;height:100%;width:{pct_dist}%;float:right;"></div></div>'''

  # Top activités
  h += f'<div style="{CARD}"><div style="{H2}">🏆 Top activités</div>'
  h += f'<table width="100%" cellpadding="0" cellspacing="0"><tr><th style="{TH}">Activité</th><th style="{TH}text-align:right;">Temps</th></tr>'
  for name, info in sorted(activities.items(), key=lambda x: x[1]["seconds"], reverse=True)[:10]:
    best_prod = max(info["prod_scores"], key=info["prod_scores"].get)
    color = PROD_COLORS.get(best_prod, "#9ca3af")
    bar_w = info["seconds"] * 100 // max_act_secs
    h += f'''<tr><td style="{TD}">
      <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{color};margin-right:8px;vertical-align:middle;"></span>
      <span style="vertical-align:middle;">{name}</span>
      <div style="background:#f1f5f9;border-radius:3px;height:4px;margin-top:6px;">
        <div style="background:{color};border-radius:3px;height:100%;width:{bar_w}%;"></div></div>
    </td><td style="{TD}text-align:right;font-weight:600;white-space:nowrap;vertical-align:top;">{fmt(info["seconds"])}</td></tr>'''
  h += '</table></div>'

  # Comparaison avec hier
  if yesterday_summary:
    ys = yesterday_summary
    def delta(t, y, pos_good=True):
      diff = t - y
      if diff == 0: return '<span style="color:#9ca3af;">=</span>'
      arrow = "↑" if diff > 0 else "↓"
      color = ("#16a34a" if diff > 0 else "#ef4444") if pos_good else ("#ef4444" if diff > 0 else "#16a34a")
      return f'<span style="color:{color};font-weight:600;">{arrow} {fmt(abs(diff))}</span>'
    h += f'<div style="{CARD}"><div style="{H2}">📈 Comparaison avec hier</div>'
    h += f'<table width="100%" cellpadding="0" cellspacing="0"><tr><th style="{TH}">Métrique</th><th style="{TH}text-align:right;">Hier</th><th style="{TH}text-align:right;">Auj.</th><th style="{TH}text-align:right;">Δ</th></tr>'
    for label, tv, yv, pg in [("Temps total", total_time, ys["total"], True), ("Productif", total_productive, ys["productive"], True), ("Distrayant", total_distracting, ys["distracting"], False)]:
      h += f'<tr><td style="{TD}font-weight:500;">{label}</td><td style="{TD}text-align:right;color:#64748b;">{fmt(yv)}</td><td style="{TD}text-align:right;font-weight:600;">{fmt(tv)}</td><td style="{TD}text-align:right;">{delta(tv, yv, pg)}</td></tr>'
    h += '</table></div>'

  # Insights
  insights = []
  if total_distracting > 0:
    insights.append((f"Ratio productif/distrayant : <strong>{total_productive/total_distracting:.1f}x</strong>", "#f0fdf4", "#16a34a"))
  if active_hours:
    best_h = max(hourly.items(), key=lambda x: x[1]["productive"])
    if best_h[1]["productive"] > 0:
      top_act = max(best_h[1]["activities"], key=lambda x: x["seconds"])
      insights.append((f"Heure la plus productive : <strong>{best_h[0]:02d}h</strong> ({fmt(best_h[1]['productive'])}, {top_act['name']})", "#eff6ff", "#3b82f6"))
    worst_h = max(hourly.items(), key=lambda x: x[1]["distracting"])
    if worst_h[1]["distracting"] > 0:
      dist_acts = [a for a in worst_h[1]["activities"] if a["productivity"] <= -1]
      if dist_acts:
        top_dist = max(dist_acts, key=lambda x: x["seconds"])
        insights.append((f"Plus grosse distraction : <strong>{top_dist['name']}</strong> ({fmt(top_dist['seconds'])}) à {worst_h[0]:02d}h", "#fef2f2", "#ef4444"))
    insights.append((f"Plage active : <strong>{active_hours[0]:02d}h → {active_hours[-1]:02d}h</strong>", "#f8fafc", "#64748b"))
  if insights:
    h += f'<div style="{CARD}"><div style="{H2}">💡 Insights</div>'
    for text, bg, bc in insights:
      h += f'<div style="background:{bg};border-left:4px solid {bc};padding:12px 14px;margin-bottom:8px;border-radius:0 8px 8px 0;font-size:14px;">{text}</div>'
    h += '</div>'

  # Blocs d'activité
  if active_hours:
    def hour_type(hd):
      if hd["productive"] > hd["distracting"]: return "productive"
      if hd["distracting"] > hd["productive"]: return "distracting"
      return "neutre"
    blocks, cur = [], {"start": active_hours[0], "end": active_hours[0], "type": hour_type(hourly[active_hours[0]]), "total": hourly[active_hours[0]]["total"]}
    for hr in active_hours[1:]:
      ht = hour_type(hourly[hr])
      if hr == cur["end"] + 1 and ht == cur["type"]:
        cur["end"] = hr
        cur["total"] += hourly[hr]["total"]
      else:
        blocks.append(cur)
        cur = {"start": hr, "end": hr, "type": ht, "total": hourly[hr]["total"]}
    blocks.append(cur)
    block_styles = {"productive": ("#16a34a", "#f0fdf4", "Focus"), "distracting": ("#ef4444", "#fef2f2", "Distraction"), "neutre": ("#9ca3af", "#f8fafc", "Neutre")}
    h += f'<div style="{CARD}"><div style="{H2}">🧱 Blocs d\'activité</div>'
    for b in blocks:
      color, bg, label = block_styles[b["type"]]
      h += f'''<div style="background:{bg};border:1px solid {color}30;border-radius:8px;padding:10px 14px;margin-bottom:6px;font-size:13px;">
        <strong>{b["start"]:02d}h-{b["end"]+1:02d}h</strong>
        <span style="color:#64748b;margin:0 6px;">·</span>{fmt(b["total"])}
        <span style="color:#64748b;margin:0 6px;">·</span>
        <span style="color:{color};font-weight:600;">{label}</span></div>'''
    h += '</div>'

  # Catégories
  h += f'<div style="{CARD}"><div style="{H2}">📂 Catégories</div>'
  h += f'<table width="100%" cellpadding="0" cellspacing="0"><tr><th style="{TH}">Catégorie</th><th style="{TH}text-align:right;">Temps</th></tr>'
  for cat, secs in sorted(categories.items(), key=lambda x: x[1], reverse=True):
    h += f'<tr><td style="{TD}">{cat}</td><td style="{TD}text-align:right;font-weight:600;">{fmt(secs)}</td></tr>'
  h += '</table></div></div>'

  return h

def send_email(subject, html_body):
  """Envoie l'email via Resend."""
  full_html = f'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head><body style="margin:0;padding:20px;background:#f8fafc;">{html_body}</body></html>'
  payload = {
    "from": "RescueTime Report <onboarding@resend.dev>",
    "to": [EMAIL_TO],
    "subject": subject,
    "html": full_html
  }
  response = requests.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}, json=payload)
  response.raise_for_status()
  return response.json()

def main():
  if not RESCUETIME_API_KEY:
    raise ValueError("RESCUETIME_API_KEY non définie")
  if not RESEND_API_KEY:
    raise ValueError("RESEND_API_KEY non définie")

  print("Récupération des données RescueTime...")
  data = get_rescuetime_data()

  yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
  try:
    yesterday_summary = get_summary(get_rescuetime_data(yesterday))
  except Exception:
    yesterday_summary = None

  print("Génération du rapport...")
  report = generate_report(data, yesterday_summary)

  today = datetime.now().strftime("%d/%m/%Y")
  subject = f"📊 Rapport RescueTime - {today}"

  print("Envoi de l'email...")
  result = send_email(subject, report)
  print(f"Email envoyé avec succès ! ID: {result.get('id')}")

if __name__ == "__main__":
  main()
