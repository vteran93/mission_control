#!/usr/bin/env python3
"""
Daily Standup Generator - Run at 23:30 COT

Queries Mission Control DB and generates summary for Victor
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import sys

DB_PATH = Path.home() / 'repositories/mission_control/instance/mission_control.db'

def generate_standup():
    """Generate daily standup report from Mission Control database"""
    
    if not DB_PATH.exists():
        return f"❌ Database not found: {DB_PATH}"
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        today = datetime.now().date()
        
        # Tasks completed today
        completed = conn.execute("""
            SELECT title, assignee_agent_ids FROM tasks 
            WHERE status='completed' 
            AND DATE(updated_at)=?
            ORDER BY updated_at DESC
        """, (today,)).fetchall()
        
        # Tasks in progress
        in_progress = conn.execute("""
            SELECT title, assignee_agent_ids, 
                   ROUND((julianday('now') - julianday(updated_at)) * 24, 1) as hours_active
            FROM tasks 
            WHERE status='in_progress'
            ORDER BY hours_active DESC
        """).fetchall()
        
        # Blocked tasks
        blocked = conn.execute("""
            SELECT title, assignee_agent_ids FROM tasks WHERE status='blocked'
        """).fetchall()
        
        # Tasks needing review
        needs_review = conn.execute("""
            SELECT title, assignee_agent_ids FROM tasks WHERE status='review'
        """).fetchall()
        
        # Recent messages (activity level)
        msg_count = conn.execute("""
            SELECT COUNT(*) FROM messages 
            WHERE created_at >= datetime('now', '-24 hours')
        """).fetchone()[0]
        
        conn.close()
        
        # Generate markdown
        report = f"""📊 **DAILY STANDUP** — {today.strftime('%B %d, %Y')}

---

## ✅ COMPLETED TODAY ({len(completed)})
"""
        
        if completed:
            for title, assignee in completed:
                assignee_display = assignee if assignee else "Unassigned"
                report += f"* **{assignee_display}:** {title}\n"
        else:
            report += "*No tasks completed today*\n"
        
        report += f"\n## 🔄 IN PROGRESS ({len(in_progress)})\n"
        
        if in_progress:
            for title, assignee, hours in in_progress:
                assignee_display = assignee if assignee else "Unassigned"
                alert = " ⚠️" if hours > 4 else ""
                report += f"* **{assignee_display}:** {title} ({hours}h active){alert}\n"
        else:
            report += "*No active tasks*\n"
        
        report += f"\n## 🚫 BLOCKED ({len(blocked)})\n"
        
        if blocked:
            for title, assignee in blocked:
                assignee_display = assignee if assignee else "Unassigned"
                report += f"* **{assignee_display}:** {title}\n"
        else:
            report += "*No blockers* ✨\n"
        
        report += f"\n## 👀 NEEDS REVIEW ({len(needs_review)})\n"
        
        if needs_review:
            for title, assignee in needs_review:
                assignee_display = assignee if assignee else "Unassigned"
                report += f"* {title} (by {assignee_display})\n"
        else:
            report += "*Nothing pending review*\n"
        
        report += f"\n## 📈 ACTIVITY\n"
        report += f"* {msg_count} messages in last 24h\n"
        
        # Warnings
        warnings = []
        if any(hours > 6 for _, _, hours in in_progress):
            warnings.append("⚠️ Tasks active >6h may be stuck")
        if len(blocked) > 0:
            warnings.append("🚧 Blockers need resolution")
        
        if warnings:
            report += f"\n## ⚠️ ATTENTION NEEDED\n"
            for w in warnings:
                report += f"* {w}\n"
        
        report += f"\n---\n*Generated automatically at {datetime.now().strftime('%H:%M COT')}*"
        
        return report
        
    except Exception as e:
        return f"❌ Standup generation failed: {e}"

if __name__ == '__main__':
    standup = generate_standup()
    print(standup)
    sys.exit(0 if not standup.startswith("❌") else 1)
