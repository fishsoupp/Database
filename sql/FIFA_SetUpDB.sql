-- CREATE DATABASE FIFA_DB;

-------------------------------------------------------------------------------------------------
-- (1) Create user roles

CREATE ROLE "fifa_admin" WITH LOGIN PASSWORD 'fifa_admin!';
CREATE ROLE "fifa_user" WITH LOGIN PASSWORD 'fifa_user!';

-- Grant privileges to 'fifa_admin'
GRANT ALL PRIVILEGES ON DATABASE fifa_db TO "fifa_admin";

-- Grant connect privilege to the database
GRANT CONNECT ON DATABASE fifa_db TO fifa_user;

REVOKE ALL ON DATABASE fifa_db FROM PUBLIC;

-------------------------------------------------------------------------------------------------
-- (2) CREATE TABLES

-- Stadiums
CREATE TABLE stadiums (
    stadium_id SERIAL PRIMARY KEY,
    stadium_name VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL
);

-- Referees
CREATE TABLE referees (
    referee_id SERIAL PRIMARY KEY,
    referee_name VARCHAR(100) NOT NULL
);

-- Teams
CREATE TABLE teams (
    team_id SERIAL PRIMARY KEY,
    team_name VARCHAR(100) NOT NULL UNIQUE,
    fifa_code CHAR(3),
    continent VARCHAR(50) NOT NULL
);

-- Players
CREATE TABLE players (
    player_id SERIAL PRIMARY KEY,
    player_name VARCHAR(100) NOT NULL,
    team_id INTEGER NOT NULL,
    position VARCHAR(20) NOT NULL,
    date_of_birth DATE NOT NULL,
    caps SMALLINT NOT NULL DEFAULT 0,
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    CHECK (date_of_birth < CURRENT_DATE)
);

-- Tournaments
CREATE TABLE tournaments (
    tournament_id SERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    host_country VARCHAR(100) NOT NULL,
    winner_team_id INTEGER NOT NULL,
    runner_up_team_id INTEGER NOT NULL,
    matches_played SMALLINT NOT NULL DEFAULT 0,
    CHECK (year > 1929 AND year <= EXTRACT(YEAR FROM CURRENT_DATE))
);

-- Tournament Scorers
CREATE TABLE tournament_scorers (
    tournament_id INT NOT NULL,
    player_id INT NOT NULL,
    PRIMARY KEY (tournament_id, player_id)
);

-- Add Foreign Keys to Tournaments
ALTER TABLE tournaments
ADD CONSTRAINT fk_winner_team_id FOREIGN KEY (winner_team_id) REFERENCES teams(team_id),
ADD CONSTRAINT fk_runner_up_team_id FOREIGN KEY (runner_up_team_id) REFERENCES teams(team_id);

-- Add Foreign Keys to Tournament Scorers
ALTER TABLE tournament_scorers
ADD CONSTRAINT fk_tournament_id FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id),
ADD CONSTRAINT fk_player_id FOREIGN KEY (player_id) REFERENCES players(player_id);

-- Matches
CREATE TABLE matches (
    match_id SERIAL PRIMARY KEY,
    tournament_id INTEGER NOT NULL,
    stadium_id INTEGER NOT NULL,
    home_team_id INTEGER NOT NULL,
    away_team_id INTEGER NOT NULL,
    home_team_goals SMALLINT NOT NULL,
    away_team_goals SMALLINT NOT NULL,
    round VARCHAR(50) NOT NULL,
    referee_id INTEGER NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id),
    FOREIGN KEY (stadium_id) REFERENCES stadiums(stadium_id),
    FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (away_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (referee_id) REFERENCES referees(referee_id)
);

-- Goals
CREATE TABLE goals (
    goal_id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL,
    match_id INTEGER NOT NULL,
    minute_scored VARCHAR(10) NOT NULL,
    is_penalty BOOLEAN NOT NULL,
    is_own_goal BOOLEAN NOT NULL,
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (match_id) REFERENCES matches(match_id)
);

-- Player Performance
CREATE TABLE player_performance (
    performance_id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL,
    match_id INTEGER NOT NULL,
    goals_scored INTEGER NOT NULL,
    yellow_cards INTEGER NOT NULL,
    red_cards INTEGER NOT NULL,
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (match_id) REFERENCES matches(match_id)
);

-- Admin
CREATE TABLE Admin (
    admin_id SERIAL PRIMARY KEY,
    admin_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(100) NOT NULL,
    created_at DATE NOT NULL DEFAULT CURRENT_DATE
);

