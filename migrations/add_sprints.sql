-- Migration: Add sprints table and sprint_id to tasks
-- Run with: sqlite3 instance/mission_control.db < migrations/add_sprints.sql

CREATE TABLE IF NOT EXISTS sprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    goal TEXT,
    start_date DATETIME,
    end_date DATETIME,
    status VARCHAR(50) DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Add sprint_id column to tasks
ALTER TABLE tasks ADD COLUMN sprint_id INTEGER REFERENCES sprints(id);

-- Create initial sprints from existing tasks
INSERT INTO sprints (name, goal, status) VALUES 
    ('Sprint 1', 'Setup inicial y primeros bugs críticos', 'completed'),
    ('Sprint 2', 'Bugfixes pipeline BlackForge', 'active');

-- Assign tasks 1-24 to Sprint 1 (completed)
UPDATE tasks SET sprint_id = 1 WHERE id <= 24;

-- Assign tasks 25+ to Sprint 2 (active)
UPDATE tasks SET sprint_id = 2 WHERE id >= 25;
