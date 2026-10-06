SET FOREIGN_KEY_CHECKS = 0;

-- alliances
CREATE TABLE IF NOT EXISTS alliances (
	id INTEGER NOT NULL AUTO_INCREMENT,
	name VARCHAR(90) NOT NULL,
	slug VARCHAR(110) NOT NULL,
	kind VARCHAR(20) NOT NULL,
	tagline VARCHAR(160),
	description TEXT,
	url VARCHAR(255),
	emblem VARCHAR(8),
	code VARCHAR(60),
	status VARCHAR(16) NOT NULL,
	starts_on DATE,
	ends_on DATE,
	sort_order INTEGER NOT NULL,
	is_featured BOOL NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_alliances PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_alliances_kind ON alliances (kind);
CREATE UNIQUE INDEX ix_alliances_slug ON alliances (slug);
CREATE INDEX ix_alliances_starts_on ON alliances (starts_on);
CREATE INDEX ix_alliances_status ON alliances (status);

-- donation_channels
CREATE TABLE IF NOT EXISTS donation_channels (
	id INTEGER NOT NULL AUTO_INCREMENT,
	label VARCHAR(60) NOT NULL,
	method VARCHAR(60) NOT NULL,
	account VARCHAR(120) NOT NULL,
	note VARCHAR(255),
	icon VARCHAR(8),
	color VARCHAR(16),
	url VARCHAR(255),
	is_active BOOL NOT NULL,
	sort_order INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_donation_channels PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- donation_goals
CREATE TABLE IF NOT EXISTS donation_goals (
	id INTEGER NOT NULL AUTO_INCREMENT,
	title VARCHAR(120) NOT NULL,
	description VARCHAR(400),
	target NUMERIC(12, 2) NOT NULL,
	is_active BOOL NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_donation_goals PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- donations
CREATE TABLE IF NOT EXISTS donations (
	id INTEGER NOT NULL AUTO_INCREMENT,
	donor_name VARCHAR(80) NOT NULL,
	message VARCHAR(400),
	amount NUMERIC(12, 2) NOT NULL,
	currency VARCHAR(8) NOT NULL,
	channel VARCHAR(60),
	is_public BOOL NOT NULL,
	donated_at DATETIME,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_donations PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_donations_donated_at ON donations (donated_at);
CREATE INDEX ix_donations_is_public ON donations (is_public);

-- live_streams
CREATE TABLE IF NOT EXISTS live_streams (
	id INTEGER NOT NULL AUTO_INCREMENT,
	title VARCHAR(160) NOT NULL,
	platform VARCHAR(20) NOT NULL,
	channel VARCHAR(80),
	embed_url VARCHAR(400),
	watch_url VARCHAR(255) NOT NULL,
	league VARCHAR(80),
	competition VARCHAR(80),
	thumbnail VARCHAR(255),
	language VARCHAR(20),
	is_live BOOL NOT NULL,
	is_featured BOOL NOT NULL,
	viewers INTEGER NOT NULL,
	scheduled_at DATETIME,
	sort_order INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_live_streams PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_live_streams_is_live ON live_streams (is_live);
CREATE INDEX ix_live_streams_platform ON live_streams (platform);

-- rooms
CREATE TABLE IF NOT EXISTS rooms (
	id INTEGER NOT NULL AUTO_INCREMENT,
	code VARCHAR(12) NOT NULL,
	name VARCHAR(80) NOT NULL,
	haxball_url VARCHAR(255) NOT NULL,
	region VARCHAR(40),
	max_players INTEGER NOT NULL,
	description VARCHAR(255),
	is_open BOOL NOT NULL,
	sort_order INTEGER NOT NULL,
	players_online INTEGER NOT NULL,
	image VARCHAR(255),
	map_name VARCHAR(80),
	mode VARCHAR(40),
	ping VARCHAR(40),
	password VARCHAR(60),
	is_pinned BOOL NOT NULL,
	is_featured BOOL NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_rooms PRIMARY KEY (id),
	CONSTRAINT uq_room_code UNIQUE (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_rooms_is_open ON rooms (is_open);

-- rule_entries
CREATE TABLE IF NOT EXISTS rule_entries (
	id INTEGER NOT NULL AUTO_INCREMENT,
	scope VARCHAR(30) NOT NULL,
	position INTEGER NOT NULL,
	title VARCHAR(90) NOT NULL,
	body TEXT,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_rule_entries PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_rule_entries_scope ON rule_entries (scope);

-- sanction_levels
CREATE TABLE IF NOT EXISTS sanction_levels (
	id INTEGER NOT NULL AUTO_INCREMENT,
	name VARCHAR(60) NOT NULL,
	color VARCHAR(20) NOT NULL,
	items TEXT,
	note VARCHAR(255),
	sort_order INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_sanction_levels PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- seasons
CREATE TABLE IF NOT EXISTS seasons (
	id INTEGER NOT NULL AUTO_INCREMENT,
	number INTEGER NOT NULL,
	name VARCHAR(60) NOT NULL,
	year VARCHAR(12),
	is_current BOOL NOT NULL,
	starts_on DATE,
	ends_on DATE,
	registration_opens DATE,
	is_registration_open BOOL NOT NULL,
	notes TEXT,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_seasons PRIMARY KEY (id),
	CONSTRAINT uq_season_number UNIQUE (number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_seasons_is_current ON seasons (is_current);

-- site_settings
CREATE TABLE IF NOT EXISTS site_settings (
	id INTEGER NOT NULL AUTO_INCREMENT,
	`key` VARCHAR(60) NOT NULL,
	value TEXT,
	`group` VARCHAR(40) NOT NULL,
	label VARCHAR(80),
	input_type VARCHAR(16),
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_site_settings PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE UNIQUE INDEX ix_site_settings_key ON site_settings (`key`);

-- social_links
CREATE TABLE IF NOT EXISTS social_links (
	id INTEGER NOT NULL AUTO_INCREMENT,
	platform VARCHAR(24) NOT NULL,
	owner VARCHAR(24) NOT NULL,
	label VARCHAR(60) NOT NULL,
	handle VARCHAR(80),
	url VARCHAR(255) NOT NULL,
	icon VARCHAR(8),
	is_primary BOOL NOT NULL,
	is_active BOOL NOT NULL,
	sort_order INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_social_links PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_social_links_is_primary ON social_links (is_primary);
CREATE INDEX ix_social_links_owner ON social_links (owner);
CREATE INDEX ix_social_links_platform ON social_links (platform);

-- staff_members
CREATE TABLE IF NOT EXISTS staff_members (
	id INTEGER NOT NULL AUTO_INCREMENT,
	name VARCHAR(60) NOT NULL,
	username VARCHAR(60),
	`role` VARCHAR(40) NOT NULL,
	title VARCHAR(80),
	bio VARCHAR(400),
	avatar VARCHAR(255),
	banner VARCHAR(255),
	tags VARCHAR(160),
	discord VARCHAR(80),
	email VARCHAR(160),
	is_leader BOOL NOT NULL,
	is_active BOOL NOT NULL,
	sort_order INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_staff_members PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_staff_members_is_active ON staff_members (is_active);
CREATE INDEX ix_staff_members_is_leader ON staff_members (is_leader);
CREATE INDEX ix_staff_members_role ON staff_members (`role`);

-- users
CREATE TABLE IF NOT EXISTS users (
	id INTEGER NOT NULL AUTO_INCREMENT,
	username VARCHAR(24) NOT NULL,
	email VARCHAR(160) NOT NULL,
	password VARCHAR(255) NOT NULL,
	`role` VARCHAR(16) NOT NULL,
	is_admin BOOL NOT NULL,
	is_premium BOOL NOT NULL,
	is_active_account BOOL NOT NULL,
	display_name VARCHAR(60),
	bio VARCHAR(400),
	haxball_id VARCHAR(40),
	avatar VARCHAR(255),
	google_email VARCHAR(160),
	country VARCHAR(60),
	last_login DATETIME,
	login_count INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_users PRIMARY KEY (id),
	CONSTRAINT ck_users_role_valid CHECK (role in ('admin','staff','user'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE INDEX ix_users_role ON users (`role`);
CREATE UNIQUE INDEX ix_users_username ON users (username);

-- activity_logs
CREATE TABLE IF NOT EXISTS activity_logs (
	id INTEGER NOT NULL AUTO_INCREMENT,
	user_id INTEGER,
	action VARCHAR(40) NOT NULL,
	entity VARCHAR(40) NOT NULL,
	entity_id INTEGER,
	detail VARCHAR(255),
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_activity_logs PRIMARY KEY (id),
	CONSTRAINT fk_activity_logs_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_activity_logs_action ON activity_logs (action);
CREATE INDEX ix_activity_logs_user_id ON activity_logs (user_id);

-- divisions
CREATE TABLE IF NOT EXISTS divisions (
	id INTEGER NOT NULL AUTO_INCREMENT,
	season_id INTEGER NOT NULL,
	`key` VARCHAR(40) NOT NULL,
	name VARCHAR(80) NOT NULL,
	short VARCHAR(8) NOT NULL,
	level INTEGER NOT NULL,
	teams_count INTEGER NOT NULL,
	journeys_count INTEGER NOT NULL,
	playoffs_slots INTEGER NOT NULL,
	relegation_slots INTEGER NOT NULL,
	promotion_slots INTEGER NOT NULL,
	modality VARCHAR(60),
	duration VARCHAR(80),
	map_name VARCHAR(80),
	server VARCHAR(60),
	tolerance VARCHAR(80),
	description TEXT,
	schedule_note VARCHAR(200),
	document_url VARCHAR(255),
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_divisions PRIMARY KEY (id),
	CONSTRAINT fk_divisions_season_id_seasons FOREIGN KEY(season_id) REFERENCES seasons (id) ON DELETE CASCADE,
	CONSTRAINT uq_divisions_key UNIQUE (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_divisions_season_id ON divisions (season_id);

-- email_logs
CREATE TABLE IF NOT EXISTS email_logs (
	id INTEGER NOT NULL AUTO_INCREMENT,
	user_id INTEGER,
	to_email VARCHAR(160) NOT NULL,
	subject VARCHAR(180) NOT NULL,
	template VARCHAR(40) NOT NULL,
	status VARCHAR(16) NOT NULL,
	error VARCHAR(255),
	sent_at DATETIME,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_email_logs PRIMARY KEY (id),
	CONSTRAINT fk_email_logs_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_email_logs_sent_at ON email_logs (sent_at);
CREATE INDEX ix_email_logs_status ON email_logs (status);
CREATE INDEX ix_email_logs_template ON email_logs (template);
CREATE INDEX ix_email_logs_to_email ON email_logs (to_email);
CREATE INDEX ix_email_logs_user_id ON email_logs (user_id);

-- password_reset_tokens
CREATE TABLE IF NOT EXISTS password_reset_tokens (
	id INTEGER NOT NULL AUTO_INCREMENT,
	user_id INTEGER NOT NULL,
	token_hash VARCHAR(128) NOT NULL,
	expires_at DATETIME NOT NULL,
	used_at DATETIME,
	requested_ip VARCHAR(45),
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_password_reset_tokens PRIMARY KEY (id),
	CONSTRAINT fk_password_reset_tokens_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_password_reset_tokens_expires_at ON password_reset_tokens (expires_at);
CREATE UNIQUE INDEX ix_password_reset_tokens_token_hash ON password_reset_tokens (token_hash);
CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);

-- suggestions
CREATE TABLE IF NOT EXISTS suggestions (
	id INTEGER NOT NULL AUTO_INCREMENT,
	user_id INTEGER NOT NULL,
	category VARCHAR(30) NOT NULL,
	title VARCHAR(120) NOT NULL,
	body TEXT NOT NULL,
	status VARCHAR(16) NOT NULL,
	staff_reply TEXT,
	replied_at DATETIME,
	replied_by_id INTEGER,
	likes INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_suggestions PRIMARY KEY (id),
	CONSTRAINT ck_suggestions_suggestion_status_valid CHECK (status in ('new','reviewing','done')),
	CONSTRAINT fk_suggestions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
	CONSTRAINT fk_suggestions_replied_by_id_users FOREIGN KEY(replied_by_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_suggestions_category ON suggestions (category);
CREATE INDEX ix_suggestions_created_status ON suggestions (created_at, status);
CREATE INDEX ix_suggestions_status ON suggestions (status);
CREATE INDEX ix_suggestions_user_id ON suggestions (user_id);

-- articles
CREATE TABLE IF NOT EXISTS articles (
	id INTEGER NOT NULL AUTO_INCREMENT,
	kind VARCHAR(20) NOT NULL,
	category VARCHAR(30) NOT NULL,
	title VARCHAR(180) NOT NULL,
	slug VARCHAR(200) NOT NULL,
	summary VARCHAR(400),
	body TEXT,
	cover VARCHAR(255),
	is_featured BOOL NOT NULL,
	is_pinned BOOL NOT NULL,
	is_published BOOL NOT NULL,
	published_at DATETIME,
	expires_at DATETIME,
	attachment VARCHAR(255),
	views INTEGER NOT NULL,
	author_id INTEGER,
	division_id INTEGER,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_articles PRIMARY KEY (id),
	CONSTRAINT ck_articles_kind_valid CHECK (kind in ('news','announcement','report')),
	CONSTRAINT ck_articles_category_valid CHECK (category in ('general','inscripcion','premios','sanciones','eventos','sorteos','entrevista')),
	CONSTRAINT fk_articles_author_id_users FOREIGN KEY(author_id) REFERENCES users (id) ON DELETE SET NULL,
	CONSTRAINT fk_articles_division_id_divisions FOREIGN KEY(division_id) REFERENCES divisions (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_article_kind_published ON articles (kind, is_published, published_at);
CREATE INDEX ix_articles_category ON articles (category);
CREATE INDEX ix_articles_is_featured ON articles (is_featured);
CREATE INDEX ix_articles_is_pinned ON articles (is_pinned);
CREATE INDEX ix_articles_is_published ON articles (is_published);
CREATE INDEX ix_articles_kind ON articles (kind);
CREATE INDEX ix_articles_published_at ON articles (published_at);
CREATE UNIQUE INDEX ix_articles_slug ON articles (slug);

-- division_rules
CREATE TABLE IF NOT EXISTS division_rules (
	id INTEGER NOT NULL AUTO_INCREMENT,
	division_id INTEGER NOT NULL,
	position INTEGER NOT NULL,
	title VARCHAR(80) NOT NULL,
	body TEXT,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_division_rules PRIMARY KEY (id),
	CONSTRAINT fk_division_rules_division_id_divisions FOREIGN KEY(division_id) REFERENCES divisions (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_division_rules_division_id ON division_rules (division_id);

-- phases
CREATE TABLE IF NOT EXISTS phases (
	id INTEGER NOT NULL AUTO_INCREMENT,
	division_id INTEGER NOT NULL,
	`order` INTEGER NOT NULL,
	tag VARCHAR(24) NOT NULL,
	title VARCHAR(80) NOT NULL,
	body TEXT,
	highlight VARCHAR(255),
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_phases PRIMARY KEY (id),
	CONSTRAINT fk_phases_division_id_divisions FOREIGN KEY(division_id) REFERENCES divisions (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_phases_division_id ON phases (division_id);

-- promotion_slots
CREATE TABLE IF NOT EXISTS promotion_slots (
	id INTEGER NOT NULL AUTO_INCREMENT,
	division_id INTEGER NOT NULL,
	kind VARCHAR(16) NOT NULL,
	tag VARCHAR(40) NOT NULL,
	title VARCHAR(80) NOT NULL,
	body VARCHAR(255),
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_promotion_slots PRIMARY KEY (id),
	CONSTRAINT fk_promotion_slots_division_id_divisions FOREIGN KEY(division_id) REFERENCES divisions (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_promotion_slots_division_id ON promotion_slots (division_id);

-- suggestion_votes
CREATE TABLE IF NOT EXISTS suggestion_votes (
	id INTEGER NOT NULL AUTO_INCREMENT,
	suggestion_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_suggestion_votes PRIMARY KEY (id),
	CONSTRAINT uq_suggestion_vote UNIQUE (suggestion_id, user_id),
	CONSTRAINT fk_suggestion_votes_suggestion_id_suggestions FOREIGN KEY(suggestion_id) REFERENCES suggestions (id) ON DELETE CASCADE,
	CONSTRAINT fk_suggestion_votes_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_suggestion_votes_suggestion_id ON suggestion_votes (suggestion_id);
CREATE INDEX ix_suggestion_votes_user_id ON suggestion_votes (user_id);

-- teams
CREATE TABLE IF NOT EXISTS teams (
	id INTEGER NOT NULL AUTO_INCREMENT,
	division_id INTEGER,
	name VARCHAR(80) NOT NULL,
	short VARCHAR(20) NOT NULL,
	slug VARCHAR(90) NOT NULL,
	crest VARCHAR(255),
	coach VARCHAR(60),
	captain VARCHAR(60),
	country VARCHAR(60),
	founded_year VARCHAR(12),
	is_active BOOL NOT NULL,
	sort_order INTEGER NOT NULL,
	description TEXT,
	color VARCHAR(16),
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_teams PRIMARY KEY (id),
	CONSTRAINT fk_teams_division_id_divisions FOREIGN KEY(division_id) REFERENCES divisions (id) ON DELETE SET NULL,
	CONSTRAINT uq_teams_name UNIQUE (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_teams_division_id ON teams (division_id);
CREATE INDEX ix_teams_is_active ON teams (is_active);
CREATE UNIQUE INDEX ix_teams_slug ON teams (slug);

-- matches
CREATE TABLE IF NOT EXISTS matches (
	id INTEGER NOT NULL AUTO_INCREMENT,
	division_id INTEGER NOT NULL,
	journey INTEGER NOT NULL,
	stage VARCHAR(40) NOT NULL,
	played_on DATE,
	kickoff VARCHAR(5),
	home_team_id INTEGER NOT NULL,
	away_team_id INTEGER NOT NULL,
	home_score INTEGER,
	away_score INTEGER,
	status VARCHAR(16) NOT NULL,
	room_url VARCHAR(255),
	replay_url VARCHAR(255),
	stream_url VARCHAR(255),
	notes TEXT,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_matches PRIMARY KEY (id),
	CONSTRAINT ck_matches_status_valid CHECK (status in ('scheduled','live','finished','wo','postponed')),
	CONSTRAINT fk_matches_division_id_divisions FOREIGN KEY(division_id) REFERENCES divisions (id) ON DELETE CASCADE,
	CONSTRAINT fk_matches_home_team_id_teams FOREIGN KEY(home_team_id) REFERENCES teams (id) ON DELETE CASCADE,
	CONSTRAINT fk_matches_away_team_id_teams FOREIGN KEY(away_team_id) REFERENCES teams (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_match_division_journey ON matches (division_id, journey);
CREATE INDEX ix_matches_away_team_id ON matches (away_team_id);
CREATE INDEX ix_matches_division_id ON matches (division_id);
CREATE INDEX ix_matches_home_team_id ON matches (home_team_id);
CREATE INDEX ix_matches_journey ON matches (journey);
CREATE INDEX ix_matches_played_on ON matches (played_on);
CREATE INDEX ix_matches_status ON matches (status);

-- museum_items
CREATE TABLE IF NOT EXISTS museum_items (
	id INTEGER NOT NULL AUTO_INCREMENT,
	title VARCHAR(140) NOT NULL,
	slug VARCHAR(160) NOT NULL,
	category VARCHAR(30) NOT NULL,
	division_short VARCHAR(8),
	season_number INTEGER,
	recipient VARCHAR(80),
	team_id INTEGER,
	description VARCHAR(400),
	image VARCHAR(255),
	place INTEGER NOT NULL,
	awarded_on DATE,
	is_highlight BOOL NOT NULL,
	sort_order INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_museum_items PRIMARY KEY (id),
	CONSTRAINT fk_museum_items_team_id_teams FOREIGN KEY(team_id) REFERENCES teams (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_museum_items_awarded_on ON museum_items (awarded_on);
CREATE INDEX ix_museum_items_category ON museum_items (category);
CREATE UNIQUE INDEX ix_museum_items_slug ON museum_items (slug);

-- players
CREATE TABLE IF NOT EXISTS players (
	id INTEGER NOT NULL AUTO_INCREMENT,
	team_id INTEGER NOT NULL,
	username VARCHAR(60) NOT NULL,
	haxball_id VARCHAR(40),
	position VARCHAR(24),
	number INTEGER,
	country VARCHAR(60),
	is_captain BOOL NOT NULL,
	is_active BOOL NOT NULL,
	matches INTEGER NOT NULL,
	goals INTEGER NOT NULL,
	assists INTEGER NOT NULL,
	clean_sheets INTEGER NOT NULL,
	clean_sheet_seconds INTEGER NOT NULL,
	own_goals INTEGER NOT NULL,
	yellow_cards INTEGER NOT NULL,
	red_cards INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_players PRIMARY KEY (id),
	CONSTRAINT fk_players_team_id_teams FOREIGN KEY(team_id) REFERENCES teams (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_players_is_active ON players (is_active);
CREATE INDEX ix_players_team_id ON players (team_id);

-- standings
CREATE TABLE IF NOT EXISTS standings (
	id INTEGER NOT NULL AUTO_INCREMENT,
	division_id INTEGER NOT NULL,
	team_id INTEGER NOT NULL,
	played INTEGER NOT NULL,
	won INTEGER NOT NULL,
	drawn INTEGER NOT NULL,
	lost INTEGER NOT NULL,
	goals_for INTEGER NOT NULL,
	goals_against INTEGER NOT NULL,
	points INTEGER NOT NULL,
	position INTEGER NOT NULL,
	note VARCHAR(80),
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_standings PRIMARY KEY (id),
	CONSTRAINT uq_standing_division_team UNIQUE (division_id, team_id),
	CONSTRAINT fk_standings_division_id_divisions FOREIGN KEY(division_id) REFERENCES divisions (id) ON DELETE CASCADE,
	CONSTRAINT fk_standings_team_id_teams FOREIGN KEY(team_id) REFERENCES teams (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_standings_division_id ON standings (division_id);
CREATE INDEX ix_standings_team_id ON standings (team_id);

-- match_reports
CREATE TABLE IF NOT EXISTS match_reports (
	id INTEGER NOT NULL AUTO_INCREMENT,
	match_id INTEGER NOT NULL,
	photo VARCHAR(255),
	photo_credit VARCHAR(120),
	headline VARCHAR(180),
	summary VARCHAR(400),
	body TEXT,
	video_url VARCHAR(255),
	mvp_player_id INTEGER,
	author_id INTEGER,
	is_published BOOL NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_match_reports PRIMARY KEY (id),
	CONSTRAINT fk_match_reports_match_id_matches FOREIGN KEY(match_id) REFERENCES matches (id) ON DELETE CASCADE,
	CONSTRAINT fk_match_reports_mvp_player_id_players FOREIGN KEY(mvp_player_id) REFERENCES players (id) ON DELETE SET NULL,
	CONSTRAINT fk_match_reports_author_id_users FOREIGN KEY(author_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_match_reports_is_published ON match_reports (is_published);
CREATE UNIQUE INDEX ix_match_reports_match_id ON match_reports (match_id);
CREATE INDEX ix_match_reports_mvp_player_id ON match_reports (mvp_player_id);

-- player_match_stats
CREATE TABLE IF NOT EXISTS player_match_stats (
	id INTEGER NOT NULL AUTO_INCREMENT,
	match_id INTEGER NOT NULL,
	player_id INTEGER NOT NULL,
	team_id INTEGER NOT NULL,
	goals INTEGER NOT NULL,
	assists INTEGER NOT NULL,
	clean_sheets INTEGER NOT NULL,
	clean_sheet_seconds INTEGER NOT NULL,
	own_goals INTEGER NOT NULL,
	yellow_cards INTEGER NOT NULL,
	red_cards INTEGER NOT NULL,
	minutes INTEGER NOT NULL,
	is_mvp BOOL NOT NULL,
	note VARCHAR(160),
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT pk_player_match_stats PRIMARY KEY (id),
	CONSTRAINT uq_stat_match_player UNIQUE (match_id, player_id),
	CONSTRAINT fk_player_match_stats_match_id_matches FOREIGN KEY(match_id) REFERENCES matches (id) ON DELETE CASCADE,
	CONSTRAINT fk_player_match_stats_player_id_players FOREIGN KEY(player_id) REFERENCES players (id) ON DELETE CASCADE,
	CONSTRAINT fk_player_match_stats_team_id_teams FOREIGN KEY(team_id) REFERENCES teams (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_player_match_stats_match_id ON player_match_stats (match_id);
CREATE INDEX ix_player_match_stats_player_id ON player_match_stats (player_id);
CREATE INDEX ix_player_match_stats_team_id ON player_match_stats (team_id);
CREATE INDEX ix_stat_player_match ON player_match_stats (player_id, match_id);

-- alembic_version
CREATE TABLE IF NOT EXISTS `alembic_version` (
	`version_num` VARCHAR(32) NOT NULL,
	CONSTRAINT `alembic_version_pkc` PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DELETE FROM `alembic_version`;
INSERT INTO `alembic_version` (`version_num`) VALUES ('c3a91f4d2b77');

SET FOREIGN_KEY_CHECKS = 1;