-- AdminProfile
CREATE TABLE AdminProfile (
    admin_id INT PRIMARY KEY,
    bio TEXT,
    phone VARCHAR(15),
    address VARCHAR(255),
    FOREIGN KEY (admin_id) REFERENCES Admin(admin_id)
);

-- Admin Log
CREATE TABLE admin_log (
    log_id SERIAL PRIMARY KEY,
    admin_id INTEGER NOT NULL,
    activity_type VARCHAR(100) NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    record_id VARCHAR(100) NOT NULL,
    activity_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATE NOT NULL DEFAULT CURRENT_DATE,
    FOREIGN KEY (admin_id) REFERENCES Admin(admin_id),
    CHECK (activity_timestamp <= CURRENT_TIMESTAMP),
    CHECK (activity_type IN ('create', 'update', 'delete'))
);

-------------------------------------------------------------------------------------------------
-- (3) Import dataset
copy stadiums FROM 'D:\path_to_project_directory...\Database\dataset\new_stadiums_table.csv' DELIMITER ',' CSV HEADER;
copy referees FROM 'D:\path_to_project_directory...\Database\dataset\new_referees_table.csv' DELIMITER ',' CSV HEADER;
copy teams FROM 'D:\path_to_project_directory...\Database\dataset\new_teams_table.csv' DELIMITER ',' CSV HEADER;
copy players FROM 'D:\path_to_project_directory...\Database\dataset\new_players_table.csv' DELIMITER ',' CSV HEADER;
copy tournaments FROM 'D:\path_to_project_directory...\Database\dataset\new_tournaments_table.csv' DELIMITER ',' CSV HEADER;
copy tournament_scorers FROM 'D:\path_to_project_directory...\Database\dataset\new_tournament_scorers_table.csv' DELIMITER ',' CSV HEADER;
copy matches FROM 'D:\path_to_project_directory...\Database\dataset\new_matches_table.csv' DELIMITER ',' CSV HEADER;
copy goals FROM 'D:\path_to_project_directory...\Database\dataset\new_goals_table.csv' DELIMITER ',' CSV HEADER;
copy player_performance FROM 'D:\path_to_project_directory...\Database\dataset\new_player_performance_table.csv' DELIMITER ',' CSV HEADER;

-------------------------------------------------------------------------------------------------
-- (4) INSERT ADMIN DATA

CREATE EXTENSION IF NOT EXISTS pgcrypto;

INSERT INTO Admin (admin_name, email, password) VALUES
('Apple Tan', 'apple@google.com', crypt('Admin123!', gen_salt('bf'))),
('Banana Goh', 'banana@google.com', crypt('Admin123!', gen_salt('bf'))),
('Cherry Lee', 'cherry@google.com', crypt('Admin123!', gen_salt('bf'))),
('Date Mok', 'date@google.com', crypt('Admin123!', gen_salt('bf'))),
('Elderberry Goh', 'elderberry@google.com', crypt('Admin123!', gen_salt('bf'))),
('Fig Loh', 'fig@google.com', crypt('Admin123!', gen_salt('bf'))),
('Grapefruit Lee', 'grapefruit@google.com', crypt('Admin123!', gen_salt('bf'))),
('Honeydew Lok', 'honeydew@google.com', crypt('Admin123!', gen_salt('bf'))),
('Indian Fig Poh', 'indianfig@google.com', crypt('Admin123!', gen_salt('bf'))),
('Jackfruit Yee', 'jackfruit@google.com', crypt('Admin123!', gen_salt('bf'))),
('Kiwi Lim', 'kiwi@google.com', crypt('Admin123!', gen_salt('bf'))),
('Lime Ang', 'lime@google.com', crypt('Admin123!', gen_salt('bf'))),
('Mango Tan', 'mango@google.com', crypt('Admin123!', gen_salt('bf'))),
('Nectarine Wei', 'nectarine@google.com', crypt('Admin123!', gen_salt('bf'))),
('Orange Joo', 'orange@google.com', crypt('Admin123!', gen_salt('bf'))),
('Papaya Teh', 'papaya@google.com', crypt('Admin123!', gen_salt('bf'))),
('Quince Koo', 'quince@google.com', crypt('Admin123!', gen_salt('bf'))),
('Raspberry Goo', 'raspberry@google.com', crypt('Admin123!', gen_salt('bf'))),
('Strawberry Kim', 'strawberry@google.com', crypt('Admin123!', gen_salt('bf'))),
('Tangerine Lin', 'tangerine@google.com', crypt('Admin123!', gen_salt('bf'))),
('Ugli Fruit Soh', 'uglifruit@google.com', crypt('Admin123!', gen_salt('bf'))),
('Vanilla Bean See', 'vanillabean@google.com', crypt('Admin123!', gen_salt('bf'))),
('Watermelon Moon', 'watermelon@google.com', crypt('Admin123!', gen_salt('bf'))),
('Xigua Ca', 'xigua@google.com', crypt('Admin123!', gen_salt('bf'))),
('Yellow Watermelon Ong', 'yellowwatermelon@google.com', crypt('Admin123!', gen_salt('bf'))),
('Zucchini Ang', 'zucchini@google.com', crypt('Admin123!', gen_salt('bf')));

