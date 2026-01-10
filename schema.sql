-- This script will reset and define the database schema.
-- First, it drops the old tables to ensure a clean setup.
-- Please execute the entire script in the Supabase SQL Editor.

-- Drop tables in reverse order of dependency to avoid foreign key errors.
DROP TABLE IF EXISTS sewaan;
DROP TABLE IF EXISTS aset;
DROP TABLE IF EXISTS penyewa;

-- Also drop the old tables with English names if they exist from the previous attempt.
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS tenants;
DROP TABLE IF EXISTS assets;


-- 1. Table for Tenants (Penyewa)
-- Stores information about each tenant.
CREATE TABLE penyewa (
    penyewa_id SERIAL PRIMARY KEY,
    nama_penyewa TEXT NOT NULL UNIQUE,
    no_telefon_penyewa TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. Table for Assets (Aset)
-- Stores information about each rental asset.
CREATE TABLE aset (
    aset_id SERIAL PRIMARY KEY,
    id_aset TEXT NOT NULL UNIQUE, -- Custom ID from CSV, e.g., 'ASSET-001'
    jenis_aset TEXT,
    lokasi TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Table for Rentals (Sewaan)
-- This table links assets to tenants and stores rental-specific details.
CREATE TABLE sewaan (
    sewaan_id SERIAL PRIMARY KEY,
    aset_id INTEGER NOT NULL REFERENCES aset(aset_id) ON DELETE CASCADE,
    penyewa_id INTEGER REFERENCES penyewa(penyewa_id) ON DELETE SET NULL, -- If a tenant is deleted, keep the rental record but nullify the link
    sewa_bulanan_rm NUMERIC(10, 2) DEFAULT 0.00,
    status_bayaran_terkini TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    -- This constraint prevents creating duplicate rental records for the same asset and tenant
    UNIQUE(aset_id, penyewa_id)
);

-- Add comments for clarity in the database schema
COMMENT ON TABLE public.penyewa IS 'Senarai semua penyewa aset.';
COMMENT ON TABLE public.aset IS 'Senarai semua aset yang boleh disewa.';
COMMENT ON TABLE public.sewaan IS 'Jadual untuk menghubungkan aset dan penyewa, serta menyimpan maklumat sewaan.';