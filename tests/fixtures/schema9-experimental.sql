-- Frozen unpublished experimental schema 9 from e676c3895c05.
CREATE TABLE device_observations (id INTEGER PRIMARY KEY,device_id TEXT NOT NULL,name TEXT NOT NULL,platforms TEXT NOT NULL,state TEXT NOT NULL,started REAL NOT NULL,ended REAL,episode_started REAL,episode_kind TEXT NOT NULL,cohort TEXT NOT NULL,attention TEXT NOT NULL,power TEXT NOT NULL,evidence TEXT NOT NULL,reason TEXT NOT NULL);
CREATE UNIQUE INDEX device_observations_open ON device_observations(device_id) WHERE ended IS NULL;
CREATE INDEX device_observations_device ON device_observations(device_id,started,id);
CREATE INDEX device_observations_end ON device_observations(ended,started);
CREATE INDEX device_observations_start ON device_observations(started,id);
CREATE TABLE device_current (device_id TEXT PRIMARY KEY,observation_id INTEGER NOT NULL REFERENCES device_observations(id));
CREATE TABLE device_coverage (id INTEGER PRIMARY KEY,started REAL NOT NULL,observed_until REAL NOT NULL,ended REAL,reason TEXT NOT NULL);
CREATE UNIQUE INDEX device_coverage_open ON device_coverage((1)) WHERE ended IS NULL;
CREATE TABLE device_policies (device_id TEXT PRIMARY KEY,attention TEXT NOT NULL CHECK(attention IN ('review','known','expected')),power TEXT NOT NULL CHECK(power IN ('unknown','battery','mains')),note TEXT NOT NULL,updated REAL NOT NULL,baseline_state TEXT NOT NULL,baseline_cohort TEXT NOT NULL,baseline_at REAL);
CREATE TABLE device_checks (id INTEGER PRIMARY KEY,device_id TEXT NOT NULL,created REAL NOT NULL,kind TEXT NOT NULL,note TEXT NOT NULL,before_state TEXT NOT NULL,cohort TEXT NOT NULL);
CREATE INDEX device_checks_device ON device_checks(device_id,created,id);
