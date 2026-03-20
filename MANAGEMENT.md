# Mission Control - Management Scripts

## 🚀 Quick Commands

### Start Mission Control
```bash
~/repositories/mission_control/start_mission_control.sh
```

### Stop Mission Control
```bash
~/repositories/mission_control/stop_mission_control.sh
```

### Check Status
```bash
~/repositories/mission_control/status_mission_control.sh
```

### Restart
```bash
~/repositories/mission_control/stop_mission_control.sh && \
~/repositories/mission_control/start_mission_control.sh
```

## 📊 Dashboard & API

- **Dashboard UI:** http://localhost:5001
- **API Tasks:** http://localhost:5001/api/tasks
- **API Messages:** http://localhost:5001/api/messages

## 📋 Logs

### View real-time logs
```bash
tail -f ~/repositories/mission_control/logs/mission_control.log
```

### View error logs
```bash
tail -f ~/repositories/mission_control/logs/mission_control_error.log
```

## 🔧 Manual Operations

### Manual start (foreground for debugging)
```bash
cd ~/repositories/mission_control
python3 app.py
```

### Kill all instances
```bash
pkill -f "python3.*app.py"
```

### Check port usage
```bash
netstat -tuln | grep 5001
```

## 🔄 Auto-Start on Boot (Optional)

### Using crontab
```bash
crontab -e
# Add line:
@reboot /home/victor/repositories/mission_control/start_mission_control.sh
```

### Using systemd (Linux)
```bash
sudo cp /tmp/mission-control.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mission-control
sudo systemctl start mission-control
sudo systemctl status mission-control
```

## 🩺 Health Checks

Mission Control should respond with:
```bash
curl -s http://localhost:5001/api/tasks | jq '. | length'
# Should return: number of tasks (e.g., 40)
```

## 📦 Dependencies

Installed via `requirements.txt`:
- Flask==3.0.0
- Flask-SQLAlchemy==3.1.1
- Flask-CORS==4.0.0
- langgraph==0.0.52

## 🔥 Troubleshooting

### Port already in use
```bash
# Find process using port 5001
lsof -i :5001
# Kill it
kill -9 <PID>
```

### Database issues
```bash
# Reinitialize database
cd ~/repositories/mission_control
python3 init_db.py
```

### Stale PID file
```bash
rm ~/repositories/mission_control/mission_control.pid
# Then restart normally
```

---

**Status:** ✅ OPERATIONAL  
**Last Updated:** 2026-02-12 21:35 GMT-5
