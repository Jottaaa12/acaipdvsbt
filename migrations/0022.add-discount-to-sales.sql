-- Migration: Add discount_value column to sales table
-- Date: 2025-11-13
-- Description: Adds a new column to store discount values applied to sales

ALTER TABLE sales ADD COLUMN discount_value REAL NOT NULL DEFAULT 0.0;
