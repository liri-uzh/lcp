\c lcp_production lcp_production_owner

CREATE OR REPLACE PROCEDURE main.init_export(
   query_hash        text
 , format            text
 , n_offset          int
 , requested         int
 , user_id           text
 , need_querying     bool
 , fn                text
 , corpus_id         int
)
AS $$
   DECLARE
      stat           text;
   BEGIN

      SELECT 
         CASE 
            WHEN $6 = TRUE THEN 'querying'
            ELSE 'exporting'
         END
        INTO stat
           ;

      INSERT
        INTO main.exports (query_hash, corpus_id, status, message, user_id, format, n_offset, requested, delivered, fn)
      SELECT $1
           , $8
           , stat::main.export_status 
           , ''
           , $5
           , $2
           , $3
           , $4
           , 0
           , $7
           ;

   END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

ALTER PROCEDURE main.init_export
  SET search_path = pg_catalog,pg_temp;

REVOKE EXECUTE ON PROCEDURE main.init_export FROM public;
GRANT EXECUTE ON PROCEDURE main.init_export TO lcp_production_web_user;




CREATE OR REPLACE PROCEDURE main.update_export(
   query_hash        text
 , format            text
 , n_offset          int
 , requested         int
 , stat              text
 , msg               text
)
AS $$
   DECLARE
      st             text;
   BEGIN

      SELECT
         CASE
            WHEN $5 = 'export' THEN 'exporting'
            WHEN $5 = 'query' THEN 'querying'
            ELSE 'failed'
         END
        INTO st
           ;

      UPDATE main.exports e
         SET "status" = st::main.export_status
           , "message" = $6
           , "modified_at" = now()
       WHERE e.query_hash = $1
         AND e.format = $2
         AND e.n_offset = $3
         AND e.requested = $4
         ;

   END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

ALTER PROCEDURE main.update_export
  SET search_path = pg_catalog,pg_temp;

REVOKE EXECUTE ON PROCEDURE main.update_export FROM public;
GRANT EXECUTE ON PROCEDURE main.update_export TO lcp_production_web_user;



CREATE OR REPLACE PROCEDURE main.finish_export(
   query_hash        text
 , format            text
 , n_offset          int
 , requested         int
 , delivered         int
)
AS $$
   BEGIN

      UPDATE main.exports e
         SET status = 'ready'::main.export_status
           , delivered = $5
           , modified_at = now()
       WHERE e.query_hash = $1
         AND e.format = $2
         AND e.n_offset = $3
         AND e.requested = $4
         AND e.status IS DISTINCT FROM 'failed'
         ;

   END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

ALTER PROCEDURE main.finish_export
  SET search_path = pg_catalog,pg_temp;

REVOKE EXECUTE ON PROCEDURE main.finish_export FROM public;
GRANT EXECUTE ON PROCEDURE main.finish_export TO lcp_production_web_user;
