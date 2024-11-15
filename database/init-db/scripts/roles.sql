CREATE ROLE lcp_production_owner        WITH CREATEDB PASSWORD '<password4>' LOGIN;
CREATE ROLE lcp_production_importer     WITH CREATEDB PASSWORD '<password1>' LOGIN;
CREATE ROLE lcp_production_maintenance  WITH PASSWORD '<password2>' LOGIN;
CREATE ROLE lcp_production_monitoring   WITH PASSWORD '<password3>' LOGIN;
CREATE ROLE lcp_production_query_engine WITH PASSWORD '<password5>' LOGIN;
CREATE ROLE lcp_production_web_user     WITH PASSWORD '<password6>' LOGIN;
CREATE ROLE lcp_production_ro           WITH PASSWORD '<password7>' NOINHERIT;


CREATE DATABASE lcp_production OWNER lcp_production_owner;
ALTER DATABASE lcp_production OWNER TO lcp_production_owner;
GRANT CONNECT ON DATABASE lcp_production TO lcp_production_ro;

-- ATTENTION: this does only work through psql (i.e. the backslash command)
\c lcp_production
CREATE SCHEMA main AUTHORIZATION lcp_production_owner;
GRANT USAGE
   ON SCHEMA main
   TO lcp_production_maintenance
    , lcp_production_monitoring
    , lcp_production_importer
    , lcp_production_web_user
    ;


-- default privileges only apply to objects created *after* granting
-- therefore lcp_production_ro cannot access objects in main
ALTER DEFAULT PRIVILEGES GRANT USAGE ON SCHEMAS TO lcp_production_ro;
ALTER DEFAULT PRIVILEGES GRANT SELECT ON TABLES TO lcp_production_ro;

-- does that make sense or too broad?
GRANT lcp_production_ro
   TO lcp_production_maintenance
    , lcp_production_monitoring
 WITH INHERIT TRUE
    , SET FALSE
    ;


