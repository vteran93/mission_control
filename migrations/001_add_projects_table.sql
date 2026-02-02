-- Migration: Add Projects Table to Mission Control
-- Date: 2026-02-02
-- Purpose: Track multiple projects with tasks organized by project

-- Create projects table
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',  -- active, paused, completed, archived
    repository_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add project_id column to tasks table
ALTER TABLE tasks ADD COLUMN project_id INTEGER REFERENCES projects(id);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id);

-- Insert initial projects
INSERT INTO projects (name, description, status, repository_path) VALUES
('Legatus Video Factory', 'BlackForge MVP - Automated documentary generation from Wikipedia', 'active', '/home/victor/repositories/legatus-video-factory'),
('Blog Agentic', 'Test project for agent evaluation - FastAPI blog with posts and comments', 'active', '/home/victor/repositories/blog-agentic');

-- Verify
SELECT 'Projects created:' as status;
SELECT * FROM projects;
