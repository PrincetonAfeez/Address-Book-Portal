-- Address Book Portal - simple contacts app schema outline
-- Target: PostgreSQL-style SQL. Django migrations remain the source of truth.

CREATE TABLE contacts_contact (
    id BIGSERIAL PRIMARY KEY,
    owner_id BIGINT NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    first_name VARCHAR(80) NOT NULL,
    last_name VARCHAR(80) NOT NULL DEFAULT '',
    email VARCHAR(254) NOT NULL DEFAULT '',
    phone VARCHAR(32) NOT NULL DEFAULT '',
    company VARCHAR(120) NOT NULL DEFAULT '',
    job_title VARCHAR(120) NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    birthday DATE NULL,
    photo VARCHAR(100) NOT NULL DEFAULT '',
    is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX contacts_contact_owner_archived_idx
    ON contacts_contact (owner_id, is_archived);

CREATE INDEX contacts_contact_owner_favorite_idx
    ON contacts_contact (owner_id, is_favorite);

CREATE INDEX contacts_contact_name_idx
    ON contacts_contact (last_name, first_name);

CREATE TABLE contacts_phone (
    id BIGSERIAL PRIMARY KEY,
    contact_id BIGINT NOT NULL REFERENCES contacts_contact(id) ON DELETE CASCADE,
    number VARCHAR(32) NOT NULL,
    label VARCHAR(16) NOT NULL DEFAULT 'mobile',
    CONSTRAINT contacts_phone_label_check CHECK (label IN ('mobile', 'work', 'home'))
);

CREATE TABLE contacts_email (
    id BIGSERIAL PRIMARY KEY,
    contact_id BIGINT NOT NULL REFERENCES contacts_contact(id) ON DELETE CASCADE,
    address VARCHAR(254) NOT NULL,
    label VARCHAR(16) NOT NULL DEFAULT 'other',
    CONSTRAINT contacts_email_label_check CHECK (label IN ('work', 'home', 'other'))
);

CREATE TABLE contacts_group (
    id BIGSERIAL PRIMARY KEY,
    owner_id BIGINT NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    name VARCHAR(80) NOT NULL
);

CREATE UNIQUE INDEX unique_group_per_owner_ci
    ON contacts_group (LOWER(name), owner_id);

CREATE TABLE contacts_group_contacts (
    id BIGSERIAL PRIMARY KEY,
    group_id BIGINT NOT NULL REFERENCES contacts_group(id) ON DELETE CASCADE,
    contact_id BIGINT NOT NULL REFERENCES contacts_contact(id) ON DELETE CASCADE,
    UNIQUE (group_id, contact_id)
);

CREATE TABLE contacts_tag (
    id BIGSERIAL PRIMARY KEY,
    owner_id BIGINT NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    name VARCHAR(80) NOT NULL,
    color VARCHAR(7) NOT NULL DEFAULT '#2563eb',
    CONSTRAINT contacts_tag_color_check CHECK (color ~ '^#[0-9A-Fa-f]{6}$')
);

CREATE UNIQUE INDEX unique_tag_per_owner_ci
    ON contacts_tag (LOWER(name), owner_id);

CREATE TABLE contacts_tag_contacts (
    id BIGSERIAL PRIMARY KEY,
    tag_id BIGINT NOT NULL REFERENCES contacts_tag(id) ON DELETE CASCADE,
    contact_id BIGINT NOT NULL REFERENCES contacts_contact(id) ON DELETE CASCADE,
    UNIQUE (tag_id, contact_id)
);