INSERT INTO AdminProfile (admin_id, bio, phone, address) VALUES
(1, 'Loves tropical fruits and data security.', '91234501', '123 Orchard Lane'),
(2, 'Enjoys organic farming and sustainable practices.', '91234502', '124 Orchard Lane'),
(3, 'Passionate about cherries and software engineering.', '91234503', '125 Orchard Lane'),
(4, 'Expert in dry fruits and database management.', '91234504', '126 Orchard Lane'),
(5, 'Interested in rare fruits and cryptography.', '91234505', '127 Orchard Lane'),
(6, 'Adventures in fig recipes and system security.', '91234506', '128 Orchard Lane'),
(7, 'Grapefruit enthusiast with a knack for coding.', '91234507', '129 Orchard Lane'),
(8, 'Researcher in melon varieties and user authentication.', '91234508', '130 Orchard Lane'),
(9, 'Lover of exotic fruits and complex databases.', '91234509', '131 Orchard Lane'),
(10, 'Jackfruit aficionado and tech innovator.', '91234510', '132 Orchard Lane'),
(11, 'Kiwi collector and encryption specialist.', '91234511', '133 Orchard Lane'),
(12, 'Citrus fruit expert and network security analyst.', '91234512', '134 Orchard Lane'),
(13, 'Tropical fruit enthusiast and data protector.', '91234513', '135 Orchard Lane'),
(14, 'Nectarine gourmet and privacy advocate.', '91234514', '136 Orchard Lane'),
(15, 'Oranges lover and cyber security expert.', '91234515', '137 Orchard Lane'),
(16, 'Papaya planter and information security guru.', '91234516', '138 Orchard Lane'),
(17, 'Quince connoisseur and digital security advisor.', '91234517', '139 Orchard Lane'),
(18, 'Raspberry farmer and software developer.', '91234518', '140 Orchard Lane'),
(19, 'Strawberry specialist and IT security consultant.', '91234519', '141 Orchard Lane'),
(20, 'Tangerine taster and systems programmer.', '91234520', '142 Orchard Lane'),
(21, 'Ugli fruit researcher and tech enthusiast.', '91234521', '143 Orchard Lane'),
(22, 'Vanilla Bean lover and data scientist.', '91234522', '144 Orchard Lane'),
(23, 'Watermelon whisperer and encryption expert.', '91234523', '145 Orchard Lane'),
(24, 'Xigua expert and full stack developer.', '91234524', '146 Orchard Lane'),
(25, 'Specialist in yellow watermelons and machine learning.', '91234525', '147 Orchard Lane'),
(26, 'Zucchini gourmet and application security analyst.', '91234526', '148 Orchard Lane');

-------------------------------------------------------------------------------------------------
-- (5) ASSIGN ACCESS RIGHTS - TABLES

-- Grant all privileges on all tables in the 'fifa' schema to 'admin'
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "fifa_admin";

-- Grant USAGE and SELECT on all sequences in the public schema
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "fifa_admin";

-- Grant select privilege on all existing tables in the 'public' schema
GRANT SELECT ON ALL TABLES IN SCHEMA public TO fifa_user;

-- Set default privileges to grant select on new tables in the 'public' schema
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO fifa_user;

-------------------------------------------------------------------------------------------------
-- (6) Reset the sequence 
SELECT setval('players_player_id_seq', (SELECT MAX(player_id) FROM players)+1);
SELECT setval('matches_match_id_seq', (SELECT MAX(match_id) FROM matches)+1);
SELECT setval('goals_goal_id_seq', (SELECT MAX(goal_id) FROM goals)+1);
SELECT setval('tournaments_tournament_id_seq', (SELECT MAX(tournament_id) FROM tournaments)+1);
