#!/usr/bin/env python3
"""Script de rapport quotidien RescueTime envoyé par email via Resend."""

import os
import requests
from datetime import datetime, timedelta
from collections import defaultdict

RESCUETIME_API_KEY = os.environ.get("RESCUETIME_API_KEY")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
EMAIL_TO = os.environ.get("EMAIL_TO", "lucjager67@gmail.com")

def get_rescuetime_data(date=None):
  """Récupère les données RescueTime pour une date donnée."""
  if date is None:
    date = datetime.now().strftime("%Y-%m-%d")
  url = "https://www.rescuetime.com/anapi/data"
  params = {
    "key": RESCUETIME_API_KEY,
    "perspective": "interval",
    "resolution_time": "hour",
    "restrict_begin": date,
    "restrict_end": date,
    "format": "json"
  }
  response = requests.get(url, params=params)
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

def format_duration(seconds):
  """Formate une durée en heures et minutes."""
  hours = seconds // 3600
  minutes = (seconds % 3600) // 60
  if hours > 0:
    return f"{hours}h{minutes:02d}"
  return f"{minutes}min"

def get_productivity_label(score):
  """Retourne un label de productivité basé sur le score."""
  labels = {2: "🟢 Très productif", 1: "🔵 Productif", 0: "⚪ Neutre", -1: "🟠 Distrayant", -2: "🔴 Très distrayant"}
  return labels.get(score, "⚪ Neutre")

def generate_report(data, yesterday_summary=None):
  """Génère le rapport markdown à partir des données RescueTime."""
  rows = data.get("rows", [])
  if not rows:
    return "Aucune donnée RescueTime disponible pour aujourd'hui."

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
  report = f"# 📊 Rapport RescueTime - {today}\n\n"
  report += f"**Temps total suivi** : {format_duration(total_time)}\n"
  report += f"**Temps productif** : {format_duration(total_productive)} ({pct_prod}%)\n"
  report += f"**Temps distrayant** : {format_duration(total_distracting)} ({pct_dist}%)\n\n"

  # 1. Top activités
  report += "---\n\n## 🏆 Top activités\n\n"
  report += "| Activité | Temps | Productivité |\n|----------|-------|--------------|\n"
  for name, info in sorted(activities.items(), key=lambda x: x[1]["seconds"], reverse=True)[:10]:
    best_prod = max(info["prod_scores"], key=info["prod_scores"].get)
    report += f"| {name} | {format_duration(info['seconds'])} | {get_productivity_label(best_prod)} |\n"
  report += "\n"

  # 2. Comparaison jour précédent
  if yesterday_summary:
    report += "---\n\n## 📈 Comparaison avec hier\n\n"
    def delta_str(t, y):
      diff = t - y
      if diff == 0: return "="
      return f"{'+'if diff>0 else '-'}{format_duration(abs(diff))}"
    ys = yesterday_summary
    report += "| Métrique | Aujourd'hui | Hier | Δ |\n|----------|-------------|------|---|\n"
    report += f"| Temps total | {format_duration(total_time)} | {format_duration(ys['total'])} | {delta_str(total_time, ys['total'])} |\n"
    report += f"| Productif | {format_duration(total_productive)} | {format_duration(ys['productive'])} | {delta_str(total_productive, ys['productive'])} |\n"
    report += f"| Distrayant | {format_duration(total_distracting)} | {format_duration(ys['distracting'])} | {delta_str(total_distracting, ys['distracting'])} |\n"
    report += "\n"

  # 3. Insights
  report += "---\n\n## 💡 Insights\n\n"
  if total_distracting > 0:
    report += f"- **Ratio productif/distrayant** : {total_productive/total_distracting:.1f}x\n"
  active_hours = sorted(hourly.keys())
  if active_hours:
    best_h = max(hourly.items(), key=lambda x: x[1]["productive"])
    if best_h[1]["productive"] > 0:
      top_act = max(best_h[1]["activities"], key=lambda x: x["seconds"])
      report += f"- **Heure la plus productive** : {best_h[0]:02d}h ({format_duration(best_h[1]['productive'])}, principalement {top_act['name']})\n"
    worst_h = max(hourly.items(), key=lambda x: x[1]["distracting"])
    if worst_h[1]["distracting"] > 0:
      dist_acts = [a for a in worst_h[1]["activities"] if a["productivity"] <= -1]
      if dist_acts:
        top_dist = max(dist_acts, key=lambda x: x["seconds"])
        report += f"- **Plus grosse distraction** : {top_dist['name']} ({format_duration(top_dist['seconds'])}) à {worst_h[0]:02d}h\n"
    report += f"- **Plage active** : {active_hours[0]:02d}h → {active_hours[-1]:02d}h\n"
  report += "\n"

  # 4. Blocs d'activité
  report += "---\n\n## 🧱 Blocs d'activité\n\n"
  if active_hours:
    def hour_type(h):
      if h["productive"] > h["distracting"]: return "productive"
      if h["distracting"] > h["productive"]: return "distracting"
      return "neutre"
    blocks, cur = [], {"start": active_hours[0], "end": active_hours[0], "type": hour_type(hourly[active_hours[0]]), "total": hourly[active_hours[0]]["total"]}
    for h in active_hours[1:]:
      ht = hour_type(hourly[h])
      if h == cur["end"] + 1 and ht == cur["type"]:
        cur["end"] = h
        cur["total"] += hourly[h]["total"]
      else:
        blocks.append(cur)
        cur = {"start": h, "end": h, "type": ht, "total": hourly[h]["total"]}
    blocks.append(cur)
    type_labels = {"productive": "🟢 Focus", "distracting": "🔴 Distraction", "neutre": "⚪ Neutre"}
    for b in blocks:
      report += f"- **{b['start']:02d}h-{b['end']+1:02d}h** ({format_duration(b['total'])}) → {type_labels[b['type']]}\n"
  report += "\n"

  # Récapitulatif par catégorie
  report += "---\n\n## 📂 Récapitulatif par catégorie\n\n"
  report += "| Catégorie | Temps |\n|-----------|-------|\n"
  for cat, secs in sorted(categories.items(), key=lambda x: x[1], reverse=True):
    report += f"| {cat} | {format_duration(secs)} |\n"

  return report

def send_email(subject, body):
  """Envoie l'email via Resend."""
  url = "https://api.resend.com/emails"
  headers = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}
  payload = {
    "from": "RescueTime Report <onboarding@resend.dev>",
    "to": [EMAIL_TO],
    "subject": subject,
    "html": f"<pre style='font-family: monospace; white-space: pre-wrap;'>{body}</pre>"
  }
  response = requests.post(url, headers=headers, json=payload)
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
