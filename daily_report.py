#!/usr/bin/env python3
"""Script de rapport quotidien RescueTime envoyé par email via Resend."""

import os
import requests
from datetime import datetime, timedelta
from collections import defaultdict

RESCUETIME_API_KEY = os.environ.get("RESCUETIME_API_KEY")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
EMAIL_TO = os.environ.get("EMAIL_TO", "lucjager67@gmail.com")

def get_rescuetime_data():
  """Récupère les données RescueTime du jour."""
  today = datetime.now().strftime("%Y-%m-%d")
  url = "https://www.rescuetime.com/anapi/data"
  params = {
    "key": RESCUETIME_API_KEY,
    "perspective": "interval",
    "resolution_time": "hour",
    "restrict_begin": today,
    "restrict_end": today,
    "format": "json"
  }
  response = requests.get(url, params=params)
  response.raise_for_status()
  return response.json()

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

def generate_report(data):
  """Génère le rapport markdown à partir des données RescueTime."""
  rows = data.get("rows", [])
  if not rows:
    return "Aucune donnée RescueTime disponible pour aujourd'hui."

  hourly_data = defaultdict(lambda: {"activities": [], "total_seconds": 0, "productive_seconds": 0, "distracting_seconds": 0})
  category_totals = defaultdict(int)
  total_productive = 0
  total_distracting = 0
  total_time = 0

  for row in rows:
    timestamp, seconds, _, activity, category, productivity = row[0], row[1], row[2], row[3], row[4], row[5]
    hour = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%Hh")

    hourly_data[hour]["activities"].append({"name": activity, "seconds": seconds, "productivity": productivity, "category": category})
    hourly_data[hour]["total_seconds"] += seconds
    category_totals[category] += seconds
    total_time += seconds

    if productivity >= 1:
      hourly_data[hour]["productive_seconds"] += seconds
      total_productive += seconds
    elif productivity <= -1:
      hourly_data[hour]["distracting_seconds"] += seconds
      total_distracting += seconds

  today = datetime.now().strftime("%d/%m/%Y")
  report = f"# 📊 Rapport RescueTime - {today}\n\n"
  report += f"**Temps total suivi** : {format_duration(total_time)}\n"
  report += f"**Temps productif** : {format_duration(total_productive)} ({total_productive*100//total_time if total_time else 0}%)\n"
  report += f"**Temps distrayant** : {format_duration(total_distracting)} ({total_distracting*100//total_time if total_time else 0}%)\n\n"
  report += "---\n\n## 🕐 Détail par heure\n\n"

  for hour in sorted(hourly_data.keys()):
    data_hour = hourly_data[hour]
    top_activities = sorted(data_hour["activities"], key=lambda x: x["seconds"], reverse=True)[:3]

    report += f"### {hour} - {format_duration(data_hour['total_seconds'])}\n"
    for act in top_activities:
      label = get_productivity_label(act["productivity"])
      report += f"- **{act['name']}** ({format_duration(act['seconds'])}) {label}\n"
    report += "\n"

  report += "---\n\n## 📂 Récapitulatif par catégorie\n\n"
  report += "| Catégorie | Temps |\n|-----------|-------|\n"
  for category, seconds in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
    report += f"| {category} | {format_duration(seconds)} |\n"

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

  print("Génération du rapport...")
  report = generate_report(data)

  today = datetime.now().strftime("%d/%m/%Y")
  subject = f"📊 Rapport RescueTime - {today}"

  print("Envoi de l'email...")
  result = send_email(subject, report)
  print(f"Email envoyé avec succès ! ID: {result.get('id')}")

if __name__ == "__main__":
  main()
